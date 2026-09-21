"""WP11: a narrow self-lookup RLS policy on memberships, for the one query
that structurally cannot work under the existing tenant-isolation policy.

Revision ID: 0015_wp11_my_orgs_rls
Revises: 0014_org_bootstrap_rls_fix
Create Date: 2026-09-20

Building the first real frontend page (WP11 -- DEC04 resolved this session)
exposed a gap no prior backend-only work needed to close: a logged-in user
with no tenant_id yet in hand (the login-landing case) has no way to ask
"which organisations can I act in?" `GET /me/orgs` is the obvious answer,
but `memberships` is RLS-protected on `tenant_id = current_setting
('app.tenant_id', true)` (migration 0002) -- correct for every per-tenant
query, but a query across ALL of a user's tenants cannot set that single
setting to more than one value at once, so it would return zero rows
against real Postgres no matter how the endpoint set context.

Same shape of fix as 0014's `invitations_token_lookup`: a second, narrowly
scoped permissive SELECT policy, OR'd with the existing tenant-isolation
policy by Postgres (multiple permissive policies for the same command
combine with OR). This one is keyed on `app.member_user_id` matching the
row's own `user_id` -- structurally incapable of returning any row that
isn't the calling user's own membership, tenant-isolation policy or not, so
it cannot become a cross-user leak no matter what the caller sets tenant
context to (or leaves it unset). See app/routers/orgs.py's `my_orgs` for
where this setting is applied.
"""

from alembic import op

revision = "0015_wp11_my_orgs_rls"
down_revision = "0014_org_bootstrap_rls_fix"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE POLICY memberships_self_lookup ON memberships
        FOR SELECT
        USING (user_id = current_setting('app.member_user_id', true))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS memberships_self_lookup ON memberships")
