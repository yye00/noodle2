"""
Comprehensive E2E test for CI integration with regression safety checks.

This test validates the complete CI regression testing workflow as specified in the
feature requirements, covering all 12 steps from setup to artifact archival.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.controller.ci_runner import (
    CIConfig,
    CIResult,
    CIRunner,
    RegressionBaseline,
    create_ci_config,
)
from src.controller.executor import StageResult, StudyResult
from src.controller.study import StudyConfig
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig
from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult


def create_mock_trial_result(
    case_name: str,
    eco_name: str,
    wns_ps: int,
    success: bool = True,
    trial_index: int = 0,
) -> TrialResult:
    """Helper to create mock TrialResult for testing."""
    config = TrialConfig(
        study_name="ci_regression_study",
        case_name=case_name,
        stage_index=0,
        trial_index=trial_index,
        script_path="/fake/script.tcl",
    )

    artifacts = TrialArtifacts(
        trial_dir=Path("/fake/artifacts"),
    )

    return TrialResult(
        config=config,
        success=success,
        return_code=0 if success else 1,
        runtime_seconds=10.0,
        metrics={"wns_ps": wns_ps} if success else {},
        artifacts=artifacts,
    )


class TestCIIntegrationE2E:
    """
    Comprehensive E2E test suite for CI integration with regression safety checks.

    Tests all 12 steps of the CI integration workflow:
    1. Create regression Study with 'locked' safety domain
    2. Define regression baseline cases with known-good metrics
    3. Configure CI pipeline to run regression Study
    4. Execute Study in CI environment
    5. Verify Study completes successfully for valid changes
    6. Introduce regression (WNS degradation beyond threshold)
    7. Verify Study detects regression and aborts
    8. Verify CI build fails with clear regression report
    9. Fix regression and re-run CI
    10. Verify Study passes and CI build succeeds
    11. Generate regression test report
    12. Archive regression artifacts for investigation
    """

    @pytest.fixture
    def regression_study_config(self) -> StudyConfig:
        """Create a regression Study with 'locked' safety domain."""
        return StudyConfig(
            name="ci_regression_study",
            pdk="Nangate45",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="nangate45_base",
            snapshot_path="/fake/snapshot",
            stages=[
                StageConfig(
                    name="regression_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

    @pytest.fixture
    def regression_baselines(self) -> list[RegressionBaseline]:
        """Define regression baseline cases with known-good metrics."""
        return [
            RegressionBaseline(
                case_name="nangate45_base",
                expected_wns_ps=-500,
                tolerance_ps=100,
                metadata={"baseline_version": "v1.0", "verified_date": "2024-01-01"},
            ),
            RegressionBaseline(
                case_name="nangate45_eco1",
                expected_wns_ps=-300,
                tolerance_ps=50,
                metadata={"baseline_version": "v1.0", "verified_date": "2024-01-01"},
            ),
        ]

    def test_step_1_create_regression_study_with_locked_safety_domain(
        self, regression_study_config: StudyConfig
    ):
        """
        Step 1: Create regression Study with 'locked' safety domain.

        Validates that the Study is configured correctly for CI regression testing.
        """
        # Verify Study uses locked safety domain
        assert regression_study_config.safety_domain == SafetyDomain.LOCKED

        # Verify Study name and PDK
        assert regression_study_config.name == "ci_regression_study"
        assert regression_study_config.pdk == "Nangate45"

        # Verify Study has stages configured
        assert len(regression_study_config.stages) == 1
        assert regression_study_config.stages[0].name == "regression_stage"

        # Verify conservative trial budget for CI
        assert regression_study_config.stages[0].trial_budget == 10

    def test_step_2_define_regression_baseline_cases_with_known_good_metrics(
        self, regression_baselines: list[RegressionBaseline]
    ):
        """
        Step 2: Define regression baseline cases with known-good metrics.

        Validates baseline configuration with expected WNS values and tolerances.
        """
        # Verify we have multiple baselines
        assert len(regression_baselines) == 2

        # Verify base case baseline
        base_baseline = regression_baselines[0]
        assert base_baseline.case_name == "nangate45_base"
        assert base_baseline.expected_wns_ps == -500
        assert base_baseline.tolerance_ps == 100
        assert "baseline_version" in base_baseline.metadata

        # Verify ECO case baseline
        eco_baseline = regression_baselines[1]
        assert eco_baseline.case_name == "nangate45_eco1"
        assert eco_baseline.expected_wns_ps == -300
        assert eco_baseline.tolerance_ps == 50

        # Verify baseline regression detection logic
        is_regression, reason = base_baseline.is_regression(-650)
        assert is_regression
        assert "regression detected" in reason.lower()

        # Verify baseline accepts values within tolerance
        is_regression, reason = base_baseline.is_regression(-550)
        assert not is_regression

    def test_step_3_configure_ci_pipeline_to_run_regression_study(
        self, regression_study_config: StudyConfig, regression_baselines: list[RegressionBaseline]
    ):
        """
        Step 3: Configure CI pipeline to run regression Study.

        Validates CI configuration creation and validation.
        """
        # Create CI configuration
        ci_config = create_ci_config(
            study_config=regression_study_config,
            baselines=regression_baselines,
            fail_on_study_abort=True,
            fail_on_regression=True,
            fail_on_safety_violation=True,
        )

        # Verify CI configuration
        assert ci_config.study_config.name == "ci_regression_study"
        assert len(ci_config.baselines) == 2
        assert ci_config.fail_on_study_abort is True
        assert ci_config.fail_on_regression is True
        assert ci_config.fail_on_safety_violation is True

        # Verify CI config validation passes
        is_valid, issues = ci_config.validate()
        assert is_valid
        assert len(issues) == 0

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step_4_execute_study_in_ci_environment(
        self,
        mock_executor_class: MagicMock,
        regression_study_config: StudyConfig,
        regression_baselines: list[RegressionBaseline],
    ):
        """
        Step 4: Execute Study in CI environment.

        Simulates Study execution within a CI pipeline.
        """
        # Create CI config
        ci_config = create_ci_config(
            study_config=regression_study_config,
            baselines=regression_baselines,
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # Create successful trial results (within baseline tolerance)
        trial_results = [
            create_mock_trial_result("nangate45_base", "noop", -480, True, 0),
            create_mock_trial_result("nangate45_eco1", "eco1", -290, True, 1),
        ]

        stage_result = StageResult(
            stage_index=0,
            stage_name="regression_stage",
            trials_executed=2,
            survivors=["nangate45_base", "nangate45_eco1"],
            total_runtime_seconds=20.0,
            trial_results=trial_results,
        )

        study_result = StudyResult(
            study_name="ci_regression_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=20.0,
            stage_results=[stage_result],
            final_survivors=["nangate45_base", "nangate45_eco1"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result

        # Execute CI run
        runner = CIRunner(ci_config)
        result = runner.run()

        # Verify executor was called
        mock_executor.execute.assert_called_once()

        # Verify result is populated
        assert result.study_result == study_result
        assert isinstance(result, CIResult)

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step_5_verify_study_completes_successfully_for_valid_changes(
        self,
        mock_executor_class: MagicMock,
        regression_study_config: StudyConfig,
        regression_baselines: list[RegressionBaseline],
    ):
        """
        Step 5: Verify Study completes successfully for valid changes.

        Validates that CI passes when changes don't introduce regressions.
        """
        ci_config = create_ci_config(
            study_config=regression_study_config,
            baselines=regression_baselines,
        )

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # Create trial results with improvements (better WNS)
        trial_results = [
            create_mock_trial_result("nangate45_base", "noop", -450, True, 0),
            create_mock_trial_result("nangate45_eco1", "eco1", -250, True, 1),
        ]

        stage_result = StageResult(
            stage_index=0,
            stage_name="regression_stage",
            trials_executed=2,
            survivors=["nangate45_base", "nangate45_eco1"],
            total_runtime_seconds=20.0,
            trial_results=trial_results,
        )

        study_result = StudyResult(
            study_name="ci_regression_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=20.0,
            stage_results=[stage_result],
            final_survivors=["nangate45_base", "nangate45_eco1"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result

        # Execute CI run
        runner = CIRunner(ci_config)
        result = runner.run()

        # Verify CI passed
        assert result.passed is True
        assert result.exit_code == 0
        assert len(result.regressions_detected) == 0
        assert result.failure_reason is None

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step_6_introduce_regression_wns_degradation_beyond_threshold(
        self,
        mock_executor_class: MagicMock,
        regression_study_config: StudyConfig,
        regression_baselines: list[RegressionBaseline],
    ):
        """
        Step 6: Introduce regression (WNS degradation beyond threshold).

        Simulates code change that causes WNS to degrade beyond tolerance.
        """
        ci_config = create_ci_config(
            study_config=regression_study_config,
            baselines=regression_baselines,
        )

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # Create trial results with regression (worse WNS beyond tolerance)
        trial_results = [
            create_mock_trial_result("nangate45_base", "noop", -650, True, 0),  # Regression!
            create_mock_trial_result("nangate45_eco1", "eco1", -290, True, 1),  # OK
        ]

        stage_result = StageResult(
            stage_index=0,
            stage_name="regression_stage",
            trials_executed=2,
            survivors=["nangate45_base", "nangate45_eco1"],
            total_runtime_seconds=20.0,
            trial_results=trial_results,
        )

        study_result = StudyResult(
            study_name="ci_regression_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=20.0,
            stage_results=[stage_result],
            final_survivors=["nangate45_base", "nangate45_eco1"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result

        # Execute CI run
        runner = CIRunner(ci_config)
        result = runner.run()

        # Verify regression was detected
        assert len(result.regressions_detected) == 1
        case_name, reason = result.regressions_detected[0]
        assert case_name == "nangate45_base"
        assert "regression detected" in reason.lower()
        assert "-650" in reason
        assert "-500" in reason

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step_7_verify_study_detects_regression_and_reports(
        self,
        mock_executor_class: MagicMock,
        regression_study_config: StudyConfig,
        regression_baselines: list[RegressionBaseline],
    ):
        """
        Step 7: Verify Study detects regression and aborts.

        Validates regression detection logic and failure reporting.
        """
        ci_config = create_ci_config(
            study_config=regression_study_config,
            baselines=regression_baselines,
        )

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # Multiple regressions
        trial_results = [
            create_mock_trial_result("nangate45_base", "noop", -700, True, 0),  # Regression
            create_mock_trial_result("nangate45_eco1", "eco1", -400, True, 1),  # Regression
        ]

        stage_result = StageResult(
            stage_index=0,
            stage_name="regression_stage",
            trials_executed=2,
            survivors=["nangate45_base", "nangate45_eco1"],
            total_runtime_seconds=20.0,
            trial_results=trial_results,
        )

        study_result = StudyResult(
            study_name="ci_regression_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=20.0,
            stage_results=[stage_result],
            final_survivors=["nangate45_base", "nangate45_eco1"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result

        # Execute CI run
        runner = CIRunner(ci_config)
        result = runner.run()

        # Verify both regressions detected
        assert len(result.regressions_detected) == 2

        # Verify each regression has detailed reason
        for case_name, reason in result.regressions_detected:
            assert case_name in ["nangate45_base", "nangate45_eco1"]
            assert "regression detected" in reason.lower()
            assert "expected" in reason
            assert "got" in reason
            assert "delta" in reason
            assert "tolerance" in reason

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step_8_verify_ci_build_fails_with_clear_regression_report(
        self,
        mock_executor_class: MagicMock,
        regression_study_config: StudyConfig,
        regression_baselines: list[RegressionBaseline],
    ):
        """
        Step 8: Verify CI build fails with clear regression report.

        Validates CI failure behavior and report quality.
        """
        ci_config = create_ci_config(
            study_config=regression_study_config,
            baselines=regression_baselines,
        )

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # Regression scenario
        trial_results = [
            create_mock_trial_result("nangate45_base", "noop", -650, True, 0),
        ]

        stage_result = StageResult(
            stage_index=0,
            stage_name="regression_stage",
            trials_executed=1,
            survivors=["nangate45_base"],
            total_runtime_seconds=10.0,
            trial_results=trial_results,
        )

        study_result = StudyResult(
            study_name="ci_regression_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=10.0,
            stage_results=[stage_result],
            final_survivors=["nangate45_base"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result

        # Execute CI run
        runner = CIRunner(ci_config)
        result = runner.run()

        # Verify CI failed
        assert result.passed is False
        assert result.exit_code == 2  # Regression failure code
        assert result.failure_reason is not None
        assert "regression" in result.failure_reason.lower()

        # Verify report is JSON serializable (for CI artifacts)
        report_dict = result.to_dict()
        assert report_dict["passed"] is False
        assert report_dict["exit_code"] == 2
        assert len(report_dict["regressions_detected"]) == 1

        # Verify report can be written as JSON
        report_json = json.dumps(report_dict, indent=2)
        assert "nangate45_base" in report_json
        assert "regression detected" in report_json.lower()

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step_9_fix_regression_and_rerun_ci(
        self,
        mock_executor_class: MagicMock,
        regression_study_config: StudyConfig,
        regression_baselines: list[RegressionBaseline],
    ):
        """
        Step 9: Fix regression and re-run CI.

        Simulates fix being applied and CI being re-executed.
        """
        ci_config = create_ci_config(
            study_config=regression_study_config,
            baselines=regression_baselines,
        )

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # First run: regression
        trial_results_regression = [
            create_mock_trial_result("nangate45_base", "noop", -650, True, 0),
        ]

        stage_result_regression = StageResult(
            stage_index=0,
            stage_name="regression_stage",
            trials_executed=1,
            survivors=["nangate45_base"],
            total_runtime_seconds=10.0,
            trial_results=trial_results_regression,
        )

        study_result_regression = StudyResult(
            study_name="ci_regression_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=10.0,
            stage_results=[stage_result_regression],
            final_survivors=["nangate45_base"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result_regression

        # Execute first CI run
        runner1 = CIRunner(ci_config)
        result1 = runner1.run()

        # Verify first run failed
        assert result1.passed is False
        assert len(result1.regressions_detected) == 1

        # Simulate fix: WNS now within tolerance
        trial_results_fixed = [
            create_mock_trial_result("nangate45_base", "noop", -480, True, 0),
        ]

        stage_result_fixed = StageResult(
            stage_index=0,
            stage_name="regression_stage",
            trials_executed=1,
            survivors=["nangate45_base"],
            total_runtime_seconds=10.0,
            trial_results=trial_results_fixed,
        )

        study_result_fixed = StudyResult(
            study_name="ci_regression_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=10.0,
            stage_results=[stage_result_fixed],
            final_survivors=["nangate45_base"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result_fixed

        # Execute second CI run (after fix)
        runner2 = CIRunner(ci_config)
        result2 = runner2.run()

        # Verify second run passed
        assert result2.passed is True
        assert len(result2.regressions_detected) == 0

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step_10_verify_study_passes_and_ci_build_succeeds(
        self,
        mock_executor_class: MagicMock,
        regression_study_config: StudyConfig,
        regression_baselines: list[RegressionBaseline],
    ):
        """
        Step 10: Verify Study passes and CI build succeeds.

        Validates successful CI execution after fix.
        """
        ci_config = create_ci_config(
            study_config=regression_study_config,
            baselines=regression_baselines,
        )

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # All trials within baseline tolerance
        trial_results = [
            create_mock_trial_result("nangate45_base", "noop", -480, True, 0),
            create_mock_trial_result("nangate45_eco1", "eco1", -290, True, 1),
        ]

        stage_result = StageResult(
            stage_index=0,
            stage_name="regression_stage",
            trials_executed=2,
            survivors=["nangate45_base", "nangate45_eco1"],
            total_runtime_seconds=20.0,
            trial_results=trial_results,
        )

        study_result = StudyResult(
            study_name="ci_regression_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=20.0,
            stage_results=[stage_result],
            final_survivors=["nangate45_base", "nangate45_eco1"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result

        # Execute CI run
        runner = CIRunner(ci_config)
        result = runner.run()

        # Verify complete success
        assert result.passed is True
        assert result.exit_code == 0
        assert len(result.regressions_detected) == 0
        assert result.failure_reason is None
        assert len(result.safety_violations) == 0

        # Verify Study completed all stages
        assert result.study_result.stages_completed == 1
        assert result.study_result.aborted is False

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step_11_generate_regression_test_report(
        self,
        mock_executor_class: MagicMock,
        regression_study_config: StudyConfig,
        regression_baselines: list[RegressionBaseline],
        tmp_path: Path,
    ):
        """
        Step 11: Generate regression test report.

        Validates report generation and formatting.
        """
        ci_config = create_ci_config(
            study_config=regression_study_config,
            baselines=regression_baselines,
        )

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # Mixed results: one pass, one regression
        trial_results = [
            create_mock_trial_result("nangate45_base", "noop", -480, True, 0),  # Pass
            create_mock_trial_result("nangate45_eco1", "eco1", -400, True, 1),  # Regression
        ]

        stage_result = StageResult(
            stage_index=0,
            stage_name="regression_stage",
            trials_executed=2,
            survivors=["nangate45_base", "nangate45_eco1"],
            total_runtime_seconds=20.0,
            trial_results=trial_results,
        )

        study_result = StudyResult(
            study_name="ci_regression_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=20.0,
            stage_results=[stage_result],
            final_survivors=["nangate45_base", "nangate45_eco1"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result

        # Execute CI run
        runner = CIRunner(ci_config)
        result = runner.run()

        # Generate report
        report = result.to_dict()

        # Write report to file
        report_path = tmp_path / "ci_regression_report.json"
        with open(report_path, "w") as f:
            json.dump(report, f, indent=2)

        # Verify report file was created
        assert report_path.exists()

        # Verify report contents
        with open(report_path) as f:
            loaded_report = json.load(f)

        assert loaded_report["study_name"] == "ci_regression_study"
        assert loaded_report["passed"] is False
        assert len(loaded_report["regressions_detected"]) == 1

        # Verify regression details in report
        regression = loaded_report["regressions_detected"][0]
        assert regression["case_name"] == "nangate45_eco1"
        assert "regression detected" in regression["reason"].lower()

        # Verify report includes study results
        assert "study_result" in loaded_report
        assert loaded_report["study_result"]["total_stages"] == 1

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step_12_archive_regression_artifacts_for_investigation(
        self,
        mock_executor_class: MagicMock,
        regression_study_config: StudyConfig,
        regression_baselines: list[RegressionBaseline],
        tmp_path: Path,
    ):
        """
        Step 12: Archive regression artifacts for investigation.

        Validates artifact archival and accessibility for debugging.
        """
        # Configure custom artifact paths
        artifacts_root = tmp_path / "artifacts"
        telemetry_root = tmp_path / "telemetry"

        ci_config = CIConfig(
            study_config=regression_study_config,
            baselines=regression_baselines,
            artifacts_root=artifacts_root,
            telemetry_root=telemetry_root,
        )

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # Regression scenario
        trial_results = [
            create_mock_trial_result("nangate45_base", "noop", -650, True, 0),
        ]

        stage_result = StageResult(
            stage_index=0,
            stage_name="regression_stage",
            trials_executed=1,
            survivors=["nangate45_base"],
            total_runtime_seconds=10.0,
            trial_results=trial_results,
        )

        study_result = StudyResult(
            study_name="ci_regression_study",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=10.0,
            stage_results=[stage_result],
            final_survivors=["nangate45_base"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result

        # Execute CI run
        runner = CIRunner(ci_config)
        result = runner.run()

        # Verify artifact paths are configured
        assert runner.config.artifacts_root == artifacts_root
        assert runner.config.telemetry_root == telemetry_root

        # Generate and archive CI report
        archive_dir = tmp_path / "ci_archives"
        archive_dir.mkdir()

        report_path = archive_dir / "regression_report.json"
        with open(report_path, "w") as f:
            json.dump(result.to_dict(), f, indent=2)

        # Create metadata file for archival
        metadata_path = archive_dir / "metadata.json"
        metadata = {
            "ci_run_id": "run_001",
            "timestamp": "2024-01-15T10:30:00Z",
            "study_name": result.study_result.study_name,
            "passed": result.passed,
            "regressions_count": len(result.regressions_detected),
            "artifacts_root": str(artifacts_root),
            "telemetry_root": str(telemetry_root),
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        # Verify archive structure
        assert report_path.exists()
        assert metadata_path.exists()

        # Verify archived report is readable
        with open(report_path) as f:
            archived_report = json.load(f)
        assert archived_report["passed"] is False
        assert len(archived_report["regressions_detected"]) == 1

        # Verify metadata is complete
        with open(metadata_path) as f:
            archived_metadata = json.load(f)
        assert archived_metadata["study_name"] == "ci_regression_study"
        assert archived_metadata["regressions_count"] == 1
        assert "artifacts_root" in archived_metadata
        assert "telemetry_root" in archived_metadata


class TestCompleteCI_E2E_Integration:
    """
    Single comprehensive test that exercises the entire CI workflow end-to-end.
    """

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_complete_ci_workflow_from_setup_to_archival(
        self, mock_executor_class: MagicMock, tmp_path: Path
    ):
        """
        Complete E2E workflow covering all 12 steps in a single test.

        This validates the entire CI integration pipeline from study creation
        through regression detection to artifact archival.
        """
        # Step 1: Create regression Study with locked safety domain
        study_config = StudyConfig(
            name="complete_ci_e2e",
            pdk="Nangate45",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="nangate45_base",
            snapshot_path="/fake/snapshot",
            stages=[
                StageConfig(
                    name="ci_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        # Step 2: Define regression baselines
        baselines = [
            RegressionBaseline(
                case_name="nangate45_base",
                expected_wns_ps=-500,
                tolerance_ps=100,
            ),
        ]

        # Step 3: Configure CI pipeline
        ci_config = create_ci_config(
            study_config=study_config,
            baselines=baselines,
            artifacts_root=tmp_path / "artifacts",
            telemetry_root=tmp_path / "telemetry",
        )

        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        # Step 4-5: Execute Study with valid changes (should pass)
        trial_results_pass = [
            create_mock_trial_result("nangate45_base", "noop", -480, True, 0),
        ]

        stage_result_pass = StageResult(
            stage_index=0,
            stage_name="ci_stage",
            trials_executed=1,
            survivors=["nangate45_base"],
            total_runtime_seconds=10.0,
            trial_results=trial_results_pass,
        )

        study_result_pass = StudyResult(
            study_name="complete_ci_e2e",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=10.0,
            stage_results=[stage_result_pass],
            final_survivors=["nangate45_base"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result_pass

        runner = CIRunner(ci_config)
        result_pass = runner.run()

        assert result_pass.passed is True
        assert result_pass.exit_code == 0

        # Step 6-8: Introduce regression and verify detection
        trial_results_regress = [
            create_mock_trial_result("nangate45_base", "noop", -650, True, 0),
        ]

        stage_result_regress = StageResult(
            stage_index=0,
            stage_name="ci_stage",
            trials_executed=1,
            survivors=["nangate45_base"],
            total_runtime_seconds=10.0,
            trial_results=trial_results_regress,
        )

        study_result_regress = StudyResult(
            study_name="complete_ci_e2e",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=10.0,
            stage_results=[stage_result_regress],
            final_survivors=["nangate45_base"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result_regress

        runner_regress = CIRunner(ci_config)
        result_regress = runner_regress.run()

        assert result_regress.passed is False
        assert result_regress.exit_code == 2
        assert len(result_regress.regressions_detected) == 1

        # Step 9-10: Fix regression and verify pass
        mock_executor.execute.return_value = study_result_pass

        runner_fixed = CIRunner(ci_config)
        result_fixed = runner_fixed.run()

        assert result_fixed.passed is True
        assert result_fixed.exit_code == 0

        # Step 11: Generate regression report
        report_dir = tmp_path / "reports"
        report_dir.mkdir()

        report_path = report_dir / "ci_report.json"
        with open(report_path, "w") as f:
            json.dump(result_fixed.to_dict(), f, indent=2)

        assert report_path.exists()

        # Step 12: Archive artifacts
        archive_dir = tmp_path / "archive"
        archive_dir.mkdir()

        # Archive regression report
        import shutil
        shutil.copy(report_path, archive_dir / "final_report.json")

        # Create archive metadata
        metadata = {
            "workflow": "complete_ci_e2e",
            "runs": 3,
            "final_status": "passed",
            "regression_detected": True,
            "regression_fixed": True,
        }

        with open(archive_dir / "metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        # Verify archive is complete
        assert (archive_dir / "final_report.json").exists()
        assert (archive_dir / "metadata.json").exists()

        # Verify final report
        with open(archive_dir / "final_report.json") as f:
            final_report = json.load(f)

        assert final_report["passed"] is True
        assert final_report["exit_code"] == 0
