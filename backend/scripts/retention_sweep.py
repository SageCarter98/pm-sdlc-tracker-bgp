"""REQ-047/REQ-048 retention enforcement: the disposal sweep.

Closes the "retention is not automatically enforced (no scheduler exists,
a gap named since WP01)" gap that `app/models.py`'s own SecurityLogEvent
docstring and `docs/wp02/data_retention_policy.md` both name.

Floors enforced here are that policy's own proposals, reviewed and
approved by Freston Kenny Adedeme on 2026-10-01 (the policy's open
question 1 -- see that file's Status line and TRACKER.md's entry for this
pass). They are NOT blueprint-derived numbers; a later governance review
can change them in one place here:

  - `invitations`: unaccepted invitations purged 90 days after
    `expires_at`. Accepted invitations are retained indefinitely -- they
    document how access was granted.
  - `tenant_access_events`: retained 12 months (REQ-005's sponsor-
    visibility log).
  - `security_log_events`: same 12-month floor. **Inference, flagged
    rather than silently assumed**: the policy's table lists
    `tenant_access_events` but never names `security_log_events`, while
    that model's own docstring points here for its retention. Same
    security-log rationale, so the same floor is applied -- confirm or
    correct this at the next policy review.

Deliberately NOT enforced, because it is not enforceable rather than
overlooked:

  - `users` ("life of account + 30-day post-deletion grace window"): this
    app has no account-deletion mechanism at all -- no `deleted_at`
    column, no deletion endpoint -- so there is no deletion event for a
    grace window to run from. Enforcing this floor needs that feature
    built first; inventing a deletion column here as a side effect of a
    sweep would be scope this pass was not asked for.
  - `memberships`: removal is already `active=false` (soft delete), which
    IS the policy's stated mechanism. Nothing to purge.
  - `mfa_recovery_codes`: policy says retain for the life of the MFA
    enrolment -- explicitly do not purge early (REQ-002 audit of recovery
    use). No action is the correct action.
  - Published `template_versions`, decisions, audit events, checkpoints:
    indefinite by design (REQ-011 immutability; append-only decision/audit
    tables with no DELETE endpoint in the approved API contract).

Run manually (this prototype has no scheduler, same as scripts/
anchor_worm.py and scripts/restore_drill.py). Dry run by default --
nothing is deleted without `--apply`:

    cd backend && .venv/Scripts/python.exe scripts/retention_sweep.py
    cd backend && .venv/Scripts/python.exe scripts/retention_sweep.py --apply

Connects as bgp_app, an ordinary operational role, and iterates tenant by
tenant setting `app.tenant_id` -- the same shape as scripts/anchor_worm.py
and for a stronger reason: `invitations` and `tenant_access_events` carry
FORCE ROW LEVEL SECURITY (migration 0002_wp04_rls.py), which applies to
the table owner too, and the tenant policy is fail-closed. A single
cross-tenant `DELETE` would therefore affect ZERO rows, silently, with no
error -- measured, not assumed (see
tests/test_req047_retention_sweep.py's first test, which guards that
premise). Deliberately rejected alternatives: granting BYPASSRLS to a
maintenance role, or adding a retention-specific RLS policy -- each would
punch a hole in the exact tenant-isolation control REQ-007/008 and the
REQ-009 adversarial suite exist to defend, to save a loop.

Commits per tenant, not once at the end, so an interrupted run keeps the
disposals it already made rather than rolling back the whole sweep --
same restartability reasoning as anchor_worm.py's per-checkpoint commit.
`security_log_events` carries no RLS (it is a global identity-level log
with no tenant_id), so its sweep is one statement outside the loop.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings  # noqa: E402

# Interval literals, not parameters: they are this module's own approved
# constants, never caller input. The reference time IS a parameter, so
# tests can pin "now" instead of depending on wall-clock drift.
INVITATION_FLOOR = "90 days"
ACCESS_EVENT_FLOOR = "12 months"
SECURITY_LOG_FLOOR = "12 months"

# Postgres interval arithmetic, rather than a Python timedelta, so "12
# months" means twelve calendar months instead of an approximated 365/366
# days against a floor the policy states as a minimum.
_TENANT_SWEEPS = {
    "invitations": f"FROM invitations WHERE accepted_at IS NULL AND expires_at < :now - INTERVAL '{INVITATION_FLOOR}'",
    "tenant_access_events": f"FROM tenant_access_events WHERE occurred_at < :now - INTERVAL '{ACCESS_EVENT_FLOOR}'",
}
_SECURITY_LOG_SWEEP = f"FROM security_log_events WHERE created_at < :now - INTERVAL '{SECURITY_LOG_FLOOR}'"


def _purge(db: Session, from_where: str, now: datetime, apply: bool) -> int:
    """Counts eligible rows, then deletes them only when `apply` -- the
    same predicate either way, so a dry run reports exactly what a real
    run would remove. Bulk `DELETE ... WHERE`, not a load-then-delete
    loop: no row is ever materialised in Python."""
    if not apply:
        return db.execute(text(f"SELECT count(*) {from_where}"), {"now": now}).scalar() or 0
    return db.execute(text(f"DELETE {from_where}"), {"now": now}).rowcount


def purge_tenant_rows(db: Session, *, now: datetime, apply: bool) -> dict[str, int]:
    """Sweeps the RLS-scoped tables for whichever single tenant `db` is
    currently scoped to -- the caller must have run
    `SET LOCAL app.tenant_id` already, exactly as every other RLS-scoped
    query in this codebase does. Returns per-table counts purged (or, on
    a dry run, that would be purged).

    Scoping to one tenant per call is a correctness property, not only an
    RLS workaround: an interrupted sweep can then never have purged rows
    beyond the tenants it actually reached.

    Commits here, once, after both tables -- not per table and not left to
    the caller. Per table would be wrong: a COMMIT ends the transaction
    `SET LOCAL app.tenant_id` was scoped to (see anchor_worm.py's own note
    on this), so the second statement would then run with no tenant
    context and fail closed to zero rows. Leaving it to the caller would
    be worse: an `apply=True` call whose caller forgot to commit would
    report rows purged while changing nothing."""
    counts = {table: _purge(db, from_where, now, apply) for table, from_where in _TENANT_SWEEPS.items()}
    if apply:
        db.commit()
    return counts


def purge_global_security_log(db: Session, *, now: datetime, apply: bool) -> int:
    """Sweeps `security_log_events`, which carries no RLS at all -- one
    statement for every tenant's rows at once, no tenant context needed.
    Commits for the same reason as purge_tenant_rows."""
    purged = _purge(db, _SECURITY_LOG_SWEEP, now, apply)
    if apply:
        db.commit()
    return purged


def main() -> None:
    parser = argparse.ArgumentParser(description="REQ-047 retention/disposal sweep (dry run unless --apply).")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="actually delete. Without this, reports what would be purged and deletes nothing.",
    )
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    engine = create_engine(settings.database_url, future=True)
    totals = dict.fromkeys(_TENANT_SWEEPS, 0)

    with Session(engine) as db:
        tenant_ids = [r[0] for r in db.execute(text("SELECT id FROM tenants")).fetchall()]

    for tenant_id in tenant_ids:
        with Session(engine) as db:
            db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
            for table, count in purge_tenant_rows(db, now=now, apply=args.apply).items():
                totals[table] += count

    with Session(engine) as db:
        totals["security_log_events"] = purge_global_security_log(db, now=now, apply=args.apply)

    engine.dispose()

    mode = "purged" if args.apply else "would purge (dry run -- pass --apply to delete)"
    print(f"=== retention_sweep across {len(tenant_ids)} tenant(s), reference time {now.isoformat()} ===")
    for table, count in totals.items():
        print(f"  {table}: {mode} {count} row(s)")
    print(
        f"  floors: invitations {INVITATION_FLOOR} after expires_at (unaccepted only), "
        f"tenant_access_events {ACCESS_EVENT_FLOOR}, security_log_events {SECURITY_LOG_FLOOR}"
    )


if __name__ == "__main__":
    main()
