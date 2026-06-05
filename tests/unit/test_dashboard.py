"""Smoke tests for src.dashboard.app render functions (M4.4).

Streamlit commands run in "bare" mode here (no script-run context); they
no-op with a warning rather than raising, so these tests exercise the data
logic in each page and confirm the wiring does not crash. UI behaviour itself
is out of scope for unit tests.
"""

from __future__ import annotations

from datetime import datetime

import fakeredis
import pandas as pd
import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.dashboard import app
from src.storage.models import UserFeatures


def _seed(engine: Engine, n: int = 8) -> None:
    """Seed n user_features rows with numeric columns for charts."""
    with Session(engine) as session:
        session.add_all(
            UserFeatures(
                user_id=i, recency_days=i, monetary_total=float(i * 10), age=20 + i,
                computed_at=datetime(2026, 5, 17), feature_version="v1",
            )
            for i in range(1, n + 1)
        )
        session.commit()


def test_render_pages_run_without_error(
    monkeypatch: pytest.MonkeyPatch,
    offline_engine: Engine,
    fake_redis_client: fakeredis.FakeRedis,
) -> None:
    """Catalog, overview, distributions, and (baseline-less) drift all run."""
    _seed(offline_engine)
    monkeypatch.setattr(app, "load_baseline", lambda: None)
    app.render_catalog()
    app.render_overview(offline_engine, fake_redis_client)
    app.render_distributions(offline_engine)
    app.render_drift(offline_engine)  # no baseline -> info branch


def test_render_drift_with_baseline_runs(
    monkeypatch: pytest.MonkeyPatch, offline_engine: Engine
) -> None:
    """With a baseline present, the drift page computes a verdict table."""
    _seed(offline_engine)
    baseline = pd.DataFrame(
        {"user_id": range(1, 9), "recency_days": range(1, 9), "age": range(21, 29)}
    )
    monkeypatch.setattr(app, "load_baseline", lambda: baseline)
    app.render_drift(offline_engine)
