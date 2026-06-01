"""Run the full app + frontend with seeded in-memory stores — no Docker needed.

Builds the FastAPI app, points its store dependencies at an in-memory SQLite
offline store and a fakeredis online store seeded with sample users, then
serves the API *and* the static showcase page at http://localhost:8000. Lets
anyone demo the page end to end without PostgreSQL or Redis running.

Usage:
    python scripts/demo_server.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

import pandas as pd  # noqa: E402
import uvicorn  # noqa: E402
from loguru import logger  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from src.api.dependencies import get_engine, get_redis  # noqa: E402
from src.api.main import create_app  # noqa: E402
from src.storage.models import Base, UserFeatures  # noqa: E402
from src.storage.online_store import write_features_batch  # noqa: E402

_NOW = datetime(2026, 5, 31, 3, 0, 0)
_CATEGORIES = ["Electronics", "Apparel", "Books", "Accessories"]
_DEVICES = ["Mobile", "Desktop", "Tablet"]
_REFERRALS = ["Organic Search", "Ad Campaign", "Email Marketing", "Social Media"]
_COUNTRIES = ["USA", "Canada", "UK", "Australia", "India", "Germany"]
_GENDERS = ["Male", "Female", "Non-Binary"]


def _feature_row(uid: int) -> dict[str, object]:
    """Build a deterministic, plausible 23-feature row for a demo user."""
    return {
        "user_id": uid,
        "recency_days": uid % 30,
        "frequency_count": 5 + uid % 40,
        "monetary_total": round(100 + uid * 13.37, 2),
        "monetary_avg_per_purchase": round(20 + uid % 90, 2),
        "monetary_max": round(50 + uid * 7.5, 2),
        "preferred_category": _CATEGORIES[uid % 4],
        "preferred_device": _DEVICES[uid % 3],
        "preferred_referral": _REFERRALS[uid % 4],
        "category_diversity_count": 1 + uid % 4,
        "product_diversity_count": 1 + uid % 7,
        "avg_session_duration": round(5 + uid % 115, 2),
        "avg_review_score": round(1 + (uid % 40) / 10, 2),
        "total_reviews_given": uid % 25,
        "positive_review_ratio": round((uid % 100) / 100, 3),
        "days_since_signup": 30 + uid % 900,
        "is_active_30d": uid % 2 == 0,
        "purchase_velocity": round((uid % 50) / 10, 3),
        "discount_usage_rate": round((uid % 100) / 100, 3),
        "avg_discount_rate": round((uid % 50) / 100, 3),
        "total_savings": round(uid * 2.5, 2),
        "age": 18 + uid % 52,
        "country": _COUNTRIES[uid % 6],
        "gender": _GENDERS[uid % 3],
        "computed_at": _NOW,
        "feature_version": "v1",
    }


def _seed(engine: Engine, redis_client: object) -> int:
    """Create the schema and seed sample users into both stores.

    Returns:
        The number of users seeded.
    """
    user_ids = list(range(1, 201)) + [12345]
    rows = [_feature_row(uid) for uid in user_ids]
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add_all(UserFeatures(**row) for row in rows)
        session.commit()
    write_features_batch(redis_client, pd.DataFrame(rows))  # type: ignore[arg-type]
    return len(rows)


def main() -> None:
    """Seed in-memory stores and serve the app + frontend on :8000."""
    import fakeredis  # local import: dev-only dependency

    app = create_app()
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    redis_client = fakeredis.FakeRedis()
    seeded = _seed(engine, redis_client)
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_redis] = lambda: redis_client
    logger.success("Seeded {} demo users — serving on http://localhost:8000", seeded)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")


if __name__ == "__main__":
    main()
