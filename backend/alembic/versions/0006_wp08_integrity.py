"""WP08 integrity checkpoints and incidents

Revision ID: 0006_wp08_integrity
Revises: 0005_wp07_decisions
Create Date: 2026-09-16

REQ-026: integrity_checkpoints is the one table in this project that is
append-only to EVERY role, including bgp_owner (the table owner) -- not
just bgp_app the way decision_records restricts bgp_app alone (WP07).

Verified empirically while building this (the first assumption was wrong,
worth recording): simply *omitting* an UPDATE/DELETE policy under FORCE
RLS does NOT deny those commands -- Postgres falls back to the SELECT
policy's USING clause to decide which rows an UPDATE/DELETE may target,
so a tenant-matching SELECT policy alone left rows fully updatable/
deletable by anyone whose tenant context matched, owner included. The fix
here is an EXPLICIT `USING (false)` policy for UPDATE and for DELETE --
that unconditionally matches zero rows for those commands, for every
role, including bgp_owner under FORCE. See IntegrityCheckpoint's
docstring in app/models.py for the honest limits of this even now
(DDL/ALTER TABLE is not something REVOKE or RLS can take from an owner).

integrity_incidents is an ordinary table -- see IntegrityIncident's
docstring for why it doesn't need the same protection.
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_wp08_integrity"
down_revision = "0005_wp07_decisions"
branch_labels = None
depends_on = None

APP_ROLE = "bgp_app"


def upgrade() -> None:
    op.create_table(
        "integrity_checkpoints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("from_sequence", sa.Integer(), nullable=True),
        sa.Column("to_sequence", sa.Integer(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("chain_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_integrity_checkpoints_tenant_id", "integrity_checkpoints", ["tenant_id"])
    op.create_index("ix_integrity_checkpoints_project_id", "integrity_checkpoints", ["project_id"])

    op.create_table(
        "integrity_incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolution_note", sa.String(1000), nullable=True),
    )
    op.create_index("ix_integrity_incidents_tenant_id", "integrity_incidents", ["tenant_id"])
    op.create_index("ix_integrity_incidents_project_id", "integrity_incidents", ["project_id"])

    # integrity_incidents: ordinary tenant-isolated table, full CRUD for bgp_app.
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON integrity_incidents TO {APP_ROLE}")
    op.execute("ALTER TABLE integrity_incidents ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE integrity_incidents FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY integrity_incidents_tenant_isolation ON integrity_incidents
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )

    # integrity_checkpoints: SELECT + INSERT only, no UPDATE/DELETE grant or
    # policy at all -- denied to every role including the table owner once
    # FORCE is set.
    op.execute(f"GRANT SELECT, INSERT ON integrity_checkpoints TO {APP_ROLE}")
    op.execute("ALTER TABLE integrity_checkpoints ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE integrity_checkpoints FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY integrity_checkpoints_select ON integrity_checkpoints
        FOR SELECT USING (tenant_id = current_setting('app.tenant_id', true))
        """
    )
    op.execute(
        """
        CREATE POLICY integrity_checkpoints_insert ON integrity_checkpoints
        FOR INSERT WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )
    # Explicit, unconditional deny -- see the module docstring for why an
    # absent policy was not enough.
    op.execute("CREATE POLICY integrity_checkpoints_no_update ON integrity_checkpoints FOR UPDATE USING (false)")
    op.execute("CREATE POLICY integrity_checkpoints_no_delete ON integrity_checkpoints FOR DELETE USING (false)")


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS integrity_checkpoints_no_delete ON integrity_checkpoints")
    op.execute("DROP POLICY IF EXISTS integrity_checkpoints_no_update ON integrity_checkpoints")
    op.execute("DROP POLICY IF EXISTS integrity_checkpoints_insert ON integrity_checkpoints")
    op.execute("DROP POLICY IF EXISTS integrity_checkpoints_select ON integrity_checkpoints")
    op.execute("ALTER TABLE integrity_checkpoints NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE integrity_checkpoints DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE SELECT, INSERT ON integrity_checkpoints FROM {APP_ROLE}")

    op.execute("DROP POLICY IF EXISTS integrity_incidents_tenant_isolation ON integrity_incidents")
    op.execute("ALTER TABLE integrity_incidents NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE integrity_incidents DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON integrity_incidents FROM {APP_ROLE}")

    op.drop_table("integrity_incidents")
    op.drop_table("integrity_checkpoints")
