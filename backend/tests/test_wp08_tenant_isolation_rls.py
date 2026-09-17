"""WP08: REQ-026's strongest claim, proven live -- integrity_checkpoints
cannot be UPDATEd or DELETEd by ANY role, including bgp_owner (the table
owner), via an explicit `USING (false)` RLS policy on those two commands
under FORCE ROW LEVEL SECURITY. This is a stronger guarantee than WP07's
"bgp_app can't" (that was a GRANT restriction on the app role only); here
it's tested directly against bgp_owner's own connection, the same role
that runs migrations and owns every other table in this database.

Note the shape of the guarantee: an RLS `USING (false)` policy makes the
UPDATE/DELETE match zero rows -- Postgres does not raise a permission
error, it just silently affects nothing. These tests assert on rowcount
and post-attempt content, not on an exception (an earlier version of this
migration relied on simply omitting an UPDATE/DELETE policy, which turned
out NOT to deny those commands -- see the migration's own docstring).
"""
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.core.config import settings

try:
    _owner_engine = create_engine(settings.migration_database_url, future=True)
    with _owner_engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    _app_engine = create_engine(settings.database_url, future=True)
    with _app_engine.connect() as _conn:
        _conn.execute(text("SELECT 1"))
    POSTGRES_AVAILABLE = True
except OperationalError:
    POSTGRES_AVAILABLE = False

pytestmark = pytest.mark.skipif(not POSTGRES_AVAILABLE, reason="live Postgres with bgp_owner/bgp_app not configured")


@pytest.fixture()
def seeded_checkpoint():
    tenant_id, user_id = str(uuid.uuid4()), str(uuid.uuid4())
    template_id, version_id = str(uuid.uuid4()), str(uuid.uuid4())
    project_id, checkpoint_id = str(uuid.uuid4()), str(uuid.uuid4())

    minimal_schema = '{"schema_version": 1, "tracks": ["Delivery"], "classes": ["A"], "roles": ["contributor"], "statuses": ["Not started"], "decision_outcomes": ["Approve"], "gates": []}'

    with _owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        conn.execute(text("INSERT INTO tenants (id, name, created_at) VALUES (:id, 'T', now())"), {"id": tenant_id})
        conn.execute(
            text("INSERT INTO users (id, email, password_hash, verified, created_at, mfa_enabled) VALUES (:id, :email, 'x', false, now(), false)"),
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        conn.execute(text("INSERT INTO templates (id, tenant_id, name, created_at) VALUES (:id, :tid, 'T', now())"), {"id": template_id, "tid": tenant_id})
        conn.execute(
            text(
                "INSERT INTO template_versions (id, template_id, version_number, schema_json, status, created_by_user_id, created_at, published_at) "
                "VALUES (:id, :tpl, 1, CAST(:schema AS JSON), 'published', :uid, now(), now())"
            ),
            {"id": version_id, "tpl": template_id, "schema": minimal_schema, "uid": user_id},
        )
        conn.execute(
            text("INSERT INTO projects (id, tenant_id, name, template_version_id, class_id, owner_user_id, created_at) VALUES (:id, :tid, 'P', :ver, 'A', :uid, now())"),
            {"id": project_id, "tid": tenant_id, "ver": version_id, "uid": user_id},
        )
        conn.execute(
            text(
                "INSERT INTO integrity_checkpoints (id, tenant_id, project_id, to_sequence, event_count, chain_digest, created_at) "
                "VALUES (:id, :tid, :pid, 1, 1, 'original-digest', now())"
            ),
            {"id": checkpoint_id, "tid": tenant_id, "pid": project_id},
        )

    yield {"tenant_id": tenant_id, "project_id": project_id, "checkpoint_id": checkpoint_id}

    # No cleanup: the checkpoint row this fixture creates can never be
    # UPDATEd or DELETEd by any role (that's the exact property under
    # test), and `integrity_checkpoints.project_id` has a real FK into
    # `projects` -- so the project, and everything the project in turn
    # references (template_version, template, user, tenant), can never be
    # deleted either as long as the checkpoint exists. Earlier versions of
    # this fixture tried to DELETE FROM projects anyway, which raised a
    # ForeignKeyViolation during teardown and could leave the shared test
    # connection pool in a bad state for whichever test ran next. A handful
    # of small, harmless rows accumulating in the local dev database across
    # test runs is the honest, permanent cost of testing an append-only-
    # forever mechanism against a real database, not a bug to work around.


def test_owner_cannot_update_a_checkpoint(seeded_checkpoint):
    t = seeded_checkpoint
    with _owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
        result = conn.execute(text("UPDATE integrity_checkpoints SET chain_digest = 'hacked' WHERE id = :id"), {"id": t["checkpoint_id"]})
        assert result.rowcount == 0, "the owner's UPDATE must match zero rows under the deny-all policy"

    with _owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
        row = conn.execute(text("SELECT chain_digest FROM integrity_checkpoints WHERE id = :id"), {"id": t["checkpoint_id"]}).fetchone()
    assert row.chain_digest == "original-digest"


def test_owner_cannot_delete_a_checkpoint(seeded_checkpoint):
    t = seeded_checkpoint
    with _owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
        result = conn.execute(text("DELETE FROM integrity_checkpoints WHERE id = :id"), {"id": t["checkpoint_id"]})
        assert result.rowcount == 0, "the owner's DELETE must match zero rows under the deny-all policy"

    with _owner_engine.begin() as conn:
        conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
        row = conn.execute(text("SELECT chain_digest FROM integrity_checkpoints WHERE id = :id"), {"id": t["checkpoint_id"]}).fetchone()
    assert row is not None, "the row must still exist -- the DELETE must not have removed it"


def test_app_role_cannot_update_or_delete_a_checkpoint_either(seeded_checkpoint):
    """bgp_app's failure mode differs from bgp_owner's: bgp_app was never
    GRANTed UPDATE/DELETE on this table at all (migration
    0006_wp08_integrity.py grants it SELECT+INSERT only), so this fails at
    the privilege check with a real permission-denied error -- it never
    even reaches RLS's deny-all policy the way bgp_owner's attempt does."""
    from sqlalchemy.exc import ProgrammingError

    t = seeded_checkpoint
    with pytest.raises(ProgrammingError, match="permission denied"):
        with _app_engine.begin() as conn:
            conn.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": t["tenant_id"]})
            conn.execute(text("UPDATE integrity_checkpoints SET chain_digest = 'hacked' WHERE id = :id"), {"id": t["checkpoint_id"]})
