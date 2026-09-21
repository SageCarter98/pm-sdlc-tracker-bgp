"""WP15 Phase 1: evidence attachments (FE-097/098, conditional capability)

Revision ID: 0016_wp15_evidence_attachments
Revises: 0015_wp11_my_orgs_rls
Create Date: 2026-09-21

Tenant-owned table, same exact-match RLS policy shape as every other
evidence table since WP06 -- see that migration's own docstring for why.
"""

from alembic import op
import sqlalchemy as sa

revision = "0016_wp15_evidence_attachments"
down_revision = "0015_wp11_my_orgs_rls"
branch_labels = None
depends_on = None

APP_ROLE = "bgp_app"

TENANT_OWNED_TABLES = ["evidence_attachments"]


def upgrade() -> None:
    op.create_table(
        "evidence_attachments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("evidence_item_id", sa.String(36), sa.ForeignKey("evidence_items.id"), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=False),
        sa.Column("scan_status", sa.String(20), nullable=False, server_default="unavailable"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("uploaded_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evidence_attachments_tenant_id", "evidence_attachments", ["tenant_id"])
    op.create_index("ix_evidence_attachments_evidence_item_id", "evidence_attachments", ["evidence_item_id"])

    for table in TENANT_OWNED_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.tenant_id', true))
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
            """
        )


def downgrade() -> None:
    for table in reversed(TENANT_OWNED_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM {APP_ROLE}")

    op.drop_table("evidence_attachments")
