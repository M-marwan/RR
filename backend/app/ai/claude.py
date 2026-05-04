"""Claude CLI wrapper with workspace-level cost cap (premortem rule 5.4).

Uses the local `claude` CLI in headless mode (subprocess) to avoid API costs.
Marwan's Claude Max subscription pays for it. Logs every call to claude_usage
**and** daily_cost_summary.

Cost cap design
---------------
Even though calls go through the Claude Max subscription (no per-token billing
right now), we still enforce a `daily_cost_cap_usd` per workspace. Two reasons:
  1. Future-proofs migration to direct Anthropic API billing.
  2. Bounds runaway loops — a buggy worker can't melt the subscription
     by triggering thousands of calls in an hour.

Cost is *estimated* from token counts using public Anthropic pricing
(haiku $0.0008/$0.004 per 1K input/output, sonnet $0.003/$0.015,
opus $0.015/$0.075). Real billing ignored — we treat it as if we paid.

Three-tier model routing (rule 5.4)
-----------------------------------
- "haiku"  — categorization, extraction, classification
- "sonnet" — synthesis, multi-step reasoning, briefing generation
- "opus"   — explicit deep dive only; needs a separate `daily_opus_cap_usd`
             (default $0, must be raised explicitly).
"""
import subprocess
import json
import time
import hashlib
import logging
from pathlib import Path
from typing import Optional
from datetime import date
from sqlalchemy import text
from app.config import get_settings
from app.db.session import get_db

logger = logging.getLogger(__name__)
settings = get_settings()
_HERE = Path(__file__).resolve().parent
PROMPTS_DIR = _HERE / "prompts"

# Approximate Anthropic pricing per 1K tokens (USD). Update when Anthropic does.
PRICING = {
    "haiku":  {"input": 0.0008, "output": 0.004},
    "sonnet": {"input": 0.003,  "output": 0.015},
    "opus":   {"input": 0.015,  "output": 0.075},
}


class ClaudeError(Exception):
    pass


class BudgetExceeded(ClaudeError):
    """Raised when a Claude call would exceed the workspace's daily cost cap."""

    def __init__(self, workspace_id, cap_usd, spent_usd, requested_usd):
        self.workspace_id = workspace_id
        self.cap_usd = float(cap_usd)
        self.spent_usd = float(spent_usd)
        self.requested_usd = float(requested_usd)
        super().__init__(
            f"Workspace {workspace_id} would exceed daily cap "
            f"(${spent_usd:.4f} spent + ${requested_usd:.4f} requested > ${cap_usd:.2f} cap)"
        )


def _estimate_input_tokens(prompt: str) -> int:
    return max(1, len(prompt) // 4)


def _estimate_output_tokens(prompt: str) -> int:
    """Worst-case rough guess that output ≈ 30% of input. Updated post-call."""
    return max(200, _estimate_input_tokens(prompt) // 3)


def _estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p = PRICING.get(model, PRICING["sonnet"])
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1000.0


def _get_workspace_cap_and_spent(db, workspace_id: str) -> tuple[float, float]:
    """Return (cap_usd, spent_today_usd) for the workspace. Cap defaults to 5.00."""
    row = db.execute(text("""
        SELECT COALESCE(daily_cost_cap_usd, 5.00) AS cap
        FROM workspaces WHERE id = :wid
    """), {"wid": workspace_id}).mappings().first()
    cap = float(row["cap"]) if row else 5.00

    spent = db.execute(text("""
        SELECT COALESCE(SUM(total_usd), 0) AS spent
        FROM daily_cost_summary
        WHERE workspace_id = :wid AND cost_date = CURRENT_DATE
    """), {"wid": workspace_id}).mappings().first()
    spent_usd = float(spent["spent"]) if spent else 0.0
    return cap, spent_usd


def _record_cost(db, workspace_id: Optional[str], model: str,
                 input_tokens: int, output_tokens: int, total_usd: float) -> None:
    if not workspace_id:
        return  # no-workspace calls don't count against any cap
    db.execute(text("""
        INSERT INTO daily_cost_summary
            (workspace_id, cost_date, model, total_input_tokens,
             total_output_tokens, total_usd, call_count, updated_at)
        VALUES (:wid, CURRENT_DATE, :m, :ti, :to, :usd, 1, NOW())
        ON CONFLICT (workspace_id, cost_date, model) DO UPDATE SET
            total_input_tokens  = daily_cost_summary.total_input_tokens  + EXCLUDED.total_input_tokens,
            total_output_tokens = daily_cost_summary.total_output_tokens + EXCLUDED.total_output_tokens,
            total_usd           = daily_cost_summary.total_usd           + EXCLUDED.total_usd,
            call_count          = daily_cost_summary.call_count          + 1,
            updated_at = NOW()
    """), {
        "wid": workspace_id, "m": model,
        "ti": input_tokens, "to": output_tokens, "usd": total_usd,
    })


def _system_context() -> str:
    """Marwan + active deals context, injected once per call."""
    ctx_file = PROMPTS_DIR / "system_context.md"
    if ctx_file.exists():
        return ctx_file.read_text(encoding="utf-8")
    return ""


def call_claude(
    prompt: str,
    job_type: str,
    job_source: str = "manual",
    timeout_seconds: int = 180,
    include_system_context: bool = True,
    workspace_id: Optional[str] = None,
    model: str = "sonnet",
) -> dict:
    """Run a Claude headless call. Returns parsed JSON if possible, else {'text': ...}.

    Cost cap (rule 5.4): when `workspace_id` is provided, today's spend for that
    workspace is checked against `daily_cost_cap_usd` BEFORE the subprocess
    runs. Raises `BudgetExceeded` if the call would exceed the cap.
    """
    if model not in PRICING:
        logger.warning("Unknown model %r — defaulting to sonnet pricing", model)

    full_prompt = prompt
    if include_system_context:
        ctx = _system_context()
        if ctx:
            full_prompt = f"{ctx}\n\n---\n\n{prompt}"

    # ─── pre-flight cost cap check (rule 5.4) ────────────────────────────
    estimated_input = _estimate_input_tokens(full_prompt)
    estimated_output = _estimate_output_tokens(full_prompt)
    estimated_cost = _estimate_cost_usd(model, estimated_input, estimated_output)

    if workspace_id:
        with get_db() as db:
            cap_usd, spent_usd = _get_workspace_cap_and_spent(db, workspace_id)
            if spent_usd + estimated_cost > cap_usd:
                raise BudgetExceeded(workspace_id, cap_usd, spent_usd, estimated_cost)

    started = time.time()
    success = True
    error_message = None
    parsed: dict = {}
    actual_output_chars = 0

    try:
        result = subprocess.run(
            [settings.claude_cli_path, "-p", "--output-format", "json"],
            input=full_prompt,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            encoding="utf-8",
            errors="replace",
            shell=True,  # required on Windows for .cmd
        )
        if result.returncode != 0:
            success = False
            error_message = result.stderr[:500]
            raise ClaudeError(f"Claude CLI exited {result.returncode}: {error_message}")

        # The Claude CLI in --output-format json returns a JSON envelope.
        # The actual response text is at .result; if we asked for JSON output
        # from Claude itself, we still need to parse that text.
        try:
            envelope = json.loads(result.stdout)
            text_out = envelope.get("result") or envelope.get("text") or result.stdout
        except json.JSONDecodeError:
            text_out = result.stdout

        actual_output_chars = len(text_out)

        # Try to parse text_out as JSON (when prompt asked for JSON response)
        try:
            parsed = json.loads(text_out)
        except json.JSONDecodeError:
            # Try to extract a JSON block from markdown fences
            stripped = text_out.strip()
            if stripped.startswith("```"):
                lines = stripped.split("\n")
                stripped = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
                try:
                    parsed = json.loads(stripped)
                except json.JSONDecodeError:
                    parsed = {"text": text_out}
            else:
                parsed = {"text": text_out}

        return parsed

    except subprocess.TimeoutExpired:
        success = False
        error_message = "Claude call timed out"
        raise ClaudeError(error_message)

    finally:
        duration_ms = int((time.time() - started) * 1000)
        # Use actual output length when available, else fall back to estimate.
        actual_output_tokens = max(1, actual_output_chars // 4) if actual_output_chars else estimated_output
        actual_cost = _estimate_cost_usd(model, estimated_input, actual_output_tokens)

        try:
            with get_db() as db:
                db.execute(text("""
                    INSERT INTO claude_usage
                    (job_type, duration_ms, estimated_input_tokens, job_source, success, error_message)
                    VALUES (:jt, :dur, :tok, :src, :ok, :err)
                """), {
                    "jt": job_type,
                    "dur": duration_ms,
                    "tok": estimated_input,
                    "src": job_source,
                    "ok": success,
                    "err": error_message,
                })
                # Record per-workspace cost (rule 5.4) — only if call actually ran.
                if success and workspace_id:
                    _record_cost(db, workspace_id, model,
                                 estimated_input, actual_output_tokens, actual_cost)
        except Exception:
            logger.exception("Failed to record claude_usage / daily_cost_summary")
            # never let usage logging break the actual call


def cached_call(prompt: str, job_type: str, **kwargs) -> dict:
    """Like call_claude, but checks synthesis_cache first by input hash."""
    input_hash = hashlib.sha256(prompt.encode()).hexdigest()
    with get_db() as db:
        cached = db.execute(text("""
            SELECT output_json FROM synthesis_cache
            WHERE job_type = :jt AND input_hash = :h
            ORDER BY created_at DESC LIMIT 1
        """), {"jt": job_type, "h": input_hash}).mappings().first()
        if cached:
            return cached["output_json"]

    result = call_claude(prompt, job_type, **kwargs)

    with get_db() as db:
        db.execute(text("""
            INSERT INTO synthesis_cache (job_type, input_hash, output_json)
            VALUES (:jt, :h, CAST(:out AS jsonb))
            ON CONFLICT (job_type, input_hash) DO UPDATE SET output_json = EXCLUDED.output_json
        """), {"jt": job_type, "h": input_hash, "out": json.dumps(result)})

    return result
