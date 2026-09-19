"""WP12 operations and hardening

Revision ID: 0009_wp12_hardening
Revises: 0008_wp10_drafts
Create Date: 2026-09-17

REQ-045: widens users.mfa_secret from 64 to 255 chars -- it now holds a
Fernet-encrypted ciphertext (~140 chars for a 32-char base32 TOTP seed),
not the plaintext secret (see app/security.py).

REQ-047: security_log_events is a global table, like users and
mfa_recovery_codes (WP04's own migration comment) -- no tenant_id RLS,
since login/register/MFA events are tenant-agnostic. Access control is
app-layer, self-scoped only (see SecurityLogEvent's docstring in
app/models.py).
"""

from alembic import op
import sqlalchemy as sa

revision = "0009_wp12_hardening"
down_revision = "0008_wp10_drafts"
branch_labels = None
depends_on = None

APP_ROLE = "bgp_app"


def upgrade() -> None:
    op.alter_column("users", "mfa_secret", type_=sa.String(255), existing_type=sa.String(64))

    op.create_table(
        "security_log_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_security_log_events_user_id", "security_log_events", ["user_id"])

    op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON security_log_events TO {APP_ROLE}")


def downgrade() -> None:
    op.execute(f"REVOKE SELECT, INSERT, UPDATE, DELETE ON security_log_events FROM {APP_ROLE}")
    op.drop_table("security_log_events")
    op.alter_column("users", "mfa_secret", type_=sa.String(64), existing_type=sa.String(255))
