# DEC05 durability mechanism — design spec

Status: draft, pending user review
Owner: this session, branch `wp13-15-frontend-evidence`
Tracker rows this closes evidence toward (not the whole row): `docs/DEFECT_REGISTER.md` IPA04

## 1. Context

DEC05 (`docs/blueprint/BGP_DEC_Resolution_Intake_2026-09-25_ANSWERED.md`,
answered by kenAddme, accepted by the delivery lead 2026-09-27, **not** an
independent Operations/security sign-off) picked "Candidate A+": synchronous
durable replication before acknowledgement, plus an asynchronous,
independently-custodied hash-chain anchor for tamper-evidence. Its five
numbered sub-answers, and what already exists in this codebase for each:

1. **Candidate: A+.** N/A — a description, not a build item.
2. **Failure scenarios covered** (process/node/storage/single-zone: zero
   loss; regional: RPO≤5min/RTO archiving) — infra-level; not buildable
   without real multi-zone/region Postgres. Out of scope here (§4).
3. **Independence of the integrity-verification mechanism** — chain anchor
   in WORM storage under a credential the app DB role can't touch;
   verification runs under a third, separate identity. **Partially built,
   partially missing**: WP08 (`app/integrity.py`, migration
   `0006_wp08_integrity.py`) already folds `AuditEvent` rows into
   append-only `IntegrityCheckpoint` rows nothing (not even `bgp_owner`)
   can UPDATE/DELETE via DML. But that model's own docstring already
   admits the gap DEC05 names: *"Genuine independence from a rogue DBA
   needs verification material with custody OUTSIDE this Postgres instance
   entirely — a separate system this project has no credentials for yet."*
   A third, separate-identity role already exists too —
   `bgp_backup` (`BYPASSRLS`, `pg_read_all_data`, `CREATEDB`, nothing else;
   `scripts/restore_drill.py`) — but it reads the *same* Postgres instance
   the chain lives in, and `restore_drill.py`'s own integrity re-check
   re-derives the chain from that same (possibly-restored-from-tampered)
   data. No independent, external anchor exists to cross-check against.
4. **Numeric availability/RPO/RTO/verification-cadence targets** —
   infra/ops-level (§4), except the "quarterly restore test into a clean
   environment" piece, which **already exists and works**:
   `scripts/restore_drill.py` (built 2026-09-17, REQ-029) does a real
   pg_dump/restore/reconcile/re-verify cycle end to end on this machine.
   Honest limits already documented in its own docstring (single machine,
   dev-scale timings, no multi-zone proof) — not revisited here.
5. **Acknowledgement point** — API returns success only when the decision
   row, its audit entry, and its chain link commit in one transaction,
   confirmed on a synchronous replica; a pending/degraded state is visible
   and alerting, never counted as recorded. **Not built**: checkpointing
   today (`app/routers/integrity.py`'s `create_checkpoint`) is a manual,
   admin-triggered, on-demand action, not tied to any individual decision's
   own commit. `app/routers/decisions.py`'s `_record_decision` commits the
   `DecisionRecord` + its `AuditEvent` + an `IdempotencyRecord` in one
   transaction today — but no chain link. TRACKER.md's WP10 entry already
   names this exact gap: *"there is no live 'Pending' decision status
   distinct from 'committed', because that distinction is DEC05 Candidate
   B's own concept."* The synchronous-replica confirmation itself is
   infra (§4).

## 2. Goals

- G1: A decision's API "Recorded" response is never returned before that
  decision's own audit event has been folded into a new
  `IntegrityCheckpoint`, committed in the same DB transaction as the
  decision itself (closes §1.5's app-layer gap).
- G2: Every `IntegrityCheckpoint`'s digest gets an asynchronous, external,
  write-once copy that neither `bgp_app` nor `bgp_owner` can alter (closes
  §1.3's external-custody gap).
- G3: A verification job, run under `bgp_backup` (reused, not a new role),
  cross-checks the DB's own checkpoints against their external anchors —
  catching exactly the "rogue DBA rewrites the data and its own checkpoint
  together" attack `restore_drill.py`'s same-instance re-verification
  cannot catch.
- G4: That verification job runs on a real, observable schedule (a
  scheduled GitHub Actions workflow, same precedent as this session's
  DEC08 CI step) — the daily cadence §1.4 asks for, honestly buildable
  unlike the multi-zone infra.

## 3. Non-goals / explicitly out of scope this pass

Same discipline as DEC08 minutes ago in this session — named, not silently
dropped:

- Real synchronous cross-zone/cross-region Postgres replication, the
  99.5%-availability baseline, and RPO/RTO measurement beyond what
  `restore_drill.py` already proves. No multi-node infra exists here.
- A "Pending"/degraded decision status tied to replica unavailability.
  Building a status for infra that doesn't exist would itself be the
  "theatre, not a control" trap DEC05 warns about — documented as an open
  gap in `DEFECT_REGISTER.md` instead of faked.
- Any change to `restore_drill.py` itself — it already satisfies the
  quarterly-restore-test sub-answer; this spec only reuses its `bgp_backup`
  role.
- A new Postgres role. `bgp_backup` already is the "third, separate
  identity" — inventing a fourth (`bgp_verifier`) would duplicate an
  existing, working trust boundary for no benefit.

## 4. Architecture

### 4.1 Synchronous per-decision chain-link (G1)

`app/integrity.py` gets a new function, `checkpoint_new_events(db, tenant_id,
project_id) -> IntegrityCheckpoint | None`, refactored out of the existing
`take_checkpoint`: identical folding logic (reuses `_fold_chain`), but
**does not call `db.commit()`** — it only queries, folds, and `db.add()`s
the new `IntegrityCheckpoint`, leaving the commit to its caller.
`take_checkpoint` becomes a two-line wrapper (`checkpoint_new_events` +
`db.commit()`) so `app/routers/integrity.py`'s existing manual endpoint is
unchanged in behavior.

`app/routers/decisions.py`'s `_record_decision`, inside the existing `try`
block, immediately after the `AuditEvent(event_type="decision_recorded",
...)` `db.add()` call (line ~675) and before `db.commit()` (line ~687):
call `checkpoint_new_events(db, tenant_id, project.id)`. Because it shares
the same session and the same `try`/`db.commit()`, the decision row, its
audit event, and its new chain-link checkpoint commit atomically — G1,
satisfying DEC05 §5's transactional half exactly. The existing
`IntegrityError` conflict-recovery path (lines 688-748) is untouched; a
checkpoint-append conflict is covered by the concurrency fix below, not a
new code path.

**Concurrency**: two decisions committing concurrently in the *same*
project must not race on "what is the latest checkpoint." Postgres-only
(guarded the same way every other live-Postgres-specific fix in this file
already is): acquire `pg_advisory_xact_lock(hashtext(project_id))` before
calling `checkpoint_new_events` — a transaction-scoped advisory lock,
auto-released at commit/rollback, chosen over `SELECT ... FOR UPDATE`
because there may be no existing checkpoint row yet to lock (a project's
first-ever decision).

**Deny path** (`_deny`, line ~585): denied decisions already write an
`AuditEvent` (`decision_denied`) and commit. Per REQ-027's existing scope
("new decisions are blocked... on any project" once an incident is open,
not narrower), a denial's own audit event also gets folded into a
checkpoint here for the same reason: an unfolded audit event is a gap in
what the chain actually covers, regardless of whether the decision it
describes succeeded.

**Existing manual checkpoint endpoint**: unaffected in behavior, still
useful for backfilling any pre-existing unfolded events (e.g. non-decision
audit events this project may add later that don't go through
`_record_decision`).

### 4.2 WORM anchor store (G2)

New `app/worm_anchor.py`, same interface-then-swap-backend shape as
`app/attachment_storage.py`:

```python
class WormAnchorStore:
    def write_once(self, key: str, payload: bytes) -> None: ...
    def read(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...

class LocalWormAnchorStore(WormAnchorStore):
    # writes to settings.worm_anchor_root; refuses (raises) if the target
    # path already exists -- the local stand-in for object-lock's
    # write-once guarantee; chmod read-only after write as a second,
    # best-effort local guard (not a real substitute for S3 Object Lock
    # governance mode / equivalent -- see module docstring).
```

`key` is `f"{project_id}/{checkpoint_id}.json"`; `payload` is the canonical
JSON of `{checkpoint_id, project_id, tenant_id, from_sequence, to_sequence,
event_count, chain_digest, anchored_at}`. New setting
`worm_anchor_root: str = "./var/worm_anchor"` (`BGP_WORM_ANCHOR_ROOT`),
same env-override convention as `attachment_storage_root`.

New script `backend/scripts/anchor_worm.py` (manual-run, same precedent as
`restore_drill.py` — "this prototype has no scheduler"): connects as
`bgp_app`, finds every `IntegrityCheckpoint` with no matching
`WormAnchorReceipt` (new table, §5 — a `NOT EXISTS` query, not by
re-deriving from the WORM store's own contents, so a checkpoint with a
half-written file on disk from an interrupted prior run isn't silently
skipped), writes each to the WORM store, then `INSERT`s one receipt row.

**Why a new table instead of a column on `integrity_checkpoints`** (an
earlier draft of this spec tried a nullable `anchored_at` column + a
narrow UPDATE policy, and self-review caught a real flaw worth recording):
Postgres row-security `USING`/`WITH CHECK` clauses restrict which *rows*
an UPDATE may touch, not which *columns* change within them — a policy
permissive enough to let `anchored_at` move from NULL to non-NULL is
exactly as permissive about every other column on that same row, including
`chain_digest`. Closing that would need a `BEFORE UPDATE` trigger
comparing OLD/NEW column-by-column, a second, different tamper-prevention
mechanism alongside migration `0006`'s existing RLS-only approach, for one
piece of bookkeeping metadata. A separate INSERT-only receipts table needs
no UPDATE policy on `integrity_checkpoints` at all — that table's existing
"zero UPDATE, ever, full stop" guarantee (migration `0006`) stays literally
untouched, and this table's own correctness doesn't matter to the security
property anyway: `verify_against_anchor` (§4.3) trusts the WORM store's
actual file contents, not this table — the receipt is only a "have I
already done this" cursor for `anchor_worm.py` to skip redundant writes.

This step is asynchronous by design (matches DEC05 §"Candidate A+" wording
exactly: the *anchor* is asynchronous, only the chain-link-at-commit is
synchronous) — it never blocks a decision's own commit or response.

### 4.3 Independent verification job (G3, G4)

`app/integrity.py` gets `verify_against_anchor(db, worm_store, tenant_id,
project_id) -> dict`: for every checkpoint, read its WORM-anchored copy and
compare `chain_digest` byte-for-byte against the DB row's own
`chain_digest`. A mismatch, or a missing anchor for a checkpoint old enough
that `anchor_worm.py` should have covered it, opens the same
`IntegrityIncident` model `verify_integrity` already uses (reused, not
duplicated) with `detail` naming which check failed.

New script `backend/scripts/verify_against_anchor.py`: connects using
`settings.backup_database_url` (**`bgp_backup`, reused** — no new role),
runs both the existing same-instance `verify_integrity` re-derivation *and*
the new `verify_against_anchor` cross-check for every project, for the same
reason `restore_drill.py` already uses `bgp_backup` rather than `bgp_app`
or `bgp_owner`: a credential the running application never uses, so a
compromised app process cannot also compromise the thing checking it.

New `.github/workflows/integrity-verify.yml`: `on: schedule: cron: '0 6 *
* *'` (daily, matching DEC05 §4's "at least daily") plus
`workflow_dispatch` for manual runs, same Postgres-service-container setup
as `ci.yml`, adding a `bgp_backup` role-creation step (**a real,
independent gap this closes as a side effect** — `bgp_backup` currently
has no CI setup at all, so `restore_drill.py` has only ever run manually
against local dev Postgres; this workflow is the first time either script
using that role runs anywhere but a developer's own machine).

## 5. Data model / migration changes

New migration `00XX_dec05_worm_anchor.py`:
- New table `worm_anchor_receipts`: `id`, `tenant_id` (FK), `project_id`
  (FK), `checkpoint_id` (FK → `integrity_checkpoints.id`, `UNIQUE` — at
  most one receipt per checkpoint, enforced at the DB layer so a racing
  double-run of `anchor_worm.py` can't insert two), `anchor_key` (the WORM
  store key actually written), `anchored_at`. Tenant-isolated RLS, same
  shape as `integrity_incidents` (an ordinary table, not append-only) —
  `SELECT, INSERT` granted to `bgp_app`; deliberately **no UPDATE/DELETE
  grant at all**, since nothing ever needs to change or remove a receipt
  (a wrong one is *detected*, not fixed in place, by `verify_against_anchor`
  cross-checking the real WORM file — see §4.2's callout on why this table
  carries no tamper-evidence weight itself).
- Zero changes to `integrity_checkpoints` or `integrity_incidents` — WP08's
  existing append-only guarantee on checkpoints is untouched, not just
  preserved-in-intent.

## 6. Testing plan

New `tests/test_dec05_durability_mechanism.py`, live-Postgres-only (same
skip pattern as every other IPA02/WP13+ test), covering:
- A decision commit produces exactly one new `IntegrityCheckpoint` whose
  `to_sequence` includes that decision's own audit event, in the same
  transaction (assert via `verify_integrity` immediately succeeding with no
  extra manual checkpoint call).
- A denied decision also gets its audit event folded.
- Two concurrent decisions on different occurrences in the same project
  (threads + separate sessions, same technique as
  `test_bgp_f03_decision_concurrency.py`) both succeed and produce two
  checkpoints whose sequence ranges don't overlap and whose digests both
  independently re-verify — proving the advisory lock actually serializes.
- `anchor_worm.py`'s core function anchors an unanchored checkpoint and
  writes exactly one `worm_anchor_receipts` row; running it again is a
  no-op for that checkpoint (the `NOT EXISTS` query excludes it, and the
  table's `UNIQUE` constraint on `checkpoint_id` rejects a duplicate even
  under a race).
- `verify_against_anchor` catches a deliberately corrupted DB-side
  `chain_digest` that `verify_integrity` alone (same-instance
  re-derivation) is structurally unable to catch when the corruption is
  consistent within the DB itself — this is the test that actually proves
  G3's value over what already existed.
- Ruff clean, full suite green, same evidence bar as every prior entry.

## 7. Rollout

Single PR/commit sequence on `wp13-15-frontend-evidence` (no separate
phasing needed — §4.1-4.3 are one cohesive mechanism, not independently
useful halves): migration → `integrity.py`/`decisions.py` changes → WORM
store + script → verification script + scheduled workflow → tests →
tracker doc updates (`DEFECT_REGISTER.md` IPA04 row gets a fourth built
sub-piece named, same as this session's DEC08 update; row stays **Open**
regardless — DEC05's own §1.2 non-replication failure modes and the
independent assurance activities are still untouched).

## 8. Risks / open questions carried forward, not silently resolved

- The advisory-lock serialization adds one Postgres round-trip to every
  decision commit. Expected to be cheap (lock-only, no data movement) and
  well within the DEC08 decision-write budget (p95≤800ms) this session
  already verified passing — will be confirmed by the perf tests, not
  assumed.
- `anchor_worm.py` and `verify_against_anchor.py` both stay manually-run
  scripts locally; only the scheduled GH Actions workflow gives real
  automated cadence, and only for whatever Postgres that CI workflow
  targets — not a production multi-region deployment, which doesn't exist.
- Local-disk WORM storage's "refuse to overwrite" + chmod-read-only is a
  process-level guard, not a real immutability guarantee against someone
  with filesystem access to the CI/dev runner itself — named honestly in
  the module docstring, same as `attachment_storage.py`'s own local-disk
  caveat.
