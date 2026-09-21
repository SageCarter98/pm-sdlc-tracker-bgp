"""BGP-F01/BGP-F02: session-bound MFA and an authenticated compensating review

Revision ID: 0010_bgp_f01_f02_fixes
Revises: 0009_wp12_hardening
Create Date: 2026-09-17

BGP_Development_Review_Findings_v1.0.pdf, two High findings:

BGP-F01: `users.token_version` lets app/deps.py invalidate a previously
issued session token the moment a factor is reset, recovered or replaced
(app/routers/mfa.py bumps it) -- a session signed before that point stops
being honoured even though its signature still verifies.

BGP-F02: `compensating_reviews` replaces the old
`SeparationOverrideIn.reviewer_user_id/note` fields the DECIDING actor used
to submit themselves. A row here can only be created by the reviewer's own
authenticated session (app/routers/decisions.py's create_compensating_review)
and is bound to the occurrence and the evidence manifest_digest at review
time. `decision_records.separation_override_review_id` traces a decision
back to the specific review row that satisfied REQ-006 for it; the app
never mutates a compensating_reviews row after insert (same SELECT+INSERT-
only grant shape as decision_records, REQ-025's precedent), since it is
audit trail material, not editable state.
"""

from alembic import op
import sqlalchemy as sa

revision = "0010_bgp_f01_f02_fixes"
down_revision = "0009_wp12_hardening"
branch_labels = None
depends_on = None

APP_ROLE = "bgp_app"


def upgrade() -> None:
    op.add_column("users", sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "compensating_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("occurrence_id", sa.String(36), sa.ForeignKey("gate_occurrences.id"), nullable=False),
        sa.Column("reviewer_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("manifest_digest", sa.String(64), nullable=False),
        sa.Column("note", sa.String(1000), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_compensating_reviews_tenant_id", "compensating_reviews", ["tenant_id"])
    op.create_index("ix_compensating_reviews_occurrence_id", "compensating_reviews", ["occurrence_id"])

    op.add_column(
        "decision_records",
        sa.Column(
            "separation_override_review_id", sa.String(36), sa.ForeignKey("compensating_reviews.id"), nullable=True
        ),
    )

    # Same shape as decision_records (REQ-025's precedent): an audit-trail
    # row, never UPDATEd or DELETEd by the application.
    op.execute(f"GRANT SELECT, INSERT ON compensating_reviews TO {APP_ROLE}")
    op.execute("ALTER TABLE compensating_reviews ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE compensating_reviews FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY compensating_reviews_tenant_isolation ON compensating_reviews
        USING (tenant_id = current_setting('app.tenant_id', true))
        WITH CHECK (tenant_id = current_setting('app.tenant_id', true))
        """
    )


def downgrade() -> None:
    op.drop_column("decision_records", "separation_override_review_id")

    op.execute("DROP POLICY IF EXISTS compensating_reviews_tenant_isolation ON compensating_reviews")
    op.execute("ALTER TABLE compensating_reviews NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE compensating_reviews DISABLE ROW LEVEL SECURITY")
    op.execute(f"REVOKE SELECT, INSERT ON compensating_reviews FROM {APP_ROLE}")

    op.drop_table("compensating_reviews")
    op.drop_column("users", "token_version")
