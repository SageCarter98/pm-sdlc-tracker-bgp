"""WP09 export and import jobs

Revision ID: 0007_wp09_export_import
Revises: 0006_wp08_integrity
Create Date: 2026-09-17

REQ-030/031: standard tenant-isolated tables, same policy shape as WP06/07.
No special append-only or deny-all treatment needed here -- unlike
decision_records/integrity_checkpoints, nothing about export/import jobs
claims tamper-evidence.
"""

from alembic import op
import sqlalchemy as sa

revision = "0007_wp09_export_import"
down_revision = "0006_wp08_integrity"
branch_labels = None
depends_on = None

APP_ROLE = "bgp_app"

TENANT_OWNED_TABLES = ["export_jobs", "import_jobs", "imported_actor_provenance"]


def upgrade() -> None:
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="complete"),
        sa.Column("format_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("archive_json", sa.JSON(), nullable=False),
        sa.Column("archive_digest", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_export_jobs_tenant_id", "export_jobs", ["tenant_id"])

    op.create_table(
        "import_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("requested_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="quarantined"),
        sa.Column("archive_json", sa.JSON(), nullable=False),
        sa.Column("validation_report", sa.JSON(), nullable=True),
        sa.Column("commit_report", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_import_jobs_tenant_id", "import_jobs", ["tenant_id"])

    op.create_table(
        "imported_actor_provenance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("import_job_id", sa.String(36), sa.ForeignKey("import_jobs.id"), nullable=False),
        sa.Column("source_actor_id", sa.String(36), nullable=False),
        sa.Column("source_email", sa.String(320), nullable=True),
        sa.Column("matched_local_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_imported_actor_provenance_tenant_id", "imported_actor_provenance", ["tenant_id"])
    op.create_index("ix_imported_actor_provenance_import_job_id", "imported_actor_provenance", ["import_job_id"])

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

    op.drop_table("imported_actor_provenance")
    op.drop_table("import_jobs")
    op.drop_table("export_jobs")
