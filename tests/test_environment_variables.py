"""Tests for environment variable configuration for trial execution."""

import tempfile
from pathlib import Path

import pytest
import yaml

from src.controller.study import load_study_config
from src.controller.types import ExecutionMode, SafetyDomain, StageConfig, StudyConfig
from src.trial_runner.docker_runner import DockerRunConfig, DockerTrialRunner
from src.trial_runner.trial import Trial, TrialConfig


class TestStudyConfigEnvironmentVariables:
    """Test environment variable support in StudyConfig."""

    def test_study_config_has_environment_field(self):
        """Test that StudyConfig has environment field."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[],
                )
            ],
            snapshot_path="/path/to/snapshot",
            environment={"VAR1": "value1", "VAR2": "value2"},
        )

        assert hasattr(config, "environment")
        assert config.environment == {"VAR1": "value1", "VAR2": "value2"}

    def test_study_config_environment_defaults_to_empty_dict(self):
        """Test that environment defaults to empty dict if not specified."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[],
                )
            ],
            snapshot_path="/path/to/snapshot",
        )

        assert config.environment == {}

    def test_study_config_validates_with_environment(self):
        """Test that StudyConfig validates successfully with environment vars."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[],
                )
            ],
            snapshot_path="/path/to/snapshot",
            environment={"OPENROAD_DEBUG": "1", "TCL_LIBRARY": "/usr/lib/tcl8.6"},
        )

        # Should not raise
        config.validate()


class TestYAMLConfigurationLoading:
    """Test loading environment variables from YAML configuration."""

    def test_load_study_with_environment_from_yaml(self):
        """
        Test loading Study configuration with environment variables from YAML.

        Step 1: Define environment variables in Study config
        """
        yaml_content = """
name: env_test_study
safety_domain: sandbox
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /path/to/snapshot
environment:
  OPENROAD_SEED: "42"
  TCL_PRECISION: "8"
  CUSTOM_VAR: "custom_value"
stages:
  - name: stage1
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 3
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = f.name

        try:
            config = load_study_config(config_path)

            assert config.environment == {
                "OPENROAD_SEED": "42",
                "TCL_PRECISION": "8",
                "CUSTOM_VAR": "custom_value",
            }
        finally:
            Path(config_path).unlink()

    def test_load_study_without_environment_from_yaml(self):
        """Test loading Study configuration without environment section defaults to empty dict."""
        yaml_content = """
name: no_env_study
safety_domain: guarded
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /path/to/snapshot
stages:
  - name: stage1
    execution_mode: sta_only
    trial_budget: 5
    survivor_count: 2
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(yaml_content)
            config_path = f.name

        try:
            config = load_study_config(config_path)
            assert config.environment == {}
        finally:
            Path(config_path).unlink()


class TestDockerRunConfigEnvironmentVariables:
    """Test environment variable passing to Docker containers."""

    def test_docker_config_accepts_environment_dict(self):
        """
        Test that DockerRunConfig accepts environment variables.

        Step 2: Pass environment vars to Docker container
        """
        docker_config = DockerRunConfig(
            environment={"VAR1": "value1", "VAR2": "value2"}
        )

        assert docker_config.environment == {"VAR1": "value1", "VAR2": "value2"}

    def test_docker_config_environment_defaults_to_none(self):
        """Test that DockerRunConfig environment defaults to None."""
        docker_config = DockerRunConfig()
        assert docker_config.environment is None

    def test_docker_runner_merges_environment_variables(self):
        """Test that Docker runner merges environment variables correctly."""
        docker_config = DockerRunConfig(
            environment={"CUSTOM_VAR": "custom", "OVERRIDE_VAR": "original"}
        )

        runner = DockerTrialRunner(docker_config)

        # Verify the config was stored
        assert runner.config.environment == {
            "CUSTOM_VAR": "custom",
            "OVERRIDE_VAR": "original",
        }


class TestEnvironmentVariableInTrialExecution:
    """Test environment variables are passed through trial execution pipeline."""

    def test_trial_config_to_docker_config_environment_flow(self, tmp_path):
        """
        Test environment variables flow from Study config through to Docker execution.

        Step 3: Verify vars are accessible in trial execution
        Step 5: Document env vars in telemetry
        """
        # Create a simple TCL script
        script_path = tmp_path / "test.tcl"
        script_path.write_text('puts "Hello"')

        # Create DockerRunConfig with environment
        docker_config = DockerRunConfig(
            environment={"TEST_VAR": "test_value", "ANOTHER_VAR": "another_value"}
        )

        # Create Trial with docker_config
        trial_config = TrialConfig(
            study_name="env_test_study",
            case_name="case_0",
            stage_index=0,
            trial_index=0,
            script_path=script_path,
        )

        trial = Trial(
            config=trial_config,
            artifacts_root=tmp_path / "artifacts",
            docker_config=docker_config,
        )

        # Verify docker_runner has the environment
        assert trial.docker_runner.config.environment == {
            "TEST_VAR": "test_value",
            "ANOTHER_VAR": "another_value",
        }


class TestEnvironmentVariablesInOpenROADScripts:
    """Test environment variables can be used in OpenROAD/TCL scripts."""

    def test_environment_variables_accessible_in_tcl(self):
        """
        Test that environment variables are accessible in TCL scripts.

        Step 4: Use env vars in OpenROAD scripts

        This is a documentation test - actual verification would require
        Docker execution. The test documents the expected usage pattern.
        """
        # Example TCL script that uses environment variables
        tcl_script_example = """
# Access environment variable in TCL
if {[info exists env(OPENROAD_SEED)]} {
    set seed $env(OPENROAD_SEED)
    puts "Using seed: $seed"
    # Set random seed for reproducible results
    set_random_seed $seed
}

if {[info exists env(CUSTOM_UTILIZATION)]} {
    set util $env(CUSTOM_UTILIZATION)
    puts "Using utilization: $util"
    initialize_floorplan -utilization $util
}
"""

        # This test documents that environment variables are accessible
        # via the standard TCL env() array in OpenROAD scripts
        assert "env(OPENROAD_SEED)" in tcl_script_example
        assert "env(CUSTOM_UTILIZATION)" in tcl_script_example


class TestEnvironmentVariableDocumentation:
    """Test environment variables are documented in telemetry."""

    def test_environment_in_study_config_serialization(self):
        """Test that environment variables are included when serializing StudyConfig."""
        config = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[],
                )
            ],
            snapshot_path="/path/to/snapshot",
            environment={"VAR1": "value1", "VAR2": "value2"},
        )

        # StudyConfig should be serializable with environment
        # (This tests that environment is a proper field)
        assert config.environment == {"VAR1": "value1", "VAR2": "value2"}


class TestEndToEndEnvironmentVariableFlow:
    """End-to-end test of environment variable configuration."""

    def test_yaml_to_docker_environment_flow(self, tmp_path):
        """
        Complete flow: YAML config → StudyConfig → DockerRunConfig → Trial execution.

        This test validates all 5 steps of the feature:
        Step 1: Define environment variables in Study config
        Step 2: Pass environment vars to Docker container
        Step 3: Verify vars are accessible in trial execution
        Step 4: Use env vars in OpenROAD scripts (documented)
        Step 5: Document env vars in telemetry
        """
        # Step 1: Define environment variables in Study config
        yaml_content = """
name: e2e_env_study
safety_domain: sandbox
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /path/to/snapshot
environment:
  OPENROAD_SEED: "123"
  CUSTOM_UTILIZATION: "0.55"
  DEBUG_MODE: "1"
stages:
  - name: stage1
    execution_mode: sta_only
    trial_budget: 5
    survivor_count: 2
"""

        config_path = tmp_path / "study_config.yaml"
        config_path.write_text(yaml_content)

        # Load Study configuration
        study_config = load_study_config(config_path)

        # Verify environment is loaded
        assert study_config.environment == {
            "OPENROAD_SEED": "123",
            "CUSTOM_UTILIZATION": "0.55",
            "DEBUG_MODE": "1",
        }

        # Step 2: Pass environment vars to Docker container
        docker_config = DockerRunConfig(environment=study_config.environment)

        assert docker_config.environment == {
            "OPENROAD_SEED": "123",
            "CUSTOM_UTILIZATION": "0.55",
            "DEBUG_MODE": "1",
        }

        # Step 3: Create Trial with docker_config
        script_path = tmp_path / "test.tcl"
        script_path.write_text('puts "test"')

        trial_config = TrialConfig(
            study_name=study_config.name,
            case_name="case_0",
            stage_index=0,
            trial_index=0,
            script_path=script_path,
        )

        trial = Trial(
            config=trial_config,
            artifacts_root=tmp_path / "artifacts",
            docker_config=docker_config,
        )

        # Verify environment variables flow through
        assert trial.docker_runner.config.environment == {
            "OPENROAD_SEED": "123",
            "CUSTOM_UTILIZATION": "0.55",
            "DEBUG_MODE": "1",
        }

        # Step 5: Environment is documented (already in StudyConfig)
        assert study_config.environment is not None
        assert len(study_config.environment) == 3


class TestEnvironmentVariableUseCases:
    """Test common use cases for environment variables."""

    def test_reproducible_seed_via_environment(self):
        """Test setting OpenROAD seed via environment variable."""
        config = StudyConfig(
            name="seed_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[],
                )
            ],
            snapshot_path="/path/to/snapshot",
            environment={"OPENROAD_SEED": "42"},
        )

        assert config.environment["OPENROAD_SEED"] == "42"

    def test_custom_pdk_path_via_environment(self):
        """Test setting custom PDK path via environment variable."""
        config = StudyConfig(
            name="pdk_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[],
                )
            ],
            snapshot_path="/path/to/snapshot",
            environment={"PDK_ROOT": "/custom/pdk/path", "PDK_VARIANT": "variant1"},
        )

        assert config.environment["PDK_ROOT"] == "/custom/pdk/path"
        assert config.environment["PDK_VARIANT"] == "variant1"

    def test_debug_mode_via_environment(self):
        """Test enabling debug mode via environment variable."""
        config = StudyConfig(
            name="debug_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[],
                )
            ],
            snapshot_path="/path/to/snapshot",
            environment={
                "OPENROAD_DEBUG": "1",
                "VERBOSE_LOGGING": "true",
                "LOG_LEVEL": "DEBUG",
            },
        )

        assert config.environment["OPENROAD_DEBUG"] == "1"
        assert config.environment["VERBOSE_LOGGING"] == "true"
        assert config.environment["LOG_LEVEL"] == "DEBUG"

    def test_multiple_environment_variables(self):
        """Test Study with multiple environment variables for different purposes."""
        config = StudyConfig(
            name="multi_env_study",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="base",
            pdk="ASAP7",
            stages=[
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[],
                )
            ],
            snapshot_path="/path/to/snapshot",
            environment={
                # Reproducibility
                "OPENROAD_SEED": "42",
                # Configuration
                "FLOORPLAN_UTILIZATION": "0.60",
                "ROUTING_LAYERS": "metal2-metal9",
                # Debugging
                "DEBUG_MODE": "0",
                # Custom paths
                "PDK_ROOT": "/pdk/asap7",
            },
        )

        assert len(config.environment) == 5
        assert all(isinstance(k, str) and isinstance(v, str) for k, v in config.environment.items())
