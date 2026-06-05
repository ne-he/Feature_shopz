"""Feature definition decorator and central registry.

Provides ``@feature_definition`` — a decorator that attaches structured
metadata to a feature computation function and registers it in a global
registry. The registry is the single source of truth for *what* features
exist, their semantics (data type, valid range, owner), and *how* to
compute them (PRD § 9).

Feature modules (rfm.py, behavior.py, ...) decorate their compute
functions; importing those modules populates ``REGISTRY`` as a side
effect. Downstream consumers — the pipeline (M2.8) and the metadata API
endpoint (M3) — read from this registry rather than hardcoding names.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from loguru import logger
from pydantic import BaseModel, ConfigDict, model_validator

DataType = Literal["int", "float", "str", "bool"]
RefreshCadence = Literal["daily", "hourly", "static"]

ComputeFunc = Callable[..., Any]


class FeatureDefinition(BaseModel):
    """Immutable metadata describing a single computed feature.

    Attributes:
        name: Unique feature name, matching a column in ``user_features``.
        description: Human-readable explanation of what the feature means.
        data_type: Logical type of the computed value.
        owner: Person or team responsible for the feature.
        refresh_cadence: How often the feature is recomputed.
        valid_range: Optional ``(min, max)`` bounds for sanity checks.
        null_handling: Optional note on how missing values are imputed.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    data_type: DataType
    owner: str
    refresh_cadence: RefreshCadence = "daily"
    valid_range: tuple[float, float] | None = None
    null_handling: str | None = None

    @model_validator(mode="after")
    def _check_valid_range(self) -> FeatureDefinition:
        """Reject a ``valid_range`` whose lower bound exceeds its upper bound."""
        if self.valid_range is not None:
            low, high = self.valid_range
            if low > high:
                raise ValueError(
                    f"valid_range lower bound {low} exceeds upper bound {high}"
                )
        return self


@dataclass(frozen=True)
class RegisteredFeature:
    """A feature definition paired with its compute function."""

    definition: FeatureDefinition
    compute: ComputeFunc


class FeatureRegistry:
    """In-memory registry of all defined features, keyed by feature name."""

    def __init__(self) -> None:
        """Initialize an empty registry."""
        self._features: dict[str, RegisteredFeature] = {}

    def register(self, feature: RegisteredFeature) -> None:
        """Add a feature to the registry.

        Args:
            feature: The definition + compute function to register.

        Raises:
            ValueError: If a feature with the same name is already registered.
        """
        name = feature.definition.name
        if name in self._features:
            raise ValueError(f"Feature {name!r} is already registered")
        self._features[name] = feature
        logger.debug("Registered feature {!r}", name)

    def get(self, name: str) -> RegisteredFeature:
        """Return the registered feature with the given name.

        Args:
            name: The feature name to look up.

        Returns:
            The matching ``RegisteredFeature``.

        Raises:
            KeyError: If no feature with that name is registered.
        """
        if name not in self._features:
            raise KeyError(f"Feature {name!r} is not registered")
        return self._features[name]

    def all(self) -> dict[str, RegisteredFeature]:
        """Return a shallow copy of all registered features keyed by name."""
        return dict(self._features)

    def names(self) -> list[str]:
        """Return all registered feature names, sorted alphabetically."""
        return sorted(self._features)

    def definitions(self) -> list[FeatureDefinition]:
        """Return the metadata of every registered feature (for the API catalog)."""
        return [feature.definition for feature in self._features.values()]

    def clear(self) -> None:
        """Remove all registered features (primarily for test isolation)."""
        self._features.clear()

    def __len__(self) -> int:
        """Return the number of registered features."""
        return len(self._features)

    def __contains__(self, name: object) -> bool:
        """Return whether a feature name is registered."""
        return name in self._features


REGISTRY = FeatureRegistry()
"""The process-wide feature registry populated by ``@feature_definition``."""


def feature_definition(
    *,
    name: str,
    description: str,
    data_type: DataType,
    owner: str,
    refresh_cadence: RefreshCadence = "daily",
    valid_range: tuple[float, float] | None = None,
    null_handling: str | None = None,
) -> Callable[[ComputeFunc], ComputeFunc]:
    """Decorate a feature compute function with metadata and register it.

    The decorated function is returned unchanged (still directly callable),
    with its ``FeatureDefinition`` attached as a ``feature_definition``
    attribute and added to the global ``REGISTRY``.

    Args:
        name: Unique feature name.
        description: Human-readable explanation of the feature.
        data_type: Logical type of the computed value.
        owner: Person or team responsible for the feature.
        refresh_cadence: How often the feature is recomputed.
        valid_range: Optional ``(min, max)`` bounds for sanity checks.
        null_handling: Optional note on how missing values are imputed.

    Returns:
        A decorator that registers the wrapped function and returns it.
    """

    def decorator(func: ComputeFunc) -> ComputeFunc:
        definition = FeatureDefinition(
            name=name,
            description=description,
            data_type=data_type,
            owner=owner,
            refresh_cadence=refresh_cadence,
            valid_range=valid_range,
            null_handling=null_handling,
        )
        REGISTRY.register(RegisteredFeature(definition=definition, compute=func))
        func.feature_definition = definition  # type: ignore[attr-defined]
        return func

    return decorator
