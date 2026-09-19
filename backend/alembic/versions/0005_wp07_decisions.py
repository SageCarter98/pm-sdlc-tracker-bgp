"""WP07 exceptions, decisions, idempotency and audit events

Revision ID: 0005_wp07_decisions
Revises: 0004_wp06_projects
Create Date: 2026-09-16

REQ-025: 'every application role is denied UPDATE or DELETE of decisions' --
decision_records is the one table in this project whose bgp_app grant is
deliberately SELECT+INSERT only, not the usual four verbs. Enforced by the
database role itself, not just by which HTTP routes exist.

Also backfills evidence_items.blocker_level (WP06 originally collapsed
blocker_level into a single `required` bool; REQ-022's conditional-approval
logic needs hard/conditional/advisory back -- see app/models.py).
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_wp07_decisions"
down_revision = "0004_wp06_projects"
branch_labels = None
depends_on = None

APP_ROLE = "bgp_app"

FULL_GRANT_TABLES = [
    "exception_records",
    "idempotency_records",
    "audit_events",
]


def upgrade() -> None:
    op.add_column("evidence_items", sa.Column("blocker_level", sa.String(20), nullable=False, server_default="hard"))

    op.create_table(
        "exception_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("evidence_item_id", sa.String(36), sa.ForeignKey("evidence_items.id"), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=False),
        sa.Column("safeguards", sa.String(1000), nullable=True),
        sa.Column("approving_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("owner_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_exception_records_tenant_id", "exception_records", ["tenant_id"])
    op.create_index("ix_exception_records_evidence_item_id", "exception_records", ["evidence_item_id"])

    op.create_table(
        "decision_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("occurrence_id", sa.String(36), sa.ForeignKey("gate_occurrences.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_role", sa.String(30), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("manifest_json", sa.JSON(), nullable=False),
        sa.Column("reviewed_manifest_digest", sa.String(64), nullable=False),
        sa.Column("conditions_json", sa.JSON(), nullable=True),
        sa.Column("supersedes_decision_id", sa.String(36), sa.ForeignKey("decision_records.id"), nullable=True),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("separation_override_reviewer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("separation_override_note", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_decision_records_tenant_id", "decision_records", ["tenant_id"])
    op.create_index("ix_decision_records_occurrence_id", "decision_records", ["occurrence_id"])

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("outcome_status", sa.String(20), nullable=False),
        sa.Column("outcome_decision_id", sa.String(36), sa.ForeignKey("decision_records.id"), nullable=True),
        sa.Column("denial_reason", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "actor_user_id", "operation", "idempotency_key", name="uq_idempotency_scope"),
    )
    op.create_index("ix_idempotency_records_tenant_id", "idempotency_records", ["tenant_id"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("occurrence_id", sa.String(36), sa.ForeignKey("gate_occurrences.id"), nullable=True),
        sa.Column("decision_id", sa.String(36), sa.ForeignKey("decision_records.id"), nullable=True),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_events_tenant_id", "audit_events", ["tenant_id"])
    op.create_index("ix_audit_events_project_id", "audit_events", ["project_id"])

    for table in FULL_GRANT_TABLES:
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

    # decision_records: SELECT+INSERT only -- REQ-025, see module docstring.
    op.execute(f"GRANT SELECT, INSERT ON decision_records TO {APP_ROLE}")
    op.execute("ALTER TABLE decision_records ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE decision_records FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY decision_records_tenant_isolation ON decision_records
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS decision_records_tenant_isolation ON decision_records")
    op.execute("ALTER TABLE decision_records NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE decision_records DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE SELECT, INSERT ON decision_records FROM {APP_ROLE}")

    for table in reversed(FULL_GRANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON {table} FROM {APP_ROLE}")

    op.drop_table("audit_events")
    op.drop_table("idempotency_records")
    op.drop_table("decision_records")
    op.drop_table("exception_records")
    op.drop_column("evidence_items", "blocker_level")
