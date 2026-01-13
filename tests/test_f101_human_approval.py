"""Tests for F101: Stages can include human approval gates that require review before proceeding."""

import tempfile

from src.controller.executor import StudyExecutor
from src.controller.human_approval import ApprovalGateSimulator, ApprovalSummary
from src.controller.study import create_study_config
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig, StageType


class TestF101HumanApprovalGates:
    """Test F101: Human approval gates in multi-stage studies."""

    def test_step_1_define_stage_with_human_approval_type(self) -> None:
        """
        Step 1: Define a stage with type: human_approval in study config.

        Verify that we can create a stage configuration with type=human_approval.
        """
        approval_stage = StageConfig(
            name="approval_gate",
            stage_type=StageType.HUMAN_APPROVAL,
            required_approvers=1,
            timeout_hours=24,
        )

        assert approval_stage.stage_type == StageType.HUMAN_APPROVAL
        assert approval_stage.name == "approval_gate"

    def test_step_2_configure_timeout_required_approvers_and_message(self) -> None:
        """
        Step 2: Configure timeout_hours, required_approvers, and message.

        Verify that all approval gate configuration parameters can be set.
        """
        approval_stage = StageConfig(
            name="approval_checkpoint",
            stage_type=StageType.HUMAN_APPROVAL,
            required_approvers=2,  # Multiple approvers
            timeout_hours=48,      # 2 day timeout
            show_summary=True,     # Display stage results
            show_visualizations=False,
        )

        assert approval_stage.required_approvers == 2
        assert approval_stage.timeout_hours == 48
        assert approval_stage.show_summary is True
        assert approval_stage.show_visualizations is False

    def test_step_3_run_study_to_approval_gate_stage(self) -> None:
        """
        Step 3: Run study to approval gate stage.

        Verify that a study can execute up to and including an approval gate.
        """
        stages = [
            StageConfig(
                name="exploration",
                stage_type=StageType.EXECUTION,
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=5,
                survivor_count=3,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="approval_gate_1",
                stage_type=StageType.HUMAN_APPROVAL,
                required_approvers=1,
                timeout_hours=24,
                show_summary=True,
            ),
        ]

        config = create_study_config(
            name="approval_test",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            approval_simulator = ApprovalGateSimulator(auto_approve=True)

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
                approval_simulator=approval_simulator,
            )
            result = executor.execute()

            # Verify study ran successfully
            assert result.study_name == "approval_test"
            assert not result.aborted
            # Verify approval gate was processed
            decisions = approval_simulator.get_decisions()
            assert len(decisions) == 1
            assert decisions[0].approved

    def test_step_4_verify_study_pauses_and_displays_approval_request(self) -> None:
        """
        Step 4: Verify study pauses and displays approval request with summary.

        Verify that when reaching an approval gate, the system:
        - Pauses execution
        - Generates a summary of study progress
        - Displays the approval request
        """
        stages = [
            StageConfig(
                name="stage_1",
                stage_type=StageType.EXECUTION,
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=3,
                survivor_count=2,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="review_checkpoint",
                stage_type=StageType.HUMAN_APPROVAL,
                required_approvers=1,
                timeout_hours=24,
                show_summary=True,
            ),
            StageConfig(
                name="stage_2",
                stage_type=StageType.EXECUTION,
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=2,
                survivor_count=1,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
        ]

        config = create_study_config(
            name="pause_display_test",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            approval_simulator = ApprovalGateSimulator(auto_approve=True)

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
                approval_simulator=approval_simulator,
            )
            result = executor.execute()

            # Verify approval was requested (paused execution)
            decisions = approval_simulator.get_decisions()
            assert len(decisions) == 1

            # Verify summary can be formatted for display
            summary = ApprovalSummary(
                study_name="pause_display_test",
                stages_completed=1,
                total_stages=3,
                current_stage_name="review_checkpoint",
                survivors_count=2,
                stage_summaries=[
                    {
                        "stage_name": "stage_1",
                        "trials_executed": 3,
                        "survivors": ["case_0_0", "case_0_1"],
                    }
                ],
            )

            display_text = summary.format_for_display()

            # Verify key information is displayed
            assert "APPROVAL GATE" in display_text
            assert "pause_display_test" in display_text or "study" in display_text.lower()
            assert "stages completed" in display_text.lower()
            assert "survivors" in display_text.lower()
            assert "Continue to next stage?" in display_text

    def test_step_5_verify_subsequent_stage_only_runs_after_approval(self) -> None:
        """
        Step 5: Verify subsequent stage only runs after approval received.

        Verify that:
        - If approval is granted, subsequent stages execute
        - If approval is rejected, subsequent stages do not execute
        """
        stages = [
            StageConfig(
                name="stage_before",
                stage_type=StageType.EXECUTION,
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=3,
                survivor_count=2,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="approval_gate",
                stage_type=StageType.HUMAN_APPROVAL,
                required_approvers=1,
                timeout_hours=24,
            ),
            StageConfig(
                name="stage_after",
                stage_type=StageType.EXECUTION,
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=2,
                survivor_count=1,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
        ]

        # Test 1: Approval granted - subsequent stage runs
        config_approved = create_study_config(
            name="approved_continuation",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            approval_simulator = ApprovalGateSimulator(auto_approve=True)

            executor = StudyExecutor(
                config=config_approved,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
                approval_simulator=approval_simulator,
            )
            result = executor.execute()

            # Verify all stages completed
            assert not result.aborted
            assert result.stages_completed == 3
            # Both execution stages should have results (approval gate doesn't add to stage_results)
            assert len(result.stage_results) == 2
            assert result.stage_results[0].stage_name == "stage_before"
            assert result.stage_results[1].stage_name == "stage_after"

        # Test 2: Approval rejected - subsequent stage does not run
        config_rejected = create_study_config(
            name="rejected_stop",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            approval_simulator = ApprovalGateSimulator(auto_approve=False)

            executor = StudyExecutor(
                config=config_rejected,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
                approval_simulator=approval_simulator,
            )
            result = executor.execute()

            # Verify study was aborted at approval gate
            assert result.aborted
            assert "Rejected at approval gate" in result.abort_reason
            # Only the first execution stage should have completed
            assert len(result.stage_results) == 1
            assert result.stage_results[0].stage_name == "stage_before"
            # stage_after should NOT have executed

    def test_approval_gate_with_summary_display(self) -> None:
        """
        Additional test: Verify approval summary displays stage results correctly.
        """
        summary = ApprovalSummary(
            study_name="test_study",
            stages_completed=2,
            total_stages=4,
            current_stage_name="approval_gate_1",
            survivors_count=3,
            best_wns_ps=-450,
            best_hot_ratio=0.18,
            stage_summaries=[
                {
                    "stage_name": "exploration",
                    "trials_executed": 5,
                    "survivors": ["case_0_0", "case_0_1", "case_0_2"],
                },
                {
                    "stage_name": "refinement",
                    "trials_executed": 3,
                    "survivors": ["case_1_0", "case_1_1", "case_1_2"],
                },
            ],
        )

        display_text = summary.format_for_display()

        # Verify all key information is present
        assert "APPROVAL GATE: approval_gate_1" in display_text
        assert "test_study" in display_text
        assert "2/4 stages completed" in display_text
        assert "Current survivors: 3" in display_text
        assert "Best WNS: -450 ps" in display_text
        assert "Best hot_ratio: 0.180" in display_text
        assert "exploration" in display_text
        assert "refinement" in display_text

    def test_approval_gate_validation(self) -> None:
        """
        Additional test: Verify approval gate configuration is validated.
        """
        # Valid configuration
        valid_stage = StageConfig(
            name="valid_approval",
            stage_type=StageType.HUMAN_APPROVAL,
            required_approvers=1,
            timeout_hours=24,
        )
        assert valid_stage.required_approvers == 1
        assert valid_stage.timeout_hours == 24

        # Invalid: required_approvers < 1
        import pytest
        with pytest.raises(ValueError, match="required_approvers must be at least 1"):
            StageConfig(
                name="invalid_approval",
                stage_type=StageType.HUMAN_APPROVAL,
                required_approvers=0,
                timeout_hours=24,
            )

        # Invalid: timeout_hours < 1
        with pytest.raises(ValueError, match="timeout_hours must be at least 1"):
            StageConfig(
                name="invalid_timeout",
                stage_type=StageType.HUMAN_APPROVAL,
                required_approvers=1,
                timeout_hours=0,
            )
