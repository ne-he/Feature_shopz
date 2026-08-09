"""Feature lookup endpoints (PRD § 12).

Four routes:
  - GET  /features/online/{user_id}   Redis-first, PostgreSQL fallback.
  - POST /features/batch              Up to 100 users from the online store.
  - GET  /features/offline/{user_id}  PostgreSQL only (training lookups).
  - GET  /features/metadata           The feature catalog from the REGISTRY.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query, status
from sqlalchemy.exc import SQLAlchemyError

from src.api.dependencies import EngineDep, RedisDep
from src.api.schemas import (
    MAX_USER_ID,
    BatchFeatureRequest,
    BatchFeatureResponse,
    BatchMetadata,
    BatchResultItem,
    FeatureCatalogEntry,
    FeatureMetadataResponse,
    FeatureProvenance,
    FeatureResponse,
    FeatureSource,
)
from src.features.definitions import REGISTRY
from src.storage.offline_store import get_last_computed_at, read_user_features
from src.storage.online_store import get_user_features

router = APIRouter(prefix="/features", tags=["features"])

# Path-parameter constraint shared by the two single-user lookups. Keeping the
# bound at the boundary means an unusable id is a 422, never a store error.
_UserIdPath = Path(ge=1, le=MAX_USER_ID, description="User identifier")

# Stored records carry these alongside feature values; they are surfaced as
# response metadata rather than as features.
_META_KEYS: frozenset[str] = frozenset({"user_id", "computed_at", "feature_version"})


def _parse_feature_list(raw: str | None) -> list[str] | None:
    """Parse a comma-separated ``feature_list`` query string into names.

    Args:
        raw: Comma-separated feature names, or None when not supplied.

    Returns:
        A list of trimmed, non-empty names, or None when no filter is given.
    """
    if raw is None:
        return None
    names = [part.strip() for part in raw.split(",") if part.strip()]
    return names or None


def _split_record(record: dict[str, Any]) -> tuple[dict[str, Any], Any, Any]:
    """Separate feature values from provenance metadata in a stored record.

    Args:
        record: A feature record from Redis (JSON) or PostgreSQL (row dict).

    Returns:
        A tuple of (feature values, computed_at, feature_version).
    """
    features = {key: val for key, val in record.items() if key not in _META_KEYS}
    return features, record.get("computed_at"), record.get("feature_version")


def _filter_features(
    features: dict[str, Any], feature_list: list[str] | None
) -> dict[str, Any]:
    """Restrict a feature dict to the requested names (those present)."""
    if feature_list is None:
        return features
    return {name: features[name] for name in feature_list if name in features}


def _build_response(
    user_id: int,
    record: dict[str, Any],
    source: FeatureSource,
    feature_list: list[str] | None,
) -> FeatureResponse:
    """Assemble a FeatureResponse from a stored record and its source."""
    features, computed_at, feature_version = _split_record(record)
    return FeatureResponse(
        user_id=user_id,
        features=_filter_features(features, feature_list),
        metadata=FeatureProvenance(
            computed_at=computed_at,
            feature_version=feature_version,
            source=source,
        ),
    )


@router.get("/metadata", response_model=FeatureMetadataResponse)
def get_feature_metadata(engine: EngineDep) -> FeatureMetadataResponse:
    """Return the catalog of available features from the registry (M3.8).

    Args:
        engine: Injected SQLAlchemy engine (for the last-computed timestamp).

    Returns:
        Feature definitions, their count, and the newest computed_at.

    Raises:
        HTTPException: 503 if the offline store is unreachable.
    """
    try:
        last_computed = get_last_computed_at(engine)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Offline store unavailable",
        ) from exc
    entries = [
        FeatureCatalogEntry(
            name=defn.name,
            description=defn.description,
            data_type=defn.data_type,
            valid_range=defn.valid_range,
        )
        for defn in REGISTRY.definitions()
    ]
    return FeatureMetadataResponse(
        features=entries,
        total_features=len(entries),
        last_computed_at=last_computed,
    )


@router.get("/online/{user_id}", response_model=FeatureResponse)
def get_online_features(
    engine: EngineDep,
    redis_client: RedisDep,
    user_id: int = _UserIdPath,
    feature_list: str | None = Query(default=None),
) -> FeatureResponse:
    """Fetch a user's features, Redis-first with a PostgreSQL fallback (M3.5).

    Args:
        user_id: User identifier, 1..MAX_USER_ID.
        engine: Injected SQLAlchemy engine (fallback source).
        redis_client: Injected Redis client (primary source).
        feature_list: Optional comma-separated names to restrict the result.

    Returns:
        The user's features and provenance metadata.

    Raises:
        HTTPException: 404 if the user exists in neither store; 503 if the
            offline store errors during fallback.
    """
    requested = _parse_feature_list(feature_list)
    blob = get_user_features(redis_client, user_id)
    if blob is not None:
        return _build_response(user_id, blob, "redis", requested)
    try:
        record = read_user_features(engine, user_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Offline store unavailable",
        ) from exc
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No features found for user {user_id}",
        )
    return _build_response(user_id, record, "postgres", requested)


@router.get("/offline/{user_id}", response_model=FeatureResponse)
def get_offline_features(
    engine: EngineDep,
    user_id: int = _UserIdPath,
) -> FeatureResponse:
    """Fetch a user's features straight from the offline store (M3.7).

    Args:
        user_id: User identifier, 1..MAX_USER_ID.
        engine: Injected SQLAlchemy engine for the offline store.

    Returns:
        The user's features and provenance metadata (source=postgres).

    Raises:
        HTTPException: 404 if the user has no row; 503 if the store errors.
    """
    try:
        record = read_user_features(engine, user_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Offline store unavailable",
        ) from exc
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No features found for user {user_id}",
        )
    return _build_response(user_id, record, "postgres", None)


@router.post("/batch", response_model=BatchFeatureResponse)
def get_batch_features(
    payload: BatchFeatureRequest,
    redis_client: RedisDep,
) -> BatchFeatureResponse:
    """Look up features for many users from the online store (M3.6).

    Args:
        payload: Validated request with ``user_ids`` (1..100) and an optional
            ``feature_list`` filter.
        redis_client: Injected Redis client.

    Returns:
        Per-user results plus aggregate found/missing counts and latency.
    """
    t0 = time.perf_counter()
    results: list[BatchResultItem] = []
    found = 0
    for user_id in payload.user_ids:
        blob = get_user_features(redis_client, user_id)
        if blob is None:
            results.append(BatchResultItem(user_id=user_id, error="not_found"))
            continue
        features, _, _ = _split_record(blob)
        results.append(
            BatchResultItem(
                user_id=user_id,
                features=_filter_features(features, payload.feature_list),
            )
        )
        found += 1
    latency_ms = round((time.perf_counter() - t0) * 1000, 2)
    return BatchFeatureResponse(
        results=results,
        metadata=BatchMetadata(
            found=found,
            missing=len(payload.user_ids) - found,
            latency_ms=latency_ms,
        ),
    )
