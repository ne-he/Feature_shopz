"""Initial database schema — all three feature store tables.

Revision ID: 001
Revises:
Create Date: 2026-05-17
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def _create_user_features() -> None:
    """Create the user_features table (one row per user, all feature groups)."""
    op.create_table(
        "user_features",
        sa.Column("user_id", sa.Integer(), primary_key=True, nullable=False),
        # RFM
        sa.Column("recency_days", sa.Integer()),
        sa.Column("frequency_count", sa.Integer()),
        sa.Column("monetary_total", sa.Numeric(12, 2)),
        sa.Column("monetary_avg_per_purchase", sa.Numeric(12, 2)),
        sa.Column("monetary_max", sa.Numeric(12, 2)),
        # Behavioral
        sa.Column("preferred_category", sa.String(50)),
        sa.Column("preferred_device", sa.String(20)),
        sa.Column("preferred_referral", sa.String(50)),
        sa.Column("category_diversity_count", sa.Integer()),
        sa.Column("product_diversity_count", sa.Integer()),
        # Engagement
        sa.Column("avg_session_duration", sa.Numeric(6, 2)),
        sa.Column("avg_review_score", sa.Numeric(3, 2)),
        sa.Column("total_reviews_given", sa.Integer()),
        sa.Column("positive_review_ratio", sa.Numeric(4, 3)),
        # Temporal
        sa.Column("days_since_signup", sa.Integer()),
        sa.Column("is_active_30d", sa.Boolean()),
        sa.Column("purchase_velocity", sa.Numeric(6, 3)),
        # Discount
        sa.Column("discount_usage_rate", sa.Numeric(4, 3)),
        sa.Column("avg_discount_rate", sa.Numeric(4, 3)),
        sa.Column("total_savings", sa.Numeric(12, 2)),
        # Demographics
        sa.Column("age", sa.Integer()),
        sa.Column("country", sa.String(50)),
        sa.Column("gender", sa.String(20)),
        # Metadata
        sa.Column("computed_at", sa.DateTime(), server_default=sa.text("NOW()")),
        sa.Column("feature_version", sa.String(20), nullable=False, server_default="v1"),
    )
    op.create_index("idx_user_features_computed_at", "user_features", ["computed_at"])
    op.create_index("idx_user_features_country", "user_features", ["country"])


def _create_feature_computation_runs() -> None:
    """Create the audit log table for batch pipeline runs."""
    op.create_table(
        "feature_computation_runs",
        sa.Column(
            "run_id",
            sa.UUID(),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("rows_processed", sa.Integer()),
        sa.Column("feature_version", sa.String(20)),
        sa.Column("error_message", sa.Text()),
    )


def _create_drift_metrics() -> None:
    """Create the drift detection results table."""
    op.create_table(
        "drift_metrics",
        sa.Column("metric_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("feature_name", sa.String(100), nullable=False),
        sa.Column("drift_score", sa.Numeric(6, 4), nullable=False),
        sa.Column("drift_detected", sa.Boolean(), nullable=False),
        sa.Column("reference_window_start", sa.Date()),
        sa.Column("reference_window_end", sa.Date()),
        sa.Column("current_window_start", sa.Date()),
        sa.Column("current_window_end", sa.Date()),
        sa.Column("computed_at", sa.DateTime(), server_default=sa.text("NOW()")),
    )


def upgrade() -> None:
    """Create all feature store tables."""
    _create_user_features()
    _create_feature_computation_runs()
    _create_drift_metrics()


def downgrade() -> None:
    """Drop all feature store tables in reverse dependency order."""
    op.drop_table("drift_metrics")
    op.drop_table("feature_computation_runs")
    op.drop_table("user_features")
