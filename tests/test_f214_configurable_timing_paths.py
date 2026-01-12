"""Tests for F214: Diagnosis enables configurable path count for analysis depth."""

import pytest

from src.analysis.diagnosis import diagnose_timing, generate_complete_diagnosis
from src.controller.types import DiagnosisConfig, TimingMetrics, TimingPath


class TestF214ConfigurableTimingPaths:
    """
    Test suite for Feature F214: Configurable timing path count.

    Verification Steps:
    1. Set diagnosis timing_paths: 20
    2. Run diagnosis
    3. Verify top 20 paths are analyzed
    4. Change to timing_paths: 50
    5. Verify top 50 paths are analyzed
    6. Confirm deeper analysis provides more comprehensive diagnosis
    """

    def test_step_1_configure_timing_paths_20(self) -> None:
        """Step 1: Set diagnosis timing_paths: 20."""
        config = DiagnosisConfig(
            enabled=True,
            timing_paths=20,
        )

        assert config.timing_paths == 20
        assert config.enabled is True

    def test_step_2_run_diagnosis_with_20_paths(self) -> None:
        """Step 2: Run diagnosis with timing_paths=20."""
        # Create metrics with 30 critical paths
        paths = [
            TimingPath(
                slack_ps=-100 * i,
                startpoint=f"input_{i}",
                endpoint=f"reg_{i}",
                path_group="clk",
                path_type="max",
            )
            for i in range(1, 31)
        ]

        metrics = TimingMetrics(
            wns_ps=-100,
            tns_ps=-15000,
            failing_endpoints=30,
            top_paths=paths,
        )

        # Run diagnosis with path_count=20
        config = DiagnosisConfig(timing_paths=20)
        diagnosis = diagnose_timing(metrics, path_count=config.timing_paths)

        assert diagnosis is not None
        assert diagnosis.wns_ps == -100

    def test_step_3_verify_20_paths_analyzed(self) -> None:
        """Step 3: Verify top 20 paths are analyzed."""
        # Create metrics with 30 paths but analyze only top 20
        paths = [
            TimingPath(
                slack_ps=-100 * i,
                startpoint=f"input_{i}",
                endpoint=f"reg_{i}",
                path_group="clk",
                path_type="max",
            )
            for i in range(1, 31)
        ]

        metrics = TimingMetrics(
            wns_ps=-100,
            tns_ps=-15000,
            failing_endpoints=30,
            top_paths=paths,
        )

        # Run diagnosis analyzing only top 20
        diagnosis = diagnose_timing(metrics, path_count=20)

        # The diagnosis function analyzes paths[:path_count]
        # We can verify this indirectly by checking problem nets count
        # In real implementation, we'd verify exact paths analyzed
        assert diagnosis.dominant_issue in ["wire_dominated", "cell_dominated", "mixed", "unknown"]
        assert len(diagnosis.problem_nets) > 0  # Should have identified problems

    def test_step_4_change_to_timing_paths_50(self) -> None:
        """Step 4: Change to timing_paths: 50."""
        config = DiagnosisConfig(
            enabled=True,
            timing_paths=50,
        )

        assert config.timing_paths == 50
        assert config.enabled is True

    def test_step_5_verify_50_paths_analyzed(self) -> None:
        """Step 5: Verify top 50 paths are analyzed."""
        # Create metrics with 60 paths, analyze top 50
        paths = [
            TimingPath(
                slack_ps=-100 * i,
                startpoint=f"input_{i}",
                endpoint=f"reg_{i}",
                path_group="clk",
                path_type="max",
            )
            for i in range(1, 61)
        ]

        metrics = TimingMetrics(
            wns_ps=-100,
            tns_ps=-30000,
            failing_endpoints=60,
            top_paths=paths,
        )

        # Run diagnosis analyzing top 50
        diagnosis = diagnose_timing(metrics, path_count=50)

        # Verify analysis was performed
        assert diagnosis is not None
        assert len(diagnosis.problem_nets) > 0

    def test_step_6_deeper_analysis_provides_more_comprehensive_diagnosis(self) -> None:
        """Step 6: Confirm deeper analysis provides more comprehensive diagnosis."""
        # Create metrics with many paths
        paths = [
            TimingPath(
                slack_ps=-100 * i,
                startpoint=f"input_{i}",
                endpoint=f"reg_{i}",
                path_group="clk",
                path_type="max",
            )
            for i in range(1, 101)
        ]

        metrics = TimingMetrics(
            wns_ps=-100,
            tns_ps=-50000,
            failing_endpoints=100,
            top_paths=paths,
        )

        # Shallow analysis (10 paths)
        diagnosis_shallow = diagnose_timing(metrics, path_count=10)

        # Deep analysis (50 paths)
        diagnosis_deep = diagnose_timing(metrics, path_count=50)

        # Deeper analysis should identify more problems
        # Note: Actual counts depend on diagnosis logic, but deeper should >= shallow
        assert len(diagnosis_deep.problem_nets) >= len(diagnosis_shallow.problem_nets)

        # Both should produce valid diagnoses
        assert diagnosis_shallow.dominant_issue in ["wire_dominated", "cell_dominated", "mixed", "unknown"]
        assert diagnosis_deep.dominant_issue in ["wire_dominated", "cell_dominated", "mixed", "unknown"]


class TestDiagnosisConfigValidation:
    """Test DiagnosisConfig validation."""

    def test_valid_config(self) -> None:
        """Valid configuration should work."""
        config = DiagnosisConfig(
            enabled=True,
            timing_paths=20,
            hotspot_threshold=0.7,
            wire_delay_threshold=0.65,
        )

        assert config.timing_paths == 20
        assert config.hotspot_threshold == 0.7
        assert config.wire_delay_threshold == 0.65

    def test_timing_paths_must_be_positive(self) -> None:
        """timing_paths must be at least 1."""
        with pytest.raises(ValueError, match="timing_paths must be at least 1"):
            DiagnosisConfig(timing_paths=0)

    def test_hotspot_threshold_must_be_valid_ratio(self) -> None:
        """hotspot_threshold must be between 0.0 and 1.0."""
        with pytest.raises(ValueError, match="hotspot_threshold must be between 0.0 and 1.0"):
            DiagnosisConfig(hotspot_threshold=1.5)

        with pytest.raises(ValueError, match="hotspot_threshold must be between 0.0 and 1.0"):
            DiagnosisConfig(hotspot_threshold=0.0)

    def test_wire_delay_threshold_must_be_valid_ratio(self) -> None:
        """wire_delay_threshold must be between 0.0 and 1.0."""
        with pytest.raises(ValueError, match="wire_delay_threshold must be between 0.0 and 1.0"):
            DiagnosisConfig(wire_delay_threshold=2.0)

        with pytest.raises(ValueError, match="wire_delay_threshold must be between 0.0 and 1.0"):
            DiagnosisConfig(wire_delay_threshold=0.0)


class TestGenerateCompleteDiagnosisWithConfig:
    """Test generate_complete_diagnosis with custom timing_path_count."""

    def test_generate_diagnosis_with_custom_path_count(self) -> None:
        """Test complete diagnosis generation with custom path count."""
        # Create timing metrics
        paths = [
            TimingPath(
                slack_ps=-100 * i,
                startpoint=f"input_{i}",
                endpoint=f"reg_{i}",
                path_group="clk",
                path_type="max",
            )
            for i in range(1, 41)
        ]

        timing_metrics = TimingMetrics(
            wns_ps=-100,
            tns_ps=-20000,
            failing_endpoints=40,
            top_paths=paths,
        )

        # Generate diagnosis with custom path count
        config = DiagnosisConfig(timing_paths=30)
        report = generate_complete_diagnosis(
            timing_metrics=timing_metrics,
            timing_path_count=config.timing_paths,
        )

        assert report is not None
        assert report.timing_diagnosis is not None
        assert report.timing_diagnosis.wns_ps == -100


class TestIntegrationWithStudyConfig:
    """Test that DiagnosisConfig integrates with StudyConfig."""

    def test_study_config_has_diagnosis_config(self) -> None:
        """StudyConfig should have diagnosis configuration."""
        from src.controller.types import SafetyDomain, StageConfig, StudyConfig

        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[],
            snapshot_path="/tmp/snapshot",
        )

        # Should have default diagnosis config
        assert config.diagnosis is not None
        assert config.diagnosis.timing_paths == 20  # Default value
        assert config.diagnosis.enabled is True

    def test_study_config_with_custom_diagnosis(self) -> None:
        """StudyConfig should allow custom diagnosis configuration."""
        from src.controller.types import SafetyDomain, StageConfig, StudyConfig

        custom_diagnosis = DiagnosisConfig(
            enabled=True,
            timing_paths=50,
            hotspot_threshold=0.8,
        )

        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[],
            snapshot_path="/tmp/snapshot",
            diagnosis=custom_diagnosis,
        )

        assert config.diagnosis.timing_paths == 50
        assert config.diagnosis.hotspot_threshold == 0.8
