"""DEC05 G3/G4 (docs/blueprint/BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.md,
Candidate A+): independent verification job. Runs BOTH the pre-existing
same-instance hash-chain re-derivation (app/integrity.py's
verify_integrity(), WP08) AND the new cross-check against each checkpoint's
externally-anchored WORM copy (verify_against_anchor(), DEC05 G3) for every
project that has any checkpoints.

Connects as bgp_backup (settings.backup_database_url) -- reused, no new role
-- for the same reason scripts/restore_drill.py already uses it rather than
bgp_app or bgp_owner: a credential the running application never uses, so a
compromised app process cannot also compromise the thing checking it.
BYPASSRLS means no per-tenant `SET LOCAL app.tenant_id` is needed here, same
as restore_drill.py's own reconciliation step.

Scheduled daily via .github/workflows/integrity-verify.yml (DEC05 s4's "at
least daily" cadence) -- also runnable manually:

    cd backend && .venv/Scripts/python.exe scripts/verify_against_anchor.py

Honest limit, named rather than silently worked around: bgp_backup has no
INSERT grant on integrity_incidents (checked directly against this
project's dev database while building this -- `pg_read_all_data` gives it
SELECT only). If this script ever finds a REAL mismatch, verify_integrity()/
verify_against_anchor() opening an IntegrityIncident under this connection
would itself fail with a permission error instead of recording the
incident. scripts/restore_drill.py has carried this exact same exposure
since 2026-09-17 (it also calls verify_integrity() over a bgp_backup-rooted
session) without ever having hit it in practice. Not fixed here: widening a
role documented everywhere as "read-only... nothing else" is a real
security-posture change, not something to slip in as a side effect of this
pass -- flagged in DEFECT_REGISTER.md instead.
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings  # noqa: E402
from app.integrity import verify_against_anchor, verify_integrity  # noqa: E402
from app.worm_anchor import worm_anchor_store  # noqa: E402


def main() -> None:
    engine = create_engine(settings.backup_database_url, future=True)
    overall_ok = True

    with Session(engine) as db:
        rows = db.execute(text("SELECT DISTINCT tenant_id, project_id FROM integrity_checkpoints")).fetchall()

        for tenant_id, project_id in rows:
            same_instance = verify_integrity(db, tenant_id, project_id)
            anchor_check = verify_against_anchor(db, worm_anchor_store, tenant_id, project_id)
            ok = same_instance["ok"] and anchor_check["ok"]
            overall_ok = overall_ok and ok
            print(
                f"project {project_id}: same-instance re-derivation="
                f"{'OK' if same_instance['ok'] else 'MISMATCH'} "
                f"({same_instance['checked_checkpoints']} checkpoint(s)), "
                f"external-anchor cross-check={'OK' if anchor_check['ok'] else 'MISMATCH'} "
                f"({anchor_check['checked_checkpoints']} anchored checkpoint(s) checked)"
            )

    if not overall_ok:
        print("=== Daily verification FAILED -- see IntegrityIncident row(s) above. ===")
        sys.exit(1)
    print(f"=== Daily verification OK across {len(rows)} project(s) with checkpoints. ===")


if __name__ == "__main__":
    main()
