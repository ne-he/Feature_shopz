"""APScheduler wiring for the daily feature refresh (PRD § 13, M4.5).

Builds a BackgroundScheduler with the ``run_refresh_job`` callable registered
on a FEATURE_REFRESH_CADENCE_HOURS interval. APScheduler is used instead of
Prefect because the workload is a single daily batch — see the CLAUDE.md
Decision Log (2026-06-01). The job is also triggerable on demand by calling
``run_refresh_job`` directly.
"""

from __future__ import annotations

from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from loguru import logger

from src.config import settings
from src.orchestration.jobs import run_refresh_job

JOB_ID: str = "daily_feature_refresh"


def build_scheduler(csv_path: str | Path | None = None) -> BackgroundScheduler:
    """Create a scheduler with the daily feature-refresh job registered.

    The scheduler is returned not yet started; the caller decides when to
    ``start()`` it (and ``shutdown()`` on exit).

    Args:
        csv_path: Optional CSV path forwarded to the refresh job.

    Returns:
        A BackgroundScheduler with one interval job (id=JOB_ID) at the
        configured FEATURE_REFRESH_CADENCE_HOURS cadence.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        run_refresh_job,
        trigger=IntervalTrigger(hours=settings.feature_refresh_cadence_hours),
        kwargs={"csv_path": csv_path},
        id=JOB_ID,
        replace_existing=True,
    )
    logger.info(
        "Registered job {!r} every {}h",
        JOB_ID,
        settings.feature_refresh_cadence_hours,
    )
    return scheduler
