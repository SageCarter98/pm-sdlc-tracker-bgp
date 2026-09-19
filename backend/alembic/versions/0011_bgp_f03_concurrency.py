"""BGP-F03: DB-level guarantees for decision concurrency

Revision ID: 0011_bgp_f03_concurrency
Revises: 0010_bgp_f01_f02_fixes
Create Date: 2026-09-17

BGP_Development_Review_Findings_v1.0.pdf, High finding: decision checks
(app/routers/decisions.py) read authority and evidence readiness, then
write a decision later, with nothing serialising a concurrent write to the
same rows in between. Application-code locking (this same session's
_compute_readiness(lock=True) and _require_decision_authority, both added
alongside this migration) closes the "read stale, then commit" half of the
race for a SINGLE occurrence. These two partial unique indexes close the
other half -- two concurrent requests that both pass every check before
either commits (there being only one occurrence, one non-superseding
decision, and one supersession-per-decision to race for) -- at the
database level, so the loser gets a real constraint violation instead of
silently creating a second, conflicting row:

- uq_decision_records_one_root_per_occurrence: at most one non-superseding
  (supersedes_decision_id IS NULL) decision per occurrence. Without this,
  two concurrent POST .../decisions calls for the same occurrence -- both
  passing the app-level 'already_decided' check before either commits --
  could both insert a root decision.
- uq_decision_records_supersedes_once: at most one decision may supersede
  any given decision. Without this, two concurrent POST
  .../decisions/{id}/superseding calls for the SAME id could both insert,
  creating two conflicting successor histories for one original decision.

app/routers/decisions.py's _record_decision now catches the resulting
IntegrityError and re-derives which of these (or the pre-existing
uq_idempotency_scope) actually fired, answering with the same deterministic
409 the up-front check would have given had it run second instead of
concurrently -- never a bare 500.
"""

from alembic import op

revision = "0011_bgp_f03_concurrency"
down_revision = "0010_bgp_f01_f02_fixes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE UNIQUE INDEX uq_decision_records_one_root_per_occurrence
        ON decision_records (occurrence_id)
        WHERE supersedes_decision_id IS NULL
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_decision_records_supersedes_once
        ON decision_records (supersedes_decision_id)
        WHERE supersedes_decision_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_decision_records_supersedes_once")
    op.execute("DROP INDEX IF EXISTS uq_decision_records_one_root_per_occurrence")
