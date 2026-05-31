"""Shared pytest fixtures for the Feature Store MVP test suite.

Fixtures defined here are available to all tests without explicit import.
Add test-wide shared state, sample DataFrames, and path helpers here.
"""

from collections.abc import Iterator
from pathlib import Path

import fakeredis
import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from src.storage.models import Base

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_CSV = FIXTURES_DIR / "sample_data.csv"


@pytest.fixture
def offline_engine() -> Iterator[Engine]:
    """In-memory SQLite engine with the feature-store schema created.

    Uses StaticPool so all connections share one database. Tables are empty;
    each test seeds the rows it needs.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def fake_redis_client() -> fakeredis.FakeRedis:
    """A fresh, isolated in-memory Redis client."""
    return fakeredis.FakeRedis()


@pytest.fixture
def sample_csv_path() -> Path:
    """Return the path to the 10-row sample CSV fixture."""
    return SAMPLE_CSV


@pytest.fixture
def sample_df() -> pd.DataFrame:
    """Return the 10-row sample DataFrame loaded from the fixture CSV.

    Uses the raw (uncleaned) CSV — individual tests decide whether to
    call ``clean_transactions`` on top of this.
    """
    return pd.read_csv(SAMPLE_CSV)
