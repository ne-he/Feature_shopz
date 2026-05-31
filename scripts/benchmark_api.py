"""Latency benchmark for the feature-serving API (PRD § 3, M3.11, M3.12).

Fires many requests at the single-user and batch endpoints, computes
p50/p95/p99 latency, and exits non-zero if a p99 target is missed:
single-user < 100ms, batch-of-100 < 500ms.

Two modes:
    --in-process  (default) drives the ASGI app directly with in-memory
                  SQLite + fakeredis stores — no server or Docker required.
                  This measures the pure serving path (no network hop), so
                  it is a lower bound on real latency.
    --base-url    benchmarks a live server backed by real PostgreSQL + Redis.

Usage:
    python scripts/benchmark_api.py
    python scripts/benchmark_api.py --base-url http://localhost:8000
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import httpx  # noqa: E402
import pandas as pd  # noqa: E402
from loguru import logger  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from src.api.dependencies import get_engine, get_redis  # noqa: E402
from src.api.main import create_app  # noqa: E402
from src.storage.models import Base, UserFeatures  # noqa: E402
from src.storage.online_store import write_features_batch  # noqa: E402

_SINGLE_P99_TARGET_MS: float = 100.0
_BATCH_P99_TARGET_MS: float = 500.0
_SEED_USERS: int = 200
_STAMP: datetime = datetime(2026, 5, 17, 3, 0, 0)


def _percentile(values: list[float], pct: float) -> float:
    """Return the nearest-rank percentile (pct in 0..100) of values."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def _seed_offline(engine: object) -> None:
    """Create the schema and seed _SEED_USERS rows into the SQLite store."""
    Base.metadata.create_all(engine)  # type: ignore[arg-type]
    with Session(engine) as session:  # type: ignore[arg-type]
        session.add_all(
            UserFeatures(
                user_id=i, recency_days=i % 30, monetary_total=float(i),
                country="USA", computed_at=_STAMP, feature_version="v1",
            )
            for i in range(1, _SEED_USERS + 1)
        )
        session.commit()


def _seed_online(redis_client: object) -> None:
    """Seed _SEED_USERS feature blobs into the fakeredis online store."""
    df = pd.DataFrame(
        {
            "user_id": range(1, _SEED_USERS + 1),
            "recency_days": [i % 30 for i in range(1, _SEED_USERS + 1)],
            "monetary_total": [float(i) for i in range(1, _SEED_USERS + 1)],
            "computed_at": [_STAMP] * _SEED_USERS,
            "feature_version": ["v1"] * _SEED_USERS,
        }
    )
    write_features_batch(redis_client, df)  # type: ignore[arg-type]


def _build_in_process_client() -> httpx.Client:
    """Build a client driving the ASGI app in-process with in-memory stores.

    Returns a Starlette TestClient (an ``httpx.Client`` subclass) so the
    sync request API works without a running server; the installed httpx
    only supports ASGI transport asynchronously.
    """
    import fakeredis  # local import: dev-only dependency
    from fastapi.testclient import TestClient  # local import: dev-only dependency

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    _seed_offline(engine)
    redis_client = fakeredis.FakeRedis()
    _seed_online(redis_client)
    app = create_app()
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_redis] = lambda: redis_client
    return TestClient(app)


def _time_request(client: httpx.Client, method: str, url: str, json: object = None) -> float:
    """Issue one request and return its round-trip latency in milliseconds."""
    start = time.perf_counter()
    response = client.request(method, url, json=json)
    response.raise_for_status()
    return (time.perf_counter() - start) * 1000


def _bench_single(client: httpx.Client, n: int) -> list[float]:
    """Time n single-user online lookups, cycling through seeded users."""
    return [
        _time_request(client, "GET", f"/features/online/{(i % _SEED_USERS) + 1}")
        for i in range(n)
    ]


def _bench_batch(client: httpx.Client, n: int, batch_size: int) -> list[float]:
    """Time n batch lookups of ``batch_size`` users each."""
    payload = {"user_ids": list(range(1, batch_size + 1))}
    return [_time_request(client, "POST", "/features/batch", payload) for _ in range(n)]


def _report(name: str, latencies: list[float], target_ms: float) -> bool:
    """Log p50/p95/p99 for a run and return whether p99 met the target."""
    p50, p95, p99 = (_percentile(latencies, p) for p in (50, 95, 99))
    passed = p99 < target_ms
    logger.log(
        "SUCCESS" if passed else "WARNING",
        "{}: n={} | p50={:.2f}ms p95={:.2f}ms p99={:.2f}ms | target p99<{:.0f}ms [{}]",
        name, len(latencies), p50, p95, p99, target_ms, "PASS" if passed else "FAIL",
    )
    return passed


def _parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Benchmark the feature-serving API")
    parser.add_argument("--base-url", default=None, help="Benchmark a live server")
    parser.add_argument("--single-requests", type=int, default=1000)
    parser.add_argument("--batch-requests", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=100)
    return parser.parse_args()


def main() -> None:
    """Entry point: run both benchmarks and exit non-zero on any target miss."""
    args = _parse_args()
    if args.base_url:
        client = httpx.Client(base_url=args.base_url, timeout=30.0)
        logger.info("Benchmarking live server at {}", args.base_url)
    else:
        client = _build_in_process_client()
        logger.info("Benchmarking in-process app ({} seeded users)", _SEED_USERS)
    try:
        _bench_single(client, 50)  # warmup
        single = _bench_single(client, args.single_requests)
        batch = _bench_batch(client, args.batch_requests, args.batch_size)
    finally:
        client.close()
    ok_single = _report("single online lookup", single, _SINGLE_P99_TARGET_MS)
    ok_batch = _report(f"batch-{args.batch_size} lookup", batch, _BATCH_P99_TARGET_MS)
    sys.exit(0 if ok_single and ok_batch else 1)


if __name__ == "__main__":
    main()
