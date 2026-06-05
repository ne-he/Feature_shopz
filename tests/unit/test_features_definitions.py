"""Unit tests for the feature definition decorator and registry.

Covers definitions.py: FeatureDefinition metadata model (including
valid_range validation), the FeatureRegistry container, and the
@feature_definition decorator (registration + attribute attachment).

Naming pattern: test_<function>_<scenario>_<expected_result>
"""

from collections.abc import Iterator

import pytest
from pydantic import ValidationError

from src.features.definitions import (
    REGISTRY,
    FeatureDefinition,
    FeatureRegistry,
    RegisteredFeature,
    feature_definition,
)


@pytest.fixture(autouse=True)
def _isolate_global_registry() -> Iterator[None]:
    """Snapshot and restore REGISTRY so decorator tests don't leak state."""
    snapshot = REGISTRY.all()
    yield
    REGISTRY.clear()
    for registered in snapshot.values():
        REGISTRY.register(registered)


# ---------------------------------------------------------------------------
# FeatureDefinition — metadata model
# ---------------------------------------------------------------------------


class TestFeatureDefinition:
    """Tests for the FeatureDefinition Pydantic model."""

    def test_feature_definition_valid_data_creates_model(self) -> None:
        """Valid metadata constructs the model with defaults applied."""
        definition = FeatureDefinition(
            name="recency_days",
            description="Days since last purchase",
            data_type="int",
            owner="nehemiah",
        )
        assert definition.name == "recency_days"
        assert definition.refresh_cadence == "daily"
        assert definition.valid_range is None

    def test_feature_definition_invalid_data_type_raises_validation_error(self) -> None:
        """A data_type outside the allowed literal set is rejected."""
        with pytest.raises(ValidationError):
            FeatureDefinition(
                name="bad",
                description="d",
                data_type="datetime",  # type: ignore[arg-type]
                owner="nehemiah",
            )

    def test_feature_definition_inverted_valid_range_raises_validation_error(
        self,
    ) -> None:
        """A valid_range with lower bound above upper bound is rejected."""
        with pytest.raises(ValidationError, match="exceeds upper bound"):
            FeatureDefinition(
                name="bad",
                description="d",
                data_type="int",
                owner="nehemiah",
                valid_range=(100.0, 0.0),
            )

    def test_feature_definition_is_immutable(self) -> None:
        """The model is frozen — attribute assignment raises."""
        definition = FeatureDefinition(
            name="x", description="d", data_type="int", owner="nehemiah"
        )
        with pytest.raises(ValidationError):
            definition.name = "y"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# FeatureRegistry — container
# ---------------------------------------------------------------------------


def _make_registered(name: str) -> RegisteredFeature:
    """Build a throwaway RegisteredFeature for registry tests."""
    definition = FeatureDefinition(
        name=name, description="d", data_type="int", owner="nehemiah"
    )
    return RegisteredFeature(definition=definition, compute=lambda: 0)


class TestFeatureRegistry:
    """Tests for the FeatureRegistry container."""

    def test_register_then_get_returns_same_feature(self) -> None:
        """A registered feature is retrievable by name."""
        registry = FeatureRegistry()
        feature = _make_registered("frequency_count")
        registry.register(feature)
        assert registry.get("frequency_count") is feature

    def test_register_duplicate_name_raises_value_error(self) -> None:
        """Registering two features with the same name raises ValueError."""
        registry = FeatureRegistry()
        registry.register(_make_registered("monetary_total"))
        with pytest.raises(ValueError, match="already registered"):
            registry.register(_make_registered("monetary_total"))

    def test_get_unknown_name_raises_key_error(self) -> None:
        """Looking up an unregistered feature raises KeyError."""
        registry = FeatureRegistry()
        with pytest.raises(KeyError, match="not registered"):
            registry.get("does_not_exist")

    def test_names_returns_sorted_list(self) -> None:
        """names() returns feature names in alphabetical order."""
        registry = FeatureRegistry()
        for name in ("temporal", "age", "monetary"):
            registry.register(_make_registered(name))
        assert registry.names() == ["age", "monetary", "temporal"]

    def test_len_reflects_registered_count(self) -> None:
        """len(registry) equals the number of registered features."""
        registry = FeatureRegistry()
        registry.register(_make_registered("a"))
        registry.register(_make_registered("b"))
        assert len(registry) == 2

    def test_contains_reports_membership(self) -> None:
        """The `in` operator reports whether a name is registered."""
        registry = FeatureRegistry()
        registry.register(_make_registered("age"))
        assert "age" in registry
        assert "missing" not in registry

    def test_clear_empties_the_registry(self) -> None:
        """clear() removes every registered feature."""
        registry = FeatureRegistry()
        registry.register(_make_registered("a"))
        registry.clear()
        assert len(registry) == 0

    def test_definitions_returns_metadata_of_all_features(self) -> None:
        """definitions() returns the FeatureDefinition of every registered feature."""
        registry = FeatureRegistry()
        registry.register(_make_registered("age"))
        registry.register(_make_registered("country"))
        names = {definition.name for definition in registry.definitions()}
        assert names == {"age", "country"}


# ---------------------------------------------------------------------------
# feature_definition — decorator
# ---------------------------------------------------------------------------


class TestFeatureDefinitionDecorator:
    """Tests for the @feature_definition decorator."""

    def test_decorator_registers_feature_in_global_registry(self) -> None:
        """Decorating a function adds it to the global REGISTRY."""

        @feature_definition(
            name="decorator_test_feature",
            description="A test feature",
            data_type="int",
            owner="nehemiah",
        )
        def compute() -> int:
            return 42

        assert "decorator_test_feature" in REGISTRY

    def test_decorator_attaches_definition_to_function(self) -> None:
        """The decorated function carries its FeatureDefinition as an attribute."""

        @feature_definition(
            name="attached_feature",
            description="A test feature",
            data_type="float",
            owner="nehemiah",
        )
        def compute() -> float:
            return 1.5

        assert compute.feature_definition.data_type == "float"  # type: ignore[attr-defined]

    def test_decorator_leaves_function_callable(self) -> None:
        """The decorated function still runs and returns its value unchanged."""

        @feature_definition(
            name="callable_feature",
            description="A test feature",
            data_type="int",
            owner="nehemiah",
        )
        def compute() -> int:
            return 99

        assert compute() == 99

    def test_decorator_stores_full_metadata(self) -> None:
        """All metadata passed to the decorator is preserved in the registry."""

        @feature_definition(
            name="metadata_feature",
            description="Full metadata",
            data_type="int",
            owner="nehemiah",
            refresh_cadence="static",
            valid_range=(0.0, 365.0),
            null_handling="impute_with_max",
        )
        def compute() -> int:
            return 0

        definition = REGISTRY.get("metadata_feature").definition
        assert definition.refresh_cadence == "static"
        assert definition.valid_range == (0.0, 365.0)
        assert definition.null_handling == "impute_with_max"
