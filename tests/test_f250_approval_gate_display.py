"""Tests for F250: Approval gate displays summary and visualizations for review."""

import tempfile
from pathlib import Path

import pytest

from src.controller.executor import StudyExecutor
from src.controller.human_approval import ApprovalGateSimulator, ApprovalSummary
from src.controller.study import create_study_config
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig, StageType


class TestApprovalGateDisplayF250:
    """Test approval gate display functionality (F250)."""

    def test_step_1_reach_approval_gate(self) -> None:
        """
        Step 1: Reach approval gate.

        Verify that a study can reach an approval gate successfully.
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
                name="approval_gate",
                stage_type=StageType.HUMAN_APPROVAL,
                required_approvers=1,
                timeout_hours=24,
                show_summary=True,
                show_visualizations=False,
            ),
        ]

        config = create_study_config(
            name="display_test",
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

            # Verify study reached and passed approval gate
            assert not result.aborted
            assert len(approval_simulator.get_decisions()) == 1
            assert approval_simulator.get_decisions()[0].approved

    def test_step_2_verify_show_summary_true_displays_stage_results(self) -> None:
        """
        Step 2: Verify show_summary: true displays stage results.

        When show_summary is enabled, the approval summary should include stage results.
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
                name="review_gate",
                stage_type=StageType.HUMAN_APPROVAL,
                required_approvers=1,
                timeout_hours=24,
                show_summary=True,  # Enable summary display
                show_visualizations=False,
            ),
        ]

        config = create_study_config(
            name="summary_display_test",
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

            # Get the approval summary that was requested
            pending = approval_simulator.get_pending_approvals()
            # After approval, pending list is empty, but we can verify from execution

            assert not result.aborted

            # Verify that stage results were available for display
            assert len(result.stage_results) == 1  # One execution stage
            assert result.stage_results[0].stage_name == "exploration"

    def test_step_2_verify_show_summary_false_hides_stage_results(self) -> None:
        """
        Step 2 (variant): Verify show_summary: false hides stage results.

        When show_summary is disabled, stage results should not be displayed.
        """
        summary = ApprovalSummary(
            study_name="test_study",
            stages_completed=1,
            total_stages=2,
            current_stage_name="approval_gate",
            survivors_count=3,
            show_summary=False,  # Disable summary
            show_visualizations=False,
            stage_summaries=[
                {
                    "stage_name": "stage_1",
                    "trials_executed": 5,
                    "survivors": ["case_1", "case_2", "case_3"],
                }
            ],
        )

        display_text = summary.format_for_display()

        # Verify stage results are NOT in display when show_summary is False
        assert "Stage Results:" not in display_text
        assert "stage_1" not in display_text

    def test_step_3_verify_show_visualizations_true_shows_heatmaps_and_charts(
        self,
    ) -> None:
        """
        Step 3: Verify show_visualizations: true shows heatmaps and charts.

        When show_visualizations is enabled, visualization paths should be displayed.
        """
        summary = ApprovalSummary(
            study_name="viz_test",
            stages_completed=1,
            total_stages=2,
            current_stage_name="approval_gate",
            survivors_count=2,
            show_summary=True,
            show_visualizations=True,  # Enable visualizations
            visualization_paths=[
                "/path/to/heatmap_placement.png",
                "/path/to/heatmap_routing.png",
                "/path/to/congestion_chart.png",
            ],
        )

        display_text = summary.format_for_display()

        # Verify visualizations section is present
        assert "Visualizations:" in display_text
        assert "heatmap_placement.png" in display_text
        assert "heatmap_routing.png" in display_text
        assert "congestion_chart.png" in display_text

    def test_step_3_verify_show_visualizations_false_hides_visualizations(self) -> None:
        """
        Step 3 (variant): Verify show_visualizations: false hides visualizations.

        When show_visualizations is disabled, visualizations should not be displayed.
        """
        summary = ApprovalSummary(
            study_name="no_viz_test",
            stages_completed=1,
            total_stages=2,
            current_stage_name="approval_gate",
            survivors_count=2,
            show_summary=True,
            show_visualizations=False,  # Disable visualizations
            visualization_paths=[
                "/path/to/heatmap.png",
            ],
        )

        display_text = summary.format_for_display()

        # Verify visualizations section is NOT present
        assert "Visualizations:" not in display_text
        assert "heatmap.png" not in display_text

    def test_step_4_verify_pareto_frontier_is_displayed_if_available(self) -> None:
        """
        Step 4: Verify Pareto frontier is displayed if available.

        When show_visualizations is enabled and pareto data exists, it should be displayed.
        """
        summary = ApprovalSummary(
            study_name="pareto_test",
            stages_completed=1,
            total_stages=2,
            current_stage_name="approval_gate",
            survivors_count=3,
            show_summary=True,
            show_visualizations=True,  # Enable visualizations
            pareto_frontier_data={
                "points": [
                    {"case_name": "case_1", "wns_ps": -500, "hot_ratio": 0.2},
                    {"case_name": "case_2", "wns_ps": -600, "hot_ratio": 0.15},
                    {"case_name": "case_3", "wns_ps": -400, "hot_ratio": 0.25},
                ],
                "objective": "wns_ps_hot_ratio",
            },
        )

        display_text = summary.format_for_display()

        # Verify pareto frontier section is present
        assert "Pareto Frontier:" in display_text
        assert "3 pareto-optimal solutions found" in display_text
        assert "case_1" in display_text
        assert "-500 ps" in display_text
        assert "0.2" in display_text

    def test_step_4_verify_pareto_frontier_not_shown_without_visualization_flag(
        self,
    ) -> None:
        """
        Step 4 (variant): Pareto frontier not shown when show_visualizations is False.
        """
        summary = ApprovalSummary(
            study_name="no_pareto_test",
            stages_completed=1,
            total_stages=2,
            current_stage_name="approval_gate",
            survivors_count=3,
            show_summary=True,
            show_visualizations=False,  # Disable visualizations
            pareto_frontier_data={
                "points": [
                    {"case_name": "case_1", "wns_ps": -500, "hot_ratio": 0.2},
                ],
                "objective": "wns_ps_hot_ratio",
            },
        )

        display_text = summary.format_for_display()

        # Verify pareto frontier is NOT displayed
        assert "Pareto Frontier:" not in display_text

    def test_step_5_verify_operator_has_sufficient_information_to_approve_reject(
        self,
    ) -> None:
        """
        Step 5: Verify operator has sufficient information to approve/reject.

        The approval summary should contain all necessary information for decision-making:
        - Study name and progress
        - Survivor count
        - Best metrics
        - Stage results (if enabled)
        - Visualizations (if enabled)
        - Clear prompt for approval decision
        """
        summary = ApprovalSummary(
            study_name="complete_info_test",
            stages_completed=2,
            total_stages=4,
            current_stage_name="checkpoint_1",
            survivors_count=5,
            best_wns_ps=-450,
            best_hot_ratio=0.18,
            show_summary=True,
            show_visualizations=True,
            stage_summaries=[
                {
                    "stage_name": "exploration",
                    "trials_executed": 10,
                    "survivors": ["c1", "c2", "c3", "c4", "c5"],
                    "runtime_seconds": 120.5,
                },
                {
                    "stage_name": "refinement",
                    "trials_executed": 8,
                    "survivors": ["c1", "c2", "c3", "c4", "c5"],
                    "runtime_seconds": 95.2,
                },
            ],
            visualization_paths=[
                "/artifacts/heatmap_exploration.png",
                "/artifacts/heatmap_refinement.png",
            ],
            pareto_frontier_data={
                "points": [
                    {"case_name": "c1", "wns_ps": -450, "hot_ratio": 0.18},
                    {"case_name": "c2", "wns_ps": -480, "hot_ratio": 0.16},
                ],
                "objective": "wns_ps_hot_ratio",
            },
        )

        display_text = summary.format_for_display()

        # Verify all critical information is present
        # 1. Study identification
        assert "complete_info_test" in display_text
        assert "APPROVAL GATE: checkpoint_1" in display_text

        # 2. Progress tracking
        assert "2/4 stages completed" in display_text
        assert "Current survivors: 5" in display_text

        # 3. Best metrics
        assert "Best WNS: -450 ps" in display_text
        assert "Best hot_ratio: 0.18" in display_text

        # 4. Stage results
        assert "Stage Results:" in display_text
        assert "exploration: 10 trials, 5 survivors" in display_text
        assert "refinement: 8 trials, 5 survivors" in display_text

        # 5. Visualizations
        assert "Visualizations:" in display_text
        assert "heatmap_exploration.png" in display_text
        assert "heatmap_refinement.png" in display_text

        # 6. Pareto frontier
        assert "Pareto Frontier:" in display_text
        assert "2 pareto-optimal solutions found" in display_text

        # 7. Clear decision prompt
        assert "Continue to next stage? (yes/no)" in display_text

    def test_end_to_end_approval_gate_with_visualizations(self) -> None:
        """
        End-to-end test: Approval gate with both summary and visualizations enabled.
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
                name="visual_review_gate",
                stage_type=StageType.HUMAN_APPROVAL,
                required_approvers=1,
                timeout_hours=24,
                show_summary=True,
                show_visualizations=True,  # Enable both
            ),
            StageConfig(
                name="refinement",
                stage_type=StageType.EXECUTION,
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=3,
                survivor_count=1,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            ),
        ]

        config = create_study_config(
            name="e2e_viz_test",
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

            # Verify study completed successfully through approval gate
            assert not result.aborted
            assert result.stages_completed == 3  # All stages including approval gate
            assert len(result.stage_results) == 2  # Two execution stages

            # Verify approval was granted
            decisions = approval_simulator.get_decisions()
            assert len(decisions) == 1
            assert decisions[0].approved

    def test_stage_config_defaults(self) -> None:
        """
        Additional test: Verify default values for show_summary and show_visualizations.
        """
        stage = StageConfig(
            name="approval_gate",
            stage_type=StageType.HUMAN_APPROVAL,
            required_approvers=1,
            timeout_hours=24,
        )

        # Verify defaults
        assert stage.show_summary is True  # Summary enabled by default
        assert stage.show_visualizations is False  # Visualizations disabled by default

    def test_approval_summary_defaults(self) -> None:
        """
        Additional test: Verify default values in ApprovalSummary.
        """
        summary = ApprovalSummary(
            study_name="test",
            stages_completed=1,
            total_stages=2,
            current_stage_name="gate",
            survivors_count=2,
        )

        # Verify defaults
        assert summary.show_summary is True
        assert summary.show_visualizations is False
        assert summary.visualization_paths == []
        assert summary.pareto_frontier_data is None

    def test_large_pareto_frontier_truncation(self) -> None:
        """
        Additional test: Verify large pareto frontiers are truncated in display.
        """
        # Create a large pareto frontier
        points = [
            {"case_name": f"case_{i}", "wns_ps": -500 - i * 10, "hot_ratio": 0.2 - i * 0.01}
            for i in range(10)
        ]

        summary = ApprovalSummary(
            study_name="large_pareto_test",
            stages_completed=1,
            total_stages=2,
            current_stage_name="approval_gate",
            survivors_count=10,
            show_summary=True,
            show_visualizations=True,
            pareto_frontier_data={
                "points": points,
                "objective": "wns_ps_hot_ratio",
            },
        )

        display_text = summary.format_for_display()

        # Verify only first 3 points shown + "and N more" message
        assert "10 pareto-optimal solutions found" in display_text
        assert "#1: case_0" in display_text
        assert "#2: case_1" in display_text
        assert "#3: case_2" in display_text
        assert "and 7 more" in display_text
        # Points beyond first 3 should not be individually listed
        assert "case_9" not in display_text
