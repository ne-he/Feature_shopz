"""Pydantic v2 request/response schemas for the feature-serving API.

These models define the JSON contract for every endpoint in PRD § 12:
single online lookup, batch lookup, offline lookup, the feature metadata
catalog, and the health check. They are intentionally decoupled from the
storage-layer representations so the API surface can evolve independently.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

MAX_BATCH_USERS: int = 100
"""Maximum number of user_ids accepted in a single batch request (PRD § 3)."""

MAX_USER_ID: int = 2_147_483_647
"""Largest accepted user_id, mirroring the INT32 ``user_features.user_id`` column.

Enforced at the API boundary so an out-of-range id is rejected as a 422 before
it reaches the offline store. Without this the driver raises on the oversized
bind parameter (OverflowError on SQLite, a range DataError on PostgreSQL), which
surfaces to the caller as a 500/503 rather than as the input error it is.
"""

UserId = Annotated[int, Field(ge=1, le=MAX_USER_ID)]
"""A user identifier constrained to the range the offline store can hold."""

FeatureSource = Literal["redis", "postgres"]


class FeatureProvenance(BaseModel):
    """Provenance metadata attached to a single-user feature response."""

    computed_at: datetime | None = None
    feature_version: str | None = None
    source: FeatureSource


class FeatureResponse(BaseModel):
    """Response for GET /features/online/{id} and /features/offline/{id}."""

    user_id: int
    features: dict[str, Any]
    metadata: FeatureProvenance


class BatchFeatureRequest(BaseModel):
    """Request body for POST /features/batch.

    ``user_ids`` is capped at MAX_BATCH_USERS; exceeding it yields a 422.
    """

    user_ids: list[UserId] = Field(min_length=1, max_length=MAX_BATCH_USERS)
    feature_list: list[str] | None = None


class BatchResultItem(BaseModel):
    """One user's result within a batch response.

    ``features`` is populated on a hit; ``error`` is set (e.g. "not_found")
    when the user has no stored features.
    """

    user_id: int
    features: dict[str, Any] | None = None
    error: str | None = None


class BatchMetadata(BaseModel):
    """Aggregate stats for a batch lookup."""

    found: int
    missing: int
    latency_ms: float


class BatchFeatureResponse(BaseModel):
    """Response for POST /features/batch."""

    results: list[BatchResultItem]
    metadata: BatchMetadata


class FeatureCatalogEntry(BaseModel):
    """One feature's public metadata in the catalog (from the REGISTRY)."""

    name: str
    description: str
    data_type: str
    valid_range: tuple[float, float] | None = None


class FeatureMetadataResponse(BaseModel):
    """Response for GET /features/metadata — the feature catalog."""

    features: list[FeatureCatalogEntry]
    total_features: int
    last_computed_at: datetime | None = None


class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: Literal["healthy", "unhealthy"]
    version: str
    checks: dict[str, str]
