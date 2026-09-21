"""WP10 drafts (save/resume)

Revision ID: 0008_wp10_drafts
Revises: 0007_wp09_export_import
Create Date: 2026-09-17

REQ-034: standard tenant-isolated table. Owner-scoping (a draft is never
visible to any user but the one who saved it) is enforced at the
application layer (app/routers/drafts.py always filters by user_id, not
just tenant_id) -- RLS here only proves tenant isolation, the same as
every other table; per-user scoping within a tenant isn't something the
existing app.tenant_id RLS mechanism expresses, and adding a second
session variable for it was judged not worth the complexity for a
same-tenant, non-adversarial-within-tenant scoping requirement.
"""

from alembic import op
import sqlalchemy as sa

revision = "0008_wp10_drafts"
down_revision = "0007_wp09_export_import"
branch_labels = None
depends_on = None

APP_ROLE = "bgp_app"


def upgrade() -> None:
    op.create_table(
        "drafts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("draft_key", sa.String(200), nullable=False),
        sa.Column("form_data", sa.JSON(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "user_id", "draft_key", name="uq_draft_scope"),
    )
    op.create_index("ix_drafts_tenant_id", "drafts", ["tenant_id"])
    op.create_index("ix_drafts_user_id", "drafts", ["user_id"])

    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON drafts TO {APP_ROLE}")
    op.execute("ALTER TABLE drafts ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE drafts FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY drafts_tenant_isolation ON drafts
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS drafts_tenant_isolation ON drafts")
    op.execute("ALTER TABLE drafts NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE drafts DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON drafts FROM {APP_ROLE}")
    op.drop_table("drafts")
