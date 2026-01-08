"""Tests for fixed OpenROAD seed support for deterministic placement/routing."""

import pytest
from pathlib import Path

from src.controller.types import ExecutionMode
from src.trial_runner.trial import TrialConfig
from src.trial_runner.tcl_generator import generate_trial_script, write_trial_script


class TestTrialConfigWithSeed:
    """Tests for TrialConfig with openroad_seed parameter."""

    def test_trial_config_has_openroad_seed_field(self) -> None:
        """Test that TrialConfig has openroad_seed field."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            openroad_seed=42,
        )

        assert hasattr(config, "openroad_seed")
        assert config.openroad_seed == 42

    def test_trial_config_seed_defaults_to_none(self) -> None:
        """Test that openroad_seed defaults to None (random seed)."""
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
        )

        assert config.openroad_seed is None

    def test_trial_config_accepts_various_seed_values(self) -> None:
        """Test that TrialConfig accepts various integer seed values."""
        # Test positive integers
        config1 = TrialConfig(
            study_name="test",
            case_name="test",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            openroad_seed=1,
        )
        assert config1.openroad_seed == 1

        # Test zero
        config2 = TrialConfig(
            study_name="test",
            case_name="test",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            openroad_seed=0,
        )
        assert config2.openroad_seed == 0

        # Test large integers
        config3 = TrialConfig(
            study_name="test",
            case_name="test",
            stage_index=0,
            trial_index=0,
            script_path="/tmp/test.tcl",
            openroad_seed=999999,
        )
        assert config3.openroad_seed == 999999


class TestTCLScriptGenerationWithSeed:
    """Tests for TCL script generation with fixed seeds."""

    def test_sta_only_script_includes_seed_command(self) -> None:
        """Test that STA-only script includes set_random_seed when seed is provided."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            openroad_seed=42,
        )

        assert "set_random_seed 42" in script
        assert "OpenROAD seed set to: 42" in script
        assert "# OpenROAD Seed: 42" in script

    def test_sta_only_script_omits_seed_command_when_none(self) -> None:
        """Test that STA-only script omits set_random_seed when seed is None."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            openroad_seed=None,
        )

        assert "set_random_seed" not in script
        assert "# OpenROAD Seed: default (random)" in script

    def test_sta_congestion_script_includes_seed_command(self) -> None:
        """Test that STA+congestion script includes set_random_seed when seed is provided."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            openroad_seed=123,
        )

        assert "set_random_seed 123" in script
        assert "OpenROAD seed set to: 123" in script
        assert "# OpenROAD Seed: 123" in script

    def test_sta_congestion_script_omits_seed_command_when_none(self) -> None:
        """Test that STA+congestion script omits set_random_seed when seed is None."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_CONGESTION,
            design_name="test_design",
            openroad_seed=None,
        )

        assert "set_random_seed" not in script
        assert "# OpenROAD Seed: default (random)" in script

    def test_seed_command_appears_before_timing_analysis(self) -> None:
        """Test that seed is set before timing analysis section."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            openroad_seed=42,
        )

        seed_index = script.find("set_random_seed 42")
        timing_index = script.find("# TIMING ANALYSIS")

        assert seed_index != -1
        assert timing_index != -1
        assert seed_index < timing_index, "Seed should be set before timing analysis"

    def test_different_seeds_produce_different_scripts(self) -> None:
        """Test that different seed values produce different scripts."""
        script1 = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            openroad_seed=42,
        )

        script2 = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            openroad_seed=99,
        )

        assert "set_random_seed 42" in script1
        assert "set_random_seed 99" in script2
        assert script1 != script2

    def test_same_seed_produces_identical_scripts(self) -> None:
        """Test that the same seed produces identical scripts."""
        script1 = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            openroad_seed=42,
        )

        script2 = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            openroad_seed=42,
        )

        assert script1 == script2

    def test_seed_zero_is_valid(self) -> None:
        """Test that seed value of 0 is valid and included in script."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            openroad_seed=0,
        )

        assert "set_random_seed 0" in script
        assert "OpenROAD seed set to: 0" in script


class TestWriteTrialScriptWithSeed:
    """Tests for write_trial_script with seed parameter."""

    def test_write_script_with_seed(self, tmp_path: Path) -> None:
        """Test that write_trial_script includes seed in written file."""
        script_path = tmp_path / "trial.tcl"

        written_path = write_trial_script(
            script_path=script_path,
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            openroad_seed=42,
        )

        assert written_path == script_path
        assert script_path.exists()

        content = script_path.read_text()
        assert "set_random_seed 42" in content
        assert "# OpenROAD Seed: 42" in content

    def test_write_script_without_seed(self, tmp_path: Path) -> None:
        """Test that write_trial_script works without seed."""
        script_path = tmp_path / "trial.tcl"

        written_path = write_trial_script(
            script_path=script_path,
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            openroad_seed=None,
        )

        assert written_path == script_path
        assert script_path.exists()

        content = script_path.read_text()
        assert "set_random_seed" not in content
        assert "# OpenROAD Seed: default (random)" in content


class TestSeedReproducibility:
    """Tests for reproducibility with fixed seeds."""

    def test_documentation_for_reproducibility(self) -> None:
        """Test that seed feature is properly documented for reproducibility."""
        script_with_seed = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            openroad_seed=42,
        )

        # Check that script documents the seed value
        assert "# OpenROAD Seed: 42" in script_with_seed

        # Check that seed setting is logged
        assert 'puts "OpenROAD seed set to: 42"' in script_with_seed

    def test_no_seed_is_documented_as_random(self) -> None:
        """Test that lack of seed is documented as random."""
        script_without_seed = generate_trial_script(
            execution_mode=ExecutionMode.STA_ONLY,
            design_name="test_design",
            openroad_seed=None,
        )

        assert "# OpenROAD Seed: default (random)" in script_without_seed


class TestSeedPropagation:
    """Tests for seed propagation through execution modes."""

    def test_full_route_mode_propagates_seed(self) -> None:
        """Test that FULL_ROUTE mode propagates seed to underlying script."""
        script = generate_trial_script(
            execution_mode=ExecutionMode.FULL_ROUTE,
            design_name="test_design",
            openroad_seed=42,
        )

        # FULL_ROUTE delegates to STA_CONGESTION, so seed should still be present
        assert "set_random_seed 42" in script
        assert "# OpenROAD Seed: 42" in script
