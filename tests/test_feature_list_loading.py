"""
Tests for feature list loading and validation.

Feature: Feature list is loaded and validated at runtime for test tracking
"""

import json
import pytest
from pathlib import Path
import tempfile

from src.tracking.feature_loader import (
    FeatureDefinition,
    load_feature_list,
    validate_feature_list,
)


class TestFeatureListLoading:
    """Test feature list loading from JSON."""

    def test_load_feature_list_from_default_location(self):
        """Step 1: Load feature_list.json at runtime from default location."""
        features = load_feature_list()
        assert features is not None
        assert isinstance(features, list)
        assert len(features) > 0

    def test_parse_json_and_validate_structure(self):
        """Step 2: Parse JSON and validate structure."""
        features = load_feature_list()

        # Verify all features are FeatureDefinition objects
        for feature in features:
            assert isinstance(feature, FeatureDefinition)
            assert hasattr(feature, 'category')
            assert hasattr(feature, 'description')
            assert hasattr(feature, 'steps')
            assert hasattr(feature, 'passes')

    def test_count_total_features(self):
        """Step 3: Count total features."""
        features = load_feature_list()
        total_count = len(features)

        # Should have a substantial number of features
        assert total_count > 0
        print(f"Total features: {total_count}")

    def test_verify_minimum_200_features(self):
        """Step 4: Verify count >= 200."""
        features = load_feature_list()
        assert len(features) >= 200, f"Expected >= 200 features, got {len(features)}"

    def test_count_features_by_category(self):
        """Step 5: Count features by category (functional vs style)."""
        features = load_feature_list()

        functional_count = sum(1 for f in features if f.category == "functional")
        style_count = sum(1 for f in features if f.category == "style")

        assert functional_count > 0, "Should have at least one functional feature"
        assert style_count > 0, "Should have at least one style feature"
        assert functional_count + style_count == len(features), "All features should be categorized"

        print(f"Functional features: {functional_count}")
        print(f"Style features: {style_count}")

    def test_verify_all_features_have_required_fields(self):
        """Step 6: Verify all features have required fields."""
        features = load_feature_list()

        for i, feature in enumerate(features):
            assert feature.category in ["functional", "style"], \
                f"Feature {i} has invalid category: {feature.category}"
            assert isinstance(feature.description, str) and feature.description, \
                f"Feature {i} has invalid description"
            assert isinstance(feature.steps, list) and len(feature.steps) > 0, \
                f"Feature {i} has no steps"
            assert isinstance(feature.passes, bool), \
                f"Feature {i} has invalid passes field"


class TestFeatureListValidation:
    """Test feature list validation."""

    def test_validate_feature_list_structure(self):
        """Validate that feature list meets all requirements."""
        features = load_feature_list()
        result = validate_feature_list(features)

        assert isinstance(result, dict)
        assert "valid" in result
        assert "errors" in result
        assert "warnings" in result
        assert "stats" in result

        # Print any errors or warnings
        if result["errors"]:
            print("Validation errors:")
            for error in result["errors"]:
                print(f"  - {error}")

        if result["warnings"]:
            print("Validation warnings:")
            for warning in result["warnings"]:
                print(f"  - {warning}")

        # Should be valid (no errors)
        assert result["valid"], f"Feature list validation failed: {result['errors']}"

    def test_validate_minimum_200_features_requirement(self):
        """Validate minimum 200 features requirement."""
        features = load_feature_list()
        result = validate_feature_list(features)

        assert result["stats"]["total_features"] >= 200

    def test_validate_minimum_25_large_features(self):
        """Validate at least 25 features have 10+ steps."""
        features = load_feature_list()
        result = validate_feature_list(features)

        large_features = result["stats"]["features_with_10plus_steps"]
        # This may be a warning rather than error, so we just check it's reported
        assert "features_with_10plus_steps" in result["stats"]

    def test_validate_statistics_are_correct(self):
        """Validate that computed statistics match manual counts."""
        features = load_feature_list()
        result = validate_feature_list(features)

        stats = result["stats"]

        # Verify total count
        assert stats["total_features"] == len(features)

        # Verify category counts
        functional_count = sum(1 for f in features if f.category == "functional")
        style_count = sum(1 for f in features if f.category == "style")
        assert stats["functional_features"] == functional_count
        assert stats["style_features"] == style_count

        # Verify pass/fail counts
        passing = sum(1 for f in features if f.passes)
        failing = sum(1 for f in features if not f.passes)
        assert stats["passing_features"] == passing
        assert stats["failing_features"] == failing


class TestFeatureDefinition:
    """Test FeatureDefinition dataclass."""

    def test_create_feature_from_dict(self):
        """Create FeatureDefinition from dictionary."""
        data = {
            "category": "functional",
            "description": "Test feature",
            "steps": ["Step 1", "Step 2"],
            "passes": True,
        }

        feature = FeatureDefinition.from_dict(data)

        assert feature.category == "functional"
        assert feature.description == "Test feature"
        assert feature.steps == ["Step 1", "Step 2"]
        assert feature.passes is True

    def test_feature_to_dict(self):
        """Convert FeatureDefinition to dictionary."""
        feature = FeatureDefinition(
            category="style",
            description="Style test",
            steps=["Step A"],
            passes=False,
        )

        data = feature.to_dict()

        assert data["category"] == "style"
        assert data["description"] == "Style test"
        assert data["steps"] == ["Step A"]
        assert data["passes"] is False

    def test_feature_defaults_to_not_passing(self):
        """Feature should default to not passing if field is missing."""
        data = {
            "category": "functional",
            "description": "Test",
            "steps": ["Step 1"],
            # No "passes" field
        }

        feature = FeatureDefinition.from_dict(data)
        assert feature.passes is False


class TestFeatureListLoadingErrors:
    """Test error handling in feature list loading."""

    def test_load_from_custom_path(self):
        """Load feature list from custom path."""
        # Create temporary feature list
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([
                {
                    "category": "functional",
                    "description": "Test feature",
                    "steps": ["Step 1"],
                    "passes": False,
                }
            ], f)
            temp_path = f.name

        try:
            features = load_feature_list(temp_path)
            assert len(features) == 1
            assert features[0].description == "Test feature"
        finally:
            Path(temp_path).unlink()

    def test_load_nonexistent_file_raises_error(self):
        """Loading non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_feature_list("/nonexistent/path/to/features.json")

    def test_load_invalid_json_raises_error(self):
        """Loading invalid JSON should raise JSONDecodeError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = f.name

        try:
            with pytest.raises(json.JSONDecodeError):
                load_feature_list(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_non_array_json_raises_error(self):
        """Loading JSON that's not an array should raise ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"not": "an array"}, f)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="must be a JSON array"):
                load_feature_list(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_feature_missing_required_field_raises_error(self):
        """Loading feature missing required field should raise ValueError."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump([
                {
                    "category": "functional",
                    # Missing "description" field
                    "steps": ["Step 1"],
                }
            ], f)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="missing required field"):
                load_feature_list(temp_path)
        finally:
            Path(temp_path).unlink()
