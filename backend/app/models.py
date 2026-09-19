import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    """Blueprint Sec.2 role table. platform_operator is out of tenant scope
    (no membership row) and is not modelled here yet -- WP12."""

    CONTRIBUTOR = "contributor"
    APPROVER = "approver"
    SPONSOR = "sponsor"
    ASSURANCE_REVIEWER = "assurance_reviewer"
    TENANT_ADMINISTRATOR = "tenant_administrator"


ROLES_REQUIRING_MFA = {Role.APPROVER, Role.SPONSOR, Role.TENANT_ADMINISTRATOR}


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="tenant")
    invitations: Mapped[list["Invitation"]] = relationship(back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # MFA -- REQ-002. Session mechanism remains DEC04. mfa_secret holds a
    # Fernet-encrypted TOTP seed since WP12/REQ-045 (migration
    # 0009_wp12_hardening.py widened this column from 64 to 255 chars --
    # a Fernet token for a 32-char base32 secret is ~140 chars, well past
    # the old plaintext-sized column); see app/security.py's
    # encrypt_mfa_secret/decrypt_mfa_secret.
    mfa_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)

    # BGP-F01 follow-up: a factor REPLACEMENT is proposed here, encrypted the
    # same way as mfa_secret, while the currently-active mfa_secret/
    # mfa_enabled are left completely untouched. Only a successful
    # app/routers/mfa.py:verify() call atomically promotes this to the live
    # mfa_secret -- so an abandoned, failed or expired replacement (see
    # PENDING_MFA_MAX_AGE_SECONDS in app/security.py) leaves the original
    # working factor exactly as it was, and a password-only session can no
    # longer make the account appear unenrolled mid-replacement.
    pending_mfa_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pending_mfa_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # BGP-F01: bumped whenever a previously-issued session token must stop
    # working -- a new factor becomes active (app/routers/mfa.py:verify) or
    # recovery resets one (app/routers/mfa.py:recover). app/deps.py's
    # get_current_user compares this against the value embedded in the
    # session cookie at issuance; a mismatch means the session predates the
    # security change and is rejected, not silently honoured.
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user")
    recovery_codes: Mapped[list["MfaRecoveryCode"]] = relationship(back_populates="user")


class Membership(Base):
    """REQ-001, REQ-003: explicit organisation membership required before
    project access; tenant resolved from session, membership re-verified."""

    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uq_membership_tenant_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="memberships")


class Invitation(Base):
    """REQ-038: invitation landing as part of the essential task journey."""

    __tablename__ = "invitations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    tenant: Mapped["Tenant"] = relationship(back_populates="invitations")


class MfaRecoveryCode(Base):
    """REQ-002: verified recovery without elevating rights -- one-time codes,
    each usable once, consuming a code forces MFA re-enrolment."""

    __tablename__ = "mfa_recovery_codes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="recovery_codes")


class SecurityLogEvent(Base):
    """WP12/REQ-047: 'maintain security logs with minimised personal data
    and defined retention.' A global identity-level log, like `users` and
    `mfa_recovery_codes` (WP04's own migration: 'global identities, not
    tenant-owned rows') -- login/register/MFA events happen before any
    tenant is selected (this app's session model resolves tenant per
    request from the URL, re-verified against membership, REQ-003; login
    itself is tenant-agnostic), so there is no tenant_id to scope RLS on.
    Access is enforced at the application layer instead: every read path
    filters to the requesting user's own user_id (own-data only, REQ-031),
    never exposed to a tenant administrator or anyone else in this pass --
    see app/routers/auth.py's security-log endpoint. `detail` deliberately
    excludes password/code values, only ever recording outcome and a
    minimal identifier (email), per 'minimised personal data'. Retention
    is not automatically enforced (no scheduler exists yet, a gap named
    since WP01) -- see docs/wp02/data_retention_policy.md's already-drafted
    proposed floors."""

    __tablename__ = "security_log_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Template(Base):
    """REQ-010/011/012: a versioned framework template. tenant_id is NULL
    for platform-provided neutral starters (REQ-014), visible to every
    tenant as a fork source; non-NULL for a tenant's own authored/forked
    template, visible only to that tenant."""

    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Provenance only, not a DB-enforced FK: a hard FK to template_versions
    # would make templates/template_versions mutually referential, which
    # complicates table creation order for no real benefit at this scale.
    forked_from_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # BGP-F04 (canonical docstring for this pattern, repeated on every
    # exportable live-recreated table -- TemplateVersion, Project,
    # GateOccurrence, EvidenceItem): NULL for a row created natively in
    # this tenant (its own `id` IS its stable source id). Set on import to
    # the ARCHIVE's original id, which never changes again on a later
    # re-export even though `id` here is always freshly generated at
    # import time (app/routers/exports.py's commit_import never reuses an
    # archive's ids, REQ-030's own 'clean instance' requirement). Every
    # export reads `source_id or id` for this field so a re-exported
    # archive keeps pointing at the SAME original record across an
    # unbounded chain of export -> import -> export hops -- the 'stable
    # mapping' BGP-F04's required correction asks for, closing 'regenerated
    # local IDs alone must not hide missing data' (verification point 3).
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    versions: Mapped[list["TemplateVersion"]] = relationship(back_populates="template")


class TemplateVersion(Base):
    """REQ-011: published versions are immutable (enforced in
    app/routers/templates.py, not by a DB trigger, in this prototype) and
    each project binds to exactly one version."""

    __tablename__ = "template_versions"
    __table_args__ = (UniqueConstraint("template_id", "version_number", name="uq_template_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    template_id: Mapped[str] = mapped_column(String(36), ForeignKey("templates.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    schema_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # Nullable: platform starter versions are seeded administratively (see
    # scripts/seed_starter_frameworks.py), attributed to no real user row.
    created_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # BGP-F04: see Template.source_id's docstring -- same pattern.
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    template: Mapped["Template"] = relationship(back_populates="versions")


class TenantAccessEvent(Base):
    """REQ-005: record and show tenant-administrator access to projects
    outside their membership, visible to the sponsor."""

    __tablename__ = "tenant_access_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    project_ref: Mapped[str] = mapped_column(String(200), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Project(Base):
    """REQ-015: a project binds a tenant to one immutable template version
    and a class declared by that version's schema. class_id/template_version_id
    are not DB-enforced against the schema's own declared classes (SQLite
    test runs have no cross-table CHECK support) -- app/routers/projects.py
    validates this at creation time instead."""

    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    template_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("template_versions.id"), nullable=False)
    class_id: Mapped[str] = mapped_column(String(100), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    # BGP-F04: see Template.source_id's docstring -- same pattern.
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ProjectMembership(Base):
    """REQ-015: explicit project members, each carrying a Blueprint Sec.2
    role -- separate from (though usually drawn from) the user's tenant-wide
    Membership.role, since a user's authority can differ per project."""

    __tablename__ = "project_memberships"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_membership_project_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class GateOccurrence(Base):
    """REQ-016: one row per routine or triggered gate review. sequence is
    per (project_id, gate_id) -- the second routine review of the same gate
    is sequence 2, a triggered review gets its own sequence in the same
    series, so no two occurrences of the same gate ever collide or share
    evidence."""

    __tablename__ = "gate_occurrences"
    __table_args__ = (
        UniqueConstraint("project_id", "gate_id", "sequence", name="uq_gate_occurrence_project_gate_sequence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    gate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), nullable=False)  # "routine" | "triggered"
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # BGP-F04: see Template.source_id's docstring -- same pattern.
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EvidenceItem(Base):
    """REQ-017: the stable, current-state row for one rule's evidence within
    one gate occurrence. `status`/`owner_user_id`/`due_date`/`completed_date`/
    `reference` here always mirror the latest EvidenceRevision -- they exist
    for fast querying (my-work, listings); EvidenceRevision is the append-only
    history of record. `required` is derived from the rule's blocker_level
    (hard/conditional => required; advisory => not) and drives REQ-018."""

    __tablename__ = "evidence_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    occurrence_id: Mapped[str] = mapped_column(String(36), ForeignKey("gate_occurrences.id"), nullable=False)
    gate_id: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_id: Mapped[str] = mapped_column(String(100), nullable=False)
    evidence_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # WP07 addition: WP06 collapsed blocker_level into the single `required`
    # bool. REQ-022's conditional-approval logic needs the finer distinction
    # back (hard blocks any approval; conditional can be deferred via
    # "Approve with conditions"; advisory never blocks) -- see
    # app/routers/decisions.py.
    blocker_level: Mapped[str] = mapped_column(String(20), nullable=False, default="hard")
    permitted_role_ids: Mapped[list] = mapped_column(JSON, nullable=False)

    status: Mapped[str] = mapped_column(String(30), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latest_revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # BGP-F04: see Template.source_id's docstring -- same pattern.
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class EvidenceRevision(Base):
    """REQ-017/019: one immutable, append-only revision. Never updated or
    deleted after insert -- app/routers/projects.py only ever INSERTs here.
    source_version/source_hash implement REQ-019's "bind to source versions
    or hashes where available"; when both are absent the reference is an
    undisclosed/mutable pointer (the API surfaces this as
    `reference_is_mutable` rather than guessing from the reference string's
    shape, e.g. sniffing for a URL, which would be an unreliable signal)."""

    __tablename__ = "evidence_revisions"
    __table_args__ = (UniqueConstraint("evidence_item_id", "revision_number", name="uq_evidence_revision_item_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    evidence_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence_items.id"), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String(30), nullable=False)
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_version: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)

    actor_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    # BGP-F04 follow-up: same source_id pattern as Template/Project/
    # EvidenceItem/GateOccurrence (see Template.source_id), but for AUTHOR
    # identity rather than the row itself. actor_user_id is always a real,
    # resolvable local user (falls back to the importing user when the
    # archive's actor could not be matched -- app/routers/exports.py's
    # resolve()) because it is a NOT-NULL FK used for referential integrity;
    # it must never be read as "this local user really authored this" once a
    # row has been imported. source_actor_id, set only at import time, is
    # the archive's original actor id and is what re-export must report as
    # the author -- so an unmatched actor's identity survives an export/
    # import/export round trip instead of silently becoming the importer.
    # source_actor_email travels with it (same source_email idea as
    # ImportedActorProvenance) because source_actor_id is not a resolvable
    # local user id -- without the email, re-export could name an author but
    # never let a later import match that identity to a real account.
    source_actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source_actor_email: Mapped[str | None] = mapped_column(String(320), nullable=True)


class ExceptionRecord(Base):
    """REQ-020/021: scoped to exactly one EvidenceItem. `status` transitions
    active -> revoked only (never deleted -- REQ-021 "preserve earlier
    decisions" applies here too: a revoked exception must stay visible as a
    fact of history, not disappear). Validity is never read from `status`
    alone -- app/routers/decisions.py re-checks expires_at against server
    time and re-checks the approving actor still holds an authorising role,
    every time readiness is computed (REQ-020's own point: "a typed status
    alone cannot exclude an item")."""

    __tablename__ = "exception_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    evidence_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence_items.id"), nullable=False)

    reason: Mapped[str] = mapped_column(String(1000), nullable=False)
    safeguards: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    approving_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    owner_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")  # active | revoked
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class DecisionRecord(Base):
    """REQ-023/025: append-only. app/routers/decisions.py never UPDATEs or
    DELETEs a row here -- the bgp_app grant on this table (WP07 migration)
    only includes SELECT and INSERT, so the restriction is enforced at the
    database role level too, not just by which routes happen to exist.
    A correction is a new row with supersedes_decision_id set and a
    mandatory reason; the original row is untouched. manifest_json binds the
    exact evidence-item/revision-number pairs and template_version_id this
    decision was made against (REQ-019/023); reviewed_manifest_digest is
    the freshness token returned by the preview endpoint and re-submitted at
    decision time -- see decisions.py for the staleness check this defends.

    Durability (Decision transaction contract step 7, blueprint Sec.5.4) is
    explicitly NOT implemented beyond an ordinary atomic Postgres commit:
    DEC05 (which of Candidate A/B's acknowledgement semantics to build) is
    still an open decision, not something this pass can resolve on its own
    authority. Do not read a 201 response from this endpoint as satisfying
    DEC05's durability guarantee -- it only proves the local commit
    succeeded."""

    __tablename__ = "decision_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    occurrence_id: Mapped[str] = mapped_column(String(36), ForeignKey("gate_occurrences.id"), nullable=False)

    actor_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(30), nullable=False)
    outcome: Mapped[str] = mapped_column(String(30), nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    reviewed_manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    conditions_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    supersedes_decision_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("decision_records.id"), nullable=True
    )
    reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)  # required by the API when superseding

    # BGP-F02: reviewer_id/note are a denormalised snapshot of the
    # CompensatingReview row named below, copied at decision time for cheap
    # display -- review_id is the actual binding, verified fresh
    # (occurrence, manifest, reviewer independence and authority) every time
    # in app/routers/decisions.py's _check_separation_of_duties. Neither
    # field is ever populated from a client-supplied reviewer name again.
    separation_override_review_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("compensating_reviews.id"), nullable=True
    )
    separation_override_reviewer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    separation_override_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class CompensatingReview(Base):
    """REQ-006/BGP-F02: an actual review action, created from the
    independent reviewer's OWN authenticated, MFA-verified session --
    app/routers/decisions.py's create_compensating_review is the only way
    a row here comes to exist, so `reviewer_user_id` is never a name the
    deciding actor merely typed. `manifest_digest` binds it to the exact
    evidence state the reviewer actually saw at review time; the
    separation-of-duties check re-reads this row at decision-commit time
    and rejects it if the occurrence, the manifest digest, or the
    reviewer's active decision authority no longer match -- a stored row is
    never treated as permanently valid. Never UPDATEd or DELETEd by the
    app (see migration 0010's grant, same SELECT+INSERT-only shape as
    decision_records, REQ-025's precedent)."""

    __tablename__ = "compensating_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    occurrence_id: Mapped[str] = mapped_column(String(36), ForeignKey("gate_occurrences.id"), nullable=False)
    reviewer_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    manifest_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    note: Mapped[str] = mapped_column(String(1000), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class IdempotencyRecord(Base):
    """REQ-024: 'Unique scoped key' = (tenant, actor, operation, key). A
    retried request with the same four values and the same payload replays
    the stored outcome; the same key with a *different* payload is a
    conflict (app/routers/decisions.py), never silently accepted as a second
    write."""

    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("tenant_id", "actor_user_id", "operation", "idempotency_key", name="uq_idempotency_scope"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    actor_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    outcome_status: Mapped[str] = mapped_column(String(20), nullable=False)  # created | denied
    outcome_decision_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("decision_records.id"), nullable=True
    )
    denial_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class AuditEvent(Base):
    """REQ-023 step 6: 'Denied attempts create a separate authorised audit
    event; a rollback must not silently erase the refusal record.' The
    'event digest and independent checkpoint reference' half of blueprint
    Sec.5.2's AuditEvent description is WP08's IntegrityCheckpoint below,
    computed over these rows rather than stored on them directly (a
    checkpoint covers a contiguous range of events, not one event each)."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)
    occurrence_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("gate_occurrences.id"), nullable=True)
    decision_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("decision_records.id"), nullable=True)

    actor_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class IntegrityCheckpoint(Base):
    """REQ-026: 'separately controlled verification material, with defined
    custody'. Each row folds every AuditEvent since the previous checkpoint
    into one sha256 chain digest (see app/integrity.py) and, once written,
    cannot be UPDATEd or DELETEd by ANY role -- not bgp_app, not bgp_owner
    (the table owner). Migration 0006_wp08_integrity.py sets FORCE ROW
    LEVEL SECURITY with only SELECT and INSERT policies defined; Postgres
    denies any command with no matching policy by default, and FORCE makes
    that apply to the table owner too, which ordinary RLS does not.

    Read the limit of this honestly: it stops tampering via UPDATE/DELETE
    DML, including by the owner role. It does NOT stop a sufficiently
    privileged actor (bgp_owner, or any Postgres superuser) from instead
    running `ALTER TABLE ... NO FORCE ROW LEVEL SECURITY`, dropping the
    policy, or dropping the table outright -- DDL rights aren't something
    REVOKE can take from an owner. Blueprint line 704 says this plainly:
    'a stored hash chain alone neither prevents privileged rewriting nor
    proves disaster durability.' Genuine independence from a rogue DBA
    needs verification material with custody OUTSIDE this Postgres
    instance entirely -- a separate system this project has no credentials
    for yet. What this table does prove: tampering by the bgp_app role
    (the one a compromised application or SQL injection would actually
    hold) is both prevented and, for events that predate it, detected by
    the next checkpoint's verification."""

    __tablename__ = "integrity_checkpoints"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)

    from_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)  # exclusive; None = genesis
    to_sequence: Mapped[int] = mapped_column(Integer, nullable=False)  # inclusive
    event_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chain_digest: Mapped[str] = mapped_column(String(64), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class IntegrityIncident(Base):
    """REQ-027: 'Block approval acknowledgements for affected integrity
    failures, preserve evidence and trigger incident handling.' Created by
    app/integrity.py's verify_integrity() when a checkpoint fails to
    re-derive; app/routers/decisions.py denies new decisions on any project
    with an open incident. Ordinary table (not append-only like the
    checkpoint above) -- its whole purpose is the status transition from
    open to resolved, which is a legitimate application-level state change,
    not tamper-evidence material itself."""

    __tablename__ = "integrity_incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), nullable=False)

    detail: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")  # open | resolved
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class ExportJob(Base):
    """REQ-030/031: a complete, open-format export of one tenant's data.
    Synchronous in this prototype (built and returned within one request,
    not queued to the worker the blueprint's own architecture section
    describes -- no worker exists yet, WP01's own scope). `archive_json`
    holds the full archive so GET can re-fetch it later without
    regenerating; `expires_at` is recorded but nothing purges on it yet
    (planned surface)."""

    __tablename__ = "export_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    requested_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="complete")
    format_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    archive_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    archive_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ImportJob(Base):
    """REQ-030: 'lossless clean-instance re-import without privilege
    transfer'. status: quarantined (archive received, not yet checked) ->
    validated (schema/checksums/tenant-binding checked, nothing live yet --
    Blueprint Sec.5.6 'quarantine') -> committed (rows created) | rejected.
    `commit_report` is the round-trip reconciliation TST-030 asks for:
    counts, IDs and digests compared against what validate() found."""

    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    requested_by_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="quarantined")
    archive_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    validation_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    commit_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImportedActorProvenance(Base):
    """REQ-030: 'imported actors do not receive live credentials' /
    Blueprint Sec.5.6: 'Historical actors are mapped to provenance
    records, not silently created as authorised users.' One row per
    distinct source actor in the archive, per import: `matched_local_user_id`
    is set only when the source actor's email matches a real, currently
    active member of the importing tenant (app/routers/exports.py) -- never
    invented, never granted new access by the act of matching."""

    __tablename__ = "imported_actor_provenance"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    import_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("import_jobs.id"), nullable=False)
    source_actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    matched_local_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ImportedHistoricalRecord(Base):
    """BGP-F04: decisions, exceptions, audit events, integrity receipts and
    compensating reviews from an imported archive are NOT recreated as live
    rows (app/routers/exports.py's module docstring already explains why --
    Blueprint Sec.5.6's warning against reconstructing an unattributed
    historical record as if it were a verified local approval, and several
    of those tables have NOT NULL actor columns an unmatched historical
    actor cannot honestly satisfy). Before this fix they were simply
    dropped on import -- present in the archive that was imported, gone
    from every export the importing tenant ever makes again. This table is
    where they go instead: one row per historical record, read-only,
    keyed by (tenant_id, kind, source_id) so re-importing the same archive
    twice cannot duplicate it. `payload_json` is the same shape
    app/routers/exports.py already puts in an archive's `decisions` /
    `exceptions` / `audit` / `integrity_receipts` / `compensating_reviews`
    sections, with only the LIVE-row references inside it (project_id,
    occurrence_id, evidence_item_id) remapped to this instance's regenerated
    ids -- `id`/`source_id` and any decision-to-decision or decision-to-
    review links stay exactly as first exported, forever, which is what
    lets a later export of THIS tenant reproduce the identical content a
    caller can reconcile against the original (BGP-F04 verification point
    3: 'regenerated local IDs alone must not hide missing data'). Nothing
    here confers login or approval rights -- it is inert JSON no
    authorization check ever reads."""

    __tablename__ = "imported_historical_records"
    __table_args__ = (UniqueConstraint("tenant_id", "kind", "source_id", name="uq_imported_historical_record"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    import_job_id: Mapped[str] = mapped_column(String(36), ForeignKey("import_jobs.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(36), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class Draft(Base):
    """WP10/REQ-034: 'Save and resume drafts with truthful Saving, Saved
    and Not saved states.' The truthful-state UI behaviour itself is a
    frontend concern (none exists yet, DEC04) -- what this table gives a
    future frontend to build that on: a reliable, optimistically-concurrent
    save/resume primitive. `draft_key` is caller-chosen and owner-scoped
    (never shared between users, even in the same tenant -- Blueprint
    Sec.5.2: 'Owner scoped'), e.g. 'evidence:{item_id}' or 'project:new'.
    'Draft is not a decision; jobs require fresh authorisation' (Blueprint
    Sec.5.2) -- saving or resuming a draft never bypasses the real
    authorization check at actual-submission time; nothing here is ever
    read by any other endpoint."""

    __tablename__ = "drafts"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "draft_key", name="uq_draft_scope"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    tenant_id: Mapped[str] = mapped_column(String(36), ForeignKey("tenants.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    draft_key: Mapped[str] = mapped_column(String(200), nullable=False)
    form_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)
