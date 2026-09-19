"""BGP follow-up review (18 September 2026): remaining gaps in the BGP-F01
and BGP-F04 fixes shipped in 0010/0012.

Revision ID: 0013_bgp_followup_f01_f04
Revises: 0012_bgp_f04_export_import
Create Date: 2026-09-18

BGP_Follow_Up_Review_Findings_v1.0.pdf:

BGP-F01 (partially resolved): app/routers/mfa.py's enroll() immediately
overwrote users.mfa_secret and set mfa_enabled=False, so an account
temporarily lost second-factor protection for the entire window between
starting and completing a factor replacement. `pending_mfa_secret` /
`pending_mfa_created_at` let a proposed replacement be staged without
touching the active factor; only a successful verify() promotes it.

BGP-F04 (partially resolved): commit_import's EvidenceRevision constructor
did not restore the exported created_at, and an unmatched author's identity
was silently overwritten with the importing user on every subsequent
re-export. `evidence_revisions.source_actor_id`/`source_actor_email`
preserve the archive's original actor identity as historical provenance,
independent of the live actor_user_id FK -- never a local account, matched
by email on a later import exactly like ImportedActorProvenance already
does elsewhere.
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_bgp_followup_f01_f04"
down_revision = "0012_bgp_f04_export_import"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("pending_mfa_secret", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("pending_mfa_created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("evidence_revisions", sa.Column("source_actor_id", sa.String(36), nullable=True))
    op.add_column("evidence_revisions", sa.Column("source_actor_email", sa.String(320), nullable=True))


def downgrade() -> None:
    op.drop_column("evidence_revisions", "source_actor_email")
    op.drop_column("evidence_revisions", "source_actor_id")
    op.drop_column("users", "pending_mfa_created_at")
    op.drop_column("users", "pending_mfa_secret")
