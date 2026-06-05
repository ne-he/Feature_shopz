"""Application configuration.

Reads environment variables from .env using Pydantic Settings. All modules
import the module-level `settings` singleton rather than constructing their own.
"""

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised config loaded from environment variables (with .env fallback)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # PostgreSQL — offline feature store
    postgres_host: str = Field(default="localhost")
    postgres_port: int = Field(default=5432)
    postgres_user: str = Field(default="feature_store")
    postgres_password: str = Field(default="changeme")
    postgres_db: str = Field(default="feature_store")

    # Redis — online feature store
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379)

    # Full-URL overrides. Managed hosts (e.g. Render) expose a single
    # connection string rather than discrete components. When set, these take
    # precedence over the host/port fields above; unset (the default) keeps the
    # local component-based behavior unchanged.
    database_url: str | None = Field(default=None)
    redis_dsn: str | None = Field(
        default=None, validation_alias=AliasChoices("REDIS_URL", "redis_dsn")
    )

    # Logging
    log_level: str = Field(default="INFO")

    # Pipeline
    feature_refresh_cadence_hours: int = Field(default=24)

    @property
    def postgres_url(self) -> str:
        """Construct the synchronous SQLAlchemy / psycopg2 database URL.

        When ``database_url`` is set (e.g. Render's connection string), it is
        used directly with the scheme normalised to the psycopg2 driver;
        otherwise the URL is built from the discrete components.
        """
        if self.database_url:
            url = self.database_url
            for prefix in ("postgresql+psycopg2://", "postgresql://", "postgres://"):
                if url.startswith(prefix):
                    return "postgresql+psycopg2://" + url[len(prefix) :]
            return url
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Construct the Redis connection URL (database 0).

        Uses ``redis_dsn`` (env ``REDIS_URL``) verbatim when set — supporting
        managed stores that require auth/TLS (``rediss://``) — otherwise builds
        the URL from host + port.
        """
        if self.redis_dsn:
            return self.redis_dsn
        return f"redis://{self.redis_host}:{self.redis_port}/0"


settings = Settings()
