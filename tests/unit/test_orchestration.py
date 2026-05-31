"""Unit tests for src.orchestration (M4.5).

The refresh job is tested with its three heavy steps monkeypatched, so no
CSV, PostgreSQL, or Redis is touched. Naming pattern:
test_<function>_<scenario>_<expected_result>
"""

from __future__ import annotations

import fakeredis
import pandas as pd
import pytest
from sqlalchemy.engine import Engine

from src.orchestration import jobs
from src.orchestration.flows import JOB_ID, build_scheduler


def test_run_refresh_job_chains_steps_and_aggregates(
    monkeypatch: pytest.MonkeyPatch,
    offline_engine: Engine,
    fake_redis_client: fakeredis.FakeRedis,
) -> None:
    """The job runs pipeline -> write -> sync and aggregates their stats."""
    calls: list[str] = []
    monkeypatch.setattr(
        jobs, "run_feature_pipeline",
        lambda csv: calls.append("pipeline") or pd.DataFrame({"user_id": [1]}),
    )
    monkeypatch.setattr(
        jobs, "write_features_to_db",
        lambda df, eng: calls.append("write") or {"rows_written": 1, "duration_sec": 0.1},
    )
    monkeypatch.setattr(
        jobs, "sync_offline_to_online",
        lambda eng, rds: calls.append("sync") or {"rows_synced": 1, "duration_sec": 0.2},
    )
    result = jobs.run_refresh_job(
        csv_path="x.csv", engine=offline_engine, redis_client=fake_redis_client
    )
    assert calls == ["pipeline", "write", "sync"]
    assert result == {"rows_written": 1, "rows_synced": 1, "duration_sec": 0.3}


def test_build_scheduler_registers_daily_job() -> None:
    """The scheduler has exactly the daily refresh job registered."""
    scheduler = build_scheduler()
    scheduler.start(paused=True)
    try:
        assert scheduler.get_job(JOB_ID) is not None
    finally:
        scheduler.shutdown(wait=False)
