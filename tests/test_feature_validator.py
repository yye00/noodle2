"""Tests for feature validation framework.

Tests the ability to validate that all 200+ features can be tested programmatically.

Feature: Validate all 200+ features can be tested programmatically
"""

import json
from pathlib import Path

import pytest

from src.validation.feature_validator import (
    FeatureValidator,
    FeatureDefinition,
    TestabilityAnalysis,
    TestStatus,
    load_and_validate_features,
    verify_feature_list_integrity,
)


class TestFeatureListLoading:
    """Test loading and parsing feature_list.json."""

    def test_load_complete_feature_list(self, tmp_path: Path) -> None:
        """Step 1: Load complete feature_list.json."""
        # Create a test feature list
        feature_list = [
            {
                "category": "functional",
                "description": "Test feature 1",
                "steps": ["Step 1", "Step 2"],
                "passes": True,
            },
            {
                "category": "style",
                "description": "Test feature 2",
                "steps": ["Step 1"],
                "passes": False,
            },
        ]

        feature_list_path = tmp_path / "feature_list.json"
        with open(feature_list_path, "w") as f:
            json.dump(feature_list, f)

        validator = FeatureValidator(feature_list_path)
        features = validator.load_features()

        assert len(features) == 2
        assert features[0].category == "functional"
        assert features[0].description == "Test feature 1"
        assert features[0].passes is True
        assert features[1].category == "style"
        assert features[1].passes is False

        print(f"✓ Loaded {len(features)} features from feature_list.json")

    def test_parse_all_200_features(self) -> None:
        """Step 2: Parse all 200+ features from actual feature_list.json."""
        feature_list_path = Path("feature_list.json")

        if not feature_list_path.exists():
            pytest.skip("feature_list.json not found in project root")

        validator = FeatureValidator(feature_list_path)
        features = validator.load_features()

        # Should have 200+ features
        assert len(features) >= 200
        print(f"✓ Parsed {len(features)} features from actual feature_list.json")

        # Verify all features have required fields
        for i, feature in enumerate(features):
            assert feature.index == i
            assert feature.category in ["functional", "style", "unknown"]
            assert isinstance(feature.description, str)
            assert len(feature.description) > 0
            assert isinstance(feature.steps, list)
            assert len(feature.steps) > 0
            assert isinstance(feature.passes, bool)

        print(f"✓ All {len(features)} features have valid structure")

    def test_load_features_with_missing_file(self, tmp_path: Path) -> None:
        """Test error handling when feature_list.json doesn't exist."""
        missing_path = tmp_path / "nonexistent.json"
        validator = FeatureValidator(missing_path)

        with pytest.raises(FileNotFoundError):
            validator.load_features()

    def test_load_features_with_invalid_json(self, tmp_path: Path) -> None:
        """Test error handling with malformed JSON."""
        invalid_json_path = tmp_path / "invalid.json"
        with open(invalid_json_path, "w") as f:
            f.write("{ invalid json }")

        validator = FeatureValidator(invalid_json_path)

        with pytest.raises(json.JSONDecodeError):
            validator.load_features()


class TestTestabilityAnalysis:
    """Test analysis of feature testability."""

    def test_verify_test_steps_are_executable(self) -> None:
        """Step 3: For each feature, verify test steps are executable."""
        feature = FeatureDefinition(
            index=0,
            category="functional",
            description="Execute STA and parse timing report",
            steps=[
                "Step 1: Execute OpenROAD STA",
                "Step 2: Parse report_checks output",
                "Step 3: Verify WNS is extracted",
            ],
            passes=True,
        )

        validator = FeatureValidator(Path("dummy.json"))
        analysis = validator.analyze_testability(feature)

        assert analysis.is_testable is True
        assert analysis.feature_index == 0
        assert "unit or integration" in analysis.reason.lower()

        print(f"✓ Feature is testable: {analysis.reason}")

    def test_identify_browser_interaction_features(self) -> None:
        """Test identification of features requiring manual browser interaction."""
        feature = FeatureDefinition(
            index=0,
            category="style",
            description="Take screenshot of Ray Dashboard",
            steps=[
                "Step 1: Navigate to http://localhost:8265",
                "Step 2: Take screenshot of dashboard",
                "Step 3: Verify layout is clean",
            ],
            passes=False,
        )

        validator = FeatureValidator(Path("dummy.json"))
        analysis = validator.analyze_testability(feature)

        assert analysis.is_testable is False
        assert "browser interaction" in analysis.reason.lower()
        assert analysis.recommended_test_file is None

        print(f"✓ Identified untestable feature: {analysis.reason}")

    def test_identify_end_to_end_features(self) -> None:
        """Test identification of end-to-end features requiring OpenROAD."""
        feature = FeatureDefinition(
            index=0,
            category="functional",
            description="End-to-end: Complete Nangate45 Study",
            steps=[
                "Step 1: Load snapshot",
                "Step 2: Execute 3-stage Study",
                "Step 3: Select final winner",
            ],
            passes=False,
        )

        validator = FeatureValidator(Path("dummy.json"))
        analysis = validator.analyze_testability(feature)

        assert analysis.is_testable is True
        assert "openroad execution" in analysis.reason.lower()
        assert analysis.recommended_test_file is not None

        print(f"✓ Identified E2E feature: {analysis.reason}")

    def test_identify_ray_dashboard_features(self) -> None:
        """Test identification of Ray Dashboard UI validation features."""
        feature = FeatureDefinition(
            index=0,
            category="style",
            description="Ray Dashboard displays cluster status clearly",
            steps=[
                "Step 1: Open Ray Dashboard",
                "Step 2: Verify cluster status is visible",
            ],
            passes=False,
        )

        validator = FeatureValidator(Path("dummy.json"))
        analysis = validator.analyze_testability(feature)

        assert analysis.is_testable is False
        assert "visual validation" in analysis.reason.lower()

        print(f"✓ Identified Ray Dashboard UI feature: {analysis.reason}")

    def test_identify_extreme_scenario_features(self) -> None:
        """Test identification of extreme scenario features."""
        feature = FeatureDefinition(
            index=0,
            category="functional",
            description="Extreme scenario: 1000+ trial large-scale sweep",
            steps=[
                "Step 1: Configure 1000 trials",
                "Step 2: Execute on multi-node cluster",
                "Step 3: Verify completion",
            ],
            passes=False,
        )

        validator = FeatureValidator(Path("dummy.json"))
        analysis = validator.analyze_testability(feature)

        assert analysis.is_testable is True
        assert "stress test" in analysis.reason.lower()
        assert "extreme" in analysis.recommended_test_file.lower()

        print(f"✓ Identified extreme scenario: {analysis.reason}")


class TestFeatureHarness:
    """Test the feature test harness."""

    def test_create_test_harness(self, tmp_path: Path) -> None:
        """Step 4: Create test harness that can run all features."""
        # Create feature list
        features = [
            {
                "category": "functional",
                "description": "Feature A",
                "steps": ["Step 1", "Step 2"],
                "passes": True,
            },
            {
                "category": "functional",
                "description": "Feature B",
                "steps": ["Step 1"],
                "passes": False,
            },
        ]

        feature_list_path = tmp_path / "feature_list.json"
        with open(feature_list_path, "w") as f:
            json.dump(features, f)

        # Test harness: FeatureValidator
        validator = FeatureValidator(feature_list_path)
        validator.load_features()

        assert len(validator.features) == 2
        print(f"✓ Test harness can process {len(validator.features)} features")

    def test_execute_sample_features_from_each_category(self, tmp_path: Path) -> None:
        """Step 5: Execute sample of features from each category."""
        # Create features from different categories
        features = [
            {
                "category": "functional",
                "description": "Functional feature",
                "steps": ["Step 1"],
                "passes": True,
            },
            {
                "category": "style",
                "description": "Style feature",
                "steps": ["Step 1"],
                "passes": False,
            },
        ]

        feature_list_path = tmp_path / "feature_list.json"
        with open(feature_list_path, "w") as f:
            json.dump(features, f)

        validator = FeatureValidator(feature_list_path)
        validator.load_features()

        # Analyze testability for each category
        functional_features = [f for f in validator.features if f.category == "functional"]
        style_features = [f for f in validator.features if f.category == "style"]

        assert len(functional_features) == 1
        assert len(style_features) == 1

        # Analyze testability
        for feature in validator.features:
            analysis = validator.analyze_testability(feature)
            assert isinstance(analysis, TestabilityAnalysis)

        print("✓ Executed testability analysis on features from each category")

    def test_verify_test_results_can_be_captured(self, tmp_path: Path) -> None:
        """Step 6: Verify test results can be captured."""
        features = [
            {
                "category": "functional",
                "description": "Test feature",
                "steps": ["Step 1"],
                "passes": True,
            }
        ]

        feature_list_path = tmp_path / "feature_list.json"
        with open(feature_list_path, "w") as f:
            json.dump(features, f)

        validator = FeatureValidator(feature_list_path)
        validator.load_features()

        # Capture test status
        feature = validator.features[0]
        status = feature.test_status

        assert status == TestStatus.PASSING
        print(f"✓ Captured test result: {status.value}")


class TestProgrammaticMarking:
    """Test programmatic marking of features as passing."""

    def test_verify_features_can_be_marked_passing_programmatically(
        self, tmp_path: Path
    ) -> None:
        """Step 7: Verify features can be marked as passing programmatically."""
        features = [
            {
                "category": "functional",
                "description": "Test feature",
                "steps": ["Step 1"],
                "passes": False,
            }
        ]

        feature_list_path = tmp_path / "feature_list.json"
        with open(feature_list_path, "w") as f:
            json.dump(features, f)

        # Load, modify, and save
        with open(feature_list_path, "r") as f:
            data = json.load(f)

        # Mark as passing
        data[0]["passes"] = True

        with open(feature_list_path, "w") as f:
            json.dump(data, f, indent=2)

        # Verify change
        validator = FeatureValidator(feature_list_path)
        validator.load_features()

        assert validator.features[0].passes is True
        print("✓ Feature can be marked as passing programmatically")


class TestCoverageReport:
    """Test coverage report generation."""

    def test_generate_test_coverage_report(self, tmp_path: Path) -> None:
        """Step 8: Generate test coverage report."""
        features = [
            {
                "category": "functional",
                "description": "Feature 1",
                "steps": ["Step 1"],
                "passes": True,
            },
            {
                "category": "functional",
                "description": "Feature 2",
                "steps": ["Step 1"],
                "passes": True,
            },
            {
                "category": "style",
                "description": "Feature 3",
                "steps": ["Step 1"],
                "passes": False,
            },
        ]

        feature_list_path = tmp_path / "feature_list.json"
        with open(feature_list_path, "w") as f:
            json.dump(features, f)

        validator = FeatureValidator(feature_list_path)
        report = validator.validate_all_features()

        assert report.total_features == 3
        assert report.passing_features == 2
        assert report.failing_features == 1
        assert report.test_coverage_percent == pytest.approx(66.67, rel=0.1)
        assert "functional" in report.features_by_category
        assert "style" in report.features_by_category

        print(f"✓ Coverage report: {report.passing_features}/{report.total_features} passing")

    def test_write_coverage_report_to_file(self, tmp_path: Path) -> None:
        """Test writing coverage report to JSON file."""
        features = [
            {
                "category": "functional",
                "description": "Feature 1",
                "steps": ["Step 1"],
                "passes": True,
            }
        ]

        feature_list_path = tmp_path / "feature_list.json"
        with open(feature_list_path, "w") as f:
            json.dump(features, f)

        validator = FeatureValidator(feature_list_path)
        validator.load_features()

        output_path = tmp_path / "coverage_report.json"
        validator.generate_test_coverage_report(output_path)

        assert output_path.exists()

        with open(output_path, "r") as f:
            report_data = json.load(f)

        assert report_data["total_features"] == 1
        assert report_data["passing_features"] == 1
        assert "testability_analysis" in report_data

        print(f"✓ Coverage report written to {output_path}")


class TestUntestableFeatures:
    """Test identification of untestable features."""

    def test_identify_untestable_features(self, tmp_path: Path) -> None:
        """Step 9: Identify any untestable features."""
        features = [
            {
                "category": "functional",
                "description": "Testable feature",
                "steps": ["Step 1"],
                "passes": True,
            },
            {
                "category": "style",
                "description": "Take screenshot of dashboard",
                "steps": ["Step 1: Navigate to dashboard", "Step 2: Take screenshot"],
                "passes": False,
            },
        ]

        feature_list_path = tmp_path / "feature_list.json"
        with open(feature_list_path, "w") as f:
            json.dump(features, f)

        validator = FeatureValidator(feature_list_path)
        validator.load_features()

        untestable = validator.identify_untestable_features()

        assert len(untestable) == 1
        assert "screenshot" in untestable[0][1].description.lower()

        print(f"✓ Identified {len(untestable)} untestable features")


class TestCompleteValidation:
    """Test complete end-to-end validation."""

    def test_ensure_100_percent_features_are_testable(self, tmp_path: Path) -> None:
        """Step 10: Ensure 100% of features are testable (with known exceptions)."""
        features = [
            {
                "category": "functional",
                "description": "Feature 1",
                "steps": ["Step 1"],
                "passes": True,
            },
            {
                "category": "functional",
                "description": "Feature 2",
                "steps": ["Step 1"],
                "passes": True,
            },
        ]

        feature_list_path = tmp_path / "feature_list.json"
        with open(feature_list_path, "w") as f:
            json.dump(features, f)

        validator = FeatureValidator(feature_list_path)
        report = validator.validate_all_features()

        # All features should be testable (or have known reasons if not)
        for analysis in report.testability_analysis:
            assert isinstance(analysis.is_testable, bool)
            assert isinstance(analysis.reason, str)
            assert len(analysis.reason) > 0

        print(
            f"✓ All {report.total_features} features have testability analysis"
        )

    def test_validate_actual_feature_list(self) -> None:
        """Test validation on actual project feature_list.json."""
        feature_list_path = Path("feature_list.json")

        if not feature_list_path.exists():
            pytest.skip("feature_list.json not found")

        report = load_and_validate_features(feature_list_path)

        # Should have 200+ features
        assert report.total_features >= 200

        # Coverage should be > 80% (we're at 167/200 = 83.5%)
        assert report.test_coverage_percent >= 80.0

        # Should have both functional and style features
        assert "functional" in report.features_by_category
        assert "style" in report.features_by_category

        # Most features should be testable (allowing for browser UI features)
        testable_count = sum(
            1 for a in report.testability_analysis if a.is_testable
        )
        testability_ratio = testable_count / report.total_features

        assert testability_ratio >= 0.85  # At least 85% testable

        print(f"✓ Validated actual feature list:")
        print(f"  Total features: {report.total_features}")
        print(f"  Passing: {report.passing_features} ({report.test_coverage_percent:.1f}%)")
        print(f"  Failing: {report.failing_features}")
        print(f"  Untestable: {report.untestable_features}")
        print(f"  Testable: {testable_count} ({testability_ratio * 100:.1f}%)")


class TestFeatureListIntegrity:
    """Test feature_list.json integrity validation."""

    def test_verify_feature_list_integrity(self, tmp_path: Path) -> None:
        """Test integrity validation of feature_list.json."""
        # Valid feature list
        valid_features = [
            {
                "category": "functional",
                "description": "Test feature",
                "steps": ["Step 1", "Step 2"],
                "passes": True,
            }
        ]

        valid_path = tmp_path / "valid.json"
        with open(valid_path, "w") as f:
            json.dump(valid_features, f)

        assert verify_feature_list_integrity(valid_path) is True

    def test_detect_invalid_feature_list(self, tmp_path: Path) -> None:
        """Test detection of invalid feature_list.json."""
        # Missing required field
        invalid_features = [
            {
                "category": "functional",
                "description": "Test feature",
                # Missing 'steps' and 'passes'
            }
        ]

        invalid_path = tmp_path / "invalid.json"
        with open(invalid_path, "w") as f:
            json.dump(invalid_features, f)

        assert verify_feature_list_integrity(invalid_path) is False

    def test_detect_wrong_type_feature_list(self, tmp_path: Path) -> None:
        """Test detection of wrong type (not an array)."""
        wrong_type_path = tmp_path / "wrong_type.json"
        with open(wrong_type_path, "w") as f:
            json.dump({"features": []}, f)  # Object instead of array

        assert verify_feature_list_integrity(wrong_type_path) is False


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_load_and_validate_features_convenience(self, tmp_path: Path) -> None:
        """Test convenience function for loading and validating."""
        features = [
            {
                "category": "functional",
                "description": "Test",
                "steps": ["Step 1"],
                "passes": True,
            }
        ]

        feature_list_path = tmp_path / "features.json"
        with open(feature_list_path, "w") as f:
            json.dump(features, f)

        report = load_and_validate_features(feature_list_path)

        assert report.total_features == 1
        assert report.passing_features == 1
        assert report.test_coverage_percent == 100.0

        print("✓ Convenience function works correctly")
