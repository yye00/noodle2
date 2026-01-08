"""Tests for CI/CD integration with regression safety checks."""

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
) -> TrialResult:
    """Helper to create mock TrialResult for testing."""
    config = TrialConfig(
        study_name="test_study",
        case_name=case_name,
        stage_index=0,
        trial_index=0,
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


class TestRegressionBaseline:
    """Test RegressionBaseline for CI regression detection."""

    def test_create_baseline(self):
        """Test creating a regression baseline."""
        baseline = RegressionBaseline(
            case_name="test_case",
            expected_wns_ps=-500,
            tolerance_ps=100,
        )

        assert baseline.case_name == "test_case"
        assert baseline.expected_wns_ps == -500
        assert baseline.tolerance_ps == 100

    def test_no_regression_within_tolerance(self):
        """Test that results within tolerance are not flagged as regressions."""
        baseline = RegressionBaseline(
            case_name="test_case",
            expected_wns_ps=-500,
            tolerance_ps=100,
        )

        # Within tolerance (better)
        is_regression, reason = baseline.is_regression(-450)
        assert not is_regression
        assert reason == ""

        # Within tolerance (slightly worse but acceptable)
        is_regression, reason = baseline.is_regression(-550)
        assert not is_regression
        assert reason == ""

    def test_regression_detected_outside_tolerance(self):
        """Test that regressions outside tolerance are detected."""
        baseline = RegressionBaseline(
            case_name="test_case",
            expected_wns_ps=-500,
            tolerance_ps=100,
        )

        # Worse than tolerance (regression)
        is_regression, reason = baseline.is_regression(-650)
        assert is_regression
        assert "regression detected" in reason.lower()
        assert "-650" in reason
        assert "-500" in reason

    def test_improvement_not_flagged_as_regression(self):
        """Test that improvements are not flagged as regressions."""
        baseline = RegressionBaseline(
            case_name="test_case",
            expected_wns_ps=-500,
            tolerance_ps=100,
        )

        # Significant improvement (more positive WNS)
        is_regression, reason = baseline.is_regression(-100)
        assert not is_regression
        assert reason == ""

        # Even positive slack (no violations)
        is_regression, reason = baseline.is_regression(100)
        assert not is_regression
        assert reason == ""


class TestCIConfig:
    """Test CIConfig validation and creation."""

    def test_create_valid_ci_config(self):
        """Test creating valid CI configuration."""
        study = StudyConfig(
            name="ci_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        baseline = RegressionBaseline(
            case_name="test_case",
            expected_wns_ps=-500,
            tolerance_ps=100,
        )

        config = CIConfig(
            study_config=study,
            baselines=[baseline],
        )

        is_valid, issues = config.validate()
        assert is_valid
        assert len(issues) == 0

    def test_ci_config_requires_locked_safety_domain(self):
        """Test that CI config requires 'locked' safety domain."""
        study = StudyConfig(
            name="ci_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.SANDBOX,  # Wrong domain
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        config = CIConfig(
            study_config=study,
            baselines=[],
            fail_on_regression=False,
        )

        is_valid, issues = config.validate()
        assert not is_valid
        assert len(issues) >= 1
        assert any("locked" in issue.lower() for issue in issues)

    def test_ci_config_requires_baselines_when_fail_on_regression(self):
        """Test that baselines are required when fail_on_regression=True."""
        study = StudyConfig(
            name="ci_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        config = CIConfig(
            study_config=study,
            baselines=[],  # Empty baselines
            fail_on_regression=True,
        )

        is_valid, issues = config.validate()
        assert not is_valid
        assert len(issues) >= 1
        assert any("baselines" in issue.lower() for issue in issues)

    def test_create_ci_config_helper_validates(self):
        """Test that create_ci_config helper validates configuration."""
        study = StudyConfig(
            name="ci_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.SANDBOX,  # Wrong domain
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with pytest.raises(ValueError, match="Invalid CI configuration"):
            create_ci_config(study)


class TestCIRunner:
    """Test CIRunner execution and regression detection."""

    def test_create_ci_runner_validates_config(self):
        """Test that CIRunner validates configuration on creation."""
        study = StudyConfig(
            name="ci_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.SANDBOX,  # Wrong domain
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        config = CIConfig(
            study_config=study,
            baselines=[],
            fail_on_regression=False,
        )

        with pytest.raises(ValueError, match="Invalid CI configuration"):
            CIRunner(config)

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_ci_runner_passes_when_no_regressions(self, mock_executor_class):
        """Test that CI runner passes when no regressions detected."""
        # Create valid study config
        study = StudyConfig(
            name="ci_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        baseline = RegressionBaseline(
            case_name="test_case",
            expected_wns_ps=-500,
            tolerance_ps=100,
        )

        config = CIConfig(
            study_config=study,
            baselines=[baseline],
        )

        # Mock executor to return successful result
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        trial_result = create_mock_trial_result(
            case_name="test_case",
            eco_name="noop",
            wns_ps=-480,  # Within tolerance
            success=True,
        )

        stage_result = StageResult(
            stage_index=0,
            stage_name="stage0",
            trials_executed=1,
            survivors=["test_case"],
            total_runtime_seconds=10.0,
            trial_results=[trial_result],
        )

        study_result = StudyResult(
            study_name="ci_test",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=10.0,
            stage_results=[stage_result],
            final_survivors=["test_case"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result

        # Run CI
        runner = CIRunner(config)
        result = runner.run()

        # Verify passed
        assert result.passed
        assert result.exit_code == 0
        assert len(result.regressions_detected) == 0
        assert result.failure_reason is None

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_ci_runner_fails_on_regression(self, mock_executor_class):
        """Test that CI runner fails when regression detected."""
        # Create valid study config
        study = StudyConfig(
            name="ci_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        baseline = RegressionBaseline(
            case_name="test_case",
            expected_wns_ps=-500,
            tolerance_ps=100,
        )

        config = CIConfig(
            study_config=study,
            baselines=[baseline],
        )

        # Mock executor to return result with regression
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        trial_result = create_mock_trial_result(
            case_name="test_case",
            eco_name="noop",
            wns_ps=-700,  # Regression!
            success=True,
        )

        stage_result = StageResult(
            stage_index=0,
            stage_name="stage0",
            trials_executed=1,
            survivors=["test_case"],
            total_runtime_seconds=10.0,
            trial_results=[trial_result],
        )

        study_result = StudyResult(
            study_name="ci_test",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=10.0,
            stage_results=[stage_result],
            final_survivors=["test_case"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result

        # Run CI
        runner = CIRunner(config)
        result = runner.run()

        # Verify failed
        assert not result.passed
        assert result.exit_code == 2
        assert len(result.regressions_detected) == 1
        assert result.regressions_detected[0][0] == "test_case"
        assert "regression" in result.failure_reason.lower()

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_ci_runner_fails_on_study_abort(self, mock_executor_class):
        """Test that CI runner fails when Study aborts."""
        # Create valid study config
        study = StudyConfig(
            name="ci_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        config = CIConfig(
            study_config=study,
            baselines=[],
            fail_on_regression=False,
            fail_on_study_abort=True,
        )

        # Mock executor to return aborted result
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        study_result = StudyResult(
            study_name="ci_test",
            total_stages=1,
            stages_completed=0,
            total_runtime_seconds=10.0,
            stage_results=[],
            final_survivors=[],
            aborted=True,
            abort_reason="Base case failed",
        )

        mock_executor.execute.return_value = study_result

        # Run CI
        runner = CIRunner(config)
        result = runner.run()

        # Verify failed
        assert not result.passed
        assert result.exit_code == 1
        assert "aborted" in result.failure_reason.lower()


class TestCIResult:
    """Test CIResult serialization and reporting."""

    def test_ci_result_to_dict(self):
        """Test CIResult serialization to dictionary."""
        study_result = StudyResult(
            study_name="ci_test",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=10.0,
            stage_results=[],
            final_survivors=["case1"],
            aborted=False,
        )

        ci_result = CIResult(
            study_result=study_result,
            regressions_detected=[("case1", "WNS regression")],
            passed=False,
            failure_reason="Regressions detected",
            exit_code=2,
        )

        result_dict = ci_result.to_dict()

        assert result_dict["study_name"] == "ci_test"
        assert result_dict["passed"] is False
        assert result_dict["exit_code"] == 2
        assert result_dict["failure_reason"] == "Regressions detected"
        assert len(result_dict["regressions_detected"]) == 1
        assert result_dict["regressions_detected"][0]["case_name"] == "case1"

    def test_ci_result_to_dict_serializable(self):
        """Test that CIResult.to_dict() produces JSON-serializable output."""
        study_result = StudyResult(
            study_name="ci_test",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=10.0,
            stage_results=[],
            final_survivors=["case1"],
            aborted=False,
        )

        ci_result = CIResult(
            study_result=study_result,
            regressions_detected=[("case1", "WNS regression")],
            passed=False,
            failure_reason="Regressions detected",
            exit_code=2,
        )

        result_dict = ci_result.to_dict()

        # Should be JSON-serializable
        json_str = json.dumps(result_dict)
        assert len(json_str) > 0


class TestCIIntegrationFeatureSteps:
    """Test all 6 feature steps for CI integration."""

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step1_configure_study_with_locked_safety_domain(
        self, mock_executor_class
    ):
        """Step 1: Configure Study with 'locked' safety domain."""
        study = StudyConfig(
            name="ci_regression_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.LOCKED,  # Required for CI
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                        ECOClass.PLACEMENT_LOCAL,
                    ],
                )
            ],
        )

        # Verify 'locked' safety domain
        assert study.safety_domain == SafetyDomain.LOCKED

        # Verify CI config accepts it
        config = CIConfig(
            study_config=study,
            baselines=[],
            fail_on_regression=False,
        )

        is_valid, issues = config.validate()
        assert is_valid

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step2_define_regression_baselines(self, mock_executor_class):
        """Step 2: Define regression test Cases with known-good baselines."""
        study = StudyConfig(
            name="ci_regression_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        # Define known-good baselines from previous runs
        baselines = [
            RegressionBaseline(
                case_name="base_case",
                expected_wns_ps=-450,
                tolerance_ps=100,
                metadata={"source": "golden_run_2024_01_01"},
            ),
            RegressionBaseline(
                case_name="eco_variant_1",
                expected_wns_ps=-320,
                tolerance_ps=100,
                metadata={"source": "golden_run_2024_01_01"},
            ),
        ]

        config = CIConfig(
            study_config=study,
            baselines=baselines,
        )

        # Verify baselines are stored
        assert len(config.baselines) == 2
        assert config.baselines[0].case_name == "base_case"

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step3_execute_study_in_ci_pipeline(self, mock_executor_class):
        """Step 3: Execute Study in CI pipeline."""
        study = StudyConfig(
            name="ci_regression_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        baseline = RegressionBaseline(
            case_name="test_case",
            expected_wns_ps=-500,
            tolerance_ps=100,
        )

        config = CIConfig(
            study_config=study,
            baselines=[baseline],
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        study_result = StudyResult(
            study_name="ci_regression_test",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=10.0,
            stage_results=[],
            final_survivors=["test_case"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result

        # Execute Study in CI mode
        runner = CIRunner(config)
        result = runner.run()

        # Verify execution completed
        assert result.study_result.study_name == "ci_regression_test"
        mock_executor.execute.assert_called_once()

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step4_detect_and_report_regressions(self, mock_executor_class):
        """Step 4: Verify any regressions are detected and reported."""
        study = StudyConfig(
            name="ci_regression_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        baseline = RegressionBaseline(
            case_name="test_case",
            expected_wns_ps=-500,
            tolerance_ps=100,
        )

        config = CIConfig(
            study_config=study,
            baselines=[baseline],
        )

        # Mock executor with regression
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        trial_result = create_mock_trial_result(
            case_name="test_case",
            eco_name="noop",
            wns_ps=-800,  # REGRESSION!
            success=True,
        )

        stage_result = StageResult(
            stage_index=0,
            stage_name="stage0",
            trials_executed=1,
            survivors=["test_case"],
            total_runtime_seconds=10.0,
            trial_results=[trial_result],
        )

        study_result = StudyResult(
            study_name="ci_regression_test",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=10.0,
            stage_results=[stage_result],
            final_survivors=["test_case"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result

        # Run CI
        runner = CIRunner(config)
        result = runner.run()

        # Verify regression detected
        assert len(result.regressions_detected) == 1
        case_name, reason = result.regressions_detected[0]
        assert case_name == "test_case"
        assert "regression" in reason.lower()
        assert "-800" in reason  # Actual WNS
        assert "-500" in reason  # Expected WNS

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step5_fail_ci_build_on_safety_violation(self, mock_executor_class):
        """Step 5: Fail CI build if safety violations occur."""
        study = StudyConfig(
            name="ci_regression_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        baseline = RegressionBaseline(
            case_name="test_case",
            expected_wns_ps=-500,
            tolerance_ps=100,
        )

        config = CIConfig(
            study_config=study,
            baselines=[baseline],
            fail_on_study_abort=True,  # Fail on safety violations
        )

        # Mock executor with Study abort (safety violation)
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        study_result = StudyResult(
            study_name="ci_regression_test",
            total_stages=1,
            stages_completed=0,
            total_runtime_seconds=10.0,
            stage_results=[],
            final_survivors=[],
            aborted=True,
            abort_reason="Base case failed structural runnability",
        )

        mock_executor.execute.return_value = study_result

        # Run CI
        runner = CIRunner(config)
        result = runner.run()

        # Verify CI failed
        assert not result.passed
        assert result.exit_code != 0
        assert "aborted" in result.failure_reason.lower()

    @patch("src.controller.ci_runner.StudyExecutor")
    def test_step6_ci_integration_is_deterministic(self, mock_executor_class):
        """Step 6: Confirm CI integration is stable and deterministic."""
        study = StudyConfig(
            name="ci_regression_test",
            pdk="Nangate45",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="test_base",
            snapshot_path="/fake/path",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        baseline = RegressionBaseline(
            case_name="test_case",
            expected_wns_ps=-500,
            tolerance_ps=100,
        )

        config = CIConfig(
            study_config=study,
            baselines=[baseline],
        )

        # Mock executor
        mock_executor = MagicMock()
        mock_executor_class.return_value = mock_executor

        trial_result = create_mock_trial_result(
            case_name="test_case",
            eco_name="noop",
            wns_ps=-480,  # Within tolerance
            success=True,
        )

        stage_result = StageResult(
            stage_index=0,
            stage_name="stage0",
            trials_executed=1,
            survivors=["test_case"],
            total_runtime_seconds=10.0,
            trial_results=[trial_result],
        )

        study_result = StudyResult(
            study_name="ci_regression_test",
            total_stages=1,
            stages_completed=1,
            total_runtime_seconds=10.0,
            stage_results=[stage_result],
            final_survivors=["test_case"],
            aborted=False,
        )

        mock_executor.execute.return_value = study_result

        # Run CI multiple times
        runner1 = CIRunner(config)
        result1 = runner1.run()

        runner2 = CIRunner(config)
        result2 = runner2.run()

        # Verify deterministic results
        assert result1.passed == result2.passed
        assert result1.exit_code == result2.exit_code
        assert len(result1.regressions_detected) == len(result2.regressions_detected)

        # Verify both passed (no regressions)
        assert result1.passed
        assert result2.passed
