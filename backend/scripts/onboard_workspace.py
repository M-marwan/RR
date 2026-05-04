"""Interactive onboarding script — register a workspace's M365 tenant.

Usage
-----

    python scripts/onboard_workspace.py --workspace-slug gia
    python scripts/onboard_workspace.py --workspace-id <uuid>

The script walks Marwan (or whoever onboards a company) through:

  Step 1.  Pre-flight checks — workspace exists, has ≥2 principals (rule 5.10),
           AUP file is on hand (rule 5.6).

  Step 2.  Manual: register an Entra ID app inside the company's M365 tenant
           via https://entra.microsoft.com → App registrations → New
           registration. Copy the Application (client) ID and the Directory
           (tenant) ID into the prompts.

  Step 3.  Manual: configure API permissions for the new app — add
           Mail.Read (Application), User.Read.All (Application),
           MailboxSettings.Read (Application). Click "Grant admin consent
           for <tenant>" — requires Global Admin in that tenant.

  Step 4.  Manual: generate a client secret in the new app and paste it
           into the prompt. The script writes it to .env (dev) under the
           per-workspace env var name. NEVER stored in Postgres.

  Step 5.  Manual: scope mailbox access via Exchange Online RBAC — the
           script prints the PowerShell commands to run inside an
           Exchange admin session. This limits the app to a designated
           set of mailboxes (the team only).

  Step 6.  Capture aup_signed_at + signer email in the workspaces row
           (rule 5.6 gate).

  Step 7.  Probe — fetch one message from each scoped mailbox to verify
           the wiring + populate the categorizer_test corpus seed.

  Step 8.  Mark m365_consent_granted_at on the workspace.

Run this from the backend directory with the venv activated. The script
is idempotent — re-run after fixing any failed step.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Allow `python scripts/onboard_workspace.py` from backend/.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.db.session import get_db


# ─── pretty CLI helpers ──────────────────────────────────────────────────────


def step(n: int, title: str) -> None:
    print(f"\n────  Step {n}: {title}  " + "─" * (60 - len(title)))


def info(msg: str) -> None:
    print(f"  ℹ  {msg}")


def good(msg: str) -> None:
    print(f"  ✓  {msg}")


def warn(msg: str) -> None:
    print(f"  ⚠  {msg}")


def fail(msg: str) -> None:
    print(f"  ✗  {msg}", file=sys.stderr)


def ask(prompt: str, default: Optional[str] = None) -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"  ?  {prompt}{suffix}: ").strip()
    return val or (default or "")


def confirm(prompt: str) -> bool:
    return ask(f"{prompt} (y/N)").lower() in ("y", "yes")


# ─── workspace lookup ────────────────────────────────────────────────────────


def resolve_workspace(slug: Optional[str], wid: Optional[str]) -> dict:
    with get_db() as db:
        if wid:
            row = db.execute(text("SELECT * FROM workspaces WHERE id = :id"), {"id": wid}).mappings().first()
        elif slug:
            row = db.execute(text("SELECT * FROM workspaces WHERE slug = :s"), {"s": slug}).mappings().first()
        else:
            raise SystemExit("Pass --workspace-slug or --workspace-id")
    if not row:
        raise SystemExit(f"No workspace found for slug={slug!r} id={wid!r}")
    if row["archived_at"]:
        raise SystemExit(f"Workspace '{row['display_name']}' is archived; restore it first")
    return dict(row)


# ─── pre-flight gates ────────────────────────────────────────────────────────


def check_principals(ws: dict) -> None:
    """Rule 5.10 — workspace must have ≥2 principal members before M365 grant."""
    with get_db() as db:
        n = db.execute(text("""
            SELECT COUNT(*) AS n FROM workspace_members
            WHERE workspace_id = :wid AND role = 'principal'
        """), {"wid": ws["id"]}).mappings().first()["n"]
    if n < 2:
        fail(f"Rule 5.10: workspace has {n} principal member(s); ≥2 required.")
        info(
            "Add a second principal in the dashboard at "
            "/settings/companies before re-running this script. The second "
            "principal protects against single-person bus-factor lockout."
        )
        sys.exit(2)
    good(f"Rule 5.10 passed — {n} principal members present.")


def check_aup(ws: dict) -> bool:
    """Rule 5.6 — AUP must be signed before any team mail is ingested."""
    if ws["aup_signed_at"]:
        good(f"Rule 5.6 already satisfied — AUP signed {ws['aup_signed_at']} by {ws['aup_signed_by_email']}.")
        return False  # no work needed
    warn("Rule 5.6: no Acceptable Use Policy on file for this workspace.")
    info("Template at docs/legal/AUP_TEMPLATE.md. Have your DIFC employment lawyer review it,")
    info("circulate to the team for signature, then re-run this script.")
    if not confirm("AUP is signed and on file. Proceed and record signing details now?"):
        sys.exit(2)
    return True  # capture signing details below


# ─── main flow ───────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Onboard an M365 tenant for a workspace.")
    parser.add_argument("--workspace-slug")
    parser.add_argument("--workspace-id")
    args = parser.parse_args()

    ws = resolve_workspace(args.workspace_slug, args.workspace_id)
    print(f"\nOnboarding workspace: {ws['display_name']} (slug={ws['slug']}, id={ws['id']})")

    # ─── Step 1: pre-flight ─────────────────────────────────────────────
    step(1, "Pre-flight checks")
    check_principals(ws)
    capture_aup = check_aup(ws)

    # ─── Step 2: tenant + client IDs ────────────────────────────────────
    step(2, "Register Entra app and capture IDs")
    info("In a browser, sign in to https://entra.microsoft.com as a Global Admin")
    info(f"of {ws['display_name']}'s M365 tenant. Then:")
    info("  • App registrations → New registration")
    info(f"  • Name:  RR Command Center — {ws['slug']}")
    info("  • Supported account types: 'Accounts in this organizational directory only'")
    info("  • Redirect URI: leave blank")
    info("  • Click Register. On the resulting page, copy the two GUIDs.")

    tenant_id = ask("Directory (tenant) ID", ws.get("m365_tenant_id"))
    client_id = ask("Application (client) ID", ws.get("m365_app_id"))
    if not (tenant_id and client_id):
        fail("Both tenant_id and client_id are required.")
        return 2

    # ─── Step 3: API permissions + admin consent ────────────────────────
    step(3, "Configure API permissions and grant admin consent")
    info("Still in the Entra portal app you just created:")
    info("  • API permissions → Add a permission → Microsoft Graph → Application permissions")
    info("  • Add: Mail.Read, User.Read.All, MailboxSettings.Read")
    info("  • Click 'Grant admin consent for <tenant name>'")
    info("  • All three permissions should now show 'Granted for ...'")
    if not confirm("Admin consent granted for all three permissions?"):
        fail("Cannot proceed without admin consent.")
        return 2

    # ─── Step 4: client secret ──────────────────────────────────────────
    step(4, "Create a client secret and paste it here")
    info("In the same Entra app:")
    info("  • Certificates & secrets → Client secrets → New client secret")
    info("  • Description: 'RR Command Center production' or similar")
    info("  • Expires: 24 months (set a calendar reminder to rotate before expiry)")
    info("  • Click Add, then immediately copy the SECRET VALUE (not the ID).")
    secret = getpass.getpass("  ?  Paste client secret (input hidden): ").strip()
    if not secret:
        fail("Empty secret. Aborting.")
        return 2

    # Persist secret to .env under per-workspace env var name. The connector
    # reads it from there. Production should swap this for a real vault.
    env_var = f"M365_SECRET_{str(ws['id']).replace('-', '_').upper()}"
    env_file = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_file.exists():
        existing = env_file.read_text(encoding="utf-8")
        # Strip any prior line for this var
        new_lines = [
            ln for ln in existing.splitlines()
            if not ln.strip().startswith(f"{env_var}=")
        ]
        new_lines.append(f"{env_var}={secret}")
        env_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    else:
        env_file.write_text(f"{env_var}={secret}\n", encoding="utf-8")
    good(f"Wrote secret to .env as {env_var}. Don't commit .env (gitignored).")

    # ─── Step 5: Exchange Online RBAC scoping ───────────────────────────
    step(5, "Scope mailbox access via Exchange Online RBAC")
    info("This restricts the new app to ONLY the team's mailboxes (not the whole tenant).")
    info("Run these in an Exchange Online PowerShell session:")
    print(f"""
        Connect-ExchangeOnline
        New-ServicePrincipal -AppId {client_id} -ServiceId {client_id} \\
            -DisplayName "RR Command Center — {ws['slug']}"
        # Replace the filter with the actual team mailbox identity criteria
        New-ManagementScope -Name "RR-{ws['slug']}-MailboxScope" \\
            -RecipientRestrictionFilter "CustomAttribute1 -eq 'rr-monitored'"
        New-ManagementRoleAssignment \\
            -App {client_id} \\
            -Role "Application Mail.Read" \\
            -CustomResourceScope "RR-{ws['slug']}-MailboxScope"
    """)
    info("This is critical — without scoping, the app could read EVERY mailbox in the tenant.")
    if not confirm("RBAC scope applied (or you accept tenant-wide access for now)?"):
        warn("Skipped — re-run when you're ready. The connector will still work but with broader access than necessary.")

    # ─── Step 6: AUP signing record ─────────────────────────────────────
    if capture_aup:
        step(6, "Record AUP signing")
        signer = ask("Email of the person who signed the AUP")
        if not signer:
            fail("Cannot proceed without signer email — rule 5.6 not satisfied.")
            return 2
    else:
        signer = None

    # ─── Step 7: persist + mark consent granted ─────────────────────────
    step(7, "Persist workspace M365 wiring")
    now = datetime.now(timezone.utc)
    with get_db() as db:
        db.execute(text("""
            UPDATE workspaces SET
                m365_tenant_id = :tid,
                m365_app_id = :aid,
                m365_consent_granted_at = :now,
                aup_signed_at = COALESCE(:aup_now, aup_signed_at),
                aup_signed_by_email = COALESCE(:signer, aup_signed_by_email),
                updated_at = NOW()
            WHERE id = :wid
        """), {
            "tid": tenant_id,
            "aid": client_id,
            "now": now,
            "aup_now": now if capture_aup else None,
            "signer": signer,
            "wid": ws["id"],
        })
        db.execute(text("""
            INSERT INTO audit_log
                (workspace_id, actor_email, action, target_type, target_id, payload)
            VALUES (:wid, :actor, 'workspace.m365_onboarded', 'workspace', :tid,
                    CAST(:payload AS jsonb))
        """), {
            "wid": ws["id"], "actor": signer or "operator", "tid": str(ws["id"]),
            "payload": '{"tenant_id": "' + tenant_id + '", "client_id": "' + client_id + '"}',
        })
    good(f"workspaces.m365_consent_granted_at set to {now.isoformat()}")

    # ─── Step 8: smoke test ────────────────────────────────────────────
    step(8, "Smoke test the connector")
    try:
        # Lazy import so the script runs even if msal isn't installed yet,
        # surfacing a useful error.
        from app.connectors.m365 import client_for_workspace
        gc = client_for_workspace(str(ws["id"]))
        users = gc.list_users(page_size=5)
        good(f"Token + Graph reachable. Sample users (up to 5): {[u.get('displayName') for u in users]}")
        gc.close()
    except Exception as e:
        warn(f"Smoke test failed: {e}")
        info("Common causes: client secret wrong; admin consent not actually granted;")
        info("RBAC scope misconfigured; tenant has Conditional Access blocking app access.")
        info("Re-run the script after fixing — it's idempotent.")
        return 1

    print()
    good(f"✅ Onboarding complete for {ws['display_name']}.")
    info("Next: run alembic upgrade head if you haven't, restart the backend,")
    info("then in the dashboard /settings/companies the workspace shows '● M365 connected'.")
    info("M365 ingestion will start on its scheduled 5-min cadence — backfill the last 30 days via the admin endpoint.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
