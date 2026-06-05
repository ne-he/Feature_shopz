"""Initial database setup and ingestion validation script.

Workflow:
  1. Create all PostgreSQL tables (if they don't exist yet).
  2. Load and clean the raw CSV.
  3. Save the cleaned DataFrame to data/processed/ as Parquet.

This script does NOT compute features (that is Milestone 2 scope).
It proves the foundation is wired together end-to-end.

Usage (from project root, after `make up` brings DB online):
    python scripts/seed_data.py
"""

from pathlib import Path

from loguru import logger
from sqlalchemy import create_engine

from src.config import settings
from src.ingestion.cleaner import clean_transactions
from src.ingestion.loader import load_transactions
from src.storage.models import Base

RAW_DATA_PATH = Path("data/raw/ecommerce_synthetic_dataset.csv")
PROCESSED_DATA_PATH = Path("data/processed/transactions_clean.parquet")


def init_database() -> None:
    """Create all ORM-declared tables in PostgreSQL (idempotent).

    Uses SQLAlchemy's ``create_all`` with ``checkfirst=True`` semantics,
    so running the script multiple times is safe.
    """
    engine = create_engine(settings.postgres_url, echo=False)
    Base.metadata.create_all(engine)
    logger.info("Database tables created / verified OK")


def run_ingestion() -> None:
    """Load the raw CSV, apply cleaning, and persist processed output.

    Raises:
        FileNotFoundError: If the raw CSV is missing from data/raw/.
    """
    df_raw = load_transactions(RAW_DATA_PATH)
    df_clean = clean_transactions(df_raw)
    PROCESSED_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_parquet(PROCESSED_DATA_PATH, index=False)
    logger.info(
        "Saved {:,} clean rows → {}",
        len(df_clean),
        PROCESSED_DATA_PATH,
    )


def main() -> None:
    """Entry point: initialise the database and run the ingestion pipeline."""
    logger.info("seed_data.py — starting")
    init_database()
    run_ingestion()
    logger.success("Seed complete ✓")


if __name__ == "__main__":
    main()
