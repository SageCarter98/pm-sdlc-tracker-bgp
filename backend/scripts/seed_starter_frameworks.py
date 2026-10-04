"""Seed the neutral fixture frameworks as shared platform starters
(tenant_id=NULL). Run as bgp_owner (table owner, exempt from RLS) -- no
tenant's own bgp_app connection is allowed to create a tenant_id=NULL
template (see the WITH CHECK clause in alembic/versions/0003_wp05_templates.py),
so this administrative path is the only way starters get created.

Not every fixture in fixtures/synthetic/frameworks/ is a starter. Any
fixture marked `_meta.validation_fixture` is validated like the rest but
never seeded: DEC07 Q12 requires the agile DoR/DoD fixture stay "a
validation fixture, not a shipped starter template, until it has passed its
own review", and seeding it here is precisely what would break that. Two
fixtures are flagged today -- agile.json and its vocabulary-3 counterpart
agile.v3.json. The flag lives in the fixture rather than in a filename list
here so a new validation fixture cannot be shipped by forgetting to update
this script, which is why agile.v3.json needed no change to this file.

Usage (from backend/, with BGP_MIGRATION_DATABASE_URL set in .env):
    python scripts/seed_starter_frameworks.py
"""

import json
import sys
import uuid
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.models import Template, TemplateVersion  # noqa: E402
from app.rule_engine import validate_template_schema  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "synthetic" / "frameworks"


def main() -> None:
    engine = create_engine(settings.migration_database_url, future=True)
    with Session(engine) as db:
        for fixture_path in sorted(FIXTURES_DIR.glob("*.json")):
            data = json.loads(fixture_path.read_text(encoding="utf-8"))
            meta = data.pop("_meta", {})
            name = meta.get("name", fixture_path.stem)

            validate_template_schema(data)  # raises loudly if a fixture regressed

            # Validated above, deliberately not seeded -- see the module
            # docstring. Checked after validation, so a validation fixture
            # still fails this script loudly if its schema regresses.
            if meta.get("validation_fixture"):
                print(f"skip (validation fixture, not a shipped starter): {name}")
                continue

            existing = db.query(Template).filter(Template.tenant_id.is_(None), Template.name == name).one_or_none()
            if existing is not None:
                print(f"skip (already seeded): {name}")
                continue

            template = Template(id=str(uuid.uuid4()), tenant_id=None, name=name)
            db.add(template)
            db.flush()
            db.add(
                TemplateVersion(
                    id=str(uuid.uuid4()),
                    template_id=template.id,
                    version_number=1,
                    schema_json=data,
                    status="published",
                    created_by_user_id=None,
                )
            )
            print(f"seeded: {name}")
        db.commit()


if __name__ == "__main__":
    main()
