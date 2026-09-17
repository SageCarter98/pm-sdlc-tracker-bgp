"""BGP-F04: stable source ids and preserved import history

Revision ID: 0012_bgp_f04_export_import
Revises: 0011_bgp_f03_concurrency
Create Date: 2026-09-17

BGP_Development_Review_Findings_v1.0.pdf, High finding: the archive builder
exported only current evidence state (no revision history, no source
hashes per revision), decision export omitted manifest/conditions/
compensating-review detail, and imported decisions/exceptions/audit/
integrity receipts were kept only as JSON inside the ImportJob row -- never
re-emitted by a LATER export of the importing tenant, so that history was
effectively lost after one hop.

- `source_id` (nullable) on templates, template_versions, projects,
  gate_occurrences, evidence_items: NULL for a natively-created row (its
  own id is its source id); set on import to the archive's original id, and
  never touched again. See models.py's Template.source_id docstring for
  the full reasoning -- this is what lets 'id' churn on every import while
  a record's IDENTITY stays comparable across an export -> import ->
  export chain.
- `imported_historical_records`: where imported decisions/exceptions/
  audit events/integrity receipts/compensating reviews live from now on --
  read-only content, never recreated as live governance rows (same
  SELECT+INSERT-only shape as decision_records/compensating_reviews,
  REQ-025's precedent), keyed by (tenant_id, kind, source_id) so
  re-importing an already-imported archive cannot duplicate entries.
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_bgp_f04_export_import"
down_revision = "0011_bgp_f03_concurrency"
branch_labels = None
depends_on = None

APP_ROLE = "bgp_app"

SOURCE_ID_TABLES = ["templates", "template_versions", "projects", "gate_occurrences", "evidence_items"]


def upgrade() -> None:
    for table in SOURCE_ID_TABLES:
        op.add_column(table, sa.Column("source_id", sa.String(36), nullable=True))

    op.create_table(
        "imported_historical_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("import_job_id", sa.String(36), sa.ForeignKey("import_jobs.id"), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("source_id", sa.String(36), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "kind", "source_id", name="uq_imported_historical_record"),
    )
    op.create_index("ix_imported_historical_records_tenant_id", "imported_historical_records", ["tenant_id"])

    op.execute(f"GRANT SELECT, INSERT ON imported_historical_records TO {APP_ROLE}")
    op.execute("ALTER TABLE imported_historical_records ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE imported_historical_records FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY imported_historical_records_tenant_isolation ON imported_historical_records
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS imported_historical_records_tenant_isolation ON imported_historical_records")
    op.execute("ALTER TABLE imported_historical_records NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE imported_historical_records DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE SELECT, INSERT ON imported_historical_records FROM {APP_ROLE}")
    op.drop_table("imported_historical_records")

    for table in reversed(SOURCE_ID_TABLES):
        op.drop_column(table, "source_id")
