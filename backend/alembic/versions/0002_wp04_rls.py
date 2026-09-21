"""WP04 tenant isolation: RLS policies and restricted role grants

Revision ID: 0002_wp04_rls
Revises: 0001_wp03_identity
Create Date: 2026-09-16

REQ-007: tenant-owned rows carry tenant_id; RLS enforced through a role that
is neither superuser nor table owner (bgp_app -- see
backend/scripts/setup_postgres_dev.sql, run once outside Alembic).

REQ-008: policies read a per-transaction setting (app.tenant_id) set via
SET LOCAL by the application (app/deps.py), which Postgres always clears at
transaction end -- so a pooled connection reused by a different tenant's
request never inherits the previous tenant's context.

`current_setting('app.tenant_id', true)` returns NULL when unset, and
`tenant_id = NULL` is never true, so a missing tenant context yields zero
rows rather than an error or an accidental full-table match (fail closed).
"""

from alembic import op

revision = "0002_wp04_rls"
down_revision = "0001_wp03_identity"
branch_labels = None
depends_on = None

TENANT_OWNED_TABLES = ["memberships", "invitations", "tenant_access_events"]

APP_ROLE = "bgp_app"


def upgrade() -> None:
    for table in TENANT_OWNED_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        # FORCE is redundant while bgp_app (not bgp_owner) runs the app, but
        # closes the gap if ownership is ever changed by mistake later.
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.tenant_id', true))
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
            """
        )

    # `users` and `mfa_recovery_codes` are global identities, not tenant-owned
    # rows (Blueprint Sec.5.2: "Auth identities may be global") -- bgp_app
    # still needs ordinary DML on them, but no tenant policy applies.
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON users TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON mfa_recovery_codes TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON tenants TO {APP_ROLE}")


def downgrade() -> None:
    for table in TENANT_OWNED_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM {APP_ROLE}")
    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON users FROM {APP_ROLE}")
    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON mfa_recovery_codes FROM {APP_ROLE}")
    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON tenants FROM {APP_ROLE}")
