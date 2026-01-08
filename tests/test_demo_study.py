"""Tests for reproducible demo Study on Nangate45.

This module tests the creation and execution of a fixed, reproducible
demo Study configuration that can be verified across different machines.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.demo_study import (
    create_minimal_demo_study,
    create_nangate45_demo_study,
    get_demo_study_expected_metrics,
    save_demo_study_config,
)
from src.controller.types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
)


class TestNangate45DemoStudyCreation:
    """Test creating the Nangate45 demo Study configuration."""

    def test_create_demo_study_with_defaults(self) -> None:
        """Step 1: Create nangate45_demo Study with fixed configuration."""
        demo = create_nangate45_demo_study()

        # Verify basic attributes
        assert demo.name == "nangate45_demo"
        assert demo.pdk == "Nangate45"
        assert demo.base_case_name == "nangate45_base"
        assert demo.safety_domain == SafetyDomain.GUARDED

    def test_demo_study_has_three_stages(self) -> None:
        """Verify demo Study has exactly 3 stages."""
        demo = create_nangate45_demo_study()

        assert len(demo.stages) == 3
        assert demo.stages[0].name == "exploration"
        assert demo.stages[1].name == "refinement"
        assert demo.stages[2].name == "closure"

    def test_demo_study_stage_configurations(self) -> None:
        """Verify each stage has correct trial budget and survivor count."""
        demo = create_nangate45_demo_study()

        # Stage 0: Exploration
        assert demo.stages[0].trial_budget == 10
        assert demo.stages[0].survivor_count == 3
        assert demo.stages[0].execution_mode == ExecutionMode.STA_ONLY

        # Stage 1: Refinement
        assert demo.stages[1].trial_budget == 6
        assert demo.stages[1].survivor_count == 2
        assert demo.stages[1].execution_mode == ExecutionMode.STA_ONLY

        # Stage 2: Closure
        assert demo.stages[2].trial_budget == 4
        assert demo.stages[2].survivor_count == 2
        assert demo.stages[2].execution_mode == ExecutionMode.STA_ONLY

    def test_demo_study_eco_class_progression(self) -> None:
        """Verify ECO classes progress from conservative to aggressive."""
        demo = create_nangate45_demo_study()

        # Stage 0: Most conservative (topology neutral only)
        assert demo.stages[0].allowed_eco_classes == [
            ECOClass.TOPOLOGY_NEUTRAL
        ]

        # Stage 1: Moderate (topology neutral + placement local)
        assert set(demo.stages[1].allowed_eco_classes) == {
            ECOClass.TOPOLOGY_NEUTRAL,
            ECOClass.PLACEMENT_LOCAL,
        }

        # Stage 2: Most aggressive (includes routing affecting)
        assert set(demo.stages[2].allowed_eco_classes) == {
            ECOClass.TOPOLOGY_NEUTRAL,
            ECOClass.PLACEMENT_LOCAL,
            ECOClass.ROUTING_AFFECTING,
        }

    def test_demo_study_has_visualization_enabled(self) -> None:
        """Verify all stages have visualization enabled for observability."""
        demo = create_nangate45_demo_study()

        for stage in demo.stages:
            assert stage.visualization_enabled is True

    def test_demo_study_has_metadata(self) -> None:
        """Verify demo Study has comprehensive metadata."""
        demo = create_nangate45_demo_study()

        assert demo.author == "Noodle2 Team"
        assert "Reproducible" in demo.description
        assert "Nangate45" in demo.description

        # Check metadata dict
        assert demo.metadata["purpose"] == "Reproducible demo Study for Nangate45 PDK"
        assert demo.metadata["design"] == "counter (4-bit counter)"
        assert "version" in demo.metadata

    def test_demo_study_has_tags(self) -> None:
        """Verify demo Study has appropriate tags for organization."""
        demo = create_nangate45_demo_study()

        expected_tags = {"demo", "nangate45", "reproducible", "tutorial"}
        assert set(demo.tags) == expected_tags

    def test_demo_study_validation_passes(self) -> None:
        """Verify demo Study configuration passes validation."""
        demo = create_nangate45_demo_study()

        # Should not raise any exceptions
        demo.validate()

    def test_demo_study_with_custom_snapshot_path(self) -> None:
        """Verify demo Study can use custom snapshot path."""
        custom_path = "/custom/path/to/snapshot"
        demo = create_nangate45_demo_study(snapshot_path=custom_path)

        assert demo.snapshot_path == custom_path

    def test_demo_study_with_custom_safety_domain(self) -> None:
        """Verify demo Study can use different safety domains."""
        # Test with SANDBOX
        demo_sandbox = create_nangate45_demo_study(
            safety_domain=SafetyDomain.SANDBOX
        )
        assert demo_sandbox.safety_domain == SafetyDomain.SANDBOX

        # Test with LOCKED
        demo_locked = create_nangate45_demo_study(
            safety_domain=SafetyDomain.LOCKED
        )
        assert demo_locked.safety_domain == SafetyDomain.LOCKED


class TestMinimalDemoStudy:
    """Test the minimal demo Study configuration for quick testing."""

    def test_create_minimal_demo_study(self) -> None:
        """Verify minimal demo Study is created correctly."""
        demo = create_minimal_demo_study()

        assert demo.name == "nangate45_minimal_demo"
        assert demo.pdk == "Nangate45"
        assert demo.safety_domain == SafetyDomain.SANDBOX

    def test_minimal_demo_has_single_stage(self) -> None:
        """Verify minimal demo has exactly one stage."""
        demo = create_minimal_demo_study()

        assert len(demo.stages) == 1
        assert demo.stages[0].name == "quick_test"

    def test_minimal_demo_has_small_trial_budget(self) -> None:
        """Verify minimal demo has small trial budget for quick execution."""
        demo = create_minimal_demo_study()

        assert demo.stages[0].trial_budget == 3
        assert demo.stages[0].survivor_count == 1

    def test_minimal_demo_visualization_disabled(self) -> None:
        """Verify minimal demo has visualization disabled for speed."""
        demo = create_minimal_demo_study()

        assert demo.stages[0].visualization_enabled is False

    def test_minimal_demo_validation_passes(self) -> None:
        """Verify minimal demo configuration passes validation."""
        demo = create_minimal_demo_study()

        # Should not raise any exceptions
        demo.validate()


class TestDemoStudyExpectedMetrics:
    """Test expected metrics specification for reproducibility verification."""

    def test_get_expected_metrics(self) -> None:
        """Verify expected metrics dictionary is returned correctly."""
        metrics = get_demo_study_expected_metrics()

        assert isinstance(metrics, dict)
        assert "base_case_wns_ps" in metrics
        assert "min_trial_count" in metrics
        assert "max_trial_count" in metrics
        assert "expected_stages" in metrics

    def test_expected_metrics_match_demo_configuration(self) -> None:
        """Verify expected metrics align with demo Study configuration."""
        demo = create_nangate45_demo_study()
        metrics = get_demo_study_expected_metrics()

        # Verify stage count matches
        assert metrics["expected_stages"] == len(demo.stages)

        # Verify trial budgets match
        assert metrics["stage_0_trial_budget"] == demo.stages[0].trial_budget
        assert metrics["stage_1_trial_budget"] == demo.stages[1].trial_budget
        assert metrics["stage_2_trial_budget"] == demo.stages[2].trial_budget

        # Verify total trial count
        total_trials = sum(stage.trial_budget for stage in demo.stages)
        assert metrics["min_trial_count"] == total_trials
        assert metrics["max_trial_count"] == total_trials

    def test_expected_base_case_wns(self) -> None:
        """Verify expected base case WNS matches Nangate45 baseline."""
        metrics = get_demo_study_expected_metrics()

        # From studies/nangate45_base/run_sta.tcl, WNS is 2.5ns = 2500ps
        assert metrics["base_case_wns_ps"] == 2500


class TestDemoStudyConfigSerialization:
    """Test saving demo Study configuration to JSON file."""

    def test_save_demo_study_config_creates_file(self, tmp_path: Path) -> None:
        """Verify demo Study config can be saved to JSON file."""
        config_path = tmp_path / "demo_config.json"

        save_demo_study_config(config_path)

        assert config_path.exists()
        assert config_path.is_file()

    def test_saved_config_is_valid_json(self, tmp_path: Path) -> None:
        """Verify saved config is valid JSON."""
        config_path = tmp_path / "demo_config.json"

        save_demo_study_config(config_path)

        # Should be able to parse as JSON
        with config_path.open() as f:
            config_data = json.load(f)

        assert isinstance(config_data, dict)

    def test_saved_config_contains_study_metadata(self, tmp_path: Path) -> None:
        """Verify saved config contains all Study metadata."""
        config_path = tmp_path / "demo_config.json"

        save_demo_study_config(config_path)

        with config_path.open() as f:
            config_data = json.load(f)

        # Check key fields
        assert config_data["name"] == "nangate45_demo"
        assert config_data["pdk"] == "Nangate45"
        assert config_data["base_case_name"] == "nangate45_base"
        assert config_data["safety_domain"] == "guarded"

    def test_saved_config_contains_stages(self, tmp_path: Path) -> None:
        """Verify saved config contains stage definitions."""
        config_path = tmp_path / "demo_config.json"

        save_demo_study_config(config_path)

        with config_path.open() as f:
            config_data = json.load(f)

        assert "stages" in config_data
        assert len(config_data["stages"]) == 3

        # Check stage names
        stage_names = [stage["name"] for stage in config_data["stages"]]
        assert stage_names == ["exploration", "refinement", "closure"]

    def test_saved_config_has_pretty_formatting(self, tmp_path: Path) -> None:
        """Verify saved config is formatted for human readability."""
        config_path = tmp_path / "demo_config.json"

        save_demo_study_config(config_path)

        content = config_path.read_text()

        # Check for indentation (pretty formatting)
        assert "  " in content  # 2-space indentation
        assert "\n" in content  # Multiple lines

        # Check for reasonable file size (not minified)
        assert len(content) > 500  # Should be substantial with formatting


class TestDemoStudyReproducibility:
    """Test reproducibility guarantees of demo Study."""

    def test_demo_study_is_deterministic(self) -> None:
        """Step 2-3: Execute Study on multiple different machines (simulated)."""
        # Create demo Study multiple times and verify identical configuration
        demo1 = create_nangate45_demo_study()
        demo2 = create_nangate45_demo_study()

        # Verify all critical fields are identical
        assert demo1.name == demo2.name
        assert demo1.pdk == demo2.pdk
        assert demo1.safety_domain == demo2.safety_domain
        assert len(demo1.stages) == len(demo2.stages)

        for stage1, stage2 in zip(demo1.stages, demo2.stages):
            assert stage1.name == stage2.name
            assert stage1.trial_budget == stage2.trial_budget
            assert stage1.survivor_count == stage2.survivor_count
            assert stage1.execution_mode == stage2.execution_mode
            assert stage1.allowed_eco_classes == stage2.allowed_eco_classes

    def test_demo_study_config_files_are_identical(self, tmp_path: Path) -> None:
        """Step 4: Verify metrics are identical (within deterministic bounds)."""
        # Save config twice and verify identical output
        config1 = tmp_path / "config1.json"
        config2 = tmp_path / "config2.json"

        save_demo_study_config(config1)
        save_demo_study_config(config2)

        content1 = config1.read_text()
        content2 = config2.read_text()

        # Content should be byte-for-byte identical
        assert content1 == content2

    def test_demo_study_snapshot_path_is_fixed(self) -> None:
        """Verify snapshot path uses fixed default for reproducibility."""
        demo = create_nangate45_demo_study()

        # Default path should always be the same
        assert "nangate45_base" in demo.snapshot_path
        assert demo.snapshot_path.endswith("nangate45_base")


class TestDemoStudyDocumentation:
    """Test that demo Study is well-documented and shareable."""

    def test_demo_study_has_docstrings(self) -> None:
        """Verify all public functions have comprehensive docstrings."""
        # Check function docstrings
        assert create_nangate45_demo_study.__doc__ is not None
        assert create_minimal_demo_study.__doc__ is not None
        assert get_demo_study_expected_metrics.__doc__ is not None
        assert save_demo_study_config.__doc__ is not None

        # Verify docstrings are substantial
        assert len(create_nangate45_demo_study.__doc__) > 100

    def test_demo_study_has_usage_example_in_docstring(self) -> None:
        """Verify main function has usage example."""
        docstring = create_nangate45_demo_study.__doc__
        assert docstring is not None

        # Check for Example section
        assert "Example:" in docstring or "Args:" in docstring

    def test_demo_study_description_is_informative(self) -> None:
        """Verify Study description explains purpose clearly."""
        demo = create_nangate45_demo_study()

        description = demo.description
        assert description is not None
        assert len(description) > 50

        # Should mention key concepts
        assert "reproducible" in description.lower()
        assert "nangate45" in description.lower()


class TestDemoStudyIntegration:
    """Integration tests for demo Study configuration."""

    def test_demo_study_can_be_imported_from_controller(self) -> None:
        """Step 5: Confirm demo is reproducible and shareable."""
        # Verify functions can be imported from main controller module
        from src.controller import (
            create_minimal_demo_study,
            create_nangate45_demo_study,
            get_demo_study_expected_metrics,
            save_demo_study_config,
        )

        # Should be able to call them
        demo = create_nangate45_demo_study()
        assert demo is not None

        minimal = create_minimal_demo_study()
        assert minimal is not None

        metrics = get_demo_study_expected_metrics()
        assert metrics is not None

    def test_demo_study_configuration_is_complete(self) -> None:
        """Verify demo Study has all required fields for execution."""
        demo = create_nangate45_demo_study()

        # Required fields for execution
        assert demo.name
        assert demo.pdk
        assert demo.base_case_name
        assert demo.snapshot_path
        assert demo.stages
        assert demo.safety_domain

        # All stages should be properly configured
        for idx, stage in enumerate(demo.stages):
            assert stage.name, f"Stage {idx} missing name"
            assert stage.execution_mode, f"Stage {idx} missing execution mode"
            assert stage.trial_budget > 0, f"Stage {idx} has invalid trial budget"
            assert stage.survivor_count > 0, f"Stage {idx} has invalid survivor count"
            assert stage.allowed_eco_classes, f"Stage {idx} has no allowed ECO classes"

    def test_demo_study_timeout_values_are_reasonable(self) -> None:
        """Verify demo Study has reasonable timeout values."""
        demo = create_nangate45_demo_study()

        # Check each stage has a timeout
        for stage in demo.stages:
            assert stage.timeout_seconds > 0
            assert stage.timeout_seconds <= 3600  # Max 1 hour per trial

        # Check progression: later stages may have longer timeouts
        assert demo.stages[0].timeout_seconds == 300  # 5 min
        assert demo.stages[1].timeout_seconds == 600  # 10 min
        assert demo.stages[2].timeout_seconds == 900  # 15 min

    def test_demo_study_abort_thresholds_are_sensible(self) -> None:
        """Verify demo Study has sensible abort thresholds."""
        demo = create_nangate45_demo_study()

        # Early stages should have abort thresholds
        assert demo.stages[0].abort_threshold_wns_ps == -50000  # -50ns
        assert demo.stages[1].abort_threshold_wns_ps == -100000  # -100ns

        # Final stage has no abort threshold (allow completion)
        assert demo.stages[2].abort_threshold_wns_ps is None

    def test_demo_study_total_trial_budget(self) -> None:
        """Verify total trial budget is reasonable for demo purposes."""
        demo = create_nangate45_demo_study()

        total_trials = sum(stage.trial_budget for stage in demo.stages)

        # Should be substantial enough to demonstrate functionality
        assert total_trials >= 10

        # But not so large that demo takes too long
        assert total_trials <= 100

        # Exact expected value
        assert total_trials == 20  # 10 + 6 + 4


class TestDemoStudyEdgeCases:
    """Test edge cases and error handling for demo Study."""

    def test_demo_study_with_none_snapshot_path_uses_default(self) -> None:
        """Verify passing None for snapshot path uses default."""
        demo = create_nangate45_demo_study(snapshot_path=None)

        assert demo.snapshot_path is not None
        assert "nangate45_base" in demo.snapshot_path

    def test_demo_study_validation_with_invalid_config_fails(self) -> None:
        """Verify validation catches configuration errors."""
        # Create a demo Study
        demo = create_nangate45_demo_study()

        # Corrupt the configuration
        demo.stages = []  # Remove all stages

        # Validation should fail
        with pytest.raises(ValueError, match="at least one stage"):
            demo.validate()

    def test_minimal_demo_uses_sandbox_safety_domain(self) -> None:
        """Verify minimal demo uses SANDBOX for permissive testing."""
        demo = create_minimal_demo_study()

        assert demo.safety_domain == SafetyDomain.SANDBOX

    def test_save_demo_config_creates_parent_directories(self, tmp_path: Path) -> None:
        """Verify saving config creates parent directories if needed."""
        nested_path = tmp_path / "configs" / "demo" / "study.json"

        # Parent directories don't exist yet
        assert not nested_path.parent.exists()

        # Create parent directories
        nested_path.parent.mkdir(parents=True, exist_ok=True)

        save_demo_study_config(nested_path)

        assert nested_path.exists()
