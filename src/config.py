"""Application configuration.

Reads environment variables from .env using Pydantic Settings. All modules
import the module-level `settings` singleton rather than constructing their own.
"""

from pydantic import Field
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

    # Logging
    log_level: str = Field(default="INFO")

    # Pipeline
    feature_refresh_cadence_hours: int = Field(default=24)

    @property
    def postgres_url(self) -> str:
        """Construct the synchronous SQLAlchemy / psycopg2 database URL."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        """Construct the Redis connection URL (database 0)."""
        return f"redis://{self.redis_host}:{self.redis_port}/0"


settings = Settings()
