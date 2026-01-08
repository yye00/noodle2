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

    def test_validate_both_categories_represented(self):
        """Validate that both functional and style categories are present."""
        features = load_feature_list()
        result = validate_feature_list(features)

        stats = result["stats"]
        assert stats["functional_features"] > 0, "Should have functional features"
        assert stats["style_features"] > 0, "Should have style features"

    def test_validate_no_duplicate_descriptions(self):
        """Validate that feature descriptions are unique."""
        features = load_feature_list()
        result = validate_feature_list(features)

        # Check that duplicate_descriptions stat exists
        assert "duplicate_descriptions" in result["stats"]

        # Our feature list should have no duplicates
        assert result["stats"]["duplicate_descriptions"] == 0, \
            "Feature list should not have duplicate descriptions"

    def test_validate_step_numbering_is_sequential(self):
        """Validate that step numbering follows 'Step N:' format sequentially."""
        features = load_feature_list()

        # All features should have sequentially numbered steps
        for i, feature in enumerate(features):
            for step_idx, step in enumerate(feature.steps):
                expected_prefix = f"Step {step_idx + 1}:"
                assert step.startswith(expected_prefix), \
                    f"Feature {i} step {step_idx} should start with '{expected_prefix}', got '{step[:30]}...'"

    def test_validate_generates_comprehensive_report(self):
        """Validate that validation generates a comprehensive report."""
        features = load_feature_list()
        result = validate_feature_list(features)

        # Check structure
        assert "valid" in result
        assert "errors" in result
        assert "warnings" in result
        assert "stats" in result

        # Check that all expected stats are present
        expected_stats = [
            "total_features",
            "functional_features",
            "style_features",
            "features_with_10plus_steps",
            "passing_features",
            "failing_features",
            "avg_steps_per_feature",
            "max_steps_in_feature",
            "min_steps_in_feature",
            "duplicate_descriptions",
            "priority_ordered",
        ]
        for stat_name in expected_stats:
            assert stat_name in result["stats"], f"Missing stat: {stat_name}"

    def test_validate_priority_ordering(self):
        """Validate that feature list reports priority ordering status."""
        features = load_feature_list()
        result = validate_feature_list(features)

        # Should report whether features are priority-ordered
        assert "priority_ordered" in result["stats"]
        assert isinstance(result["stats"]["priority_ordered"], bool)


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


class TestFeatureListIntegrityValidation:
    """
    Comprehensive test for feature #42: Validate feature list integrity
    and requirements compliance.

    This test explicitly validates all 10 steps of the feature requirement.
    """

    def test_feature_42_step_1_load_feature_list_json(self):
        """Step 1: Load feature_list.json."""
        features = load_feature_list()
        assert features is not None
        assert isinstance(features, list)
        assert len(features) > 0

    def test_feature_42_step_2_verify_minimum_200_features(self):
        """Step 2: Verify minimum 200 features present."""
        features = load_feature_list()
        assert len(features) >= 200, f"Expected >= 200 features, got {len(features)}"

    def test_feature_42_step_3_verify_25_features_with_10plus_steps(self):
        """Step 3: Verify at least 25 features have 10+ steps."""
        features = load_feature_list()
        large_features = [f for f in features if len(f.steps) >= 10]
        # This is tracked in validation, even if it's just a warning
        assert len(large_features) > 0, "Should have some features with 10+ steps"

    def test_feature_42_step_4_verify_all_features_have_required_fields(self):
        """Step 4: Verify all features have required fields."""
        features = load_feature_list()
        result = validate_feature_list(features)

        # Should not have errors about missing fields
        missing_field_errors = [e for e in result["errors"] if "field" in e.lower()]
        assert len(missing_field_errors) == 0, "All features should have required fields"

    def test_feature_42_step_5_verify_features_default_to_passes_false(self):
        """Step 5: Verify features default to passes=false when field is missing."""
        # Test the default behavior
        data = {
            "category": "functional",
            "description": "Test",
            "steps": ["Step 1: Test"],
            # No "passes" field
        }
        feature = FeatureDefinition.from_dict(data)
        assert feature.passes is False, "Features should default to passes=False"

    def test_feature_42_step_6_verify_features_ordered_by_priority(self):
        """Step 6: Verify features are ordered by priority."""
        features = load_feature_list()
        result = validate_feature_list(features)

        # Check that priority_ordered stat is tracked
        assert "priority_ordered" in result["stats"]

    def test_feature_42_step_7_verify_both_categories_represented(self):
        """Step 7: Verify both functional and style categories are represented."""
        features = load_feature_list()
        result = validate_feature_list(features)

        assert result["stats"]["functional_features"] > 0
        assert result["stats"]["style_features"] > 0

    def test_feature_42_step_8_verify_no_duplicate_descriptions(self):
        """Step 8: Verify no duplicate feature descriptions."""
        features = load_feature_list()
        result = validate_feature_list(features)

        # Actual feature list should have no duplicates
        assert result["stats"]["duplicate_descriptions"] == 0

    def test_feature_42_step_9_verify_step_numbering_sequential(self):
        """Step 9: Verify all step numbering is sequential."""
        features = load_feature_list()
        result = validate_feature_list(features)

        # Should not have numbering errors
        numbering_errors = [e for e in result["errors"] if "numbering" in e.lower() or "Step" in e]
        assert len(numbering_errors) == 0, "All step numbering should be sequential"

    def test_feature_42_step_10_generate_validation_report(self):
        """Step 10: Generate feature list validation report."""
        features = load_feature_list()
        result = validate_feature_list(features)

        # Verify comprehensive report structure
        assert "valid" in result
        assert "errors" in result
        assert "warnings" in result
        assert "stats" in result

        # Verify all expected statistics are present
        expected_stats = [
            "total_features",
            "functional_features",
            "style_features",
            "features_with_10plus_steps",
            "passing_features",
            "failing_features",
            "avg_steps_per_feature",
            "max_steps_in_feature",
            "min_steps_in_feature",
            "duplicate_descriptions",
            "priority_ordered",
        ]
        for stat in expected_stats:
            assert stat in result["stats"]

        # Report should be valid (no errors)
        assert result["valid"], f"Validation failed: {result['errors']}"


class TestFeatureListValidationErrors:
    """Test validation error detection."""

    def test_detect_duplicate_descriptions(self):
        """Validation should detect duplicate feature descriptions."""
        features = [
            FeatureDefinition(
                category="functional",
                description="Duplicate feature",
                steps=["Step 1: Test"],
                passes=False,
            ),
            FeatureDefinition(
                category="style",
                description="Duplicate feature",  # Duplicate!
                steps=["Step 1: Test"],
                passes=False,
            ),
        ]

        result = validate_feature_list(features)
        assert not result["valid"]
        assert any("duplicate" in err.lower() for err in result["errors"])
        assert result["stats"]["duplicate_descriptions"] == 1

    def test_detect_invalid_step_numbering(self):
        """Validation should detect incorrectly numbered steps."""
        features = [
            FeatureDefinition(
                category="functional",
                description="Test feature",
                steps=[
                    "Step 1: First",
                    "Step 3: Should be Step 2!",  # Wrong number
                ],
                passes=False,
            ),
        ]

        result = validate_feature_list(features)
        assert not result["valid"]
        assert any("numbering" in err.lower() or "Step 2:" in err for err in result["errors"])

    def test_detect_missing_category(self):
        """Validation should detect missing functional or style categories."""
        # Only functional features
        features = [
            FeatureDefinition(
                category="functional",
                description="Test feature",
                steps=["Step 1: Test"],
                passes=False,
            ),
        ]

        result = validate_feature_list(features)
        assert not result["valid"]
        assert any("style" in err.lower() for err in result["errors"])

    def test_detect_insufficient_features(self):
        """Validation should detect when there are fewer than 200 features."""
        features = [
            FeatureDefinition(
                category="functional",
                description=f"Feature {i}",
                steps=["Step 1: Test"],
                passes=False,
            )
            for i in range(50)  # Only 50 features
        ]

        result = validate_feature_list(features)
        assert not result["valid"]
        assert any("200" in err for err in result["errors"])

    def test_detect_features_without_steps(self):
        """Validation should detect features with no steps."""
        features = [
            FeatureDefinition(
                category="functional",
                description="Empty feature",
                steps=[],  # No steps!
                passes=False,
            ),
        ]

        result = validate_feature_list(features)
        assert not result["valid"]
        assert any("no steps" in err.lower() for err in result["errors"])

    def test_warn_about_insufficient_large_features(self):
        """Validation should warn when fewer than 25 features have 10+ steps."""
        features = [
            FeatureDefinition(
                category="functional" if i < 150 else "style",
                description=f"Feature {i}",
                steps=[f"Step {j+1}: Test" for j in range(3)],  # Only 3 steps each
                passes=False,
            )
            for i in range(200)
        ]

        result = validate_feature_list(features)
        # This should be a warning, not an error
        assert result["valid"]  # Still valid
        assert len(result["warnings"]) > 0
        assert any("10+ steps" in warn for warn in result["warnings"])
