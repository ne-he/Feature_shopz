"""Feature pipeline orchestrator.

Runs the full batch feature-computation flow: load raw CSV → clean →
group by user → compute every registered feature per user → assemble a
wide feature DataFrame ready for the offline store (PRD § 9, § 11).

Importing the six feature modules below is intentional and required:
each module registers its compute functions into the global REGISTRY as
an import side effect. Without these imports the registry would be empty.
"""

from __future__ import annotations

import inspect
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from loguru import logger

from src.features import (  # noqa: F401 -- imported for REGISTRY registration side effect
    behavior,
    demographics,
    discount,
    engagement,
    rfm,
    temporal,
)
from src.features.definitions import REGISTRY, ComputeFunc, FeatureRegistry
from src.ingestion.cleaner import clean_transactions
from src.ingestion.loader import load_transactions

FEATURE_VERSION: str = "v1"
PROGRESS_INTERVAL: int = 10_000

# A compute function paired with whether it needs a reference_date argument.
ComputePlan = list[tuple[str, ComputeFunc, bool]]


def _resolve_reference_date(df: pd.DataFrame, reference_date: date | None) -> date:
    """Return the explicit reference date, or default to the latest PurchaseDate.

    Args:
        df: Cleaned transactions DataFrame.
        reference_date: Caller-supplied anchor date, or None to auto-derive.

    Returns:
        The date against which temporal features are computed.
    """
    if reference_date is not None:
        return reference_date
    latest_purchase: date = df["PurchaseDate"].max()
    return latest_purchase


def _build_compute_plan(registry: FeatureRegistry) -> ComputePlan:
    """Precompute, once per run, how each registered feature must be called.

    Inspecting each function's signature here (instead of per-user) avoids
    millions of redundant ``inspect`` calls on large datasets.

    Args:
        registry: The feature registry to read definitions from.

    Returns:
        A list of (feature_name, compute_func, needs_reference_date) tuples.
    """
    plan: ComputePlan = []
    for name, registered in registry.all().items():
        params = inspect.signature(registered.compute).parameters
        plan.append((name, registered.compute, "reference_date" in params))
    return plan


def _safe_compute(
    name: str,
    compute: ComputeFunc,
    user_df: pd.DataFrame,
    needs_reference_date: bool,
    reference_date: date,
) -> object:
    """Compute one feature for one user, returning None on failure.

    Args:
        name: Feature name (for logging).
        compute: The feature's compute function.
        user_df: One user's transaction rows.
        needs_reference_date: Whether ``compute`` takes a reference_date arg.
        reference_date: The anchor date for temporal features.

    Returns:
        The computed feature value, or None if computation raised.
    """
    try:
        if needs_reference_date:
            return compute(user_df, reference_date)
        return compute(user_df)
    except Exception as exc:  # noqa: BLE001
        # Resilience boundary: one user's bad data must not abort the batch.
        logger.warning("Feature {!r} failed for a user, imputing null: {}", name, exc)
        return None


def _compute_all_users(
    df: pd.DataFrame, plan: ComputePlan, reference_date: date
) -> list[dict[str, object]]:
    """Compute every planned feature for every user, grouped by UserID.

    Args:
        df: Cleaned transactions DataFrame.
        plan: The compute plan from ``_build_compute_plan``.
        reference_date: The anchor date for temporal features.

    Returns:
        One dict per user: ``{"user_id": ..., <feature>: <value>, ...}``.
    """
    records: list[dict[str, object]] = []
    for index, (user_id, user_df) in enumerate(df.groupby("UserID", sort=True), start=1):
        record: dict[str, object] = {"user_id": int(user_id)}
        for name, compute, needs_ref in plan:
            record[name] = _safe_compute(name, compute, user_df, needs_ref, reference_date)
        records.append(record)
        if index % PROGRESS_INTERVAL == 0:
            logger.info("Processed {:,} users", index)
    return records


def run_feature_pipeline(
    csv_path: str | Path,
    registry: FeatureRegistry = REGISTRY,
    reference_date: date | None = None,
) -> pd.DataFrame:
    """Compute all registered features for every user in the dataset.

    Args:
        csv_path: Path to the raw transactions CSV file.
        registry: Feature registry to compute from (default: global REGISTRY).
        reference_date: Anchor date for temporal features. Defaults to the
            latest PurchaseDate in the dataset when omitted.

    Returns:
        A wide DataFrame with one row per user: ``user_id``, every feature
        column, plus ``computed_at`` and ``feature_version`` metadata.
    """
    raw_df = load_transactions(Path(csv_path))
    clean_df = clean_transactions(raw_df)
    resolved_date = _resolve_reference_date(clean_df, reference_date)
    plan = _build_compute_plan(registry)
    logger.info(
        "Computing {} features for {:,} users (reference_date={})",
        len(plan),
        clean_df["UserID"].nunique(),
        resolved_date,
    )
    records = _compute_all_users(clean_df, plan, resolved_date)
    result = pd.DataFrame.from_records(records)
    result["computed_at"] = datetime.now()
    result["feature_version"] = FEATURE_VERSION
    logger.success("Pipeline complete: {:,} users × {} features", len(result), len(plan))
    return result
