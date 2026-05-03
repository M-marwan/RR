"""Seed database from existing Reddington System markdown files.

Run from the backend directory:
    python scripts/seed_from_rr.py
"""
import sys
import os
import uuid
import re
from pathlib import Path

# Add parent dir so we can import app
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import get_settings
from app.db.session import get_db
from sqlalchemy import text

settings = get_settings()
RR_PATH = Path(settings.rr_source_path)


def extract_yaml_field(content: str, field: str) -> str:
    """Extract a field from a markdown frontmatter or key: value line."""
    pattern = rf"^{field}:\s*(.+)$"
    match = re.search(pattern, content, re.MULTILINE)
    return match.group(1).strip() if match else ""


def seed_people():
    people_dir = RR_PATH / "03_MEMORY" / "dossiers" / "people"
    if not people_dir.exists():
        print(f"  People dir not found: {people_dir}")
        return

    for md_file in sorted(people_dir.glob("*.md")):
        if "_template" in md_file.name.lower():
            continue
        content = md_file.read_text(encoding="utf-8")

        name = extract_yaml_field(content, "name")
        if not name:
            # Try to infer from filename
            name = md_file.stem.replace("_", " ").replace("-", " ").title()
            if "tfa" in name.lower():
                name = name.replace("Tfa", "(TFA)").strip()
            if "gia" in name.lower():
                name = name.replace("Gia", "(Gia)").strip()

        role = extract_yaml_field(content, "role")
        email_match = re.search(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}", content)
        email = email_match.group(0) if email_match else ""

        profile = {
            "role": role,
            "source_file": md_file.name,
        }

        entity_id = str(uuid.uuid4())
        with get_db() as db:
            existing = db.execute(
                text("SELECT id FROM entities WHERE canonical_name = :name AND type = 'person'"),
                {"name": name},
            ).mappings().first()

            if existing:
                entity_id = str(existing["id"])
                print(f"  Updating person: {name}")
                db.execute(text("""
                    UPDATE entities SET profile = CAST(:profile AS jsonb), last_updated = NOW()
                    WHERE id = :id
                """), {"profile": __import__("json").dumps(profile), "id": entity_id})
            else:
                print(f"  Inserting person: {name}")
                db.execute(text("""
                    INSERT INTO entities (id, type, canonical_name, country_code, profile)
                    VALUES (:id, 'person', :name, 'AE', CAST(:profile AS jsonb))
                """), {
                    "id": entity_id,
                    "name": name,
                    "profile": __import__("json").dumps(profile),
                })

            # Insert contact if email found
            if email:
                db.execute(text("""
                    INSERT INTO contacts (id, entity_id, display_name, email_address, is_primary)
                    VALUES (:cid, :eid, :name, :email, true)
                    ON CONFLICT (entity_id, email_address) DO NOTHING
                """), {
                    "cid": str(uuid.uuid4()),
                    "eid": entity_id,
                    "name": name,
                    "email": email,
                })

        print(f"    -> entity_id: {entity_id}, email: {email or '(none)'}")


def seed_companies():
    companies_dir = RR_PATH / "03_MEMORY" / "dossiers" / "companies"
    if not companies_dir.exists():
        print(f"  Companies dir not found: {companies_dir}")
        return

    for md_file in sorted(companies_dir.glob("*.md")):
        if "_template" in md_file.name.lower():
            continue
        content = md_file.read_text(encoding="utf-8")
        name = extract_yaml_field(content, "name") or md_file.stem.upper()
        sector = extract_yaml_field(content, "sector")
        profile = {
            "sector": sector,
            "source_file": md_file.name,
        }

        print(f"  Inserting company: {name}")
        with get_db() as db:
            existing = db.execute(
                text("SELECT id FROM entities WHERE canonical_name = :name AND type = 'company'"),
                {"name": name},
            ).mappings().first()
            if not existing:
                db.execute(text("""
                    INSERT INTO entities (id, type, canonical_name, profile)
                    VALUES (:id, 'company', :name, CAST(:profile AS jsonb))
                """), {
                    "id": str(uuid.uuid4()),
                    "name": name,
                    "profile": __import__("json").dumps(profile),
                })


def seed_deals():
    pipeline_file = RR_PATH / "06_DEALS" / "00_pipeline.md"
    if not pipeline_file.exists():
        print(f"  Pipeline file not found: {pipeline_file}")
        return

    # Also seed from White Space Brief
    whitespace_file = RR_PATH / "04_PLAYBOOKS" / "WHITE_SPACE_BRIEF_001.md"
    ideas = [
        {
            "code": "OPP-001",
            "name": "Post-OPEC-Exit Compliance & Strategy Desk",
            "description": "90-day compliance/strategy pack for non-ADNOC UAE oil & gas independents post-OPEC exit. Pricing AED 40K-80K per engagement.",
            "type": "deal",
            "status": "prospecting",
        },
        {
            "code": "OPP-002",
            "name": "GCC–East Africa Petroleum & Logistics Brokerage",
            "description": "Two-sided brokerage: GCC operators seeking East Africa exposure + Kenya operators seeking Gulf capital. Success fees 2-5%.",
            "type": "deal",
            "status": "prospecting",
        },
        {
            "code": "OPP-003",
            "name": "Saudi RHQ Operating Reality Boutique",
            "description": "RHQ Operating Concierge for the 700+ international firms that moved RHQs to Riyadh. $3K-$8K/month retainer.",
            "type": "deal",
            "status": "prospecting",
        },
        {
            "code": "OPP-004",
            "name": "Antigua–Dubai–Amman HNW Vehicle Stack",
            "description": "Three-jurisdiction stack for GCC HNW diversification: Antigua CIP + Dubai operating + Amman discretion banking. $25K-$75K per engagement.",
            "type": "deal",
            "status": "prospecting",
        },
        {
            "code": "GIA-001",
            "name": "Gia Venture Studio",
            "description": "Marwan's co-founded venture studio in Amman, Jordan. Production + dev talent at Levant cost structure.",
            "type": "venture",
            "status": "active",
        },
    ]

    for idea in ideas:
        print(f"  Inserting project: {idea['code']} — {idea['name']}")
        with get_db() as db:
            existing = db.execute(
                text("SELECT id FROM projects WHERE code = :code"),
                {"code": idea["code"]},
            ).mappings().first()
            if not existing:
                db.execute(text("""
                    INSERT INTO projects (id, code, name, type, status, description, canvas_order)
                    VALUES (:id, :code, :name, :type, :status, :description, :order)
                """), {
                    "id": str(uuid.uuid4()),
                    "code": idea["code"],
                    "name": idea["name"],
                    "type": idea["type"],
                    "status": idea["status"],
                    "description": idea["description"],
                    "order": ideas.index(idea),
                })


def seed_marwan_entity():
    """Ensure Marwan himself is in the entities table."""
    print("  Inserting Marwan entity...")
    import json as _json
    profile = {
        "role": "Strategy & Planning at TFA | Co-founder Gia",
        "primary_city": "Dubai",
        "operating_presence": ["UAE", "Saudi Arabia", "Jordan", "Antigua", "Kenya"],
        "capital_deployable_usd": "5000-50000",
    }
    with get_db() as db:
        existing = db.execute(
            text("SELECT id FROM entities WHERE canonical_name = 'Marwan' AND type = 'person'"),
        ).mappings().first()
        if not existing:
            eid = str(uuid.uuid4())
            db.execute(text("""
                INSERT INTO entities (id, type, canonical_name, country_code, profile)
                VALUES (:id, 'person', 'Marwan', 'AE', CAST(:profile AS jsonb))
            """), {"id": eid, "profile": _json.dumps(profile)})
            db.execute(text("""
                INSERT INTO contacts (id, entity_id, display_name, email_address, is_primary)
                VALUES (:cid, :eid, 'Marwan', '014.marwan@gmail.com', true)
                ON CONFLICT (entity_id, email_address) DO NOTHING
            """), {"cid": str(uuid.uuid4()), "eid": eid})


if __name__ == "__main__":
    print("=== Seeding RR Command Center database from Reddington System ===\n")
    print(f"Source path: {RR_PATH}\n")

    print("1. Seeding Marwan...")
    seed_marwan_entity()

    print("\n2. Seeding people...")
    seed_people()

    print("\n3. Seeding companies...")
    seed_companies()

    print("\n4. Seeding deals/projects...")
    seed_deals()

    print("\nSeed complete.")
