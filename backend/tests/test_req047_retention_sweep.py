"""REQ-047/REQ-048 retention enforcement (scripts/retention_sweep.py).

Closes the "no scheduler exists" gap named since WP01 and restated in
`app/models.py`'s own SecurityLogEvent docstring, against the floors
`docs/wp02/data_retention_policy.md` proposes and that Freston Kenny
Adedeme reviewed and approved 2026-10-01 (see that file's Status line and
TRACKER.md's own entry): unaccepted invitations purged 90 days after
`expires_at`, accepted ones retained indefinitely; `tenant_access_events`
retained 12 months.

Live Postgres required, same skip pattern and for the same reason as
test_dec05_durability_mechanism.py: `invitations` and
`tenant_access_events` carry FORCE ROW LEVEL SECURITY (migration
0002_wp04_rls.py), and the fail-closed tenant policy that forces this
sweep's per-tenant design is exactly what the SQLite `client` fixture
cannot reproduce.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

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

_TestSession = sessionmaker(bind=_app_engine, future=True, expire_on_commit=False) if POSTGRES_AVAILABLE else None

NOW = datetime(2026, 10, 1, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture()
def tenant_id():
    """A throwaway tenant. `tenants` carries no RLS (migration
    0002_wp04_rls.py only covers memberships/invitations/
    tenant_access_events), so this needs no tenant context to insert."""
    tid = str(uuid.uuid4())
    with _TestSession() as db:
        db.execute(
            text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :n, :c)"),
            {"id": tid, "n": f"REQ-047 sweep {tid[:8]}", "c": NOW},
        )
        db.commit()
    return tid


def _add_invitation(tenant_id, *, expires_at, accepted_at=None):
    inv_id = str(uuid.uuid4())
    with _TestSession() as db:
        db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        db.execute(
            text(
                """INSERT INTO invitations (id, tenant_id, email, role, token_hash, expires_at, accepted_at, created_at)
                   VALUES (:id, :tid, :e, 'contributor', :th, :exp, :acc, :c)"""
            ),
            {
                "id": inv_id,
                "tid": tenant_id,
                "e": f"{inv_id[:8]}@example.com",
                "th": inv_id,
                "exp": expires_at,
                "acc": accepted_at,
                "c": NOW - timedelta(days=400),
            },
        )
        db.commit()
    return inv_id


def _add_access_event(tenant_id, *, occurred_at):
    event_id = str(uuid.uuid4())
    with _TestSession() as db:
        db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        db.execute(
            text(
                """INSERT INTO tenant_access_events (id, tenant_id, actor_user_id, project_ref, occurred_at)
                   SELECT :id, :tid, u.id, 'proj-ref', :occ FROM users u LIMIT 1"""
            ),
            {"id": event_id, "tid": tenant_id, "occ": occurred_at},
        )
        db.commit()
    return event_id


def _invitation_ids(tenant_id):
    with _TestSession() as db:
        db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        return {r[0] for r in db.execute(text("SELECT id FROM invitations")).fetchall()}


def _access_event_ids(tenant_id):
    with _TestSession() as db:
        db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        return {r[0] for r in db.execute(text("SELECT id FROM tenant_access_events")).fetchall()}


def _sweep(tenant_id, *, apply, now=NOW):
    from scripts.retention_sweep import purge_tenant_rows

    with _TestSession() as db:
        db.execute(text("SET LOCAL app.tenant_id = :tid"), {"tid": tenant_id})
        return purge_tenant_rows(db, now=now, apply=apply)


def test_the_fail_closed_rls_behaviour_this_sweeps_per_tenant_design_depends_on():
    """Not a test of the sweep itself -- a guard on the premise that forces
    its shape. `invitations`/`tenant_access_events` are FORCE ROW LEVEL
    SECURITY, so even bgp_owner sees zero rows with no `app.tenant_id` set
    (`tenant_id = NULL` is never true -- migration 0002_wp04_rls.py's own
    'fail closed'). A cross-tenant bulk DELETE would therefore silently
    affect nothing, which is why the sweep iterates tenant by tenant
    instead. If this ever starts failing, the sweep can be simplified --
    and until then, nobody should 'optimise' that loop away."""
    with _owner_engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM invitations")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM tenant_access_events")).scalar() == 0
        forced = conn.execute(
            text(
                """SELECT relname FROM pg_class
                   WHERE relname IN ('invitations', 'tenant_access_events')
                   AND relrowsecurity AND relforcerowsecurity"""
            )
        ).fetchall()
        assert {r[0] for r in forced} == {"invitations", "tenant_access_events"}


def test_purges_unaccepted_invitations_past_the_90_day_floor_only(tenant_id):
    well_past = _add_invitation(tenant_id, expires_at=NOW - timedelta(days=200))
    just_inside = _add_invitation(tenant_id, expires_at=NOW - timedelta(days=30))
    accepted_but_old = _add_invitation(
        tenant_id, expires_at=NOW - timedelta(days=200), accepted_at=NOW - timedelta(days=210)
    )

    counts = _sweep(tenant_id, apply=True)

    assert counts["invitations"] == 1
    remaining = _invitation_ids(tenant_id)
    assert well_past not in remaining
    # Policy: accepted invitations are retained indefinitely -- they
    # document how access was granted -- regardless of age.
    assert {just_inside, accepted_but_old} <= remaining


def test_purges_tenant_access_events_past_the_12_month_floor_only(tenant_id):
    old = _add_access_event(tenant_id, occurred_at=NOW - timedelta(days=400))
    recent = _add_access_event(tenant_id, occurred_at=NOW - timedelta(days=300))

    counts = _sweep(tenant_id, apply=True)

    assert counts["tenant_access_events"] == 1
    remaining = _access_event_ids(tenant_id)
    assert old not in remaining
    assert recent in remaining


def test_dry_run_reports_what_it_would_purge_without_deleting_anything(tenant_id):
    doomed = _add_invitation(tenant_id, expires_at=NOW - timedelta(days=200))
    old_event = _add_access_event(tenant_id, occurred_at=NOW - timedelta(days=400))

    counts = _sweep(tenant_id, apply=False)

    assert counts == {"invitations": 1, "tenant_access_events": 1}
    assert doomed in _invitation_ids(tenant_id)
    assert old_event in _access_event_ids(tenant_id)


def test_rerunning_the_sweep_is_a_no_op(tenant_id):
    _add_invitation(tenant_id, expires_at=NOW - timedelta(days=200))
    _add_access_event(tenant_id, occurred_at=NOW - timedelta(days=400))

    first = _sweep(tenant_id, apply=True)
    second = _sweep(tenant_id, apply=True)

    assert first == {"invitations": 1, "tenant_access_events": 1}
    assert second == {"invitations": 0, "tenant_access_events": 0}


def test_the_sweep_never_touches_another_tenants_eligible_rows(tenant_id):
    """The per-tenant loop is a correctness boundary, not just a workaround
    for FORCE RLS: sweeping tenant A must leave tenant B's equally-eligible
    rows alone, so an interrupted sweep can never have purged beyond the
    tenants it actually reached."""
    other = str(uuid.uuid4())
    with _TestSession() as db:
        db.execute(
            text("INSERT INTO tenants (id, name, created_at) VALUES (:id, :n, :c)"),
            {"id": other, "n": "REQ-047 bystander", "c": NOW},
        )
        db.commit()
    bystander = _add_invitation(other, expires_at=NOW - timedelta(days=200))

    _sweep(tenant_id, apply=True)

    assert bystander in _invitation_ids(other)


def test_security_log_events_purge_runs_globally_since_that_table_has_no_rls():
    """security_log_events carries no RLS at all (verified in-test below,
    not assumed): it is a global identity-level log with no tenant_id to
    scope on, filtered at the application layer instead -- so its sweep is
    one statement, not a per-tenant loop."""
    from scripts.retention_sweep import purge_global_security_log

    old_id, recent_id = str(uuid.uuid4()), str(uuid.uuid4())
    with _TestSession() as db:
        rls = db.execute(text("SELECT relrowsecurity FROM pg_class WHERE relname = 'security_log_events'")).scalar()
        assert rls is False, "this test's global-sweep premise assumes no RLS on security_log_events"
        for ev_id, created in ((old_id, NOW - timedelta(days=400)), (recent_id, NOW - timedelta(days=10))):
            db.execute(
                text("INSERT INTO security_log_events (id, event_type, created_at) VALUES (:id, 'test', :c)"),
                {"id": ev_id, "c": created},
            )
        db.commit()

    with _TestSession() as db:
        purged = purge_global_security_log(db, now=NOW, apply=True)

    with _TestSession() as db:
        ids = {
            r[0]
            for r in db.execute(
                text("SELECT id FROM security_log_events WHERE id IN (:a, :b)"), {"a": old_id, "b": recent_id}
            ).fetchall()
        }
    assert purged >= 1
    assert old_id not in ids
    assert recent_id in ids
