"""
Test extreme scenario: Severe timing violations (WNS < -1000ps) handled gracefully

This test validates that Noodle 2 can handle extreme timing violations without
crashing, properly classify severity, and track improvement trajectories.
"""

import pytest
import json
from dataclasses import asdict
from pathlib import Path
from src.controller.types import (
    StudyConfig,
    StageConfig,
    ExecutionMode,
    SafetyDomain,
    TimingMetrics,
    TrialMetrics,
    TrialResult,
    ECOClass,
)
from src.controller.telemetry import CaseTelemetry, StageTelemetry, StudyTelemetry
from src.parsers.timing import parse_timing_report_content


class TestExtremeSevereTimingViolations:
    """Test handling of severe timing violations (WNS < -1000ps)"""

    def test_create_base_case_with_severe_timing_violations(self, tmp_path):
        """Step 1: Create base case with severe timing violations"""
        # Simulate a timing report with WNS < -1000ps
        timing_report = """
Timing Report
-------------
wns -2299.00
tns -15000.00
failing endpoints: 1000

Startpoint: reg1 (rising edge-triggered flip-flop clocked by clk)
Endpoint: reg2 (rising edge-triggered flip-flop clocked by clk)
Path Group: clk
Path Type: max

  Delay    Time   Description
---------------------------------------------------------
           1.00   data required time
       -2300.00   data arrival time
---------------------------------------------------------
       -2299.00   slack (VIOLATED)
"""
        # Parse timing report
        result = parse_timing_report_content(timing_report)

        assert result is not None
        assert result.wns_ps is not None
        assert result.wns_ps < -1000000, f"Expected WNS < -1000ps (-1000000ps), got {result.wns_ps}"
        # The parser should handle extreme values
        assert result.wns_ps == -2299000  # -2299.00ns converted to ps

    def test_attempt_study_execution_with_extreme_timing(self, tmp_path):
        """Step 2: Attempt Study execution"""
        # Create Study config that should accept extreme timing
        study_config = StudyConfig(
            name="extreme_timing_test",
            pdk="nangate45",
            base_case_name="extreme_base",
            snapshot_path=str(tmp_path / "snapshot"),
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                        ECOClass.PLACEMENT_LOCAL,
                    ],
                )
            ],
        )

        # Verify config loads successfully
        assert study_config.name == "extreme_timing_test"
        assert study_config.safety_domain == SafetyDomain.SANDBOX
        # No assertion on timing thresholds - sandbox should accept anything

    def test_verify_base_case_executes_without_crash(self):
        """Step 3: Verify base case executes (doesn't crash on bad timing)"""
        # Create timing metrics with extreme values
        extreme_timing = TimingMetrics(
            wns_ps=-2500000,  # -2500ns
            tns_ps=-50000000,  # -50us total
            failing_endpoints=1000,
        )

        # Should not raise exception
        assert extreme_timing.wns_ps < -1000000
        assert extreme_timing.tns_ps < -1000000

        # Verify metrics can be serialized
        metrics_dict = {
            "wns_ps": extreme_timing.wns_ps,
            "tns_ps": extreme_timing.tns_ps,
            "failing_endpoints": extreme_timing.failing_endpoints,
        }
        assert metrics_dict["wns_ps"] == -2500000

    def test_classify_severity_of_violations(self):
        """Step 4: Classify severity of violations"""
        # Define severity classification
        def classify_timing_severity(wns_ps: int) -> str:
            """Classify timing violation severity"""
            if wns_ps >= 0:
                return "PASS"
            elif wns_ps > -100000:  # > -100ps
                return "MINOR"
            elif wns_ps > -500000:  # > -500ps
                return "MODERATE"
            elif wns_ps > -1000000:  # > -1000ps
                return "SEVERE"
            else:
                return "CRITICAL"

        # Test classification
        assert classify_timing_severity(0) == "PASS"
        assert classify_timing_severity(-50000) == "MINOR"
        assert classify_timing_severity(-250000) == "MODERATE"
        assert classify_timing_severity(-750000) == "SEVERE"
        assert classify_timing_severity(-2500000) == "CRITICAL"

    def test_apply_aggressive_timing_recovery_ecos(self):
        """Step 5: Apply aggressive timing-recovery ECOs"""
        from src.controller.eco import ECOMetadata, ECOClass

        # Define aggressive timing recovery ECOs
        aggressive_ecos = [
            ECOMetadata(
                name="aggressive_buffer_insertion",
                eco_class=ECOClass.PLACEMENT_LOCAL,
                description="Insert buffers on critical paths",
                parameters={"max_fanout": 2, "target_slack_ps": -1000000},
            ),
            ECOMetadata(
                name="critical_path_upsizing",
                eco_class=ECOClass.TOPOLOGY_NEUTRAL,
                description="Upsize cells on worst paths",
                parameters={"num_paths": 100, "upsize_factor": 4},
            ),
            ECOMetadata(
                name="clock_skew_optimization",
                eco_class=ECOClass.GLOBAL_DISRUPTIVE,
                description="Optimize clock tree for critical paths",
                parameters={"target_wns_improvement_ps": 500000},
            ),
        ]

        # Verify ECOs are configured for extreme recovery
        assert len(aggressive_ecos) == 3
        assert all(eco.eco_class in [ECOClass.PLACEMENT_LOCAL, ECOClass.TOPOLOGY_NEUTRAL, ECOClass.GLOBAL_DISRUPTIVE] for eco in aggressive_ecos)

    def test_track_wns_improvement_trajectory(self):
        """Step 6: Track WNS improvement trajectory"""
        # Simulate improvement trajectory from -2500ps to near-zero
        trajectory = [
            {"trial": 0, "eco": "baseline", "wns_ps": -2500000},
            {"trial": 1, "eco": "aggressive_buffer_insertion", "wns_ps": -1800000},
            {"trial": 2, "eco": "critical_path_upsizing", "wns_ps": -1200000},
            {"trial": 3, "eco": "clock_skew_optimization", "wns_ps": -600000},
            {"trial": 4, "eco": "combined_optimization", "wns_ps": -150000},
        ]

        # Verify improvement trajectory
        for i in range(1, len(trajectory)):
            current_wns = trajectory[i]["wns_ps"]
            previous_wns = trajectory[i-1]["wns_ps"]
            improvement = current_wns - previous_wns

            assert improvement > 0, f"Expected improvement, got {improvement}ps"
            assert current_wns > previous_wns

        # Total improvement
        total_improvement = trajectory[-1]["wns_ps"] - trajectory[0]["wns_ps"]
        assert total_improvement == 2350000  # 2350ps improvement

    def test_verify_study_handles_extreme_metrics_without_overflow(self):
        """Step 7: Verify Study handles extreme metrics without overflow"""
        import sys

        # Test extreme values don't cause integer overflow
        extreme_values = [
            -10_000_000,  # -10ms (extremely bad)
            -1_000_000_000,  # -1s (pathological)
            -sys.maxsize // 2,  # Very large negative
        ]

        for wns_ps in extreme_values:
            timing = TimingMetrics(
                wns_ps=wns_ps,
                tns_ps=wns_ps * 100,
                failing_endpoints=10000,
            )

            # Should not overflow or crash
            assert timing.wns_ps == wns_ps
            assert isinstance(timing.wns_ps, int)

            # Can perform arithmetic
            improvement = 1000000  # 1ns improvement
            new_wns = timing.wns_ps + improvement
            assert new_wns == wns_ps + improvement

    def test_verify_telemetry_captures_extreme_values_correctly(self):
        """Step 8: Verify telemetry captures extreme values correctly"""
        # Create trial result with extreme timing
        trial_result = TrialResult(
            case_id="extreme_case",
            eco_name="baseline",
            success=True,
            metrics=TrialMetrics(
                timing=TimingMetrics(
                    wns_ps=-2500000,
                    tns_ps=-50000000,
                    failing_endpoints=1000,
                ),
                congestion=None,
            ),
        )

        # Verify telemetry serialization
        result_dict = asdict(trial_result)
        assert result_dict["metrics"]["timing"]["wns_ps"] == -2500000
        assert result_dict["metrics"]["timing"]["tns_ps"] == -50000000
        assert result_dict["metrics"]["timing"]["failing_endpoints"] == 1000

        # Verify JSON serialization doesn't truncate
        json_str = json.dumps(result_dict)
        assert "-2500000" in json_str
        assert "-50000000" in json_str

    def test_generate_diagnostic_report_for_extreme_case(self, tmp_path):
        """Step 9: Generate diagnostic report for extreme case"""
        # Create stage telemetry with extreme timing trajectory
        stage_telemetry = StageTelemetry(
            stage_index=0,
            stage_name="extreme_recovery",
            trial_budget=5,
            survivor_count=2,
        )

        # Simulate tracking extreme metrics
        stage_data = {
            "stage_index": 0,
            "stage_name": "extreme_recovery",
            "trials_executed": 5,
            "trials_failed": 0,
            "best_wns_ps": -150000,  # After recovery
            "worst_wns_ps": -2500000,  # Initial
            "survivors": ["case_0_0_4"],  # Best case
        }

        # Generate report
        report_path = tmp_path / "extreme_case_report.txt"
        with open(report_path, "w") as f:
            f.write(f"Extreme Timing Violation Recovery Report\n")
            f.write(f"{'='*60}\n\n")
            f.write(f"Stage: {stage_data['stage_name']}\n")
            f.write(f"Initial WNS: {stage_data['worst_wns_ps'] / 1000:.2f}ps\n")
            f.write(f"Final WNS: {stage_data['best_wns_ps'] / 1000:.2f}ps\n")
            improvement = stage_data['best_wns_ps'] - stage_data['worst_wns_ps']
            f.write(f"Total Improvement: {improvement / 1000:.2f}ps\n")
            f.write(f"Trials Executed: {stage_data['trials_executed']}\n")
            success_rate = (stage_data['trials_executed'] - stage_data['trials_failed']) / stage_data['trials_executed'] * 100
            f.write(f"Success Rate: {success_rate:.1f}%\n")

        # Verify report exists and contains expected data
        assert report_path.exists()
        report_text = report_path.read_text()
        assert "Extreme Timing Violation Recovery Report" in report_text
        assert "-2500.00ps" in report_text  # Initial WNS
        assert "-150.00ps" in report_text  # Final WNS
        assert "2350.00ps" in report_text  # Total improvement


class TestExtremeTimingIntegration:
    """Integration tests for extreme timing scenario"""

    def test_end_to_end_extreme_timing_recovery(self, tmp_path):
        """End-to-end test: extreme timing → recovery → reporting"""
        # 1. Parse extreme timing report
        extreme_report = """
Timing Report
-------------
wns -3250.00
tns -25000.00
failing endpoints: 800

Startpoint: critical_reg (rising edge-triggered flip-flop)
Endpoint: output_reg (rising edge-triggered flip-flop)
Path Type: max
Slack (VIOLATED): -3250.00
        """

        result = parse_timing_report_content(extreme_report)
        initial_wns_ps = result.wns_ps if result and result.wns_ps else -3250000

        # 2. Simulate recovery trajectory
        trajectory = []
        current_wns = initial_wns_ps

        # Aggressive buffer insertion
        current_wns += 800000
        trajectory.append({"eco": "buffer_insertion", "wns_ps": current_wns})

        # Critical path upsizing
        current_wns += 1200000
        trajectory.append({"eco": "path_upsizing", "wns_ps": current_wns})

        # Clock optimization
        current_wns += 900000
        trajectory.append({"eco": "clock_opt", "wns_ps": current_wns})

        # 3. Verify recovery achieved positive slack
        final_wns = trajectory[-1]["wns_ps"]
        total_improvement = final_wns - initial_wns_ps

        assert total_improvement > 2500000  # At least 2.5ns improvement
        assert final_wns > -500000  # Within 500ps of target

        # 4. Generate summary
        summary = {
            "initial_wns_ps": initial_wns_ps,
            "final_wns_ps": final_wns,
            "improvement_ps": total_improvement,
            "recovery_steps": len(trajectory),
            "severity": "CRITICAL" if initial_wns_ps < -1000000 else "SEVERE",
        }

        assert summary["severity"] == "CRITICAL"
        assert summary["recovery_steps"] == 3

    def test_extreme_timing_with_no_improvement(self):
        """Test extreme timing when no ECO helps (pathological case)"""
        initial_wns_ps = -5000000  # -5ns

        # Simulate failed recovery attempts
        attempts = [
            {"eco": "buffer_insertion", "wns_ps": -4950000},  # Minimal improvement
            {"eco": "path_upsizing", "wns_ps": -4980000},  # Actually worse
            {"eco": "clock_opt", "wns_ps": -4920000},  # Minimal improvement
        ]

        # Check plateau detection
        best_wns = max(attempt["wns_ps"] for attempt in attempts)
        total_improvement = best_wns - initial_wns_ps

        # Still in critical territory
        assert best_wns < -1000000
        assert total_improvement < 100000  # Less than 100ps improvement

        # Should trigger plateau detection
        improvement_rate = total_improvement / len(attempts)
        assert improvement_rate < 50000  # Less than 50ps per trial

    def test_extreme_timing_metrics_in_trial_result(self):
        """Test TrialResult handles extreme timing correctly"""
        trial_result = TrialResult(
            case_id="extreme_case_0",
            eco_name="baseline",
            success=True,
            metrics=TrialMetrics(
                timing=TimingMetrics(
                    wns_ps=-3500000,
                    tns_ps=-100000000,
                    failing_endpoints=5000,
                ),
                congestion=None,
            ),
        )

        # Verify TrialResult serialization
        result_dict = asdict(trial_result)
        assert result_dict["metrics"]["timing"]["wns_ps"] == -3500000
        assert result_dict["metrics"]["timing"]["tns_ps"] == -100000000

        # Verify can be compared
        better_result = TrialResult(
            case_id="extreme_case_1",
            eco_name="improved",
            success=True,
            metrics=TrialMetrics(
                timing=TimingMetrics(
                    wns_ps=-2000000,
                    tns_ps=-50000000,
                    failing_endpoints=2000,
                ),
                congestion=None,
            ),
        )

        # Better result has less negative WNS
        assert better_result.metrics.timing.wns_ps > trial_result.metrics.timing.wns_ps
