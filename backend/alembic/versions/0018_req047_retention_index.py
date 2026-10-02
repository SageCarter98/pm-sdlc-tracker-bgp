"""REQ-047 retention sweep: index security_log_events.created_at

Revision ID: 0018_req047_retention_index
Revises: 0017_dec05_worm_anchor
Create Date: 2026-10-01

scripts/retention_sweep.py's global sweep of `security_log_events` filters
on `created_at` alone -- that table carries no RLS and so no tenant_id
predicate to narrow on first. Measured before adding this (EXPLAIN against
the real dev database, 3529 rows): `Seq Scan ... Filter: (created_at <
now())`, cost 126.94, growing without bound as the log accumulates.

Deliberately NOT adding matching indexes to `invitations.expires_at` or
`tenant_access_events.occurred_at`, which the same sweep also filters on:
those two are swept per tenant under FORCE ROW LEVEL SECURITY, and their
measured plans already ride the existing `ix_invitations_tenant_id` /
`ix_tenant_access_events_tenant_id` with the timestamp as a cheap filter
over one tenant's few rows (Index Scan, cost 8.31 / 8.17). An index there
would be write-cost for no measured read benefit -- checked rather than
assumed by symmetry.
"""

from alembic import op

revision = "0018_req047_retention_index"
down_revision = "0017_dec05_worm_anchor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_security_log_events_created_at", "security_log_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_security_log_events_created_at", table_name="security_log_events")
