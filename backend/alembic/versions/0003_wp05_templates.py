"""WP05 templates and template versions

Revision ID: 0003_wp05_templates
Revises: 0002_wp04_rls
Create Date: 2026-09-16

REQ-007 extended to templates: tenant_id is nullable here (NULL = a
platform-neutral starter, readable by every tenant, REQ-014), so the RLS
policy differs from WP04's -- it allows a row through when tenant_id matches
the session's tenant OR tenant_id is NULL, instead of an exact match only.
template_versions has no tenant_id of its own; its policy is expressed via a
subquery against its parent template.

READ is permissive (tenant's own rows + shared starters); WRITE (WITH CHECK)
requires an exact tenant match, deliberately excluding NULL -- no tenant's
bgp_app connection can create a shared starter through the API. Only
bgp_owner (table owner, exempt from RLS) can seed those, e.g. via
scripts/seed_starter_frameworks.py.
"""

from alembic import op
import sqlalchemy as sa

revision = "0003_wp05_templates"
down_revision = "0002_wp04_rls"
branch_labels = None
depends_on = None

APP_ROLE = "bgp_app"


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("forked_from_version_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_templates_tenant_id", "templates", ["tenant_id"])

    op.create_table(
        "template_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("templates.id"), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("template_id", "version_number", name="uq_template_version"),
    )
    op.create_index("ix_template_versions_template_id", "template_versions", ["template_id"])

    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON templates TO {APP_ROLE}")
    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON template_versions TO {APP_ROLE}")

    op.execute("ALTER TABLE templates ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE templates FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY templates_tenant_or_shared_starter ON templates
        USING (tenant_id = current_setting('app.tenant_id', true) OR tenant_id IS NULL)
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )

    op.execute("ALTER TABLE template_versions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE template_versions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY template_versions_via_parent ON template_versions
        USING (
            EXISTS (
                SELECT 1 FROM templates t
                WHERE t.id = template_versions.template_id
                AND (t.tenant_id = current_setting('app.tenant_id', true) OR t.tenant_id IS NULL)
            )
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS template_versions_via_parent ON template_versions")
    op.execute("ALTER TABLE template_versions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE template_versions DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS templates_tenant_or_shared_starter ON templates")
    op.execute("ALTER TABLE templates NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE templates DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON template_versions FROM {APP_ROLE}")
    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON templates FROM {APP_ROLE}")
    op.drop_table("template_versions")
    op.drop_table("templates")
