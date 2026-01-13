"""Test F069: Study summary JSON contains aggregate statistics.

This test validates that study_summary.json includes all required aggregate
statistics as specified in F069:
- Total trials
- Successful trials
- ECO success rate
- Runtime
- Stages to converge
- Final metrics (WNS, TNS, hot_ratio)
- Improvement deltas from baseline
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.case import Case, CaseGraph
from src.controller.executor import StudyExecutor
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig, StageType, StudyConfig


class TestStudySummaryJSONAggregateStatistics:
    """Test that study_summary.json contains all required aggregate statistics."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for artifacts and telemetry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            telemetry_root = Path(tmpdir) / "telemetry"
            artifacts_root.mkdir(parents=True)
            telemetry_root.mkdir(parents=True)
            yield artifacts_root, telemetry_root

    @pytest.fixture
    def simple_study_config(self):
        """Create a simple study configuration for testing."""
        return StudyConfig(
            name="test_study_summary",
            pdk="nangate45",
            base_case_name="test_base",
            snapshot_path=Path("studies/nangate45_extreme"),
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_1",
                    stage_type=StageType.EXECUTION,
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
                StageConfig(
                    name="stage_2",
                    stage_type=StageType.EXECUTION,
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
                ),
            ],
        )

    def test_step_1_complete_a_study(self, temp_dirs, simple_study_config):
        """Step 1: Complete a study."""
        artifacts_root, telemetry_root = temp_dirs

        executor = StudyExecutor(
            config=simple_study_config,
            artifacts_root=artifacts_root,
            telemetry_root=telemetry_root,
            skip_base_case_verification=True,
            enable_graceful_shutdown=False,
        )

        # Execute the study
        result = executor.execute()

        # Verify study completed
        assert result.stages_completed > 0
        assert len(result.stage_results) > 0

    def test_step_2_load_study_summary_json(self, temp_dirs, simple_study_config):
        """Step 2: Load study_summary.json."""
        artifacts_root, telemetry_root = temp_dirs

        executor = StudyExecutor(
            config=simple_study_config,
            artifacts_root=artifacts_root,
            telemetry_root=telemetry_root,
            skip_base_case_verification=True,
            enable_graceful_shutdown=False,
        )

        result = executor.execute()

        # Check that study_summary.json exists
        summary_path = artifacts_root / simple_study_config.name / "study_summary.json"
        assert summary_path.exists(), "study_summary.json should exist"

        # Load and parse the JSON
        with open(summary_path, "r") as f:
            summary = json.load(f)

        assert summary is not None
        assert isinstance(summary, dict)

    def test_step_3_verify_aggregate_statistics_fields(self, temp_dirs, simple_study_config):
        """Step 3: Verify contains: total trials, successful trials, ECO success rate, runtime, stages to converge."""
        artifacts_root, telemetry_root = temp_dirs

        executor = StudyExecutor(
            config=simple_study_config,
            artifacts_root=artifacts_root,
            telemetry_root=telemetry_root,
            skip_base_case_verification=True,
            enable_graceful_shutdown=False,
        )

        result = executor.execute()

        # Load study_summary.json
        summary_path = artifacts_root / simple_study_config.name / "study_summary.json"
        with open(summary_path, "r") as f:
            summary = json.load(f)

        # Verify aggregate_statistics section exists
        assert "aggregate_statistics" in summary, "aggregate_statistics section should exist"
        stats = summary["aggregate_statistics"]

        # Verify required fields
        assert "total_trials" in stats, "total_trials should be present"
        assert "successful_trials" in stats, "successful_trials should be present"
        assert "eco_success_rate_percent" in stats, "eco_success_rate_percent should be present"
        assert "stages_to_converge" in stats, "stages_to_converge should be present"

        # Verify runtime is in the main summary
        assert "total_runtime_seconds" in summary, "total_runtime_seconds should be present"

        # Verify values are reasonable
        assert stats["total_trials"] >= 0
        assert stats["successful_trials"] >= 0
        assert stats["successful_trials"] <= stats["total_trials"]
        assert 0 <= stats["eco_success_rate_percent"] <= 100
        assert stats["stages_to_converge"] >= 0

    def test_step_4_verify_final_metrics(self, temp_dirs, simple_study_config):
        """Step 4: Verify contains final metrics (WNS, TNS, hot_ratio)."""
        artifacts_root, telemetry_root = temp_dirs

        executor = StudyExecutor(
            config=simple_study_config,
            artifacts_root=artifacts_root,
            telemetry_root=telemetry_root,
            skip_base_case_verification=True,
            enable_graceful_shutdown=False,
        )

        result = executor.execute()

        # Load study_summary.json
        summary_path = artifacts_root / simple_study_config.name / "study_summary.json"
        with open(summary_path, "r") as f:
            summary = json.load(f)

        # Verify final_metrics section exists
        assert "final_metrics" in summary, "final_metrics section should exist"

        if summary["final_metrics"] is not None:
            final_metrics = summary["final_metrics"]

            # At least one of the key metrics should be present
            has_wns = "wns_ps" in final_metrics
            has_tns = "tns_ps" in final_metrics
            has_hot_ratio = "hot_ratio" in final_metrics

            assert has_wns or has_tns or has_hot_ratio, "At least one final metric should be present"

    def test_step_5_verify_improvement_deltas(self, temp_dirs, simple_study_config):
        """Step 5: Verify contains improvement deltas from baseline."""
        artifacts_root, telemetry_root = temp_dirs

        executor = StudyExecutor(
            config=simple_study_config,
            artifacts_root=artifacts_root,
            telemetry_root=telemetry_root,
            skip_base_case_verification=True,
            enable_graceful_shutdown=False,
        )

        result = executor.execute()

        # Load study_summary.json
        summary_path = artifacts_root / simple_study_config.name / "study_summary.json"
        with open(summary_path, "r") as f:
            summary = json.load(f)

        # Verify baseline_metrics section exists
        assert "baseline_metrics" in summary, "baseline_metrics section should exist"

        # Verify improvement_deltas section exists
        assert "improvement_deltas" in summary, "improvement_deltas section should exist"

        # If both baseline and final metrics exist, improvement deltas should be computed
        if summary["baseline_metrics"] and summary["final_metrics"]:
            deltas = summary["improvement_deltas"]

            # Deltas should be a dict (even if empty)
            assert isinstance(deltas, dict)

            # If WNS is in both baseline and final, WNS delta should be computed
            if "wns_ps" in summary["baseline_metrics"] and "wns_ps" in summary["final_metrics"]:
                assert "wns_ps" in deltas, "WNS delta should be computed"


class TestStudySummaryJSONIntegration:
    """Integration tests for study summary JSON generation."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for artifacts and telemetry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            telemetry_root = Path(tmpdir) / "telemetry"
            artifacts_root.mkdir(parents=True)
            telemetry_root.mkdir(parents=True)
            yield artifacts_root, telemetry_root

    def test_aggregate_statistics_are_accurate(self, temp_dirs):
        """Verify that aggregate statistics match actual trial results."""
        artifacts_root, telemetry_root = temp_dirs

        config = StudyConfig(
            name="test_accuracy",
            pdk="nangate45",
            base_case_name="test_base",
            snapshot_path=Path("studies/nangate45_extreme"),
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_1",
                    stage_type=StageType.EXECUTION,
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=1,
                ),
            ],
        )

        executor = StudyExecutor(
            config=config,
            artifacts_root=artifacts_root,
            telemetry_root=telemetry_root,
            skip_base_case_verification=True,
            enable_graceful_shutdown=False,
        )

        result = executor.execute()

        # Load study_summary.json
        summary_path = artifacts_root / config.name / "study_summary.json"
        with open(summary_path, "r") as f:
            summary = json.load(f)

        # Count actual trials from stage_results
        actual_total = 0
        actual_successful = 0

        for stage_result in summary["stage_results"]:
            actual_total += len(stage_result["trial_results"])
            actual_successful += sum(
                1 for trial in stage_result["trial_results"] if trial["success"]
            )

        # Verify aggregate statistics match
        stats = summary["aggregate_statistics"]
        assert stats["total_trials"] == actual_total, "Total trials should match"
        assert stats["successful_trials"] == actual_successful, "Successful trials should match"

    def test_eco_success_rate_calculation(self, temp_dirs):
        """Verify ECO success rate is calculated correctly."""
        artifacts_root, telemetry_root = temp_dirs

        config = StudyConfig(
            name="test_eco_rate",
            pdk="nangate45",
            base_case_name="test_base",
            snapshot_path=Path("studies/nangate45_extreme"),
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_1",
                    stage_type=StageType.EXECUTION,
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                ),
            ],
        )

        executor = StudyExecutor(
            config=config,
            artifacts_root=artifacts_root,
            telemetry_root=telemetry_root,
            skip_base_case_verification=True,
            enable_graceful_shutdown=False,
        )

        result = executor.execute()

        # Load study_summary.json
        summary_path = artifacts_root / config.name / "study_summary.json"
        with open(summary_path, "r") as f:
            summary = json.load(f)

        # ECO success rate should be present and valid
        stats = summary["aggregate_statistics"]
        assert "eco_success_rate_percent" in stats
        assert 0 <= stats["eco_success_rate_percent"] <= 100

    def test_improvement_deltas_calculated_correctly(self, temp_dirs):
        """Verify improvement deltas are calculated correctly."""
        artifacts_root, telemetry_root = temp_dirs

        config = StudyConfig(
            name="test_deltas",
            pdk="nangate45",
            base_case_name="test_base",
            snapshot_path=Path("studies/nangate45_extreme"),
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_1",
                    stage_type=StageType.EXECUTION,
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=1,
                ),
            ],
        )

        executor = StudyExecutor(
            config=config,
            artifacts_root=artifacts_root,
            telemetry_root=telemetry_root,
            skip_base_case_verification=True,
            enable_graceful_shutdown=False,
        )

        result = executor.execute()

        # Load study_summary.json
        summary_path = artifacts_root / config.name / "study_summary.json"
        with open(summary_path, "r") as f:
            summary = json.load(f)

        # If baseline and final metrics exist, deltas should be computed
        if summary["baseline_metrics"] and summary["final_metrics"]:
            baseline = summary["baseline_metrics"]
            final = summary["final_metrics"]
            deltas = summary["improvement_deltas"]

            # Verify WNS delta calculation if WNS is present
            if "wns_ps" in baseline and "wns_ps" in final:
                expected_delta = final["wns_ps"] - baseline["wns_ps"]
                assert deltas["wns_ps"] == expected_delta, "WNS delta should be correctly calculated"

            # Verify hot_ratio delta calculation if present
            if "hot_ratio" in baseline and "hot_ratio" in final:
                expected_reduction = baseline["hot_ratio"] - final["hot_ratio"]
                assert abs(deltas["hot_ratio_reduction"] - expected_reduction) < 0.0001, \
                    "Hot ratio reduction should be correctly calculated"

    def test_summary_json_is_well_formed(self, temp_dirs):
        """Verify that study_summary.json is well-formed and parseable."""
        artifacts_root, telemetry_root = temp_dirs

        config = StudyConfig(
            name="test_wellformed",
            pdk="nangate45",
            base_case_name="test_base",
            snapshot_path=Path("studies/nangate45_extreme"),
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_1",
                    stage_type=StageType.EXECUTION,
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=2,
                    survivor_count=1,
                ),
            ],
        )

        executor = StudyExecutor(
            config=config,
            artifacts_root=artifacts_root,
            telemetry_root=telemetry_root,
            skip_base_case_verification=True,
            enable_graceful_shutdown=False,
        )

        result = executor.execute()

        # Load and verify JSON is valid
        summary_path = artifacts_root / config.name / "study_summary.json"
        with open(summary_path, "r") as f:
            summary = json.load(f)

        # Verify top-level structure
        required_keys = [
            "study_name",
            "total_stages",
            "stages_completed",
            "total_runtime_seconds",
            "stage_results",
            "final_survivors",
            "aggregate_statistics",
            "baseline_metrics",
            "final_metrics",
            "improvement_deltas",
        ]

        for key in required_keys:
            assert key in summary, f"Key {key} should be present in study_summary.json"

        # Verify aggregate_statistics has all required fields
        stats_required = [
            "total_trials",
            "successful_trials",
            "failed_trials",
            "success_rate_percent",
            "eco_success_rate_percent",
            "stages_to_converge",
        ]

        stats = summary["aggregate_statistics"]
        for key in stats_required:
            assert key in stats, f"Key {key} should be present in aggregate_statistics"


class TestStudySummaryJSONEdgeCases:
    """Test edge cases for study summary JSON generation."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for artifacts and telemetry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_root = Path(tmpdir) / "artifacts"
            telemetry_root = Path(tmpdir) / "telemetry"
            artifacts_root.mkdir(parents=True)
            telemetry_root.mkdir(parents=True)
            yield artifacts_root, telemetry_root

    def test_empty_study_has_valid_summary(self, temp_dirs):
        """Verify that a study with no trials still has a valid summary."""
        artifacts_root, telemetry_root = temp_dirs

        config = StudyConfig(
            name="test_empty",
            pdk="nangate45",
            base_case_name="test_base",
            snapshot_path=Path("studies/nangate45_extreme"),
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_1",
                    stage_type=StageType.EXECUTION,
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=0,  # No trials
                    survivor_count=0,
                ),
            ],
        )

        executor = StudyExecutor(
            config=config,
            artifacts_root=artifacts_root,
            telemetry_root=telemetry_root,
            skip_base_case_verification=True,
            enable_graceful_shutdown=False,
        )

        result = executor.execute()

        # Load study_summary.json
        summary_path = artifacts_root / config.name / "study_summary.json"
        with open(summary_path, "r") as f:
            summary = json.load(f)

        # Verify aggregate statistics are valid even with no trials
        stats = summary["aggregate_statistics"]
        assert stats["total_trials"] == 0
        assert stats["successful_trials"] == 0
        assert stats["eco_success_rate_percent"] == 0.0

    def test_single_stage_study_summary(self, temp_dirs):
        """Verify summary for a single-stage study."""
        artifacts_root, telemetry_root = temp_dirs

        config = StudyConfig(
            name="test_single_stage",
            pdk="nangate45",
            base_case_name="test_base",
            snapshot_path=Path("studies/nangate45_extreme"),
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_1",
                    stage_type=StageType.EXECUTION,
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=2,
                    survivor_count=1,
                ),
            ],
        )

        executor = StudyExecutor(
            config=config,
            artifacts_root=artifacts_root,
            telemetry_root=telemetry_root,
            skip_base_case_verification=True,
            enable_graceful_shutdown=False,
        )

        result = executor.execute()

        # Load study_summary.json
        summary_path = artifacts_root / config.name / "study_summary.json"
        with open(summary_path, "r") as f:
            summary = json.load(f)

        # Verify summary is valid for single-stage study
        assert summary["total_stages"] == 1
        assert summary["stages_completed"] == 1
        assert summary["aggregate_statistics"]["stages_to_converge"] == 1
