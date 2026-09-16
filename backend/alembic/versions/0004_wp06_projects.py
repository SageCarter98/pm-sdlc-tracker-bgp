"""WP06 projects, occurrences and evidence revisions

Revision ID: 0004_wp06_projects
Revises: 0003_wp05_templates
Create Date: 2026-09-16

REQ-007 extended: every table here is tenant-owned (no NULL-tenant shared
rows, unlike templates) -- same exact-match RLS policy shape as WP04's
memberships/invitations/tenant_access_events.

REQ-017: evidence_revisions is INSERT-only from the application's point of
view (app/routers/projects.py never UPDATEs or DELETEs a row here) -- the
RLS grant below still includes UPDATE/DELETE for symmetry with every other
table's grant, since revoking them at the role level would be a second,
overlapping enforcement mechanism for the same invariant the application
code already owns; immutability is enforced by never calling those
statements, not by making the role incapable of them.
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_wp06_projects"
down_revision = "0003_wp05_templates"
branch_labels = None
depends_on = None

APP_ROLE = "bgp_app"

TENANT_OWNED_TABLES = [
    "projects",
    "project_memberships",
    "gate_occurrences",
    "evidence_items",
    "evidence_revisions",
]


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("template_version_id", sa.String(36), sa.ForeignKey("template_versions.id"), nullable=False),
        sa.Column("class_id", sa.String(100), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])

    op.create_table(
        "project_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "user_id", name="uq_project_membership_project_user"),
    )
    op.create_index("ix_project_memberships_tenant_id", "project_memberships", ["tenant_id"])
    op.create_index("ix_project_memberships_project_id", "project_memberships", ["project_id"])

    op.create_table(
        "gate_occurrences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("gate_id", sa.String(100), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "gate_id", "sequence", name="uq_gate_occurrence_project_gate_sequence"),
    )
    op.create_index("ix_gate_occurrences_tenant_id", "gate_occurrences", ["tenant_id"])
    op.create_index("ix_gate_occurrences_project_id", "gate_occurrences", ["project_id"])

    op.create_table(
        "evidence_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("occurrence_id", sa.String(36), sa.ForeignKey("gate_occurrences.id"), nullable=False),
        sa.Column("gate_id", sa.String(100), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("evidence_kind", sa.String(50), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("permitted_role_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference", sa.String(500), nullable=True),
        sa.Column("latest_revision_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_evidence_items_tenant_id", "evidence_items", ["tenant_id"])
    op.create_index("ix_evidence_items_project_id", "evidence_items", ["project_id"])
    op.create_index("ix_evidence_items_occurrence_id", "evidence_items", ["occurrence_id"])

    op.create_table(
        "evidence_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("evidence_item_id", sa.String(36), sa.ForeignKey("evidence_items.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference", sa.String(500), nullable=True),
        sa.Column("source_version", sa.String(200), nullable=True),
        sa.Column("source_hash", sa.String(128), nullable=True),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("evidence_item_id", "revision_number", name="uq_evidence_revision_item_number"),
    )
    op.create_index("ix_evidence_revisions_tenant_id", "evidence_revisions", ["tenant_id"])
    op.create_index("ix_evidence_revisions_evidence_item_id", "evidence_revisions", ["evidence_item_id"])

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

    op.drop_table("evidence_revisions")
    op.drop_table("evidence_items")
    op.drop_table("gate_occurrences")
    op.drop_table("project_memberships")
    op.drop_table("projects")
