"""DEC05 G2 (docs/blueprint/BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.md,
Candidate A+): asynchronously anchors every IntegrityCheckpoint that has no
matching WormAnchorReceipt yet to the external WORM store
(app/worm_anchor.py). This is the "independently-custodied" half of DEC05 --
the synchronous chain-link at commit time (app/routers/decisions.py) is the
other half.

Run manually (this prototype has no scheduler, same as scripts/
restore_drill.py):

    cd backend && .venv/Scripts/python.exe scripts/anchor_worm.py

Connects as bgp_app (an ordinary operational role, unlike bgp_backup's
BYPASSRLS) -- so it must iterate tenant by tenant, setting `app.tenant_id`
for each, the same as every other RLS-scoped query in this codebase.
`tenants` itself carries no RLS (migration 0002_wp04_rls.py), so enumerating
tenant ids needs no tenant context first.

anchor_unanchored_checkpoints() (the tested core) commits once per
checkpoint anchored, not once at the end -- deliberately, so an interrupted
run leaves already-anchored checkpoints untouched rather than losing them.
Honest limit this doesn't fully close, named rather than silently
dropped: if a run is killed mid-write (partial file on disk, no receipt row
committed yet), a re-run's NOT EXISTS query still finds that checkpoint
"unanchored" and retries it -- but LocalWormAnchorStore.write_once() refuses
to overwrite an existing path, so that retry would raise FileExistsError
instead of resuming. Recovering from that specific interruption needs a
manual on-disk cleanup; not solved here.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings  # noqa: E402
from app.models import IntegrityCheckpoint, WormAnchorReceipt  # noqa: E402
from app.worm_anchor import WormAnchorStore, worm_anchor_store  # noqa: E402


def _anchor_payload(checkpoint: IntegrityCheckpoint) -> bytes:
    return json.dumps(
        {
            "checkpoint_id": checkpoint.id,
            "project_id": checkpoint.project_id,
            "tenant_id": checkpoint.tenant_id,
            "from_sequence": checkpoint.from_sequence,
            "to_sequence": checkpoint.to_sequence,
            "event_count": checkpoint.event_count,
            "chain_digest": checkpoint.chain_digest,
            "anchored_at": datetime.now(timezone.utc).isoformat(),
        },
        sort_keys=True,
    ).encode("utf-8")


def anchor_unanchored_checkpoints(db: Session, worm_store: WormAnchorStore, tenant_id: str) -> int:
    """For the tenant `db`'s session is currently scoped to (via
    `SET LOCAL app.tenant_id`, already applied by the caller before this
    runs): finds every IntegrityCheckpoint with no matching
    WormAnchorReceipt -- a NOT EXISTS query against the receipts table
    itself, not by re-deriving from the WORM store's own contents, so a
    checkpoint with a half-written file on disk from an interrupted prior
    run isn't silently skipped (see this module's docstring for the
    remaining gap that doesn't fully close). Writes each to `worm_store`,
    then INSERTs one receipt row, committing per-checkpoint. Returns the
    count newly anchored.

    `tenant_id` is re-applied via SET LOCAL before each commit -- a plain
    Postgres COMMIT ends the transaction SET LOCAL was scoped to (see
    app/deps.py's get_active_membership docstring for the same fact), so a
    session anchoring more than one checkpoint here would otherwise lose
    RLS tenant context after its first commit."""
    unanchored = (
        db.query(IntegrityCheckpoint)
        .filter(~db.query(WormAnchorReceipt).filter(WormAnchorReceipt.checkpoint_id == IntegrityCheckpoint.id).exists())
        .order_by(IntegrityCheckpoint.to_sequence)
        .all()
    )

    count = 0
    for checkpoint in unanchored:
        key = f"{checkpoint.project_id}/{checkpoint.id}.json"
        worm_store.write_once(key, _anchor_payload(checkpoint))

        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        db.add(
            WormAnchorReceipt(
                tenant_id=checkpoint.tenant_id,
                project_id=checkpoint.project_id,
                checkpoint_id=checkpoint.id,
                anchor_key=key,
            )
        )
        db.commit()
        count += 1
    return count


def main() -> None:
    engine = create_engine(settings.database_url, future=True)
    total = 0
    with Session(engine) as db:
        tenant_ids = [r[0] for r in db.execute(text("SELECT id FROM tenants")).fetchall()]

    for tenant_id in tenant_ids:
        with Session(engine) as db:
            db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
            total += anchor_unanchored_checkpoints(db, worm_anchor_store, tenant_id)

    print(f"=== anchor_worm: {total} checkpoint(s) newly anchored across {len(tenant_ids)} tenant(s). ===")


if __name__ == "__main__":
    main()
