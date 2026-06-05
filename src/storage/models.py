"""SQLAlchemy 2.0 ORM models for the feature store.

Three tables per PRD § 11:
  - user_features            : pre-computed user-level features (offline store)
  - feature_computation_runs : audit log for every batch pipeline run
  - drift_metrics            : per-feature drift detection results
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    UUID,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base — all ORM models inherit from this."""


class UserFeatures(Base):
    """Pre-computed user-level features written by the batch pipeline.

    One row per user_id, overwritten on each pipeline run.
    Mirrors the ``user_features`` table in PRD § 11.
    """

    __tablename__ = "user_features"

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # RFM features
    recency_days: Mapped[int | None] = mapped_column(Integer)
    frequency_count: Mapped[int | None] = mapped_column(Integer)
    monetary_total: Mapped[float | None] = mapped_column(Numeric(12, 2))
    monetary_avg_per_purchase: Mapped[float | None] = mapped_column(Numeric(12, 2))
    monetary_max: Mapped[float | None] = mapped_column(Numeric(12, 2))

    # Behavioral features
    preferred_category: Mapped[str | None] = mapped_column(String(50))
    preferred_device: Mapped[str | None] = mapped_column(String(20))
    preferred_referral: Mapped[str | None] = mapped_column(String(50))
    category_diversity_count: Mapped[int | None] = mapped_column(Integer)
    product_diversity_count: Mapped[int | None] = mapped_column(Integer)

    # Engagement features
    avg_session_duration: Mapped[float | None] = mapped_column(Numeric(6, 2))
    avg_review_score: Mapped[float | None] = mapped_column(Numeric(3, 2))
    total_reviews_given: Mapped[int | None] = mapped_column(Integer)
    positive_review_ratio: Mapped[float | None] = mapped_column(Numeric(4, 3))

    # Temporal features
    days_since_signup: Mapped[int | None] = mapped_column(Integer)
    is_active_30d: Mapped[bool | None] = mapped_column(Boolean)
    purchase_velocity: Mapped[float | None] = mapped_column(Numeric(6, 3))

    # Discount features
    discount_usage_rate: Mapped[float | None] = mapped_column(Numeric(4, 3))
    avg_discount_rate: Mapped[float | None] = mapped_column(Numeric(4, 3))
    total_savings: Mapped[float | None] = mapped_column(Numeric(12, 2))

    # Demographic features (static user info)
    age: Mapped[int | None] = mapped_column(Integer)
    country: Mapped[str | None] = mapped_column(String(50))
    gender: Mapped[str | None] = mapped_column(String(20))

    # Pipeline metadata
    computed_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now()
    )
    feature_version: Mapped[str] = mapped_column(
        String(20), nullable=False, default="v1"
    )

    __table_args__ = (
        Index("idx_user_features_computed_at", "computed_at"),
        Index("idx_user_features_country", "country"),
    )


class FeatureComputationRun(Base):
    """Audit record for a single batch feature computation run.

    Mirrors the ``feature_computation_runs`` table in PRD § 11.
    ``status`` must be one of: 'running', 'success', 'failed'.
    """

    __tablename__ = "feature_computation_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    rows_processed: Mapped[int | None] = mapped_column(Integer)
    feature_version: Mapped[str | None] = mapped_column(String(20))
    error_message: Mapped[str | None] = mapped_column(Text)


class DriftMetric(Base):
    """Result of a single drift-detection check for one feature.

    Mirrors the ``drift_metrics`` table in PRD § 11.
    Reference windows are DATE (not DATETIME) per the DDL spec.
    """

    __tablename__ = "drift_metrics"

    metric_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    feature_name: Mapped[str] = mapped_column(String(100), nullable=False)
    drift_score: Mapped[float] = mapped_column(Numeric(6, 4), nullable=False)
    drift_detected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reference_window_start: Mapped[date | None] = mapped_column(Date)
    reference_window_end: Mapped[date | None] = mapped_column(Date)
    current_window_start: Mapped[date | None] = mapped_column(Date)
    current_window_end: Mapped[date | None] = mapped_column(Date)
    computed_at: Mapped[datetime | None] = mapped_column(
        DateTime, server_default=func.now()
    )
