# Data inventory and classification (Public / Internal / Confidential / Restricted)

**Status: drafted 2026-09-16, not independently reviewed.** See [README.md](README.md). This
closes the specific gap flagged in `TRACKER.md`'s original G1 section (2026-09-15) and tracker
evidence item **G1.06 (id 97)**: "Data model (Sec.5.2) and retention/legal-hold rules (REQ-048)
exist, but no explicit Public/Internal/Confidential/Restricted classification scheme found."

Scope: every table that exists in `backend/app/models.py` as of 2026-09-16 (WP01/WP03/WP04/WP05).
Tables from the blueprint's full data model (§5.2) that aren't built yet are listed separately at
the end as planned surface, not classified — classifying a table that doesn't exist yet would be
guessing at fields that haven't been finalised.

Classification scheme (four levels, as named in the blueprint's own gap description and standard
practice — not separately defined anywhere in the blueprint pack itself, so definitions are
stated here for the first time and need independent confirmation they match KenAddme's intended
meaning):

- **Public** — safe to disclose with no restriction.
- **Internal** — not for external disclosure, but broadly accessible within the platform/tenant.
- **Confidential** — access restricted by role/authority boundary within a tenant.
- **Restricted** — highest sensitivity; compromise has direct security or legal consequence
  (credentials, secrets, audit evidence of access).

## Tables built so far

| Table | Field | Classification | Basis |
| --- | --- | --- | --- |
| `tenants` | `id`, `name`, `created_at` | Internal | Organisation name is not secret but isn't public; visible to members. |
| `users` | `id` | Internal | Opaque identifier, not itself sensitive. |
| `users` | `email` | Confidential | Personal data; login identifier; must not leak cross-tenant (T1.1/T1.5 in the threat model). |
| `users` | `password_hash` | Restricted | Compromise directly enables account takeover, even though bcrypt-hashed. |
| `users` | `mfa_secret` | Restricted | TOTP seed; compromise defeats MFA entirely. Currently stored unencrypted — see threat-model finding in `threat_model_and_privacy_assessment.md` §Privacy assessment. |
| `users` | `mfa_enabled`, `verified` | Internal | Status flags, not sensitive on their own. |
| `memberships` | `role`, `active` | Internal | Authorisation-relevant but not confidential data in itself; who-has-what-role is normal tenant-admin-visible information. |
| `memberships` | `tenant_id`, `user_id` (as a pair) | Confidential | The linkage itself (who belongs to which org) can be sensitive depending on tenant; protected by RLS regardless. |
| `invitations` | `email` | Confidential | Personal data, same basis as `users.email`; additionally exposed pre-acceptance to whoever holds the invite link. |
| `invitations` | `token_hash` | Restricted | Possession of the underlying token grants membership; hash compromise (if reversible) would too. |
| `mfa_recovery_codes` | `code_hash`, `used_at` | Restricted | Recovery codes are an MFA-bypass mechanism by design; compromise has the same consequence as `mfa_secret` compromise. |
| `templates` / `template_versions` | `schema_json` | Internal (tenant's own) / Public (platform starters, `tenant_id IS NULL`) | Rule content is business logic a tenant may consider proprietary once authored; platform-provided neutral starters (REQ-014) are meant to be visible to every tenant, so they're Public. |
| `templates` / `template_versions` | `created_by_user_id` | Confidential | Personal-data linkage (which user authored/published a version). |
| `tenant_access_events` | `actor_user_id`, `project_ref` | Confidential | Audit trail of administrator access outside normal membership (REQ-005) — sensitive precisely because it documents who accessed what and when. |

## Cross-cutting note

Every **Confidential** or **Restricted** row above that carries a `tenant_id` (directly or via a
foreign key) is already covered by the RLS enforcement verified in
`backend/tests/test_tenant_isolation_rls.py` (WP04). Classification here documents *sensitivity*;
tenant isolation is a separate, already-tested control for cross-tenant exposure specifically.
Classification additionally implies **within-tenant** access rules (e.g. `mfa_secret` should not
be readable by a fellow tenant member just because RLS lets them see other rows on `users`) —
whether current route-level authorization actually enforces that distinction has **not been
checked as part of this document** and should be verified separately (ties to G2.07 "Security
design: authentication, authorisation..." — still Not started in the tracker).

## Planned surface (not built, not classified here)

`Project`/`ProjectMembership`, `Template`'s `GateDefinition`/`ArtefactRule`, `GateOccurrence`,
`EvidenceItem`/`EvidenceRevision`, `ExceptionRecord`, `DecisionRecord`/`Manifest`, `AuditEvent`/
`Checkpoint`, `IdempotencyRecord`, `Draft`/`ExportJob`/`ImportJob`, `AttachmentVersion` (blueprint
§5.2, scheduled WP06-WP09/WP14). This inventory should be re-run — not just appended to — once
each of those tables has real column definitions to classify, since guessing field-level
sensitivity ahead of the actual schema would be exactly the kind of unverifiable claim this
project's governance discipline exists to prevent.
