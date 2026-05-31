"""Benchmark the feature pipeline throughput.

Measures load + clean + compute time for the full dataset and reports
users/second. Exits non-zero if the pipeline exceeds the 5-minute SLA.

Usage:
    python scripts/benchmark_pipeline.py
    python scripts/benchmark_pipeline.py --csv path/to/data.csv
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from loguru import logger  # noqa: E402

from src.features.pipeline import run_feature_pipeline  # noqa: E402

_SLA_SECONDS: float = 300.0  # 5-minute SLA per PRD § 12
_DEFAULT_CSV: Path = (
    Path(__file__).parents[1] / "data" / "raw" / "ecommerce_synthetic_dataset.csv"
)


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Benchmark the feature pipeline throughput"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=_DEFAULT_CSV,
        help="Path to raw transactions CSV (default: data/raw/ecommerce_synthetic_dataset.csv)",
    )
    return parser.parse_args()


def run_benchmark(csv_path: Path) -> bool:
    """Run the pipeline and print timing stats.

    Args:
        csv_path: Path to the raw transactions CSV.

    Returns:
        True if pipeline finished within SLA, False otherwise.
    """
    logger.info("Benchmark starting — CSV: {}", csv_path)
    t0 = time.perf_counter()
    result = run_feature_pipeline(csv_path)
    elapsed = time.perf_counter() - t0

    n_users = len(result)
    n_features = result.shape[1] - 3  # subtract user_id, computed_at, feature_version
    throughput = n_users / elapsed if elapsed > 0 else float("inf")

    logger.success(
        "Benchmark complete | {:,} users × {} features | {:.2f}s | {:,.0f} users/sec",
        n_users,
        n_features,
        elapsed,
        throughput,
    )

    within_sla = elapsed <= _SLA_SECONDS
    if within_sla:
        logger.info("SLA OK — {:.1f}s < {:.0f}s limit", elapsed, _SLA_SECONDS)
    else:
        logger.warning(
            "SLA BREACH — {:.1f}s > {:.0f}s limit for {:,} users",
            elapsed,
            _SLA_SECONDS,
            n_users,
        )
    return within_sla


def main() -> None:
    """Entry point."""
    args = _parse_args()
    csv_path: Path = args.csv
    if not csv_path.exists():
        logger.error("CSV not found: {}", csv_path)
        sys.exit(1)
    ok = run_benchmark(csv_path)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
