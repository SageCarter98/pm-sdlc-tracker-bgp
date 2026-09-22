import secrets as _secrets

from cryptography.fernet import Fernet
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """WP01 placeholder settings. Session mechanism, pinned frontend and
    hosting region are DEC04/DEC02 and remain undecided — do not treat these
    defaults as approved production configuration."""

    model_config = SettingsConfigDict(env_prefix="BGP_", env_file=".env")

    environment: str = "local-synthetic"

    # WP12/REQ-045: was a hardcoded literal in app/security.py until
    # 2026-09-17 (a real vulnerability -- see docs/wp02/
    # threat_model_and_privacy_assessment.md T1 cross-cutting finding,
    # anyone with read access to the source could forge any session).
    # Set BGP_SESSION_SECRET_KEY in backend/.env for a real deployment
    # where sessions must survive a process restart or span multiple
    # processes/nodes; the random default below is safe for local
    # dev/test (a single process, restarting it just logs everyone out,
    # which is honest -- not the same failure mode as a shared, guessable,
    # source-committed key).
    session_secret_key: str = Field(default_factory=lambda: _secrets.token_urlsafe(32))

    # WP12/REQ-045: 'separately held key material' for encrypting
    # users.mfa_secret at rest (previously stored in cleartext -- also
    # flagged in the threat model's privacy assessment). Deliberately a
    # DIFFERENT env var than the database credentials, so a leaked DB
    # connection string alone is not sufficient to decrypt MFA seeds.
    # Set BGP_MFA_ENCRYPTION_KEY in backend/.env for any deployment where
    # existing encrypted secrets must remain decryptable across restarts;
    # the random per-process default is safe for local dev/test only.
    mfa_encryption_key: str = Field(default_factory=lambda: Fernet.generate_key().decode())

    # Runtime app connection: the restricted role, never the table owner
    # (REQ-007). Set BGP_DATABASE_URL in backend/.env once bgp_app exists.
    database_url: str = "postgresql+psycopg2://bgp_app:CHANGE-ME-APP@localhost:5432/bgp_dev"

    # Migration connection: the owning role, used only by Alembic. Set
    # BGP_MIGRATION_DATABASE_URL in backend/.env once bgp_owner exists.
    migration_database_url: str = "postgresql+psycopg2://bgp_owner:CHANGE-ME-OWNER@localhost:5432/bgp_dev"

    # WP08/REQ-029: BYPASSRLS, read-only role used only by
    # scripts/restore_drill.py's pg_dump step -- bgp_owner (correctly, since
    # 2026-09-17) cannot read tenant-owned rows without a tenant context,
    # which pg_dump has no way to provide per-row. Never used by the running
    # application. Set BGP_BACKUP_DATABASE_URL in backend/.env once
    # bgp_backup exists.
    backup_database_url: str = "postgresql+psycopg2://bgp_backup:CHANGE-ME-BACKUP@localhost:5432/bgp_dev"

    # WP15 Phase 1 (FE-097/098): local-disk root for uploaded evidence
    # attachments -- deliberately not object storage; nothing else in this
    # stack uses it yet, and the app is still local-prototype/synthetic-data
    # stage. Set BGP_ATTACHMENT_STORAGE_ROOT for a real deployment; a
    # relative default is fine for local dev (created on first use).
    attachment_storage_root: str = "./var/attachments"

    # Not an approved numeric budget (no DEC has set one, same honest gap
    # as DEC08's performance numbers) -- a conservative placeholder so
    # Phase 1 has SOME bound rather than none. Set
    # BGP_ATTACHMENT_MAX_SIZE_BYTES to override; revisit once a real limit
    # is actually decided.
    attachment_max_size_bytes: int = 20 * 1024 * 1024

    # WP15 Phase 2 (FE-097): Cloudmersive Virus Scan API key. Chosen over
    # VirusTotal specifically because VirusTotal's standard API shares
    # submitted files with a multi-vendor corpus -- a poor fit for a
    # platform built around not letting tenant data cross boundaries it
    # shouldn't. Empty string means "no scanner configured" -- every
    # attachment stays scan_status="unavailable" and permanently
    # undownloadable, same as Phase 1, never silently treated as safe. Set
    # BGP_CLOUDMERSIVE_API_KEY in backend/.env (never commit the real key).
    cloudmersive_api_key: str = ""


settings = Settings()
