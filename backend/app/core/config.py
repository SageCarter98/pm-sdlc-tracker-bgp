from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """WP01 placeholder settings. Session mechanism, pinned frontend and
    hosting region are DEC04/DEC02 and remain undecided — do not treat these
    defaults as approved production configuration."""

    model_config = SettingsConfigDict(env_prefix="BGP_", env_file=".env")

    environment: str = "local-synthetic"

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


settings = Settings()
