from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """WP01 placeholder settings. Session mechanism, pinned frontend and
    hosting region are DEC04/DEC02 and remain undecided — do not treat these
    defaults as approved production configuration."""

    model_config = SettingsConfigDict(env_prefix="BGP_", env_file=".env")

    environment: str = "local-synthetic"
    database_url: str = "postgresql+psycopg2://localhost:5432/bgp_dev"


settings = Settings()
