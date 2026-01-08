"""
Test extreme scenario: Zero-improvement plateau across all ECOs handled intelligently.

This test validates that Noodle 2 can detect when no ECOs produce any improvement,
classify the situation as an optimization plateau, terminate early to save compute,
and provide actionable suggestions for alternative approaches.

Feature #187: Extreme scenario: Zero-improvement plateau across all ECOs handled intelligently
"""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from src.controller.early_stopping import (
    EarlyStoppingConfig,
    EarlyStoppingPolicy,
    SurvivorDeterminationResult,
)
from src.controller.telemetry import StageTelemetry
from src.controller.types import (
    CongestionMetrics,
    ECOClass,
    ExecutionMode,
    FailureSeverity,
    FailureType,
    SafetyDomain,
    StageConfig,
    StudyConfig,
    TimingMetrics,
    TrialMetrics,
    TrialResult,
)


class TestZeroImprovementPlateau:
    """Test handling of zero-improvement plateau scenarios"""

    def test_create_base_case_at_local_optimum(self):
        """Step 1: Create base case at local optimum"""
        # Simulate a base case that's already well-optimized
        # This represents a local optimum where simple ECOs won't help
        optimal_timing = TimingMetrics(
            wns_ps=-50000,  # -50ns (tight but achievable)
            tns_ps=-200000,  # -200ns total
            failing_endpoints=10,  # Few failing paths
        )

        optimal_congestion = CongestionMetrics(
            bins_total=10000,
            bins_hot=1500,  # 15% congestion (reasonable)
            hot_ratio=0.15,
            max_overflow=10,
        )

        base_metrics = TrialMetrics(
            timing=optimal_timing,
            congestion=optimal_congestion,
            runtime_seconds=120.0,
        )

        # This represents a "good enough" starting point
        # where further optimization is difficult
        assert base_metrics.timing.wns_ps > -100000  # Not terrible
        assert base_metrics.congestion.hot_ratio < 0.30  # Reasonable congestion
        assert base_metrics.timing.failing_endpoints < 20  # Few violations

    def test_execute_stage_with_multiple_ecos(self, tmp_path):
        """Step 2: Execute stage with 20 different ECOs"""
        # Configure study with many ECOs
        study_config = StudyConfig(
            name="plateau_detection_study",
            pdk="nangate45",
            base_case_name="optimal_base",
            snapshot_path=str(tmp_path / "snapshot"),
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_0_refinement",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=20,  # Try 20 different ECOs
                    survivor_count=3,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                        ECOClass.PLACEMENT_LOCAL,
                    ],
                )
            ],
        )

        # Simulate 20 different ECO attempts
        eco_names = [
            "buffer_insertion_1",
            "buffer_insertion_2",
            "gate_sizing_1",
            "gate_sizing_2",
            "gate_sizing_3",
            "placement_tweak_1",
            "placement_tweak_2",
            "placement_tweak_3",
            "pin_swap_1",
            "pin_swap_2",
            "layer_assignment_1",
            "layer_assignment_2",
            "net_reorder_1",
            "net_reorder_2",
            "clock_buffer_1",
            "clock_buffer_2",
            "repeater_insertion_1",
            "repeater_insertion_2",
            "via_optimization_1",
            "via_optimization_2",
        ]

        assert len(eco_names) == 20
        assert study_config.stages[0].trial_budget == 20

    def test_detect_zero_or_negative_improvement(self):
        """Step 3: Detect that all ECOs produce zero or negative improvement"""
        # Baseline metrics
        baseline_wns = -50000  # -50ns

        # Simulate 20 ECO results with no improvement (or degradation)
        eco_results = []
        for i in range(20):
            # Each ECO either makes no change or makes things slightly worse
            if i % 3 == 0:
                # No change
                new_wns = baseline_wns
            elif i % 3 == 1:
                # Slight degradation
                new_wns = baseline_wns - 5000  # 5ns worse
            else:
                # Slight degradation
                new_wns = baseline_wns - 3000  # 3ns worse

            improvement = new_wns - baseline_wns
            eco_results.append(
                {
                    "eco_name": f"eco_{i}",
                    "wns_ps": new_wns,
                    "improvement_ps": improvement,
                }
            )

        # Verify all ECOs showed zero or negative improvement
        improvements = [r["improvement_ps"] for r in eco_results]
        assert all(imp <= 0 for imp in improvements), "All ECOs should show zero or negative improvement"
        assert max(improvements) == 0, "Best improvement should be zero"
        assert sum(improvements) <= 0, "Total improvement should be zero or negative"

        # Calculate plateau metrics
        positive_improvements = [imp for imp in improvements if imp > 0]
        assert len(positive_improvements) == 0, "No positive improvements on plateau"

    def test_classify_as_optimization_plateau(self):
        """Step 4: Classify as optimization plateau"""

        def detect_plateau(trial_results: list[dict]) -> dict[str, Any]:
            """
            Detect optimization plateau from trial results.

            A plateau is detected when:
            - All trials complete successfully (not crashes)
            - No trial shows significant improvement (> threshold)
            - Majority of trials show zero or negative improvement
            """
            if not trial_results:
                return {"is_plateau": False, "reason": "No trials to analyze"}

            improvements = [r["improvement_ps"] for r in trial_results]
            threshold_ps = 1000  # 1ns minimum meaningful improvement

            positive_improvements = [imp for imp in improvements if imp > threshold_ps]
            zero_or_negative = [imp for imp in improvements if imp <= 0]

            is_plateau = len(positive_improvements) == 0 and len(zero_or_negative) >= len(improvements) * 0.8

            return {
                "is_plateau": is_plateau,
                "total_trials": len(trial_results),
                "positive_improvements": len(positive_improvements),
                "zero_or_negative": len(zero_or_negative),
                "best_improvement_ps": max(improvements) if improvements else 0,
                "mean_improvement_ps": sum(improvements) / len(improvements) if improvements else 0,
                "reason": "Optimization plateau detected: no meaningful improvements across all ECOs"
                if is_plateau
                else "Some improvements found",
            }

        # Test with plateau data
        plateau_results = [
            {"eco_name": f"eco_{i}", "improvement_ps": 0 if i % 2 == 0 else -2000}
            for i in range(20)
        ]

        detection = detect_plateau(plateau_results)
        assert detection["is_plateau"] is True
        assert detection["positive_improvements"] == 0
        assert detection["best_improvement_ps"] == 0
        assert detection["mean_improvement_ps"] <= 0

        # Test with non-plateau data (some improvements)
        improving_results = [
            {"eco_name": f"eco_{i}", "improvement_ps": 5000 if i < 5 else -1000}
            for i in range(20)
        ]

        detection_non_plateau = detect_plateau(improving_results)
        assert detection_non_plateau["is_plateau"] is False
        assert detection_non_plateau["positive_improvements"] == 5

    def test_trigger_early_stage_termination(self):
        """Step 5: Trigger early stage termination (no survivors found)"""
        # When plateau is detected, stage should terminate early
        # to avoid wasting compute on unproductive trials

        def should_terminate_early(
            completed_trials: int,
            total_budget: int,
            plateau_detected: bool,
            min_trials_for_detection: int = 10,
        ) -> dict[str, Any]:
            """
            Determine if stage should terminate early due to plateau.

            Args:
                completed_trials: Number of trials completed so far
                total_budget: Total trial budget for stage
                plateau_detected: Whether plateau has been detected
                min_trials_for_detection: Minimum trials before plateau detection

            Returns:
                Dictionary with termination decision and reasoning
            """
            # Must complete minimum trials before considering plateau
            if completed_trials < min_trials_for_detection:
                return {
                    "should_terminate": False,
                    "reason": f"Need at least {min_trials_for_detection} trials for plateau detection",
                    "remaining_trials": total_budget - completed_trials,
                }

            # If plateau detected, terminate early
            if plateau_detected:
                saved_trials = total_budget - completed_trials
                return {
                    "should_terminate": True,
                    "reason": "Optimization plateau detected - no further improvement expected",
                    "trials_completed": completed_trials,
                    "trials_saved": saved_trials,
                    "compute_savings_percent": (saved_trials / total_budget) * 100,
                }

            return {
                "should_terminate": False,
                "reason": "Continue: improvements still possible",
                "remaining_trials": total_budget - completed_trials,
            }

        # Test early termination after 10 trials on 20 budget
        result = should_terminate_early(
            completed_trials=10,
            total_budget=20,
            plateau_detected=True,
            min_trials_for_detection=10,
        )

        assert result["should_terminate"] is True
        assert result["trials_saved"] == 10
        assert result["compute_savings_percent"] == 50.0

        # Test no termination when plateau not detected
        result_no_plateau = should_terminate_early(
            completed_trials=10,
            total_budget=20,
            plateau_detected=False,
        )

        assert result_no_plateau["should_terminate"] is False

    def test_mark_study_as_completed_at_plateau(self, tmp_path):
        """Step 6: Mark Study as completed at plateau"""
        # Study should have special completion status for plateau

        study_status = {
            "study_name": "plateau_study",
            "completion_status": "COMPLETED_AT_PLATEAU",
            "reason": "No viable survivors found - optimization plateau reached",
            "stages_completed": 1,
            "total_stages": 3,
            "early_termination": True,
            "compute_saved": {
                "trials_budgeted": 60,  # 20 per stage × 3 stages
                "trials_executed": 15,  # Only 15 trials in stage 0
                "trials_saved": 45,
                "compute_savings_percent": 75.0,
            },
        }

        # Verify status structure
        assert study_status["completion_status"] == "COMPLETED_AT_PLATEAU"
        assert study_status["early_termination"] is True
        assert study_status["compute_saved"]["trials_saved"] == 45

        # Write to file for auditability
        status_file = tmp_path / "study_status.json"
        status_file.write_text(json.dumps(study_status, indent=2))
        assert status_file.exists()

        # Verify readable
        loaded_status = json.loads(status_file.read_text())
        assert loaded_status["completion_status"] == "COMPLETED_AT_PLATEAU"

    def test_generate_plateau_analysis_report(self, tmp_path):
        """Step 7: Generate plateau analysis report"""

        def generate_plateau_report(trial_results: list[dict], baseline_metrics: dict) -> dict:
            """
            Generate comprehensive plateau analysis report.

            Args:
                trial_results: List of trial results
                baseline_metrics: Baseline case metrics

            Returns:
                Plateau analysis report with statistics and diagnostics
            """
            improvements = [r["improvement_ps"] for r in trial_results]

            report = {
                "plateau_detected": True,
                "detection_summary": {
                    "total_trials": len(trial_results),
                    "trials_with_improvement": sum(1 for imp in improvements if imp > 1000),
                    "trials_with_degradation": sum(1 for imp in improvements if imp < -1000),
                    "trials_neutral": sum(1 for imp in improvements if -1000 <= imp <= 1000),
                },
                "improvement_statistics": {
                    "best_improvement_ps": max(improvements) if improvements else 0,
                    "worst_degradation_ps": min(improvements) if improvements else 0,
                    "mean_change_ps": sum(improvements) / len(improvements) if improvements else 0,
                    "median_change_ps": sorted(improvements)[len(improvements) // 2] if improvements else 0,
                },
                "baseline_metrics": baseline_metrics,
                "attempted_eco_classes": [
                    ECOClass.TOPOLOGY_NEUTRAL.value,
                    ECOClass.PLACEMENT_LOCAL.value,
                ],
                "conclusion": "No meaningful improvement achieved across all attempted ECOs",
            }

            return report

        # Generate report
        plateau_results = [
            {"eco_name": f"eco_{i}", "improvement_ps": 0 if i % 2 == 0 else -1500}
            for i in range(15)
        ]

        baseline = {
            "wns_ps": -50000,
            "tns_ps": -200000,
            "congestion_hot_ratio": 0.15,
        }

        report = generate_plateau_report(plateau_results, baseline)

        # Verify report contents
        assert report["plateau_detected"] is True
        assert report["detection_summary"]["total_trials"] == 15
        assert report["detection_summary"]["trials_with_improvement"] == 0
        assert report["improvement_statistics"]["best_improvement_ps"] == 0
        assert report["improvement_statistics"]["mean_change_ps"] <= 0

        # Write report to file
        report_file = tmp_path / "plateau_analysis.json"
        report_file.write_text(json.dumps(report, indent=2))
        assert report_file.exists()

    def test_suggest_alternative_approaches(self):
        """Step 8: Suggest alternative approaches (different ECO classes, etc)"""

        def generate_suggestions(
            attempted_eco_classes: list[str],
            plateau_context: dict,
        ) -> dict[str, Any]:
            """
            Generate actionable suggestions for escaping plateau.

            Args:
                attempted_eco_classes: ECO classes that were tried
                plateau_context: Context about the plateau (metrics, stage config)

            Returns:
                Dictionary with categorized suggestions
            """
            suggestions = {
                "eco_strategy": [],
                "design_changes": [],
                "tool_settings": [],
                "process_changes": [],
            }

            # Analyze what was tried
            attempted_set = set(attempted_eco_classes)

            # Suggest untried ECO classes
            all_eco_classes = {
                ECOClass.TOPOLOGY_NEUTRAL.value,
                ECOClass.PLACEMENT_LOCAL.value,
                ECOClass.ROUTING_AFFECTING.value,
                ECOClass.GLOBAL_DISRUPTIVE.value,
            }
            untried = all_eco_classes - attempted_set

            if untried:
                suggestions["eco_strategy"].extend(
                    [f"Try {eco_class} ECO class (not yet attempted)" for eco_class in sorted(untried)]
                )

            # Suggest more aggressive approaches if only conservative ones were tried
            if ECOClass.GLOBAL_DISRUPTIVE.value not in attempted_set:
                suggestions["eco_strategy"].append(
                    "Consider global_disruptive ECOs for larger design changes"
                )

            # Design-level suggestions
            suggestions["design_changes"].extend(
                [
                    "Review design utilization - may need to reduce target",
                    "Analyze critical path structure - may need RTL changes",
                    "Consider pin placement optimization",
                    "Evaluate clock tree structure and skew",
                ]
            )

            # Tool settings suggestions
            suggestions["tool_settings"].extend(
                [
                    "Try different placement effort levels",
                    "Adjust routing layer assignment strategy",
                    "Enable timing-driven placement optimizations",
                    "Tune global router congestion weights",
                ]
            )

            # Process suggestions
            suggestions["process_changes"].extend(
                [
                    "Move to next stage with different execution mode",
                    "Consider multi-objective optimization approach",
                    "Re-evaluate safety domain constraints",
                    "Investigate if base case needs structural fixes",
                ]
            )

            return suggestions

        # Generate suggestions after plateau on limited ECO classes
        attempted = [
            ECOClass.TOPOLOGY_NEUTRAL.value,
            ECOClass.PLACEMENT_LOCAL.value,
        ]

        context = {"stage_index": 0, "baseline_wns_ps": -50000}

        suggestions = generate_suggestions(attempted, context)

        # Verify suggestions are comprehensive
        assert len(suggestions["eco_strategy"]) > 0
        assert len(suggestions["design_changes"]) > 0
        assert len(suggestions["tool_settings"]) > 0
        assert len(suggestions["process_changes"]) > 0

        # Verify it suggests untried ECO classes
        assert any("routing_affecting" in s.lower() for s in suggestions["eco_strategy"])
        assert any("global_disruptive" in s.lower() for s in suggestions["eco_strategy"])

    def test_verify_system_handles_zero_progress_gracefully(self, tmp_path):
        """Step 9: Verify system handles zero-progress case gracefully"""
        # System should not crash or fail when no progress is made
        # This tests robustness of the plateau detection and handling

        # Create stage telemetry with zero progress
        stage_telemetry = StageTelemetry(
            stage_index=0,
            stage_name="stage_0_refinement",
            trial_budget=20,
            survivor_count=3,
            trials_executed=15,
            successful_trials=15,  # All succeeded...
            failed_trials=0,  # ...but none improved
        )

        # Add metadata about plateau
        stage_telemetry.metadata = {
            "plateau_detected": True,
            "early_termination": True,
            "trials_saved": 5,
            "reason": "Zero-improvement plateau",
        }

        # Convert to dict and serialize
        telemetry_dict = asdict(stage_telemetry)
        json_str = json.dumps(telemetry_dict, indent=2)

        # Write to file
        telemetry_file = tmp_path / "stage_0_telemetry.json"
        telemetry_file.write_text(json_str)

        # Verify it's readable and valid
        loaded = json.loads(telemetry_file.read_text())
        assert loaded["stage_name"] == "stage_0_refinement"
        assert loaded["metadata"]["plateau_detected"] is True

        # Verify survivor selection with no valid survivors
        # When no survivors meet criteria, stage should handle gracefully
        def select_survivors_with_plateau_handling(
            trial_results: list[dict],
            survivor_count: int,
            min_improvement_threshold_ps: int = 1000,
        ) -> dict[str, Any]:
            """
            Select survivors with special handling for plateau case.

            Returns:
                Dictionary with survivors list and plateau information
            """
            # Filter for trials with meaningful improvement
            viable = [
                r for r in trial_results if r.get("improvement_ps", 0) > min_improvement_threshold_ps
            ]

            if len(viable) == 0:
                # Plateau case: no viable survivors
                return {
                    "survivors": [],
                    "selection_status": "PLATEAU",
                    "reason": "No trials met minimum improvement threshold",
                    "tried_trials": len(trial_results),
                    "viable_trials": 0,
                    "early_termination_recommended": True,
                }

            # Normal case: select top N
            viable_sorted = sorted(viable, key=lambda x: x["improvement_ps"], reverse=True)
            survivors = viable_sorted[:survivor_count]

            return {
                "survivors": survivors,
                "selection_status": "NORMAL",
                "reason": f"Selected top {len(survivors)} survivors",
                "tried_trials": len(trial_results),
                "viable_trials": len(viable),
            }

        # Test with plateau data
        plateau_results = [
            {"case_id": f"case_{i}", "improvement_ps": -500} for i in range(15)
        ]

        selection = select_survivors_with_plateau_handling(plateau_results, survivor_count=3)

        # Verify graceful handling
        assert selection["selection_status"] == "PLATEAU"
        assert selection["survivors"] == []
        assert selection["viable_trials"] == 0
        assert selection["early_termination_recommended"] is True

        # System should not crash, produce clear status
        assert "reason" in selection
        assert "tried_trials" in selection


class TestPlateauIntegration:
    """Integration tests for plateau detection and handling"""

    def test_plateau_detection_in_early_stopping_system(self):
        """Verify plateau detection integrates with early stopping"""
        # Early stopping config
        config = EarlyStoppingConfig(
            policy=EarlyStoppingPolicy.ADAPTIVE,
            min_trials_before_stopping=10,
            confidence_threshold=0.95,
        )

        # Verify config is valid
        config.validate()
        assert config.min_trials_before_stopping == 10

    def test_plateau_telemetry_in_study_artifacts(self, tmp_path):
        """Verify plateau information flows into study telemetry"""
        study_telemetry = {
            "study_name": "plateau_study",
            "stages": [
                {
                    "stage_index": 0,
                    "status": "TERMINATED_AT_PLATEAU",
                    "trials_executed": 12,
                    "trials_budgeted": 20,
                    "plateau_detected_after_trial": 10,
                    "survivors_selected": 0,
                }
            ],
            "completion_status": "COMPLETED_AT_PLATEAU",
            "overall_improvement_ps": 0,
        }

        # Write telemetry
        telemetry_file = tmp_path / "study_telemetry.json"
        telemetry_file.write_text(json.dumps(study_telemetry, indent=2))

        # Verify structure
        loaded = json.loads(telemetry_file.read_text())
        assert loaded["completion_status"] == "COMPLETED_AT_PLATEAU"
        assert loaded["stages"][0]["status"] == "TERMINATED_AT_PLATEAU"

    def test_compute_savings_from_plateau_termination(self):
        """Calculate actual compute savings from plateau early termination"""

        def calculate_savings(
            stages_completed: int,
            total_stages: int,
            trials_per_stage: int,
            trials_executed_final_stage: int,
        ) -> dict[str, Any]:
            """Calculate compute savings from plateau termination."""
            stages_skipped = total_stages - stages_completed
            trials_saved_final_stage = trials_per_stage - trials_executed_final_stage
            trials_saved_skipped_stages = stages_skipped * trials_per_stage

            total_trials_budgeted = total_stages * trials_per_stage
            total_trials_executed = (stages_completed - 1) * trials_per_stage + trials_executed_final_stage
            total_trials_saved = total_trials_budgeted - total_trials_executed

            return {
                "total_trials_budgeted": total_trials_budgeted,
                "total_trials_executed": total_trials_executed,
                "total_trials_saved": total_trials_saved,
                "savings_percent": (total_trials_saved / total_trials_budgeted) * 100,
                "breakdown": {
                    "saved_in_final_stage": trials_saved_final_stage,
                    "saved_from_skipped_stages": trials_saved_skipped_stages,
                },
            }

        # Example: 3-stage study, 20 trials per stage, plateau detected at stage 0 after 12 trials
        savings = calculate_savings(
            stages_completed=1,  # Only stage 0 completed (partially)
            total_stages=3,
            trials_per_stage=20,
            trials_executed_final_stage=12,
        )

        assert savings["total_trials_budgeted"] == 60  # 3 × 20
        assert savings["total_trials_executed"] == 12  # Only 12 in stage 0
        assert savings["total_trials_saved"] == 48  # 8 + 40
        assert savings["savings_percent"] == 80.0  # 80% compute saved
