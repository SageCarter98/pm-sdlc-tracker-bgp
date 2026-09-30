"""REQ-029: 'Restore ordinary data with RPO at most one hour and service
within eight hours; test quarterly in clean environments.' Verification
TST-029: 'Restore drill measures latest recoverable ordinary write and
service recovery including integrity reconciliation.'

**Superseded numeric target, DEC05 (Candidate A+, accepted 2026-09-27,
docs/blueprint/BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.md)**: RPO 0
in-region / <=5 min cross-region (tighter than REQ-029's original 1h
figure above -- this script still reports against REQ-029's number below
since that's what it can actually measure; DEC05's own in-region/
cross-region RPO needs real synchronous/cross-region replication
infrastructure this single-instance prototype does not have, see the
"Honest limits" section). RTO 8 hours matches REQ-029. DEC05 also names
this exact drill explicitly: "Quarterly restore test into a clean
environment" -- this script is that drill, not a new one.

Run manually (this prototype has no scheduler -- see TRACKER.md for the
recommended quarterly cadence, an operational practice this script doesn't
itself implement):

    cd backend && .venv/Scripts/python.exe scripts/restore_drill.py

What this actually does, end to end, against the real local bgp_dev:
1. pg_dump the live database (custom format), as bgp_backup -- a real
   backup, timed.
2. Find the latest committed write timestamp across every tenant-owned
   table with a created_at column -- the RPO measurement TST-029 asks for.
3. CREATE DATABASE a fresh, empty target and pg_restore the backup into it
   -- a real restore into a genuinely clean environment, timed (the RTO
   measurement).
4. Reconcile: compare row counts per table between source and restored
   database, and re-run the WP08 hash-chain verification
   (app/integrity.py) against every project in the restored copy, proving
   the restored data is not just present but internally consistent.
5. Drop the temporary restored database.

Why bgp_backup, not bgp_owner: a real finding from building this drill
2026-09-17. bgp_owner is correctly restricted by RLS since that day's
superuser-bug fix (see TRACKER.md) -- and RLS-restricted means pg_dump,
which has no way to set a per-row tenant context, cannot read tenant-owned
data through it at all. A dedicated BYPASSRLS, read-only role
(`bgp_backup`, backend/scripts/setup_postgres_dev.sql has no entry for it
yet -- created ad hoc via pgAdmin this session, see TRACKER.md for the
exact grants and the two follow-up fixes an inheritance default and a
PG16 per-grant inherit_option quirk required) is the standard answer for
backing up an RLS-protected database, and is also the role this script
uses for CREATE/DROP DATABASE (needs CREATEDB, granted to bgp_backup
specifically, not to bgp_owner -- keeping bgp_owner's privileges exactly
where WP04-07 left them).

Honest limits, read before treating a clean run as more than it is:
- This is a single local Postgres instance on one machine. It proves the
  backup/restore/reconcile MECHANISM works end to end; it says nothing
  about multi-node, multi-zone or multi-region failure domains -- DEC05's
  own numeric RPO targets (0 in-region, <=5 min cross-region) need real
  synchronous/cross-region replication infrastructure that does not exist
  in this prototype (named as a non-goal in
  docs/superpowers/specs/2026-09-29-dec05-durability-mechanism-design.md),
  not something a single-instance restore drill can prove either way.
- Measured elapsed times here reflect this dev machine's near-empty
  database, plus whatever this machine's own resource load happens to be
  at the moment (see TRACKER.md's 2026-09-30 entry on this machine's
  memory constraints affecting timing-sensitive tests). Not a
  production-scale RPO/RTO measurement -- don't quote them as if they were.
- bgp_backup's BYPASSRLS is real, standing access to every tenant's data,
  for backup purposes. It is not used by the running application anywhere
  (backend/app never imports BGP_BACKUP_DATABASE_URL) -- but its
  credential is itself now a thing requiring its own custody discipline,
  which this drill script does not solve, only names.
- **The reconciliation step's hash-chain re-verification will show a
  nonzero "known test-fixture artifact" count on this specific long-lived
  `bgp_dev` database, and that is expected, not a defect.**
  `test_wp08_tenant_isolation_rls.py` inserts a raw-SQL `IntegrityCheckpoint`
  row (`chain_digest='original-digest'`, not a real 64-hex-char sha256
  digest, with zero backing `AuditEvent` rows) to test the RLS policy
  itself, bypassing the real checkpoint pipeline entirely -- and because
  that table's own append-only guarantee means literally no role can
  UPDATE or DELETE it afterward (see `IntegrityCheckpoint`'s own docstring
  in app/models.py), every run of that test across every session on this
  shared dev database has left one more such row behind, permanently (141
  of them, found 2026-09-30). This script tells those apart from a
  genuinely unexplained mismatch by digest shape (real digests are always
  64 lowercase hex characters; a fabricated fixture value never is) --
  only a nonzero count under "UNEXPLAINED" below is worth investigating.
"""

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings  # noqa: E402

BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
# (table, timestamp column) -- tenant_access_events uses occurred_at, not
# created_at, unlike every other tenant-owned table (app/models.py).
TENANT_OWNED_TABLES_WITH_TIMESTAMPS = [
    ("memberships", "created_at"),
    ("invitations", "created_at"),
    ("tenant_access_events", "occurred_at"),
    ("templates", "created_at"),
    ("template_versions", "created_at"),
    ("projects", "created_at"),
    ("project_memberships", "created_at"),
    ("gate_occurrences", "created_at"),
    ("evidence_items", "created_at"),
    ("evidence_revisions", "created_at"),
    ("exception_records", "created_at"),
    ("decision_records", "created_at"),
    ("idempotency_records", "created_at"),
    ("audit_events", "created_at"),
    ("integrity_checkpoints", "created_at"),
    ("integrity_incidents", "detected_at"),
]
TENANT_OWNED_TABLES = [t for t, _ in TENANT_OWNED_TABLES_WITH_TIMESTAMPS]


def _find_pg_binary(name: str) -> str:
    import shutil

    found = shutil.which(name)
    if found:
        return found
    candidates = sorted(Path("C:/Program Files/PostgreSQL").glob(f"*/bin/{name}.exe"), reverse=True)
    if candidates:
        return str(candidates[0])
    raise RuntimeError(f"{name} not found on PATH or under C:/Program Files/PostgreSQL/*/bin")


def _conn_parts(url: str) -> dict:
    u = urlparse(url.replace("postgresql+psycopg2", "postgresql"))
    return {
        "host": u.hostname,
        "port": str(u.port),
        "user": u.username,
        "password": u.password,
        "dbname": u.path.lstrip("/"),
    }


def main() -> None:
    import os

    backup_role = _conn_parts(settings.backup_database_url)
    pg_dump = _find_pg_binary("pg_dump")
    pg_restore = _find_pg_binary("pg_restore")
    psql = _find_pg_binary("psql")
    backup_env = {**os.environ, "PGPASSWORD": backup_role["password"]}

    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = BACKUP_DIR / f"bgp_dev_{stamp}.dump"

    print(f"=== REQ-029 restore drill -- {stamp} ===")

    # --- Step 1: backup, as bgp_backup (BYPASSRLS + pg_read_all_data) --
    # bgp_owner cannot read tenant-owned rows without a tenant context,
    # which pg_dump has no way to set per-row; see this script's docstring.
    t0 = time.monotonic()
    subprocess.run(
        [
            pg_dump,
            "-h",
            backup_role["host"],
            "-p",
            backup_role["port"],
            "-U",
            backup_role["user"],
            "-Fc",
            "-f",
            str(backup_path),
            backup_role["dbname"],
        ],
        env=backup_env,
        check=True,
    )
    backup_seconds = time.monotonic() - t0
    backup_size = backup_path.stat().st_size
    print(f"[1/5] Backup complete: {backup_path.name} ({backup_size:,} bytes) in {backup_seconds:.2f}s")

    # --- Step 2: RPO measurement -- latest recoverable write. Uses
    # bgp_backup (BYPASSRLS), same reasoning as step 1: bgp_owner without a
    # tenant context sees zero rows in every tenant-owned table, which
    # would make this measurement silently wrong, not just unavailable.
    backup_engine = create_engine(settings.backup_database_url, future=True)
    latest_write = None
    for table, ts_column in TENANT_OWNED_TABLES_WITH_TIMESTAMPS:
        # One connection per table, not one shared across the whole loop:
        # a Postgres error aborts the rest of that connection's transaction,
        # so a single missing/renamed column would otherwise silently mask
        # every table checked after it (found and fixed 2026-09-17 -- this
        # script's first run reported "no rows" for a database that
        # demonstrably had rows, because tenant_access_events uses
        # occurred_at, not created_at, and the resulting error poisoned
        # every subsequent query in that same connection).
        with backup_engine.connect() as conn:
            row = conn.execute(text(f"SELECT max({ts_column}) AS m FROM {table}")).fetchone()
        if row and row.m and (latest_write is None or row.m > latest_write):
            latest_write = row.m
    now = datetime.now(timezone.utc)
    rpo = (now - latest_write).total_seconds() if latest_write else None
    print(
        f"[2/5] Latest recoverable ordinary write: {latest_write} (RPO proxy: {rpo:.1f}s ago)"
        if latest_write
        else "[2/5] No tenant-owned rows exist yet -- RPO has nothing to measure this run."
    )

    # --- Step 3: restore into a fresh, empty database ---
    drill_db = f"bgp_restore_drill_{stamp.lower()}"
    t0 = time.monotonic()
    try:
        subprocess.run(
            [
                psql,
                "-h",
                backup_role["host"],
                "-p",
                backup_role["port"],
                "-U",
                backup_role["user"],
                "-d",
                "postgres",
                "-c",
                f'CREATE DATABASE "{drill_db}"',
            ],
            env=backup_env,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"[3/5] SKIPPED: could not CREATE DATABASE ({exc.stderr.strip()}). "
            f"bgp_backup needs CREATEDB for this step -- see this script's own docstring. "
            f"Falling back to pg_restore --list (structural validation only, not a full restore)."
        )
        result = subprocess.run(
            [pg_restore, "--list", str(backup_path)], env=backup_env, capture_output=True, text=True, check=True
        )
        object_count = len([line for line in result.stdout.splitlines() if line and not line.startswith(";")])
        print(f"    Dump is structurally valid: {object_count} restorable objects listed.")
        print("=== Drill incomplete: full restore-into-clean-environment step needs bgp_backup CREATEDB. ===")
        return

    subprocess.run(
        [
            pg_restore,
            "-h",
            backup_role["host"],
            "-p",
            backup_role["port"],
            "-U",
            backup_role["user"],
            "-d",
            drill_db,
            "--no-owner",
            str(backup_path),
        ],
        env=backup_env,
        check=True,
        capture_output=True,
        text=True,
    )
    restore_seconds = time.monotonic() - t0
    print(f"[3/5] Restore into clean database '{drill_db}' complete in {restore_seconds:.2f}s (RTO proxy)")

    # --- Step 4: reconciliation. Restored copy is read as bgp_backup too --
    # it was restored --no-owner, so RLS still applies to whichever role
    # reads it, and this script has no tenant to scope to.
    drill_url = f"postgresql+psycopg2://{backup_role['user']}:{backup_role['password']}@{backup_role['host']}:{backup_role['port']}/{drill_db}"
    drill_engine = create_engine(drill_url, future=True)
    mismatches = []
    for table in TENANT_OWNED_TABLES:
        with backup_engine.connect() as src, drill_engine.connect() as dst:
            src_count = src.execute(text(f"SELECT count(*) FROM {table}")).scalar()
            dst_count = dst.execute(text(f"SELECT count(*) FROM {table}")).scalar()
        if src_count != dst_count:
            mismatches.append((table, src_count, dst_count))

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from app.integrity import verify_integrity  # noqa: E402
    from sqlalchemy.orm import Session

    import re

    _REAL_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")

    known_fixture_mismatches = []
    unexplained_mismatches = []
    with Session(drill_engine) as dsession:
        project_ids = [
            r[0] for r in dsession.execute(text("SELECT DISTINCT project_id FROM integrity_checkpoints")).fetchall()
        ]
        for pid in project_ids:
            tenant_id = dsession.execute(text("SELECT tenant_id FROM projects WHERE id = :id"), {"id": pid}).scalar()
            result = verify_integrity(dsession, tenant_id, pid)
            if result["ok"]:
                continue
            # Tell a genuinely unexplained mismatch apart from
            # test_wp08_tenant_isolation_rls.py's raw-SQL RLS-policy
            # fixture (chain_digest='original-digest', no real backing
            # audit events) -- by digest SHAPE, not by hardcoding that
            # one test's literal string, so any future non-pipeline
            # fixture with a non-hex digest is caught the same way. See
            # this script's own "Honest limits" docstring section.
            digests = [
                r[0]
                for r in dsession.execute(
                    text("SELECT chain_digest FROM integrity_checkpoints WHERE project_id = :pid"), {"pid": pid}
                ).fetchall()
            ]
            if any(not _REAL_DIGEST_RE.match(d) for d in digests):
                known_fixture_mismatches.append(pid)
            else:
                unexplained_mismatches.append((pid, tenant_id, result))

    integrity_ok = not unexplained_mismatches

    if mismatches:
        print(f"[4/5] RECONCILIATION FAILED -- row count mismatches: {mismatches}")
    else:
        print(
            f"[4/5] Reconciliation OK: row counts match across {len(TENANT_OWNED_TABLES)} tables checked; "
            f"hash-chain integrity re-verified on {len(project_ids)} project(s) in the restored copy -- "
            f"{len(known_fixture_mismatches)} known test-fixture artifact(s) (non-hex digest, expected on this "
            f"shared dev database, see docstring), {len(unexplained_mismatches)} UNEXPLAINED mismatch(es): "
            f"{'OK' if integrity_ok else 'INVESTIGATE -- ' + str(unexplained_mismatches)}"
        )

    # --- Step 5: cleanup ---
    drill_engine.dispose()
    subprocess.run(
        [
            psql,
            "-h",
            backup_role["host"],
            "-p",
            backup_role["port"],
            "-U",
            backup_role["user"],
            "-d",
            "postgres",
            "-c",
            f'DROP DATABASE "{drill_db}"',
        ],
        env=backup_env,
        check=True,
        capture_output=True,
        text=True,
    )
    print(f"[5/5] Dropped temporary database '{drill_db}'")

    print(
        f"=== Drill complete. Backup {backup_seconds:.2f}s, Restore {restore_seconds:.2f}s. "
        f"Both trivially within REQ-029/DEC05's 8h RTO target on this near-empty dev database -- "
        f"see this script's docstring for why that is not a production-scale proof, and why DEC05's "
        f"own in-region/cross-region RPO targets need infrastructure this drill cannot exercise. "
        f"Reconciliation: {len(unexplained_mismatches)} unexplained hash-chain mismatch(es) "
        f"({'none -- clean' if integrity_ok else 'INVESTIGATE, see [4/5] above'}). ==="
    )


if __name__ == "__main__":
    main()
