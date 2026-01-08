"""
Tests for progress report generation.

Feature: Generate progress report showing percentage of features passing
"""

import pytest
from io import StringIO

from src.tracking.feature_loader import FeatureDefinition, load_feature_list
from src.tracking.progress_report import ProgressReport, generate_progress_report


class TestProgressReportGeneration:
    """Test progress report generation."""

    def test_load_feature_list(self):
        """Step 1: Load feature_list.json."""
        features = load_feature_list()
        assert features is not None
        assert len(features) > 0

    def test_count_total_features(self):
        """Step 2: Count total features."""
        features = load_feature_list()
        total_count = len(features)

        assert total_count > 0
        print(f"Total features: {total_count}")

    def test_count_passing_features(self):
        """Step 3: Count features with passes=true."""
        features = load_feature_list()
        passing_count = sum(1 for f in features if f.passes)

        assert passing_count >= 0  # Can be 0 if all failing
        print(f"Passing features: {passing_count}")

    def test_calculate_completion_percentage(self):
        """Step 4: Calculate completion percentage."""
        features = load_feature_list()
        total = len(features)
        passing = sum(1 for f in features if f.passes)

        percentage = (passing / total * 100) if total > 0 else 0.0

        assert 0.0 <= percentage <= 100.0
        print(f"Completion: {percentage:.1f}%")

    def test_generate_report_showing_progress_by_category(self):
        """Step 5: Generate report showing progress by category."""
        features = load_feature_list()
        report = generate_progress_report(features)

        assert report.functional_total > 0
        assert report.style_total > 0
        assert report.functional_passing >= 0
        assert report.style_passing >= 0

        print(f"Functional: {report.functional_passing}/{report.functional_total}")
        print(f"Style: {report.style_passing}/{report.style_total}")

    def test_display_report_in_human_readable_format(self):
        """Step 6: Display report in human-readable format."""
        features = load_feature_list()
        report = generate_progress_report(features)

        # Format as string
        output = report.format_report(detailed=True)

        assert isinstance(output, str)
        assert len(output) > 0
        assert "Progress Report" in output
        assert "Overall Progress" in output
        assert "Completion:" in output

        # Print to verify readability
        print("\n" + output)


class TestProgressReportObject:
    """Test ProgressReport dataclass."""

    def test_create_progress_report(self):
        """Create a ProgressReport object."""
        report = ProgressReport(
            total_features=100,
            passing_features=60,
            failing_features=40,
            completion_percentage=60.0,
            functional_passing=40,
            functional_total=70,
            style_passing=20,
            style_total=30,
        )

        assert report.total_features == 100
        assert report.passing_features == 60
        assert report.failing_features == 40
        assert report.completion_percentage == 60.0

    def test_functional_percentage_property(self):
        """Test functional_percentage property."""
        report = ProgressReport(
            total_features=100,
            passing_features=60,
            failing_features=40,
            completion_percentage=60.0,
            functional_passing=40,
            functional_total=80,
            style_passing=20,
            style_total=20,
        )

        assert report.functional_percentage == 50.0  # 40/80

    def test_style_percentage_property(self):
        """Test style_percentage property."""
        report = ProgressReport(
            total_features=100,
            passing_features=75,
            failing_features=25,
            completion_percentage=75.0,
            functional_passing=60,
            functional_total=80,
            style_passing=15,
            style_total=20,
        )

        assert report.style_percentage == 75.0  # 15/20

    def test_percentage_properties_handle_zero_division(self):
        """Percentage properties should handle zero totals gracefully."""
        report = ProgressReport(
            total_features=0,
            passing_features=0,
            failing_features=0,
            completion_percentage=0.0,
            functional_passing=0,
            functional_total=0,
            style_passing=0,
            style_total=0,
        )

        assert report.functional_percentage == 0.0
        assert report.style_percentage == 0.0

    def test_format_report_basic(self):
        """Test basic report formatting."""
        report = ProgressReport(
            total_features=200,
            passing_features=133,
            failing_features=67,
            completion_percentage=66.5,
            functional_passing=100,
            functional_total=150,
            style_passing=33,
            style_total=50,
        )

        output = report.format_report(detailed=False)

        assert "133/200" in output
        assert "66.5%" in output
        assert "Progress Report" in output

    def test_format_report_detailed(self):
        """Test detailed report formatting with category breakdown."""
        report = ProgressReport(
            total_features=200,
            passing_features=133,
            failing_features=67,
            completion_percentage=66.5,
            functional_passing=100,
            functional_total=150,
            style_passing=33,
            style_total=50,
        )

        output = report.format_report(detailed=True)

        assert "Functional Features: 100/150" in output
        assert "Style Features: 33/50" in output
        assert "Breakdown by Category" in output

    def test_print_report_to_stdout(self):
        """Test printing report to stdout."""
        report = ProgressReport(
            total_features=100,
            passing_features=50,
            failing_features=50,
            completion_percentage=50.0,
            functional_passing=30,
            functional_total=60,
            style_passing=20,
            style_total=40,
        )

        # Capture output
        output = StringIO()
        report.print_report(file=output)

        result = output.getvalue()
        assert len(result) > 0
        assert "50/100" in result

    def test_to_dict(self):
        """Test conversion to dictionary."""
        report = ProgressReport(
            total_features=200,
            passing_features=133,
            failing_features=67,
            completion_percentage=66.5,
            functional_passing=100,
            functional_total=150,
            style_passing=33,
            style_total=50,
        )

        data = report.to_dict()

        assert data["total_features"] == 200
        assert data["passing_features"] == 133
        assert data["failing_features"] == 67
        assert data["completion_percentage"] == 66.5
        assert data["functional_passing"] == 100
        assert data["functional_total"] == 150
        assert data["style_passing"] == 33
        assert data["style_total"] == 50


class TestGenerateProgressReport:
    """Test generate_progress_report function."""

    def test_generate_from_real_feature_list(self):
        """Generate progress report from actual feature list."""
        features = load_feature_list()
        report = generate_progress_report(features)

        assert report.total_features == len(features)
        assert report.passing_features + report.failing_features == len(features)
        assert 0.0 <= report.completion_percentage <= 100.0

    def test_generate_from_sample_features(self):
        """Generate progress report from sample feature list."""
        features = [
            FeatureDefinition("functional", "Feature 1", ["Step 1"], True),
            FeatureDefinition("functional", "Feature 2", ["Step 1"], False),
            FeatureDefinition("style", "Feature 3", ["Step 1"], True),
            FeatureDefinition("style", "Feature 4", ["Step 1"], False),
        ]

        report = generate_progress_report(features)

        assert report.total_features == 4
        assert report.passing_features == 2
        assert report.failing_features == 2
        assert report.completion_percentage == 50.0
        assert report.functional_total == 2
        assert report.functional_passing == 1
        assert report.style_total == 2
        assert report.style_passing == 1

    def test_generate_from_all_passing(self):
        """Generate report when all features pass."""
        features = [
            FeatureDefinition("functional", "Feature 1", ["Step 1"], True),
            FeatureDefinition("functional", "Feature 2", ["Step 1"], True),
        ]

        report = generate_progress_report(features)

        assert report.total_features == 2
        assert report.passing_features == 2
        assert report.failing_features == 0
        assert report.completion_percentage == 100.0

    def test_generate_from_all_failing(self):
        """Generate report when all features fail."""
        features = [
            FeatureDefinition("functional", "Feature 1", ["Step 1"], False),
            FeatureDefinition("style", "Feature 2", ["Step 1"], False),
        ]

        report = generate_progress_report(features)

        assert report.total_features == 2
        assert report.passing_features == 0
        assert report.failing_features == 2
        assert report.completion_percentage == 0.0

    def test_generate_from_empty_list(self):
        """Generate report from empty feature list."""
        features = []

        report = generate_progress_report(features)

        assert report.total_features == 0
        assert report.passing_features == 0
        assert report.failing_features == 0
        assert report.completion_percentage == 0.0


class TestProgressReportVisualElements:
    """Test visual elements in progress reports."""

    def test_progress_bar_in_report(self):
        """Verify progress bar is included in report."""
        report = ProgressReport(
            total_features=100,
            passing_features=50,
            failing_features=50,
            completion_percentage=50.0,
            functional_passing=30,
            functional_total=60,
            style_passing=20,
            style_total=40,
        )

        output = report.format_report()

        # Progress bar should contain filled and empty characters
        assert "█" in output or "░" in output  # Progress bar characters

    def test_detailed_report_has_category_bars(self):
        """Verify detailed report includes bars for each category."""
        report = ProgressReport(
            total_features=100,
            passing_features=60,
            failing_features=40,
            completion_percentage=60.0,
            functional_passing=40,
            functional_total=70,
            style_passing=20,
            style_total=30,
        )

        output = report.format_report(detailed=True)

        # Should have multiple progress bars (overall + categories)
        bar_count = output.count("[")
        assert bar_count >= 3  # Overall, functional, style
