"""Claude CLI wrapper.

Uses the local `claude` CLI in headless mode (subprocess) to avoid API costs.
Marwan's Claude Max subscription pays for it. Logs every call to claude_usage.
"""
import subprocess
import json
import time
import hashlib
from pathlib import Path
from typing import Optional
from sqlalchemy import text
from app.config import get_settings
from app.db.session import get_db

settings = get_settings()
_HERE = Path(__file__).resolve().parent
PROMPTS_DIR = _HERE / "prompts"


class ClaudeError(Exception):
    pass


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
) -> dict:
    """Run a Claude headless call. Returns parsed JSON if possible, else {'text': ...}."""
    full_prompt = prompt
    if include_system_context:
        ctx = _system_context()
        if ctx:
            full_prompt = f"{ctx}\n\n---\n\n{prompt}"

    started = time.time()
    success = True
    error_message = None
    parsed: dict = {}

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
        try:
            with get_db() as db:
                db.execute(text("""
                    INSERT INTO claude_usage
                    (job_type, duration_ms, estimated_input_tokens, job_source, success, error_message)
                    VALUES (:jt, :dur, :tok, :src, :ok, :err)
                """), {
                    "jt": job_type,
                    "dur": duration_ms,
                    "tok": len(full_prompt) // 4,  # rough estimate
                    "src": job_source,
                    "ok": success,
                    "err": error_message,
                })
        except Exception:
            pass  # never let usage logging break the actual call


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
