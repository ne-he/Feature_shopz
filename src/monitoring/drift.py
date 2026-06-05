"""Feature drift detection with Evidently (PRD § 17, M4.2 / M4.3).

Wraps Evidently 0.7.x's ``DataDriftPreset`` to compare a reference feature
distribution against a current one, returning a clean per-feature verdict and
persisting it to the ``drift_metrics`` table. A baseline reference snapshot
(M4.3) is saved to / loaded from ``data/processed/`` as Parquet so successive
runs always have something to compare against.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from evidently import DataDefinition, Dataset, Report
from evidently.presets import DataDriftPreset
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.storage.models import DriftMetric

_META_COLUMNS: frozenset[str] = frozenset({"user_id", "computed_at", "feature_version"})
_VALUE_DRIFT_TYPE: str = "evidently:metric_v2:ValueDrift"
BASELINE_PATH: Path = (
    Path(__file__).parents[2] / "data" / "processed" / "feature_baseline.parquet"
)


class DriftResult(BaseModel):
    """Per-feature drift verdict distilled from an Evidently report."""

    feature_name: str
    drift_score: float
    drift_detected: bool
    method: str
    threshold: float


def _parse_value_drift(metric: dict[str, Any]) -> DriftResult | None:
    """Convert one Evidently ValueDrift metric into a DriftResult.

    Args:
        metric: A single entry from ``snapshot.dict()["metrics"]``.

    Returns:
        A DriftResult, or None if the metric is not a per-column ValueDrift.
        For p-value methods drift means ``score < threshold``; for distance
        methods it means ``score > threshold``.
    """
    config = metric.get("config", {})
    if config.get("type") != _VALUE_DRIFT_TYPE:
        return None
    method = str(config["method"])
    threshold = float(config["threshold"])
    score = float(metric["value"])
    detected = score < threshold if "p_value" in method else score > threshold
    return DriftResult(
        feature_name=str(config["column"]),
        drift_score=round(score, 6),
        drift_detected=detected,
        method=method,
        threshold=threshold,
    )


def run_drift_report(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    columns: list[str] | None = None,
) -> list[DriftResult]:
    """Compare reference vs current feature distributions via Evidently.

    Args:
        reference: Baseline feature DataFrame.
        current: Current feature DataFrame.
        columns: Columns to evaluate; defaults to all shared non-metadata
            columns.

    Returns:
        One DriftResult per evaluated feature.
    """
    cols = columns or [
        c for c in reference.columns if c not in _META_COLUMNS and c in current.columns
    ]
    ref_ds = Dataset.from_pandas(reference[cols], data_definition=DataDefinition())
    cur_ds = Dataset.from_pandas(current[cols], data_definition=DataDefinition())
    snapshot = Report([DataDriftPreset()]).run(cur_ds, ref_ds)
    results = [
        parsed
        for metric in snapshot.dict().get("metrics", [])
        if (parsed := _parse_value_drift(metric)) is not None
    ]
    drifted = sum(r.drift_detected for r in results)
    logger.info("Drift report: {}/{} columns drifted", drifted, len(results))
    return results


def persist_drift_metrics(
    engine: Engine,
    results: list[DriftResult],
    reference_window: tuple[date, date] | None = None,
    current_window: tuple[date, date] | None = None,
) -> int:
    """Insert drift results into the ``drift_metrics`` table.

    Args:
        engine: SQLAlchemy engine for the offline store.
        results: Drift verdicts from ``run_drift_report``.
        reference_window: Optional (start, end) dates of the baseline window.
        current_window: Optional (start, end) dates of the current window.

    Returns:
        The number of rows inserted.
    """
    ref_start, ref_end = reference_window or (None, None)
    cur_start, cur_end = current_window or (None, None)
    rows = [
        DriftMetric(
            feature_name=r.feature_name,
            drift_score=r.drift_score,
            drift_detected=r.drift_detected,
            reference_window_start=ref_start,
            reference_window_end=ref_end,
            current_window_start=cur_start,
            current_window_end=cur_end,
        )
        for r in results
    ]
    with Session(engine) as session:
        session.add_all(rows)
        session.commit()
    logger.success("Persisted {} drift metrics", len(rows))
    return len(rows)


def save_baseline(df: pd.DataFrame, path: Path = BASELINE_PATH) -> Path:
    """Persist a reference feature snapshot to Parquet (M4.3)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    logger.info("Saved drift baseline ({} rows) to {}", len(df), path)
    return path


def load_baseline(path: Path = BASELINE_PATH) -> pd.DataFrame | None:
    """Load the reference feature snapshot, or None if it does not exist."""
    if not path.exists():
        return None
    return pd.read_parquet(path)
