"""Streamlit monitoring dashboard (PRD § 17, M4.4).

Four pages over the live offline (PostgreSQL) and online (Redis) stores:
  - Overview      : health + freshness + store counts.
  - Catalog       : searchable table of registered features.
  - Distributions : per-feature histogram + summary stats.
  - Drift         : Evidently drift verdict of current vs the saved baseline.

Run with: ``streamlit run src/dashboard/app.py``.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from redis import Redis
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from src.config import settings
from src.features import (  # noqa: F401 -- imported to populate REGISTRY on load
    behavior,
    demographics,
    discount,
    engagement,
    rfm,
    temporal,
)
from src.features.definitions import REGISTRY
from src.monitoring.drift import load_baseline, run_drift_report
from src.monitoring.freshness import build_freshness_report
from src.monitoring.metrics import (
    count_offline_users,
    count_online_keys,
    load_feature_frame,
)
from src.storage.online_store import get_redis_client


@st.cache_resource
def _get_engine() -> Engine:
    """Return a cached SQLAlchemy engine for the offline store."""
    return create_engine(settings.postgres_url, pool_pre_ping=True)


@st.cache_resource
def _get_redis() -> Redis:
    """Return a cached Redis client for the online store."""
    return get_redis_client()


def render_overview(engine: Engine, redis_client: Redis) -> None:
    """Render the system-overview page: store counts + freshness."""
    st.header("System Overview")
    fresh = build_freshness_report(engine, redis_client)
    col1, col2, col3 = st.columns(3)
    col1.metric("Users (offline)", count_offline_users(engine))
    col2.metric("Keys (online)", count_online_keys(redis_client))
    col3.metric("Freshness", "🟢 fresh" if fresh.is_fresh else "🔴 stale")
    st.write({
        "last_computed_at": str(fresh.last_computed_at),
        "age_hours": fresh.age_hours,
        "cadence_hours": fresh.cadence_hours,
        "last_sync_at": str(fresh.last_sync_at),
    })


def render_catalog() -> None:
    """Render the searchable feature catalog from the registry."""
    st.header("Feature Catalog")
    frame = pd.DataFrame(
        {
            "name": d.name, "description": d.description, "data_type": d.data_type,
            "owner": d.owner, "refresh_cadence": d.refresh_cadence,
        }
        for d in REGISTRY.definitions()
    )
    query = st.text_input("Search by name")
    if query:
        frame = frame[frame["name"].str.contains(query, case=False)]
    st.dataframe(frame, width="stretch")


def render_distributions(engine: Engine) -> None:
    """Render a histogram + summary stats for a chosen numeric feature."""
    st.header("Feature Distributions")
    frame = load_feature_frame(engine)
    if frame.empty:
        st.warning("No features computed yet.")
        return
    numeric = [c for c in frame.select_dtypes("number").columns if c != "user_id"]
    feature = st.selectbox("Feature", numeric)
    st.plotly_chart(px.histogram(frame, x=feature), width="stretch")
    st.dataframe(frame[feature].describe().to_frame().T)


def render_drift(engine: Engine) -> None:
    """Render the drift verdict of the current features vs the baseline."""
    st.header("Drift Report")
    baseline = load_baseline()
    if baseline is None:
        st.info("No baseline saved yet — save one from a known-good run.")
        return
    current = load_feature_frame(engine)
    if current.empty:
        st.warning("No current features to compare.")
        return
    frame = pd.DataFrame(r.model_dump() for r in run_drift_report(baseline, current))
    drifted = int(frame["drift_detected"].sum()) if not frame.empty else 0
    st.metric("Features drifted", f"{drifted}/{len(frame)}")
    st.dataframe(frame, width="stretch")


def main() -> None:
    """Entry point: page selection + dispatch."""
    st.set_page_config(page_title="Feature Store Monitor", layout="wide")
    st.title("📊 Feature Store — Monitoring")
    engine = _get_engine()
    redis_client = _get_redis()
    page = st.sidebar.radio("Page", ["Overview", "Catalog", "Distributions", "Drift"])
    if page == "Overview":
        render_overview(engine, redis_client)
    elif page == "Catalog":
        render_catalog()
    elif page == "Distributions":
        render_distributions(engine)
    else:
        render_drift(engine)


if __name__ == "__main__":
    main()
