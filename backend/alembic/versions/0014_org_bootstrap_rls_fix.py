"""Fix org-bootstrap RLS ordering: no user could ever create an org, and no
invitation could ever be accepted, against real Postgres.

Revision ID: 0014_org_bootstrap_rls_fix
Revises: 0013_bgp_followup_f01_f04
Create Date: 2026-09-19

Discovered while building an application-level (real HTTP, real Postgres)
test for the BGP-F03 follow-up review -- no prior test ever combined "a
genuine request through the app's own dependency-injected code" with "RLS
actually enforced" for the org-membership bootstrap path (the ~130-test
functional suite runs on SQLite, which has no RLS; the existing live-
Postgres suites seed data via raw SQL as bgp_owner, bypassing this code
path entirely). Two bugs, same root cause (SET LOCAL app.tenant_id applied
AFTER the query that needed it, or not applied at all):

1. `app/deps.py`'s `get_active_membership` queried `memberships` (RLS,
   fail-closed with no context) BEFORE setting `app.tenant_id` -- fixed in
   application code alone (reordered), no schema change needed. This alone
   made every already-a-member endpoint (`GET/POST /orgs/{tenant_id}/...`)
   return "No active membership" for a real, valid member.
2. `app/routers/orgs.py`'s `create_org` inserted the first `Membership` row
   for a brand-new tenant with no context ever set -- rejected outright at
   the database with "new row violates row-level security policy". Fixed
   by setting context from the just-generated tenant id before the insert.
3. `accept_invitation` has the same missing-context problem for ITS
   Membership insert, plus a structural one: its initial `Invitation`
   lookup is BY TOKEN, before any tenant is known -- there is no tenant
   context to set beforehand. This migration adds a second, narrowly
   scoped permissive SELECT policy on `invitations`, keyed on a per-request
   `app.invitation_lookup_token_hash` setting: Postgres combines multiple
   permissive policies for the same command with OR, so this lets a caller
   who presents the exact (unguessable, high-entropy) token hash find that
   ONE row regardless of tenant context, without weakening the existing
   tenant-isolation policy for anything else -- INSERT/UPDATE/DELETE, or
   any SELECT that doesn't set this. See app/routers/orgs.py's
   accept_invitation docstring for the full reasoning.
"""

from alembic import op

revision = "0014_org_bootstrap_rls_fix"
down_revision = "0013_bgp_followup_f01_f04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE POLICY invitations_token_lookup ON invitations
        FOR SELECT
        USING (token_hash = current_setting('app.invitation_lookup_token_hash', true))
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS invitations_token_lookup ON invitations")
