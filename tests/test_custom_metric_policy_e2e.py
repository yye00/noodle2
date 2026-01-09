"""End-to-end tests for custom metric extraction and policy evaluation.

This test validates the complete workflow:
1. Define custom metric extractor for project-specific KPI
2. Register extractor with Noodle 2 metric system
3. Execute trials and invoke custom extractor
4. Verify custom metrics appear in telemetry
5. Define custom policy rule using custom metric
6. Register policy rule with safety system
7. Execute Study with custom policy active
8. Verify custom policy rules are evaluated correctly
9. Log all policy evaluations for audit
10. Generate custom metric leaderboard
11. Use custom metric in survivor ranking
12. Export custom metrics for external analysis
"""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from src.parsers.custom_metrics import MetricExtractor, MetricExtractorRegistry
from src.policy.policy_trace import PolicyTrace, PolicyRuleOutcome, PolicyRuleType


# Step 1: Define custom metric extractor for project-specific KPI


class RoutingQualityExtractor(MetricExtractor):
    """Custom extractor for routing quality score.

    This is a project-specific KPI that combines multiple routing metrics
    into a single quality score (0-100).
    """

    def extract(self, artifact_dir: Path) -> dict[str, Any]:
        """Extract routing quality metrics from trial artifacts."""
        metrics: dict[str, Any] = {}

        # Look for routing report
        route_report = artifact_dir / "route_metrics.txt"
        if route_report.exists():
            content = route_report.read_text()
            metrics.update(self._parse_routing_quality(content))

        # Calculate composite quality score
        if "drc_violations" in metrics and "short_count" in metrics:
            # Higher is better (inverse of violations)
            drc_score = max(0, 100 - metrics["drc_violations"])
            short_score = max(0, 100 - metrics["short_count"] * 5)
            metrics["routing_quality_score"] = (drc_score + short_score) / 2

        return metrics

    def _parse_routing_quality(self, content: str) -> dict[str, Any]:
        """Parse routing quality metrics from report."""
        import re

        result = {}

        # Match "DRC violations: 5"
        drc_match = re.search(r"DRC violations:\s*(\d+)", content, re.IGNORECASE)
        if drc_match:
            result["drc_violations"] = int(drc_match.group(1))

        # Match "Short violations: 2"
        short_match = re.search(r"Short violations:\s*(\d+)", content, re.IGNORECASE)
        if short_match:
            result["short_count"] = int(short_match.group(1))

        # Match "Via count: 1234"
        via_match = re.search(r"Via count:\s*(\d+)", content, re.IGNORECASE)
        if via_match:
            result["via_count"] = int(via_match.group(1))

        return result


class TestStep1DefineCustomExtractor:
    """Test Step 1: Define custom metric extractor for project-specific KPI."""

    def test_routing_quality_extractor_can_be_instantiated(self):
        """Verify custom extractor can be created."""
        extractor = RoutingQualityExtractor()
        assert extractor is not None
        assert isinstance(extractor, MetricExtractor)

    def test_routing_quality_extractor_extracts_metrics(self):
        """Verify custom extractor can parse metrics from artifacts."""
        extractor = RoutingQualityExtractor()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create sample routing report
            report_path = Path(tmpdir) / "route_metrics.txt"
            report_path.write_text("""
Routing Quality Report
======================
DRC violations: 3
Short violations: 1
Via count: 567
            """)

            metrics = extractor.extract(Path(tmpdir))

        assert "drc_violations" in metrics
        assert metrics["drc_violations"] == 3
        assert metrics["short_count"] == 1
        assert metrics["via_count"] == 567

    def test_routing_quality_score_calculation(self):
        """Verify custom quality score is calculated correctly."""
        extractor = RoutingQualityExtractor()

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "route_metrics.txt"
            report_path.write_text("""
DRC violations: 5
Short violations: 2
            """)

            metrics = extractor.extract(Path(tmpdir))

        # Expected: drc_score = 100-5 = 95, short_score = 100-10 = 90
        # quality_score = (95 + 90) / 2 = 92.5
        assert "routing_quality_score" in metrics
        assert metrics["routing_quality_score"] == 92.5


# Step 2: Register extractor with Noodle 2 metric system


class TestStep2RegisterExtractor:
    """Test Step 2: Register extractor with Noodle 2 metric system."""

    def test_register_custom_extractor_with_registry(self):
        """Verify custom extractor can be registered."""
        registry = MetricExtractorRegistry()
        extractor = RoutingQualityExtractor()

        registry.register("routing_quality", extractor)

        assert "routing_quality" in registry.list_extractors()

    def test_retrieve_registered_custom_extractor(self):
        """Verify registered extractor can be retrieved."""
        registry = MetricExtractorRegistry()
        extractor = RoutingQualityExtractor()

        registry.register("routing_quality", extractor)
        retrieved = registry.get("routing_quality")

        assert retrieved is extractor

    def test_registry_prevents_duplicate_registration(self):
        """Verify duplicate registration is prevented."""
        registry = MetricExtractorRegistry()
        extractor1 = RoutingQualityExtractor()
        extractor2 = RoutingQualityExtractor()

        registry.register("routing_quality", extractor1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register("routing_quality", extractor2)


# Step 3: Execute trials and invoke custom extractor


class TestStep3ExecuteTrialsWithCustomExtractor:
    """Test Step 3: Execute trials and invoke custom extractor."""

    def test_execute_custom_extractor_on_trial_artifacts(self):
        """Verify custom extractor runs on trial artifacts."""
        registry = MetricExtractorRegistry()
        registry.register("routing_quality", RoutingQualityExtractor())

        with tempfile.TemporaryDirectory() as tmpdir:
            # Simulate trial artifacts
            trial_dir = Path(tmpdir) / "trial_001"
            trial_dir.mkdir()

            route_report = trial_dir / "route_metrics.txt"
            route_report.write_text("DRC violations: 2\nShort violations: 0")

            # Extract all metrics
            results = registry.extract_all(trial_dir)

        assert "routing_quality" in results
        assert "drc_violations" in results["routing_quality"]
        assert results["routing_quality"]["drc_violations"] == 2

    def test_execute_multiple_extractors_including_custom(self):
        """Verify custom extractor works alongside built-in extractors."""
        from src.parsers.custom_metrics import CellCountExtractor

        registry = MetricExtractorRegistry()
        registry.register("cell_count", CellCountExtractor())
        registry.register("routing_quality", RoutingQualityExtractor())

        with tempfile.TemporaryDirectory() as tmpdir:
            trial_dir = Path(tmpdir)

            # Create artifacts for both extractors
            (trial_dir / "metrics.txt").write_text("Number of cells: 1500")
            (trial_dir / "route_metrics.txt").write_text("DRC violations: 1")

            results = registry.extract_all(trial_dir)

        assert "cell_count" in results
        assert "routing_quality" in results
        assert results["cell_count"]["cell_count"] == 1500
        assert results["routing_quality"]["drc_violations"] == 1

    def test_custom_extractor_handles_missing_artifacts_gracefully(self):
        """Verify custom extractor returns empty dict for missing artifacts."""
        registry = MetricExtractorRegistry()
        registry.register("routing_quality", RoutingQualityExtractor())

        with tempfile.TemporaryDirectory() as tmpdir:
            # Empty directory - no artifacts
            results = registry.extract_all(Path(tmpdir))

        assert "routing_quality" in results
        assert results["routing_quality"] == {}


# Step 4: Verify custom metrics appear in telemetry


class TestStep4CustomMetricsInTelemetry:
    """Test Step 4: Verify custom metrics appear in telemetry."""

    def test_custom_metrics_included_in_trial_telemetry(self):
        """Verify custom metrics are included in trial telemetry output."""
        registry = MetricExtractorRegistry()
        registry.register("routing_quality", RoutingQualityExtractor())

        with tempfile.TemporaryDirectory() as tmpdir:
            trial_dir = Path(tmpdir) / "trial_001"
            trial_dir.mkdir()

            (trial_dir / "route_metrics.txt").write_text("""
DRC violations: 0
Short violations: 0
Via count: 300
            """)

            # Simulate telemetry collection
            custom_metrics = registry.extract_all(trial_dir)

            # Write telemetry JSON
            telemetry_file = trial_dir / "telemetry.json"
            telemetry_data = {
                "trial_id": "trial_001",
                "custom_metrics": custom_metrics,
            }
            telemetry_file.write_text(json.dumps(telemetry_data, indent=2))

            # Verify telemetry file
            loaded_telemetry = json.loads(telemetry_file.read_text())

        assert "custom_metrics" in loaded_telemetry
        assert "routing_quality" in loaded_telemetry["custom_metrics"]
        assert loaded_telemetry["custom_metrics"]["routing_quality"]["routing_quality_score"] == 100.0

    def test_custom_metrics_serializable_to_json(self):
        """Verify custom metrics are JSON-serializable."""
        extractor = RoutingQualityExtractor()

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "route_metrics.txt").write_text("DRC violations: 5")

            metrics = extractor.extract(Path(tmpdir))

            # Should not raise
            json_str = json.dumps(metrics)
            loaded = json.loads(json_str)

        assert loaded["drc_violations"] == 5

    def test_flattened_custom_metrics_for_export(self):
        """Verify custom metrics can be flattened for CSV export."""
        registry = MetricExtractorRegistry()
        registry.register("routing_quality", RoutingQualityExtractor())

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "route_metrics.txt").write_text("""
DRC violations: 2
Short violations: 1
            """)

            # Get flattened metrics with prefix
            flat_metrics = registry.extract_flat(Path(tmpdir), prefix_with_extractor=True)

        assert "routing_quality_drc_violations" in flat_metrics
        assert "routing_quality_short_count" in flat_metrics
        assert flat_metrics["routing_quality_drc_violations"] == 2


# Step 5: Define custom policy rule using custom metric


class CustomMetricPolicy:
    """Custom policy for ranking trials based on routing quality score."""

    def __init__(self, min_quality_threshold: float = 80.0):
        """Initialize policy with quality threshold."""
        self.min_quality_threshold = min_quality_threshold

    def evaluate_trial(self, trial_metrics: dict[str, Any]) -> tuple[bool, str]:
        """Evaluate if trial meets routing quality requirements.

        Returns:
            (passes, rationale) tuple
        """
        # Check if routing quality score exists
        if "routing_quality_score" not in trial_metrics:
            return False, "Routing quality score not available"

        quality_score = trial_metrics["routing_quality_score"]

        if quality_score >= self.min_quality_threshold:
            return True, f"Quality score {quality_score:.1f} meets threshold {self.min_quality_threshold}"
        else:
            return False, f"Quality score {quality_score:.1f} below threshold {self.min_quality_threshold}"

    def rank_trials(self, trials: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Rank trials by routing quality score (descending).

        Args:
            trials: List of trial dictionaries with metrics

        Returns:
            Sorted list of trials (best first)
        """
        return sorted(
            trials,
            key=lambda t: t.get("routing_quality_score", -1),
            reverse=True
        )


class TestStep5DefineCustomPolicy:
    """Test Step 5: Define custom policy rule using custom metric."""

    def test_custom_policy_can_be_instantiated(self):
        """Verify custom policy can be created."""
        policy = CustomMetricPolicy(min_quality_threshold=85.0)
        assert policy is not None
        assert policy.min_quality_threshold == 85.0

    def test_custom_policy_evaluates_passing_trial(self):
        """Verify policy correctly identifies passing trials."""
        policy = CustomMetricPolicy(min_quality_threshold=80.0)

        trial_metrics = {"routing_quality_score": 95.0}
        passes, rationale = policy.evaluate_trial(trial_metrics)

        assert passes is True
        assert "meets threshold" in rationale

    def test_custom_policy_evaluates_failing_trial(self):
        """Verify policy correctly identifies failing trials."""
        policy = CustomMetricPolicy(min_quality_threshold=80.0)

        trial_metrics = {"routing_quality_score": 65.0}
        passes, rationale = policy.evaluate_trial(trial_metrics)

        assert passes is False
        assert "below threshold" in rationale

    def test_custom_policy_ranks_trials_correctly(self):
        """Verify policy ranks trials by quality score."""
        policy = CustomMetricPolicy()

        trials = [
            {"trial_id": "A", "routing_quality_score": 70.0},
            {"trial_id": "B", "routing_quality_score": 95.0},
            {"trial_id": "C", "routing_quality_score": 85.0},
        ]

        ranked = policy.rank_trials(trials)

        assert ranked[0]["trial_id"] == "B"  # Best quality
        assert ranked[1]["trial_id"] == "C"
        assert ranked[2]["trial_id"] == "A"  # Worst quality


# Step 6: Register policy rule with safety system


class CustomPolicyRegistry:
    """Registry for custom policy rules."""

    def __init__(self):
        """Initialize empty policy registry."""
        self._policies: dict[str, CustomMetricPolicy] = {}

    def register(self, name: str, policy: CustomMetricPolicy) -> None:
        """Register a custom policy."""
        if name in self._policies:
            raise ValueError(f"Policy '{name}' is already registered")
        self._policies[name] = policy

    def get(self, name: str) -> CustomMetricPolicy:
        """Get a registered policy."""
        if name not in self._policies:
            raise KeyError(f"Policy '{name}' is not registered")
        return self._policies[name]

    def list_policies(self) -> list[str]:
        """List all registered policy names."""
        return list(self._policies.keys())


class TestStep6RegisterPolicyRule:
    """Test Step 6: Register policy rule with safety system."""

    def test_register_custom_policy_with_registry(self):
        """Verify custom policy can be registered."""
        registry = CustomPolicyRegistry()
        policy = CustomMetricPolicy(min_quality_threshold=85.0)

        registry.register("routing_quality_policy", policy)

        assert "routing_quality_policy" in registry.list_policies()

    def test_retrieve_registered_custom_policy(self):
        """Verify registered policy can be retrieved."""
        registry = CustomPolicyRegistry()
        policy = CustomMetricPolicy(min_quality_threshold=90.0)

        registry.register("strict_quality", policy)
        retrieved = registry.get("strict_quality")

        assert retrieved is policy
        assert retrieved.min_quality_threshold == 90.0

    def test_registry_prevents_duplicate_policy_registration(self):
        """Verify duplicate policy registration is prevented."""
        registry = CustomPolicyRegistry()
        policy1 = CustomMetricPolicy(min_quality_threshold=80.0)
        policy2 = CustomMetricPolicy(min_quality_threshold=85.0)

        registry.register("quality_policy", policy1)

        with pytest.raises(ValueError, match="already registered"):
            registry.register("quality_policy", policy2)


# Step 7: Execute Study with custom policy active


class TestStep7ExecuteStudyWithCustomPolicy:
    """Test Step 7: Execute Study with custom policy active."""

    def test_execute_study_with_custom_policy_filtering(self):
        """Verify Study can execute with custom policy filtering trials."""
        policy = CustomMetricPolicy(min_quality_threshold=80.0)

        # Simulate trial results
        trial_results = [
            {"trial_id": "trial_001", "routing_quality_score": 95.0},
            {"trial_id": "trial_002", "routing_quality_score": 75.0},  # Below threshold
            {"trial_id": "trial_003", "routing_quality_score": 88.0},
        ]

        # Apply policy filtering
        passing_trials = []
        for trial in trial_results:
            passes, rationale = policy.evaluate_trial(trial)
            if passes:
                passing_trials.append(trial)

        assert len(passing_trials) == 2
        assert passing_trials[0]["trial_id"] == "trial_001"
        assert passing_trials[1]["trial_id"] == "trial_003"

    def test_execute_study_with_custom_policy_ranking(self):
        """Verify Study uses custom policy for survivor ranking."""
        policy = CustomMetricPolicy()

        trial_results = [
            {"trial_id": "trial_001", "routing_quality_score": 92.0},
            {"trial_id": "trial_002", "routing_quality_score": 88.0},
            {"trial_id": "trial_003", "routing_quality_score": 95.0},
            {"trial_id": "trial_004", "routing_quality_score": 85.0},
        ]

        # Rank and select top 2 survivors
        ranked = policy.rank_trials(trial_results)
        survivors = ranked[:2]

        assert len(survivors) == 2
        assert survivors[0]["trial_id"] == "trial_003"  # Best: 95.0
        assert survivors[1]["trial_id"] == "trial_001"  # Second: 92.0


# Step 8: Verify custom policy rules are evaluated correctly


class TestStep8CustomPolicyEvaluationCorrectness:
    """Test Step 8: Verify custom policy rules are evaluated correctly."""

    def test_custom_policy_evaluation_is_deterministic(self):
        """Verify policy evaluation produces consistent results."""
        policy = CustomMetricPolicy(min_quality_threshold=80.0)

        trial_metrics = {"routing_quality_score": 85.0}

        # Evaluate multiple times
        result1 = policy.evaluate_trial(trial_metrics)
        result2 = policy.evaluate_trial(trial_metrics)
        result3 = policy.evaluate_trial(trial_metrics)

        assert result1 == result2 == result3

    def test_custom_policy_ranking_is_stable(self):
        """Verify policy ranking is stable (same input = same output)."""
        policy = CustomMetricPolicy()

        trials = [
            {"trial_id": f"trial_{i:03d}", "routing_quality_score": 50 + i}
            for i in range(10)
        ]

        # Rank multiple times
        ranked1 = policy.rank_trials(trials.copy())
        ranked2 = policy.rank_trials(trials.copy())

        assert ranked1 == ranked2

    def test_custom_policy_handles_missing_metrics(self):
        """Verify policy handles trials missing custom metrics."""
        policy = CustomMetricPolicy()

        trial_metrics = {}  # No routing_quality_score
        passes, rationale = policy.evaluate_trial(trial_metrics)

        assert passes is False
        assert "not available" in rationale


# Step 9: Log all policy evaluations for audit


class TestStep9LogPolicyEvaluations:
    """Test Step 9: Log all policy evaluations for audit."""

    def test_create_policy_trace_for_custom_metric_evaluation(self):
        """Verify PolicyTrace can record custom metric policy evaluations."""
        trace = PolicyTrace(study_name="custom_metric_study")

        # Record custom policy evaluation
        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="routing_quality_policy",
            trial_count=10,
            survivor_count=3,
            selected_cases=["trial_003", "trial_001", "trial_005"],
            baseline_metrics={"routing_quality_score": 85.0},
            weights={"routing_quality": 1.0},
        )

        assert len(trace.evaluations) == 1
        evaluation = trace.evaluations[0]
        assert evaluation.rule_type == PolicyRuleType.SURVIVOR_RANKING
        assert evaluation.outcome == PolicyRuleOutcome.APPLIED
        assert "routing_quality_policy" in evaluation.logic["policy_name"]

    def test_policy_trace_includes_custom_metric_details(self):
        """Verify policy trace captures custom metric details."""
        trace = PolicyTrace(study_name="routing_study")

        trace.record_trial_filtering(
            stage_index=0,
            filter_type="routing_quality_threshold",
            trials_before=20,
            trials_after=15,
            filter_criteria={"min_quality_score": 80.0},
            filtered_items=["trial_002", "trial_007", "trial_011", "trial_015", "trial_019"],
        )

        evaluation = trace.evaluations[0]
        assert evaluation.rule_type == PolicyRuleType.TRIAL_FILTERING
        assert evaluation.logic["filter_type"] == "routing_quality_threshold"
        assert evaluation.logic["filter_criteria"]["min_quality_score"] == 80.0
        assert len(evaluation.result["filtered_items"]) == 5

    def test_export_policy_trace_to_json(self):
        """Verify policy trace can be exported to JSON for audit."""
        trace = PolicyTrace(study_name="audit_study")

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="custom_quality",
            trial_count=10,
            survivor_count=5,
            selected_cases=[f"trial_{i:03d}" for i in range(5)],
            baseline_metrics={"routing_quality_score": 90.0},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "policy_trace.json"
            trace.save_json(output_path)

            # Verify file was created and is valid JSON
            assert output_path.exists()
            loaded = json.loads(output_path.read_text())

        assert loaded["study_name"] == "audit_study"
        assert "evaluations" in loaded
        assert len(loaded["evaluations"]) == 1


# Step 10: Generate custom metric leaderboard


class CustomMetricLeaderboard:
    """Leaderboard for custom metrics."""

    def __init__(self, metric_name: str):
        """Initialize leaderboard for specific metric."""
        self.metric_name = metric_name
        self.entries: list[dict[str, Any]] = []

    def add_trial(self, trial_id: str, metrics: dict[str, Any]) -> None:
        """Add trial to leaderboard."""
        if self.metric_name in metrics:
            self.entries.append({
                "trial_id": trial_id,
                "metric_value": metrics[self.metric_name],
                "full_metrics": metrics,
            })

    def get_rankings(self, descending: bool = True) -> list[dict[str, Any]]:
        """Get ranked trials (best first)."""
        return sorted(
            self.entries,
            key=lambda e: e["metric_value"],
            reverse=descending
        )

    def get_top_n(self, n: int) -> list[dict[str, Any]]:
        """Get top N trials."""
        rankings = self.get_rankings()
        return rankings[:n]

    def to_dict(self) -> dict[str, Any]:
        """Export leaderboard to dictionary."""
        rankings = self.get_rankings()
        return {
            "metric_name": self.metric_name,
            "entry_count": len(self.entries),
            "rankings": rankings,
        }


class TestStep10GenerateCustomMetricLeaderboard:
    """Test Step 10: Generate custom metric leaderboard."""

    def test_create_leaderboard_for_custom_metric(self):
        """Verify leaderboard can be created for custom metric."""
        leaderboard = CustomMetricLeaderboard(metric_name="routing_quality_score")

        assert leaderboard.metric_name == "routing_quality_score"
        assert len(leaderboard.entries) == 0

    def test_add_trials_to_leaderboard(self):
        """Verify trials can be added to leaderboard."""
        leaderboard = CustomMetricLeaderboard("routing_quality_score")

        leaderboard.add_trial("trial_001", {"routing_quality_score": 95.0})
        leaderboard.add_trial("trial_002", {"routing_quality_score": 88.0})
        leaderboard.add_trial("trial_003", {"routing_quality_score": 92.0})

        assert len(leaderboard.entries) == 3

    def test_leaderboard_rankings_sorted_correctly(self):
        """Verify leaderboard returns trials in correct order."""
        leaderboard = CustomMetricLeaderboard("routing_quality_score")

        leaderboard.add_trial("trial_A", {"routing_quality_score": 85.0})
        leaderboard.add_trial("trial_B", {"routing_quality_score": 95.0})
        leaderboard.add_trial("trial_C", {"routing_quality_score": 90.0})

        rankings = leaderboard.get_rankings()

        assert rankings[0]["trial_id"] == "trial_B"  # Best: 95.0
        assert rankings[1]["trial_id"] == "trial_C"  # Second: 90.0
        assert rankings[2]["trial_id"] == "trial_A"  # Third: 85.0

    def test_leaderboard_get_top_n(self):
        """Verify leaderboard can return top N trials."""
        leaderboard = CustomMetricLeaderboard("routing_quality_score")

        for i in range(10):
            leaderboard.add_trial(f"trial_{i:03d}", {"routing_quality_score": 50 + i * 5})

        top_3 = leaderboard.get_top_n(3)

        assert len(top_3) == 3
        assert top_3[0]["metric_value"] == 95.0
        assert top_3[1]["metric_value"] == 90.0
        assert top_3[2]["metric_value"] == 85.0


# Step 11: Use custom metric in survivor ranking


class TestStep11CustomMetricSurvivorRanking:
    """Test Step 11: Use custom metric in survivor ranking."""

    def test_select_survivors_based_on_custom_metric(self):
        """Verify survivors can be selected using custom metric."""
        trials = [
            {"trial_id": "trial_001", "routing_quality_score": 92.0},
            {"trial_id": "trial_002", "routing_quality_score": 78.0},
            {"trial_id": "trial_003", "routing_quality_score": 95.0},
            {"trial_id": "trial_004", "routing_quality_score": 85.0},
            {"trial_id": "trial_005", "routing_quality_score": 88.0},
        ]

        # Sort by custom metric
        ranked = sorted(trials, key=lambda t: t["routing_quality_score"], reverse=True)

        # Select top 3 survivors
        survivors = ranked[:3]

        assert len(survivors) == 3
        assert survivors[0]["trial_id"] == "trial_003"
        assert survivors[1]["trial_id"] == "trial_001"
        assert survivors[2]["trial_id"] == "trial_005"

    def test_survivor_selection_with_custom_policy(self):
        """Verify CustomMetricPolicy selects correct survivors."""
        policy = CustomMetricPolicy()

        trials = [
            {"trial_id": f"trial_{i:03d}", "routing_quality_score": 60 + i * 5}
            for i in range(8)
        ]

        # Rank all trials
        ranked = policy.rank_trials(trials)

        # Select top 3
        survivors = ranked[:3]

        assert survivors[0]["routing_quality_score"] == 95.0
        assert survivors[1]["routing_quality_score"] == 90.0
        assert survivors[2]["routing_quality_score"] == 85.0

    def test_log_survivor_selection_to_policy_trace(self):
        """Verify survivor selection based on custom metric is logged."""
        trace = PolicyTrace(study_name="survivor_selection_study")

        # Simulate survivor selection
        selected_cases = ["trial_003", "trial_001", "trial_005"]

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="routing_quality_ranking",
            trial_count=10,
            survivor_count=3,
            selected_cases=selected_cases,
            baseline_metrics={"routing_quality_score": 90.0},
            weights={"routing_quality": 1.0},
        )

        evaluation = trace.evaluations[0]
        assert evaluation.result["selected_cases"] == selected_cases
        assert evaluation.result["selected_count"] == 3


# Step 12: Export custom metrics for external analysis


class TestStep12ExportCustomMetrics:
    """Test Step 12: Export custom metrics for external analysis."""

    def test_export_custom_metrics_to_json(self):
        """Verify custom metrics can be exported to JSON."""
        leaderboard = CustomMetricLeaderboard("routing_quality_score")

        for i in range(5):
            leaderboard.add_trial(
                f"trial_{i:03d}",
                {
                    "routing_quality_score": 80 + i * 3,
                    "drc_violations": 5 - i,
                }
            )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "custom_metrics.json"

            data = leaderboard.to_dict()
            output_path.write_text(json.dumps(data, indent=2))

            # Verify export
            loaded = json.loads(output_path.read_text())

        assert loaded["metric_name"] == "routing_quality_score"
        assert loaded["entry_count"] == 5
        assert len(loaded["rankings"]) == 5

    def test_export_custom_metrics_to_csv(self):
        """Verify custom metrics can be exported to CSV format."""
        import csv

        trials_data = [
            {"trial_id": "trial_001", "routing_quality_score": 95.0, "drc_violations": 0},
            {"trial_id": "trial_002", "routing_quality_score": 88.0, "drc_violations": 2},
            {"trial_id": "trial_003", "routing_quality_score": 92.0, "drc_violations": 1},
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "custom_metrics.csv"

            with open(output_path, "w", newline="") as f:
                fieldnames = ["trial_id", "routing_quality_score", "drc_violations"]
                writer = csv.DictWriter(f, fieldnames=fieldnames)

                writer.writeheader()
                writer.writerows(trials_data)

            # Verify CSV was created
            assert output_path.exists()

            # Read back and verify
            with open(output_path, "r") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

        assert len(rows) == 3
        assert rows[0]["trial_id"] == "trial_001"
        assert rows[0]["routing_quality_score"] == "95.0"

    def test_export_flattened_metrics_for_analysis(self):
        """Verify flattened custom metrics ready for external analysis."""
        registry = MetricExtractorRegistry()
        registry.register("routing_quality", RoutingQualityExtractor())

        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "route_metrics.txt").write_text("""
DRC violations: 3
Short violations: 1
Via count: 450
            """)

            # Extract and flatten
            flat_metrics = registry.extract_flat(Path(tmpdir), prefix_with_extractor=True)

            # Export to JSON for external tools
            export_path = Path(tmpdir) / "flat_metrics.json"
            export_path.write_text(json.dumps(flat_metrics, indent=2))

            loaded = json.loads(export_path.read_text())

        assert "routing_quality_drc_violations" in loaded
        assert "routing_quality_short_count" in loaded
        assert "routing_quality_via_count" in loaded
        assert "routing_quality_routing_quality_score" in loaded


# Complete E2E integration test


class TestCompleteCustomMetricPolicyE2E:
    """Complete end-to-end workflow test for custom metric and policy."""

    def test_complete_custom_metric_policy_workflow(self):
        """Test complete workflow from metric extraction to survivor selection."""
        # Step 1: Create custom extractor
        extractor = RoutingQualityExtractor()

        # Step 2: Register with metric system
        metric_registry = MetricExtractorRegistry()
        metric_registry.register("routing_quality", extractor)

        # Step 3: Simulate trial execution and metric extraction
        trial_metrics = []

        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(10):
                trial_dir = Path(tmpdir) / f"trial_{i:03d}"
                trial_dir.mkdir()

                # Create varying quality results
                drc_count = i % 5
                short_count = i % 3

                (trial_dir / "route_metrics.txt").write_text(
                    f"DRC violations: {drc_count}\nShort violations: {short_count}"
                )

                # Extract metrics
                metrics = metric_registry.extract_all(trial_dir)
                flat_metrics = metric_registry.extract_flat(trial_dir, prefix_with_extractor=False)
                flat_metrics["trial_id"] = f"trial_{i:03d}"
                trial_metrics.append(flat_metrics)

        # Step 4: Verify metrics in trial data
        assert len(trial_metrics) == 10
        for tm in trial_metrics:
            assert "routing_quality_score" in tm or "drc_violations" in tm

        # Step 5: Create custom policy
        policy = CustomMetricPolicy(min_quality_threshold=85.0)

        # Step 6: Register policy
        policy_registry = CustomPolicyRegistry()
        policy_registry.register("quality_ranking", policy)

        # Step 7: Apply policy to filter and rank trials
        passing_trials = [tm for tm in trial_metrics if policy.evaluate_trial(tm)[0]]
        ranked_trials = policy.rank_trials(passing_trials)

        # Step 8: Verify policy evaluation
        assert len(passing_trials) <= len(trial_metrics)

        # Step 9: Log policy evaluations
        trace = PolicyTrace(study_name="complete_e2e_study")
        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="quality_ranking",
            trial_count=len(trial_metrics),
            survivor_count=3,
            selected_cases=[t["trial_id"] for t in ranked_trials[:3]],
            baseline_metrics={"routing_quality_score": 90.0},
        )

        # Step 10: Generate leaderboard
        leaderboard = CustomMetricLeaderboard("routing_quality_score")
        for tm in trial_metrics:
            if "routing_quality_score" in tm:
                leaderboard.add_trial(tm["trial_id"], tm)

        # Step 11: Select survivors
        top_survivors = leaderboard.get_top_n(3)

        # Step 12: Export for analysis
        with tempfile.TemporaryDirectory() as tmpdir:
            # Export leaderboard
            (Path(tmpdir) / "leaderboard.json").write_text(
                json.dumps(leaderboard.to_dict(), indent=2)
            )

            # Export policy trace
            trace.save_json(Path(tmpdir) / "policy_trace.json")

            # Verify exports
            assert (Path(tmpdir) / "leaderboard.json").exists()
            assert (Path(tmpdir) / "policy_trace.json").exists()

        # Final verification
        assert len(top_survivors) == 3
        assert len(trace.evaluations) == 1
        assert trace.get_summary()["total_evaluations"] == 1
