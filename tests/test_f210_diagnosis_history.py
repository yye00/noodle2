"""Tests for F210: Diagnosis history is tracked and saved across stages."""

import json
from pathlib import Path

import pytest

from src.analysis.diagnosis import generate_complete_diagnosis
from src.controller.types import (
    CongestionMetrics,
    TimingMetrics,
    TimingPath,
)
from src.analysis.diagnosis_history import (
    DiagnosisHistory,
    StageDiagnosisEntry,
    IssueResolution,
    DiagnosisTrend,
    create_diagnosis_history,
)


class TestF210DiagnosisHistory:
    """
    Test suite for Feature F210: Diagnosis history tracking across stages.

    Steps from feature_list.json:
    1. Run multi-stage study with diagnosis enabled
    2. Verify diagnosis_history.json is created
    3. Verify diagnosis is captured per stage
    4. Verify diagnosis changes are tracked (issue resolution)
    5. Verify diagnosis history informs later stages
    """

    def test_step_1_run_multi_stage_study_with_diagnosis_enabled(self) -> None:
        """Step 1: Run multi-stage study with diagnosis enabled."""
        # Create diagnosis history tracker
        history = create_diagnosis_history("test_study")

        assert history is not None
        assert history.study_name == "test_study"
        assert len(history.stages) == 0

        # Simulate Stage 1: Initial timing issue
        stage1_timing = TimingMetrics(
            wns_ps=-1200,
            tns_ps=-15000,
            failing_endpoints=25,
            top_paths=[
                TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-1200),
                TimingPath(startpoint="clk", endpoint="reg2/D", slack_ps=-1050),
                TimingPath(startpoint="clk", endpoint="reg3/D", slack_ps=-900),
            ],
        )

        stage1_report = generate_complete_diagnosis(timing_metrics=stage1_timing)
        history.add_stage_diagnosis("stage_1_initial", stage1_report)

        # Simulate Stage 2: Timing improved, congestion appeared
        stage2_timing = TimingMetrics(
            wns_ps=-600,
            tns_ps=-8000,
            failing_endpoints=15,
            top_paths=[
                TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-600),
                TimingPath(startpoint="clk", endpoint="reg2/D", slack_ps=-500),
            ],
        )

        stage2_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=400,
            hot_ratio=0.4,
            max_overflow=800,
            layer_metrics={"metal2": 300, "metal3": 250},
        )

        stage2_report = generate_complete_diagnosis(
            timing_metrics=stage2_timing,
            congestion_metrics=stage2_congestion,
        )
        history.add_stage_diagnosis("stage_2_eco_applied", stage2_report)

        # Simulate Stage 3: Both improved
        stage3_timing = TimingMetrics(
            wns_ps=-150,
            tns_ps=-1500,
            failing_endpoints=5,
            top_paths=[
                TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-150),
                TimingPath(startpoint="clk", endpoint="reg2/D", slack_ps=-100),
            ],
        )

        stage3_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=150,
            hot_ratio=0.15,
            max_overflow=200,
            layer_metrics={"metal2": 100, "metal3": 80},
        )

        stage3_report = generate_complete_diagnosis(
            timing_metrics=stage3_timing,
            congestion_metrics=stage3_congestion,
        )
        history.add_stage_diagnosis("stage_3_optimized", stage3_report)

        # Verify multi-stage tracking
        assert len(history.stages) == 3
        assert history.stages[0].stage_name == "stage_1_initial"
        assert history.stages[1].stage_name == "stage_2_eco_applied"
        assert history.stages[2].stage_name == "stage_3_optimized"

    def test_step_2_verify_diagnosis_history_json_is_created(self, tmp_path: Path) -> None:
        """Step 2: Verify diagnosis_history.json is created."""
        # Create diagnosis history
        history = create_diagnosis_history("test_study")

        # Add some diagnosis entries
        timing = TimingMetrics(
            wns_ps=-800,
            tns_ps=-10000,
            failing_endpoints=20,
            top_paths=[TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-800)],
        )

        report = generate_complete_diagnosis(timing_metrics=timing)
        history.add_stage_diagnosis("stage_1", report)

        # Save to file
        output_path = history.save(tmp_path)

        # Verify file was created
        assert output_path.exists()
        assert output_path.name == "diagnosis_history.json"

        # Verify file contains valid JSON
        with open(output_path) as f:
            data = json.load(f)

        assert "study_name" in data
        assert data["study_name"] == "test_study"
        assert "stages" in data
        assert len(data["stages"]) == 1

    def test_step_3_verify_diagnosis_is_captured_per_stage(self) -> None:
        """Step 3: Verify diagnosis is captured per stage."""
        history = create_diagnosis_history("multi_stage_study")

        # Stage 1
        stage1_timing = TimingMetrics(
            wns_ps=-1000,
            tns_ps=-12000,
            failing_endpoints=20,
            top_paths=[TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-1000)],
        )
        stage1_report = generate_complete_diagnosis(timing_metrics=stage1_timing)
        history.add_stage_diagnosis("stage_1", stage1_report)

        # Stage 2
        stage2_timing = TimingMetrics(
            wns_ps=-500,
            tns_ps=-6000,
            failing_endpoints=10,
            top_paths=[TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-500)],
        )
        stage2_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=300,
            hot_ratio=0.3,
            max_overflow=500,
            layer_metrics={"metal2": 200},
        )
        stage2_report = generate_complete_diagnosis(
            timing_metrics=stage2_timing,
            congestion_metrics=stage2_congestion,
        )
        history.add_stage_diagnosis("stage_2", stage2_report)

        # Verify per-stage capture
        assert len(history.stages) == 2

        # Verify Stage 1 captured
        stage1_entry = history.get_stage_diagnosis("stage_1")
        assert stage1_entry is not None
        assert stage1_entry.stage_name == "stage_1"
        assert stage1_entry.wns_ps == -1000
        assert stage1_entry.hot_ratio is None  # No congestion in stage 1

        # Verify Stage 2 captured
        stage2_entry = history.get_stage_diagnosis("stage_2")
        assert stage2_entry is not None
        assert stage2_entry.stage_name == "stage_2"
        assert stage2_entry.wns_ps == -500
        assert stage2_entry.hot_ratio == 0.3

        # Verify timestamps are captured
        assert stage1_entry.timestamp is not None
        assert stage2_entry.timestamp is not None

        # Verify ECO suggestions are captured
        assert len(stage1_entry.eco_suggestions) > 0

    def test_step_4_verify_diagnosis_changes_are_tracked_issue_resolution(self) -> None:
        """Step 4: Verify diagnosis changes are tracked (issue resolution)."""
        history = create_diagnosis_history("resolution_tracking")

        # Stage 1: Timing issue present
        stage1_timing = TimingMetrics(
            wns_ps=-1200,
            tns_ps=-15000,
            failing_endpoints=30,
            top_paths=[TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-1200)],
        )
        stage1_report = generate_complete_diagnosis(timing_metrics=stage1_timing)
        history.add_stage_diagnosis("stage_1_initial", stage1_report)

        # Stage 2: Timing improving
        stage2_timing = TimingMetrics(
            wns_ps=-400,
            tns_ps=-5000,
            failing_endpoints=10,
            top_paths=[TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-400)],
        )
        stage2_report = generate_complete_diagnosis(timing_metrics=stage2_timing)
        history.add_stage_diagnosis("stage_2_optimized", stage2_report)

        # Stage 3: Timing resolved
        stage3_timing = TimingMetrics(
            wns_ps=100,  # Positive! Timing met
            tns_ps=0,
            failing_endpoints=0,
            top_paths=[],
        )
        stage3_report = generate_complete_diagnosis(timing_metrics=stage3_timing)
        history.add_stage_diagnosis("stage_3_met_timing", stage3_report)

        # Verify issue resolution tracking
        assert len(history.issue_resolutions) > 0

        # Find timing issue resolution
        timing_resolutions = [
            r for r in history.issue_resolutions if r.issue_type == "timing"
        ]
        assert len(timing_resolutions) == 1

        resolution = timing_resolutions[0]
        assert resolution.initial_stage == "stage_1_initial"
        assert resolution.initial_severity == -1200.0
        assert resolution.resolved_stage == "stage_3_met_timing"
        assert resolution.final_severity == 100.0
        assert resolution.stages_to_resolve == 2  # Took 2 stages to resolve

    def test_step_5_verify_diagnosis_history_informs_later_stages(self) -> None:
        """Step 5: Verify diagnosis history informs later stages."""
        history = create_diagnosis_history("informed_decisions")

        # Stage 1: Initial state
        stage1_timing = TimingMetrics(
            wns_ps=-1000,
            tns_ps=-12000,
            failing_endpoints=20,
            top_paths=[TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-1000)],
        )
        stage1_report = generate_complete_diagnosis(timing_metrics=stage1_timing)
        history.add_stage_diagnosis("stage_1", stage1_report)

        # Stage 2: Improved
        stage2_timing = TimingMetrics(
            wns_ps=-500,
            tns_ps=-6000,
            failing_endpoints=10,
            top_paths=[TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-500)],
        )
        stage2_report = generate_complete_diagnosis(timing_metrics=stage2_timing)
        history.add_stage_diagnosis("stage_2", stage2_report)

        # Verify trends are computed
        assert len(history.trends) > 0

        # Find WNS trend
        wns_trends = [t for t in history.trends if t.metric_name == "wns_ps"]
        assert len(wns_trends) == 1

        wns_trend = wns_trends[0]
        assert wns_trend.trend == "improving"
        assert wns_trend.stages == ["stage_1", "stage_2"]
        assert wns_trend.values == [-1000, -500]
        assert wns_trend.improvement_pct is not None
        assert wns_trend.improvement_pct > 0  # Improved by 50%

        # Later stages can use this trend information
        latest_diagnosis = history.get_latest_diagnosis()
        assert latest_diagnosis is not None
        assert latest_diagnosis.stage_name == "stage_2"

        # Can inform decision: timing is improving, continue current strategy
        assert wns_trend.trend == "improving"


class TestDiagnosisHistoryDetails:
    """Additional detailed tests for diagnosis history features."""

    def test_stage_diagnosis_entry_structure(self) -> None:
        """Verify StageDiagnosisEntry structure."""
        entry = StageDiagnosisEntry(
            stage_name="test_stage",
            timestamp="2026-01-12T00:00:00Z",
            wns_ps=-800,
            hot_ratio=0.4,
            primary_issue="timing",
            recommended_strategy="timing_first",
            eco_suggestions=["insert_buffers", "resize_critical_drivers"],
        )

        # Verify structure
        assert entry.stage_name == "test_stage"
        assert entry.wns_ps == -800
        assert entry.hot_ratio == 0.4
        assert entry.primary_issue == "timing"
        assert len(entry.eco_suggestions) == 2

        # Verify serialization
        entry_dict = entry.to_dict()
        assert "stage_name" in entry_dict
        assert "timestamp" in entry_dict
        assert "wns_ps" in entry_dict
        assert "hot_ratio" in entry_dict
        assert "primary_issue" in entry_dict
        assert "eco_suggestions" in entry_dict

    def test_issue_resolution_tracking(self) -> None:
        """Verify IssueResolution tracking."""
        resolution = IssueResolution(
            issue_type="congestion",
            initial_stage="stage_1",
            initial_severity=0.75,
            resolved_stage="stage_3",
            final_severity=0.12,
            stages_to_resolve=2,
        )

        assert resolution.issue_type == "congestion"
        assert resolution.initial_severity == 0.75
        assert resolution.final_severity == 0.12
        assert resolution.stages_to_resolve == 2

        # Verify serialization
        res_dict = resolution.to_dict()
        assert res_dict["issue_type"] == "congestion"
        assert res_dict["initial_severity"] == 0.75
        assert res_dict["stages_to_resolve"] == 2

    def test_diagnosis_trend_calculation(self) -> None:
        """Verify DiagnosisTrend calculation."""
        trend = DiagnosisTrend(
            metric_name="wns_ps",
            stages=["stage_1", "stage_2", "stage_3"],
            values=[-1000, -500, -100],
            trend="improving",
            improvement_pct=90.0,
        )

        assert trend.metric_name == "wns_ps"
        assert len(trend.stages) == 3
        assert len(trend.values) == 3
        assert trend.trend == "improving"
        assert trend.improvement_pct == 90.0

        # Verify serialization
        trend_dict = trend.to_dict()
        assert trend_dict["trend"] == "improving"
        assert trend_dict["improvement_pct"] == 90.0

    def test_save_and_load_diagnosis_history(self, tmp_path: Path) -> None:
        """Verify diagnosis history can be saved and loaded."""
        # Create history
        history = create_diagnosis_history("test_study")

        timing = TimingMetrics(
            wns_ps=-800,
            tns_ps=-10000,
            failing_endpoints=15,
            top_paths=[TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-800)],
        )

        report = generate_complete_diagnosis(timing_metrics=timing)
        history.add_stage_diagnosis("stage_1", report)

        # Save
        output_path = history.save(tmp_path)

        # Load
        loaded_history = DiagnosisHistory.load(output_path)

        # Verify
        assert loaded_history.study_name == "test_study"
        assert len(loaded_history.stages) == 1
        assert loaded_history.stages[0].stage_name == "stage_1"
        assert loaded_history.stages[0].wns_ps == -800

    def test_congestion_issue_resolution_tracking(self) -> None:
        """Verify congestion issue resolution is tracked."""
        history = create_diagnosis_history("congestion_tracking")

        # Stage 1: High congestion
        stage1_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=800,
            hot_ratio=0.8,
            max_overflow=1500,
            layer_metrics={"metal2": 600, "metal3": 500},
        )
        stage1_report = generate_complete_diagnosis(congestion_metrics=stage1_congestion)
        history.add_stage_diagnosis("stage_1", stage1_report)

        # Stage 2: Congestion reduced
        stage2_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=100,
            hot_ratio=0.1,  # Below threshold
            max_overflow=50,
            layer_metrics={"metal2": 30, "metal3": 20},
        )
        stage2_report = generate_complete_diagnosis(congestion_metrics=stage2_congestion)
        history.add_stage_diagnosis("stage_2", stage2_report)

        # Verify congestion resolution tracked
        congestion_resolutions = [
            r for r in history.issue_resolutions if r.issue_type == "congestion"
        ]
        assert len(congestion_resolutions) == 1

        resolution = congestion_resolutions[0]
        assert resolution.initial_severity == 0.8
        assert resolution.final_severity == 0.1
        assert resolution.resolved_stage == "stage_2"

    def test_get_latest_diagnosis(self) -> None:
        """Verify get_latest_diagnosis returns most recent entry."""
        history = create_diagnosis_history("latest_test")

        # Add multiple stages
        for i in range(3):
            timing = TimingMetrics(
                wns_ps=-1000 + (i * 300),
                tns_ps=-10000,
                failing_endpoints=20,
                top_paths=[TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-1000 + (i * 300))],
            )
            report = generate_complete_diagnosis(timing_metrics=timing)
            history.add_stage_diagnosis(f"stage_{i + 1}", report)

        # Get latest
        latest = history.get_latest_diagnosis()
        assert latest is not None
        assert latest.stage_name == "stage_3"
        assert latest.wns_ps == -400  # -1000 + (2 * 300)


class TestF210Integration:
    """Integration test for complete F210 feature workflow."""

    def test_complete_f210_workflow(self, tmp_path: Path) -> None:
        """
        Complete workflow test for F210.

        This test verifies all 5 steps in sequence:
        1. Run multi-stage study with diagnosis enabled
        2. Verify diagnosis_history.json is created
        3. Verify diagnosis is captured per stage
        4. Verify diagnosis changes are tracked (issue resolution)
        5. Verify diagnosis history informs later stages
        """
        # Step 1: Run multi-stage study with diagnosis enabled
        history = create_diagnosis_history("complete_workflow_study")

        # Stage 1: Initial problems
        stage1_timing = TimingMetrics(
            wns_ps=-1500,
            tns_ps=-20000,
            failing_endpoints=40,
            top_paths=[
                TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-1500),
                TimingPath(startpoint="clk", endpoint="reg2/D", slack_ps=-1300),
            ],
        )
        stage1_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=700,
            hot_ratio=0.7,
            max_overflow=1400,
            layer_metrics={"metal2": 550, "metal3": 480},
        )
        stage1_report = generate_complete_diagnosis(
            timing_metrics=stage1_timing,
            congestion_metrics=stage1_congestion,
        )
        history.add_stage_diagnosis("stage_1_initial", stage1_report)

        # Stage 2: ECOs applied, some improvement
        stage2_timing = TimingMetrics(
            wns_ps=-800,
            tns_ps=-10000,
            failing_endpoints=20,
            top_paths=[TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-800)],
        )
        stage2_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=300,
            hot_ratio=0.3,
            max_overflow=600,
            layer_metrics={"metal2": 250, "metal3": 200},
        )
        stage2_report = generate_complete_diagnosis(
            timing_metrics=stage2_timing,
            congestion_metrics=stage2_congestion,
        )
        history.add_stage_diagnosis("stage_2_eco_applied", stage2_report)

        # Stage 3: Further optimization
        stage3_timing = TimingMetrics(
            wns_ps=-200,
            tns_ps=-2000,
            failing_endpoints=5,
            top_paths=[TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-200)],
        )
        stage3_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=100,
            hot_ratio=0.1,
            max_overflow=100,
            layer_metrics={"metal2": 50, "metal3": 40},
        )
        stage3_report = generate_complete_diagnosis(
            timing_metrics=stage3_timing,
            congestion_metrics=stage3_congestion,
        )
        history.add_stage_diagnosis("stage_3_optimized", stage3_report)

        # Step 2: Verify diagnosis_history.json is created
        output_path = history.save(tmp_path)
        assert output_path.exists()

        with open(output_path) as f:
            data = json.load(f)

        assert "study_name" in data
        assert "stages" in data

        # Step 3: Verify diagnosis is captured per stage
        assert len(history.stages) == 3
        assert history.stages[0].stage_name == "stage_1_initial"
        assert history.stages[1].stage_name == "stage_2_eco_applied"
        assert history.stages[2].stage_name == "stage_3_optimized"

        # Verify each stage has diagnosis data
        for stage in history.stages:
            assert stage.wns_ps is not None
            assert stage.hot_ratio is not None
            assert stage.timestamp is not None

        # Step 4: Verify diagnosis changes are tracked (issue resolution)
        assert len(history.issue_resolutions) > 0

        # Verify both timing and congestion resolutions tracked
        timing_res = [r for r in history.issue_resolutions if r.issue_type == "timing"]
        congestion_res = [r for r in history.issue_resolutions if r.issue_type == "congestion"]

        assert len(timing_res) > 0
        assert len(congestion_res) > 0

        # Verify congestion was resolved (hot_ratio < 0.15 in stage 3)
        cong_resolution = congestion_res[0]
        assert cong_resolution.resolved_stage == "stage_3_optimized"

        # Step 5: Verify diagnosis history informs later stages
        assert len(history.trends) > 0

        # Verify WNS trend shows improvement
        wns_trend = next(t for t in history.trends if t.metric_name == "wns_ps")
        assert wns_trend.trend == "improving"
        assert len(wns_trend.values) == 3
        assert wns_trend.values == [-1500, -800, -200]

        # Verify hot_ratio trend shows improvement
        hot_trend = next(t for t in history.trends if t.metric_name == "hot_ratio")
        assert hot_trend.trend == "improving"
        assert len(hot_trend.values) == 3
        assert hot_trend.values == [0.7, 0.3, 0.1]

        # Latest diagnosis available for decision making
        latest = history.get_latest_diagnosis()
        assert latest is not None
        assert latest.stage_name == "stage_3_optimized"

        print("✓ F210: All steps verified successfully")
        print(f"  - Stages tracked: {len(history.stages)}")
        print(f"  - Issue resolutions: {len(history.issue_resolutions)}")
        print(f"  - Trends computed: {len(history.trends)}")
        print(f"  - WNS improvement: {wns_trend.improvement_pct:.1f}%")
        print(f"  - Hot ratio improvement: {hot_trend.improvement_pct:.1f}%")


class TestDiagnosisHistoryEdgeCases:
    """Test edge cases for diagnosis history tracking."""

    def test_empty_history(self) -> None:
        """Verify empty history is handled gracefully."""
        history = create_diagnosis_history("empty_study")

        assert len(history.stages) == 0
        assert len(history.issue_resolutions) == 0
        assert len(history.trends) == 0

        latest = history.get_latest_diagnosis()
        assert latest is None

    def test_single_stage_history(self) -> None:
        """Verify single stage history (no trends possible)."""
        history = create_diagnosis_history("single_stage")

        timing = TimingMetrics(
            wns_ps=-500,
            tns_ps=-5000,
            failing_endpoints=10,
            top_paths=[TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-500)],
        )
        report = generate_complete_diagnosis(timing_metrics=timing)
        history.add_stage_diagnosis("stage_1", report)

        assert len(history.stages) == 1
        assert len(history.trends) == 0  # Need at least 2 stages for trends

    def test_mixed_timing_and_congestion_stages(self) -> None:
        """Verify handling of stages with different metric availability."""
        history = create_diagnosis_history("mixed_stages")

        # Stage 1: Timing only
        stage1_timing = TimingMetrics(
            wns_ps=-800,
            tns_ps=-8000,
            failing_endpoints=15,
            top_paths=[TimingPath(startpoint="clk", endpoint="reg1/D", slack_ps=-800)],
        )
        stage1_report = generate_complete_diagnosis(timing_metrics=stage1_timing)
        history.add_stage_diagnosis("stage_1", stage1_report)

        # Stage 2: Congestion only
        stage2_congestion = CongestionMetrics(
            bins_total=1000,
            bins_hot=400,
            hot_ratio=0.4,
            max_overflow=800,
            layer_metrics={"metal2": 300},
        )
        stage2_report = generate_complete_diagnosis(congestion_metrics=stage2_congestion)
        history.add_stage_diagnosis("stage_2", stage2_report)

        # Verify both stages captured
        assert len(history.stages) == 2

        # Verify first stage has timing, no congestion
        stage1 = history.stages[0]
        assert stage1.wns_ps is not None
        assert stage1.hot_ratio is None

        # Verify second stage has congestion, no timing
        stage2 = history.stages[1]
        assert stage2.wns_ps is None
        assert stage2.hot_ratio is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
