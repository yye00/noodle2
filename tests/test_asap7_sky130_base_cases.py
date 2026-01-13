"""
Tests for F011 and F012: ASAP7 and Sky130 base case execution.

This module tests:
- F011: ASAP7 base case runs successfully with required workarounds
- F012: Sky130 base case runs successfully

Both tests follow the same pattern as F009 (Nangate45 base case):
- Load base snapshot
- Execute STA-only trial
- Verify rc=0 and timing_report.txt exists
"""

import tempfile
from pathlib import Path

import pytest

from src.trial_runner.trial import Trial, TrialConfig


class TestASAP7BaseCase:
    """Test F011: ASAP7 base case execution."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create temporary artifacts directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def asap7_base_script(self):
        """Path to ASAP7 base case script."""
        return Path("studies/asap7_base/run_sta.tcl")

    @pytest.fixture
    def asap7_snapshot_dir(self):
        """Path to ASAP7 snapshot directory."""
        return Path("studies/asap7_base")

    def test_asap7_base_script_exists(self, asap7_base_script):
        """Step 1: Verify ASAP7 base case script exists."""
        assert asap7_base_script.exists(), f"ASAP7 base script not found: {asap7_base_script}"

    def test_asap7_snapshot_exists(self, asap7_snapshot_dir):
        """Step 1: Verify ASAP7 base snapshot exists."""
        snapshot_file = asap7_snapshot_dir / "gcd_placed.odb"
        assert snapshot_file.exists(), f"ASAP7 snapshot not found: {snapshot_file}"
        assert snapshot_file.stat().st_size > 0, "ASAP7 snapshot should not be empty"

    @pytest.mark.slow
    def test_asap7_base_case_execution(
        self, asap7_base_script, asap7_snapshot_dir, temp_artifacts_dir
    ):
        """
        F011: Execute ASAP7 base case and verify it runs successfully.

        Steps:
        1. Load ASAP7 base snapshot (GCD design)
        2. Apply ASAP7-specific workarounds (routing layers, floorplan site, etc.)
        3. Run STA-only trial
        4. Verify OpenROAD completes with rc=0
        5. Verify timing_report.txt exists
        """
        # Create trial configuration
        config = TrialConfig(
            study_name="asap7_base",
            case_name="base",
            stage_index=0,
            trial_index=0,
            script_path=asap7_base_script,
            snapshot_dir=asap7_snapshot_dir,
            timeout_seconds=300,  # ASAP7 may need more time
            metadata={"test": "asap7_base_case", "pdk": "asap7"},
        )

        # Create and execute trial
        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Step 4: Verify OpenROAD completes with rc=0
        assert result.return_code == 0, f"Expected return code 0, got {result.return_code}"
        assert result.success is True, "ASAP7 trial should succeed"

        # Step 5: Verify timing_report.txt exists
        assert result.artifacts.timing_report is not None, "Timing report should be produced"
        assert result.artifacts.timing_report.exists(), "Timing report file should exist"

        # Verify timing metrics were extracted
        assert "wns_ps" in result.metrics, "Metrics should contain wns_ps"
        wns_ps = result.metrics["wns_ps"]
        assert isinstance(wns_ps, (int, float)), f"wns_ps should be numeric, got {type(wns_ps)}"

    @pytest.mark.slow
    def test_asap7_base_case_metrics_extraction(
        self, asap7_base_script, asap7_snapshot_dir, temp_artifacts_dir
    ):
        """Verify metrics are correctly extracted from ASAP7 base case."""
        config = TrialConfig(
            study_name="asap7_base",
            case_name="base",
            stage_index=0,
            trial_index=1,
            script_path=asap7_base_script,
            snapshot_dir=asap7_snapshot_dir,
            timeout_seconds=300,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Verify execution succeeded
        assert result.success is True, "ASAP7 trial should succeed"

        # Verify metrics
        assert "wns_ps" in result.metrics, "Should extract WNS from ASAP7 report"

        # Verify metrics are reasonable
        wns_ps = result.metrics["wns_ps"]
        # ASAP7 can have large violations with aggressive constraints
        assert -1000000 < wns_ps < 1000000, "WNS should be in reasonable range"

        # Verify artifacts were created
        assert result.artifacts.trial_dir.exists(), "Trial directory should exist"
        assert result.artifacts.metrics_json is not None, "Metrics JSON should be produced"
        assert result.artifacts.metrics_json.exists(), "Metrics JSON file should exist"


class TestSky130BaseCase:
    """Test F012: Sky130 base case execution."""

    @pytest.fixture
    def temp_artifacts_dir(self):
        """Create temporary artifacts directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sky130_base_script(self):
        """Path to Sky130 base case script."""
        return Path("studies/sky130_base/run_sta.tcl")

    @pytest.fixture
    def sky130_snapshot_dir(self):
        """Path to Sky130 snapshot directory."""
        return Path("studies/sky130_base")

    def test_sky130_base_script_exists(self, sky130_base_script):
        """Step 1: Verify Sky130 base case script exists."""
        assert sky130_base_script.exists(), f"Sky130 base script not found: {sky130_base_script}"

    def test_sky130_snapshot_exists(self, sky130_snapshot_dir):
        """Step 1: Verify Sky130 base snapshot exists."""
        snapshot_file = sky130_snapshot_dir / "gcd_placed.odb"
        assert snapshot_file.exists(), f"Sky130 snapshot not found: {snapshot_file}"
        assert snapshot_file.stat().st_size > 0, "Sky130 snapshot should not be empty"

    @pytest.mark.slow
    def test_sky130_base_case_execution(
        self, sky130_base_script, sky130_snapshot_dir, temp_artifacts_dir
    ):
        """
        F012: Execute Sky130 base case and verify it runs successfully.

        Steps:
        1. Load Sky130 base snapshot (Ibex design)
        2. Set PDK to sky130A, library to sky130_fd_sc_hd
        3. Run STA-only trial
        4. Verify OpenROAD completes with rc=0
        5. Verify timing_report.txt exists
        """
        # Create trial configuration
        config = TrialConfig(
            study_name="sky130_base",
            case_name="base",
            stage_index=0,
            trial_index=0,
            script_path=sky130_base_script,
            snapshot_dir=sky130_snapshot_dir,
            timeout_seconds=300,  # Sky130 may need more time for larger design
            metadata={"test": "sky130_base_case", "pdk": "sky130"},
        )

        # Create and execute trial
        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Step 4: Verify OpenROAD completes with rc=0
        assert result.return_code == 0, f"Expected return code 0, got {result.return_code}"
        assert result.success is True, "Sky130 trial should succeed"

        # Step 5: Verify timing_report.txt exists
        assert result.artifacts.timing_report is not None, "Timing report should be produced"
        assert result.artifacts.timing_report.exists(), "Timing report file should exist"

        # Verify timing metrics were extracted
        assert "wns_ps" in result.metrics, "Metrics should contain wns_ps"
        wns_ps = result.metrics["wns_ps"]
        assert isinstance(wns_ps, (int, float)), f"wns_ps should be numeric, got {type(wns_ps)}"

    @pytest.mark.slow
    def test_sky130_base_case_metrics_extraction(
        self, sky130_base_script, sky130_snapshot_dir, temp_artifacts_dir
    ):
        """Verify metrics are correctly extracted from Sky130 base case."""
        config = TrialConfig(
            study_name="sky130_base",
            case_name="base",
            stage_index=0,
            trial_index=1,
            script_path=sky130_base_script,
            snapshot_dir=sky130_snapshot_dir,
            timeout_seconds=300,
        )

        trial = Trial(config=config, artifacts_root=temp_artifacts_dir)
        result = trial.execute()

        # Verify execution succeeded
        assert result.success is True, "Sky130 trial should succeed"

        # Verify metrics
        assert "wns_ps" in result.metrics, "Should extract WNS from Sky130 report"

        # Verify metrics are reasonable
        wns_ps = result.metrics["wns_ps"]
        # ASAP7 can have large violations with aggressive constraints
        assert -1000000 < wns_ps < 1000000, "WNS should be in reasonable range"

        # Verify artifacts were created
        assert result.artifacts.trial_dir.exists(), "Trial directory should exist"
        assert result.artifacts.metrics_json is not None, "Metrics JSON should be produced"
        assert result.artifacts.metrics_json.exists(), "Metrics JSON file should exist"
