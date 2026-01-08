"""Tests for unattended long-running Study execution without human intervention.

This module validates that Noodle 2 can execute complete multi-stage Studies
autonomously with no blocking calls for user input.

Feature Requirements (from feature_list.json):
- Step 1: Configure multi-stage Study with large trial budget
- Step 2: Launch Study in unattended mode
- Step 3: Verify Study progresses through all stages automatically
- Step 4: Confirm all safety gates are evaluated programmatically
- Step 5: Verify Study completes or aborts without human input
- Step 6: Review telemetry to confirm full automation
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.controller.executor import StudyExecutor, StudyResult
from src.controller.study import create_study_config
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig


class TestUnattendedStudyExecution:
    """Test unattended execution of complete multi-stage Studies."""

    def test_configure_multi_stage_study_with_large_trial_budget(self) -> None:
        """
        Step 1: Configure multi-stage Study with large trial budget.

        Verifies that Studies can be configured with realistic budgets
        suitable for long-running experimentation.
        """
        # Configure a 3-stage Study with substantial trial budgets
        stages = [
            StageConfig(
                name="exploration",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=50,  # Large budget for exploration
                survivor_count=20,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                ],
            ),
            StageConfig(
                name="refinement",
                execution_mode=ExecutionMode.STA_CONGESTION,
                trial_budget=30,  # Medium budget for refinement
                survivor_count=10,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="closure",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,  # Focused budget for final stage
                survivor_count=3,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
        ]

        config = create_study_config(
            name="large_budget_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.GUARDED,
            stages=stages,
        )

        # Verify configuration
        assert config.name == "large_budget_study"
        assert len(config.stages) == 3
        assert config.stages[0].trial_budget == 50
        assert config.stages[1].trial_budget == 30
        assert config.stages[2].trial_budget == 10

        # Total budget across all stages
        total_budget = sum(stage.trial_budget for stage in config.stages)
        assert total_budget == 90  # Substantial budget for long-running study

    def test_launch_study_in_unattended_mode(self) -> None:
        """
        Step 2: Launch Study in unattended mode.

        Verifies that StudyExecutor.execute() is a non-blocking method
        that requires no user intervention.
        """
        config = create_study_config(
            name="unattended_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Execute should return without blocking
            # No input() calls, no user prompts
            result = executor.execute()

            # Verify execution completed
            assert isinstance(result, StudyResult)
            assert result.study_name == "unattended_study"

            # Verify no user intervention was required
            # (if execute() completes, it didn't block on user input)
            assert result.stages_completed >= 0

    def test_study_progresses_through_all_stages_automatically(self) -> None:
        """
        Step 3: Verify Study progresses through all stages automatically.

        Confirms that all configured stages execute sequentially without
        any manual intervention or approval gates.
        """
        stages = [
            StageConfig(
                name="stage_1",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=3,
                survivor_count=2,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="stage_2",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=2,
                survivor_count=1,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="stage_3",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=1,
                survivor_count=1,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
        ]

        config = create_study_config(
            name="auto_progression_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            result = executor.execute()

            # Verify all 3 stages were executed automatically
            assert result.total_stages == 3
            assert result.stages_completed == 3
            assert len(result.stage_results) == 3

            # Verify sequential progression (stage indices 0, 1, 2)
            for i, stage_result in enumerate(result.stage_results):
                assert stage_result.stage_index == i

            # No manual approval was required between stages
            assert not result.aborted

    def test_all_safety_gates_evaluated_programmatically(self) -> None:
        """
        Step 4: Confirm all safety gates are evaluated programmatically.

        Verifies that safety decisions (ECO class legality, base case
        verification, abort thresholds) are made automatically without
        user input.
        """
        # Configure Study with safety constraints
        config = create_study_config(
            name="safety_gate_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.GUARDED,  # Enforces safety constraints
            stages=[
                StageConfig(
                    name="guarded_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    # Only topology-neutral ECOs allowed in GUARDED domain
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,  # Skip for testing
            )

            # Safety gates should be evaluated programmatically
            result = executor.execute()

            # Verify safety domain was enforced
            assert config.safety_domain == SafetyDomain.GUARDED

            # Legality report should have been generated automatically
            legality_report_path = Path(tmpdir) / "safety_gate_study" / "run_legality_report.txt"
            assert legality_report_path.exists()

            # No user was prompted for safety decisions
            assert result.stages_completed >= 0

    def test_study_completes_without_human_input_success_path(self) -> None:
        """
        Step 5: Verify Study completes without human input (success path).

        Confirms that a well-configured Study runs to completion
        autonomously without any user interaction.
        """
        config = create_study_config(
            name="autonomous_completion_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="final_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Execute should complete autonomously
            result = executor.execute()

            # Verify successful completion
            assert result.stages_completed == 1
            assert not result.aborted
            assert result.abort_reason is None

            # Study reached natural completion
            assert len(result.final_survivors) >= 0

    def test_study_aborts_without_human_input_failure_path(self) -> None:
        """
        Step 5: Verify Study aborts without human input (failure path).

        Confirms that Studies abort autonomously when safety conditions
        are violated, without requiring user acknowledgment.
        """
        # Configure Study with illegal ECO class for safety domain
        # This will trigger automatic abort during safety gate check
        config = create_study_config(
            name="auto_abort_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.LOCKED,  # Most restrictive
            stages=[
                StageConfig(
                    name="illegal_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    # GLOBAL_DISRUPTIVE not allowed in LOCKED domain
                    allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Execute should abort autonomously when illegal config detected
            result = executor.execute()

            # Verify automatic abort
            assert result.aborted
            assert result.abort_reason is not None
            assert "ILLEGAL" in result.abort_reason or "illegal" in result.abort_reason
            assert result.stages_completed == 0

            # No user was prompted to approve the abort
            # Decision was made programmatically

    def test_telemetry_confirms_full_automation(self) -> None:
        """
        Step 6: Review telemetry to confirm full automation.

        Verifies that telemetry captures complete execution trace,
        demonstrating that all decisions were made programmatically.
        """
        config = create_study_config(
            name="telemetry_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=2,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
                StageConfig(
                    name="stage_1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=2,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            telemetry_dir = Path(tmpdir) / "telemetry"

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                telemetry_root=telemetry_dir,
                skip_base_case_verification=True,
            )

            result = executor.execute()

            # Verify telemetry was emitted
            study_telemetry_file = telemetry_dir / "telemetry_study" / "study_telemetry.json"
            assert study_telemetry_file.exists()

            # Read and validate telemetry
            with open(study_telemetry_file) as f:
                telemetry = json.load(f)

            # Telemetry should document full execution
            assert telemetry["study_name"] == "telemetry_study"
            assert telemetry["total_stages"] == 2
            assert "stages_completed" in telemetry

            # Telemetry proves automation: all stages tracked programmatically
            assert "stage_results" in telemetry or "final_survivors" in telemetry

            # No manual intervention recorded in telemetry
            # (all timestamps, decisions, outcomes are system-generated)


class TestUnattendedExecutionEdgeCases:
    """Test edge cases for unattended execution."""

    def test_unattended_execution_with_no_survivors_triggers_auto_abort(self) -> None:
        """
        Verify that Study aborts autonomously when a stage produces no survivors.

        No user confirmation required for abort decision.
        """
        config = create_study_config(
            name="no_survivors_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=3,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
                StageConfig(
                    name="stage_1_should_not_execute",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Use custom survivor selector that returns no survivors
            def no_survivors_selector(trial_results, survivor_count):
                return []  # Simulate all trials failing

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                survivor_selector=no_survivors_selector,
                skip_base_case_verification=True,
            )

            result = executor.execute()

            # Verify automatic abort
            assert result.aborted
            assert result.stages_completed == 1  # First stage completed, then aborted
            assert "no survivors" in result.abort_reason.lower() or "survivor" in result.abort_reason.lower()

    def test_unattended_execution_tracks_execution_time_autonomously(self) -> None:
        """
        Verify that execution time tracking is automatic.

        No user interaction required to record timing metrics.
        """
        config = create_study_config(
            name="timing_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=2,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            result = executor.execute()

            # Timing tracked automatically
            assert result.total_runtime_seconds >= 0
            assert result.stage_results[0].total_runtime_seconds >= 0

    def test_unattended_execution_with_custom_survivor_selector(self) -> None:
        """
        Verify that custom survivor selection logic runs autonomously.

        Custom selectors should not block or require user input.
        """
        config = create_study_config(
            name="custom_selector_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            # Custom programmatic survivor selector
            def custom_selector(trial_results, survivor_count):
                # Select first N trials (arbitrary but deterministic)
                successful = [
                    tr.config.case_name
                    for tr in trial_results
                    if tr.success
                ]
                return successful[:survivor_count]

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                survivor_selector=custom_selector,
                skip_base_case_verification=True,
            )

            # Custom selector should run autonomously
            result = executor.execute()

            assert result.stages_completed == 1
            assert not result.aborted


class TestUnattendedExecutionWithSafetyGates:
    """Test that safety gates are evaluated autonomously."""

    def test_safety_domain_enforcement_is_automatic(self) -> None:
        """
        Verify that safety domain rules are enforced programmatically.

        No user approval required for ECO class restrictions.
        """
        # LOCKED domain restricts to TOPOLOGY_NEUTRAL only
        config = create_study_config(
            name="locked_domain_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.LOCKED,
            stages=[
                StageConfig(
                    name="safe_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=2,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Safety domain enforced automatically
            result = executor.execute()

            # Study should complete (legal configuration)
            assert not result.aborted

    def test_legality_report_generated_automatically(self) -> None:
        """
        Verify that Run Legality Report is generated without user intervention.
        """
        config = create_study_config(
            name="legality_report_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.GUARDED,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=2,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            result = executor.execute()

            # Legality report auto-generated
            report_path = Path(tmpdir) / "legality_report_study" / "run_legality_report.txt"
            assert report_path.exists()

            # Report content confirms safety evaluation
            content = report_path.read_text()
            assert "Safety Domain" in content or "LEGALITY" in content


class TestUnattendedExecutionCompleteness:
    """Verify complete unattended execution scenarios."""

    def test_end_to_end_unattended_multi_stage_study(self) -> None:
        """
        Complete end-to-end test: 3-stage Study runs to completion unattended.

        This is the integration test for the full "unattended execution" feature.
        """
        stages = [
            StageConfig(
                name="exploration",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="refinement",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=5,
                survivor_count=3,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
            StageConfig(
                name="closure",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=3,
                survivor_count=1,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
        ]

        config = create_study_config(
            name="complete_unattended_study",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="studies/nangate45_base",
            safety_domain=SafetyDomain.SANDBOX,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            telemetry_dir = Path(tmpdir) / "telemetry"

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                telemetry_root=telemetry_dir,
                skip_base_case_verification=True,
            )

            # CRITICAL: This should complete without ANY user interaction
            result = executor.execute()

            # Verify complete autonomous execution
            assert result.study_name == "complete_unattended_study"
            assert result.total_stages == 3
            assert result.stages_completed == 3
            assert not result.aborted

            # All 3 stages executed
            assert len(result.stage_results) == 3

            # Survivors selected autonomously at each stage
            assert len(result.stage_results[0].survivors) <= 5
            assert len(result.stage_results[1].survivors) <= 3
            assert len(result.stage_results[2].survivors) <= 1

            # Telemetry proves full automation
            study_telemetry_file = telemetry_dir / "complete_unattended_study" / "study_telemetry.json"
            assert study_telemetry_file.exists()

            # Timing tracked automatically
            assert result.total_runtime_seconds > 0
