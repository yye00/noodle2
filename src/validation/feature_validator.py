"""Feature validation framework for programmatic testing.

This module provides tools to validate that all 200+ features in feature_list.json
can be tested programmatically and that the test coverage is complete.

Feature: Validate all 200+ features can be tested programmatically
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from enum import Enum


class TestStatus(Enum):
    """Status of a feature test."""

    PASSING = "passing"
    FAILING = "failing"
    UNTESTABLE = "untestable"
    UNKNOWN = "unknown"


@dataclass
class FeatureDefinition:
    """Definition of a feature from feature_list.json."""

    index: int
    category: str
    description: str
    steps: list[str]
    passes: bool

    @property
    def test_status(self) -> TestStatus:
        """Infer test status from feature data."""
        if self.passes:
            return TestStatus.PASSING
        return TestStatus.FAILING


@dataclass
class TestabilityAnalysis:
    """Analysis of whether a feature can be tested programmatically."""

    feature_index: int
    is_testable: bool
    reason: str
    recommended_test_file: str | None = None


@dataclass
class FeatureValidationReport:
    """Complete validation report for all features."""

    total_features: int
    passing_features: int
    failing_features: int
    untestable_features: int
    test_coverage_percent: float
    features_by_category: dict[str, int]
    testability_analysis: list[TestabilityAnalysis]

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for JSON export."""
        return {
            "total_features": self.total_features,
            "passing_features": self.passing_features,
            "failing_features": self.failing_features,
            "untestable_features": self.untestable_features,
            "test_coverage_percent": self.test_coverage_percent,
            "features_by_category": self.features_by_category,
            "testability_analysis": [
                {
                    "feature_index": analysis.feature_index,
                    "is_testable": analysis.is_testable,
                    "reason": analysis.reason,
                    "recommended_test_file": analysis.recommended_test_file,
                }
                for analysis in self.testability_analysis
            ],
        }


class FeatureValidator:
    """Validates that features can be tested programmatically."""

    def __init__(self, feature_list_path: Path):
        """Initialize validator with feature list.

        Args:
            feature_list_path: Path to feature_list.json
        """
        self.feature_list_path = feature_list_path
        self.features: list[FeatureDefinition] = []

    def load_features(self) -> list[FeatureDefinition]:
        """Load and parse all features from feature_list.json.

        Returns:
            List of FeatureDefinition objects

        Raises:
            FileNotFoundError: If feature_list.json doesn't exist
            json.JSONDecodeError: If feature_list.json is invalid
        """
        if not self.feature_list_path.exists():
            raise FileNotFoundError(f"Feature list not found: {self.feature_list_path}")

        with open(self.feature_list_path, "r") as f:
            data = json.load(f)

        if not isinstance(data, list):
            raise ValueError("Feature list must be a JSON array")

        self.features = []
        for i, feature_data in enumerate(data):
            feature = FeatureDefinition(
                index=i,
                category=feature_data.get("category", "unknown"),
                description=feature_data.get("description", ""),
                steps=feature_data.get("steps", []),
                passes=feature_data.get("passes", False),
            )
            self.features.append(feature)

        return self.features

    def analyze_testability(self, feature: FeatureDefinition) -> TestabilityAnalysis:
        """Analyze whether a feature can be tested programmatically.

        Args:
            feature: Feature to analyze

        Returns:
            TestabilityAnalysis with testability assessment
        """
        # Features requiring browser interaction
        if any(
            keyword in feature.description.lower()
            for keyword in ["screenshot", "navigate to", "verify in browser"]
        ):
            return TestabilityAnalysis(
                feature_index=feature.index,
                is_testable=False,
                reason="Requires manual browser interaction and screenshot capture",
                recommended_test_file=None,
            )

        # Features requiring actual OpenROAD execution in Docker
        if "end-to-end" in feature.description.lower() and any(
            keyword in feature.description.lower()
            for keyword in ["nangate45", "asap7", "sky130", "complete", "study"]
        ):
            return TestabilityAnalysis(
                feature_index=feature.index,
                is_testable=True,
                reason="Requires OpenROAD execution (marked @pytest.mark.slow)",
                recommended_test_file=f"tests/test_{feature.description.split(':')[1].strip().replace(' ', '_').lower()[:40]}.py"
                if ":" in feature.description
                else "tests/test_e2e.py",
            )

        # Features requiring Ray Dashboard interaction
        if "ray dashboard" in feature.description.lower() and any(
            keyword in feature.description.lower()
            for keyword in ["displays", "shows", "provides", "ui/ux"]
        ):
            return TestabilityAnalysis(
                feature_index=feature.index,
                is_testable=False,
                reason="Requires visual validation of Ray Dashboard UI",
                recommended_test_file=None,
            )

        # Features requiring extreme scenarios
        if "extreme scenario" in feature.description.lower():
            return TestabilityAnalysis(
                feature_index=feature.index,
                is_testable=True,
                reason="Requires large-scale or stress test (marked @pytest.mark.slow)",
                recommended_test_file="tests/test_extreme_scenarios.py",
            )

        # All other features are testable with unit/integration tests
        # Infer test file from category and description
        category_prefix = feature.category if feature.category else "functional"
        desc_words = feature.description.lower().replace(":", "").split()[:4]
        test_name = "_".join(desc_words)

        return TestabilityAnalysis(
            feature_index=feature.index,
            is_testable=True,
            reason="Can be tested with unit or integration tests",
            recommended_test_file=f"tests/test_{test_name}.py",
        )

    def validate_all_features(self) -> FeatureValidationReport:
        """Validate all features and generate comprehensive report.

        Returns:
            FeatureValidationReport with complete analysis
        """
        if not self.features:
            self.load_features()

        testability_analyses = [self.analyze_testability(f) for f in self.features]

        # Count features by status
        passing = sum(1 for f in self.features if f.passes)
        failing = sum(1 for f in self.features if not f.passes)
        untestable = sum(1 for a in testability_analyses if not a.is_testable)

        # Count features by category
        features_by_category: dict[str, int] = {}
        for feature in self.features:
            cat = feature.category if feature.category else "unknown"
            features_by_category[cat] = features_by_category.get(cat, 0) + 1

        # Calculate test coverage (passing / total)
        coverage = (passing / len(self.features) * 100) if self.features else 0.0

        return FeatureValidationReport(
            total_features=len(self.features),
            passing_features=passing,
            failing_features=failing,
            untestable_features=untestable,
            test_coverage_percent=coverage,
            features_by_category=features_by_category,
            testability_analysis=testability_analyses,
        )

    def identify_untestable_features(self) -> list[tuple[int, FeatureDefinition, str]]:
        """Identify features that cannot be tested programmatically.

        Returns:
            List of (index, feature, reason) tuples for untestable features
        """
        if not self.features:
            self.load_features()

        untestable = []
        for feature in self.features:
            analysis = self.analyze_testability(feature)
            if not analysis.is_testable:
                untestable.append((feature.index, feature, analysis.reason))

        return untestable

    def generate_test_coverage_report(self, output_path: Path) -> None:
        """Generate a comprehensive test coverage report.

        Args:
            output_path: Path to write the JSON report
        """
        report = self.validate_all_features()

        with open(output_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)


def load_and_validate_features(feature_list_path: Path) -> FeatureValidationReport:
    """Convenience function to load and validate all features.

    Args:
        feature_list_path: Path to feature_list.json

    Returns:
        FeatureValidationReport with complete analysis
    """
    validator = FeatureValidator(feature_list_path)
    validator.load_features()
    return validator.validate_all_features()


def verify_feature_list_integrity(feature_list_path: Path) -> bool:
    """Verify that feature_list.json has valid structure.

    Args:
        feature_list_path: Path to feature_list.json

    Returns:
        True if valid, False otherwise
    """
    try:
        with open(feature_list_path, "r") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return False

        # Verify each feature has required fields
        for i, feature in enumerate(data):
            if not isinstance(feature, dict):
                return False

            required_fields = ["category", "description", "steps", "passes"]
            for field in required_fields:
                if field not in feature:
                    return False

            # Verify steps is a list
            if not isinstance(feature["steps"], list):
                return False

            # Verify passes is a boolean
            if not isinstance(feature["passes"], bool):
                return False

        return True

    except (FileNotFoundError, json.JSONDecodeError):
        return False
