"""DEC05 G2: worm_anchor_receipts

Revision ID: 0017_dec05_worm_anchor
Revises: 0016_wp15_evidence_attachments
Create Date: 2026-09-29

Ordinary tenant-isolated table, same RLS shape as integrity_incidents
(migration 0006) -- NOT append-only itself, unlike integrity_checkpoints,
because this table carries no tamper-evidence weight of its own (see
WormAnchorReceipt's docstring in app/models.py). Only SELECT and INSERT are
granted to bgp_app -- deliberately no UPDATE/DELETE grant at all, since
nothing ever legitimately changes or removes a receipt; a wrong one is
detected by verify_against_anchor() cross-checking the real WORM file, not
corrected in place.
"""

from alembic import op
import sqlalchemy as sa

revision = "0017_dec05_worm_anchor"
down_revision = "0016_wp15_evidence_attachments"
branch_labels = None
depends_on = None

APP_ROLE = "bgp_app"


def upgrade() -> None:
    op.create_table(
        "worm_anchor_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column(
            "checkpoint_id",
            sa.String(36),
            sa.ForeignKey("integrity_checkpoints.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("anchor_key", sa.String(255), nullable=False),
        sa.Column("anchored_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_worm_anchor_receipts_tenant_id", "worm_anchor_receipts", ["tenant_id"])
    op.create_index("ix_worm_anchor_receipts_project_id", "worm_anchor_receipts", ["project_id"])

    op.execute(f"GRANT SELECT, INSERT ON worm_anchor_receipts TO {APP_ROLE}")
    op.execute("ALTER TABLE worm_anchor_receipts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE worm_anchor_receipts FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY worm_anchor_receipts_select ON worm_anchor_receipts
        FOR SELECT USING (tenant_id = current_setting('app.tenant_id', true))
        """
    )
    op.execute(
        """
        CREATE POLICY worm_anchor_receipts_insert ON worm_anchor_receipts
        FOR INSERT WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS worm_anchor_receipts_insert ON worm_anchor_receipts")
    op.execute("DROP POLICY IF EXISTS worm_anchor_receipts_select ON worm_anchor_receipts")
    op.execute("ALTER TABLE worm_anchor_receipts NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE worm_anchor_receipts DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE SELECT, INSERT ON worm_anchor_receipts FROM {APP_ROLE}")

    op.drop_table("worm_anchor_receipts")
