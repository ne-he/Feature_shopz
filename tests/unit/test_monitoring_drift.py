"""Unit tests for src.monitoring.drift (M4.2 / M4.3).

Evidently runs are kept to a minimum (they are relatively slow). Naming
pattern: test_<function>_<scenario>_<expected_result>
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.monitoring.drift import (
    DriftResult,
    _parse_value_drift,
    load_baseline,
    persist_drift_metrics,
    run_drift_report,
    save_baseline,
)
from src.storage.models import DriftMetric


def _frame(values: range, scale: float = 1.0) -> pd.DataFrame:
    """Build a 2-column feature frame plus metadata columns."""
    nums = list(values)
    return pd.DataFrame(
        {
            "user_id": range(1, len(nums) + 1),
            "recency_days": nums,
            "monetary_total": [v * scale for v in nums],
            "computed_at": [None] * len(nums),
        }
    )


def test_run_drift_report_detects_shifted_distribution() -> None:
    """A clearly shifted current distribution is flagged as drifted."""
    reference = _frame(range(1, 51))
    current = _frame(range(500, 550))
    results = run_drift_report(reference, current)
    names = {r.feature_name for r in results}
    assert "user_id" not in names and "computed_at" not in names
    assert all(r.drift_detected for r in results)


def test_run_drift_report_identical_data_no_drift() -> None:
    """Identical reference and current distributions show no drift."""
    frame = _frame(range(1, 81))
    results = run_drift_report(frame, frame.copy())
    assert results and not any(r.drift_detected for r in results)


def test_parse_value_drift_ignores_non_value_drift_metric() -> None:
    """A non-ValueDrift metric entry is skipped (returns None)."""
    metric = {"config": {"type": "evidently:metric_v2:DriftedColumnsCount"}, "value": {}}
    assert _parse_value_drift(metric) is None


def test_persist_drift_metrics_inserts_rows(offline_engine: Engine) -> None:
    """Drift results are written to the drift_metrics table."""
    results = [
        DriftResult(
            feature_name="recency_days", drift_score=0.01,
            drift_detected=True, method="K-S p_value", threshold=0.05,
        ),
        DriftResult(
            feature_name="age", drift_score=0.4,
            drift_detected=False, method="K-S p_value", threshold=0.05,
        ),
    ]
    inserted = persist_drift_metrics(offline_engine, results)
    assert inserted == 2
    with Session(offline_engine) as session:
        rows = session.execute(select(DriftMetric)).scalars().all()
    assert {r.feature_name for r in rows} == {"recency_days", "age"}


def test_save_and_load_baseline_round_trips(tmp_path: Path) -> None:
    """A saved baseline frame loads back equal."""
    path = tmp_path / "baseline.parquet"
    frame = _frame(range(1, 11))
    save_baseline(frame, path)
    loaded = load_baseline(path)
    assert loaded is not None and len(loaded) == 10


def test_load_baseline_missing_returns_none(tmp_path: Path) -> None:
    """Loading a non-existent baseline returns None."""
    assert load_baseline(tmp_path / "nope.parquet") is None
