"""Tests for Study configuration loading and validation."""

import pytest
import tempfile
from pathlib import Path

from src.controller.study import create_study_config, load_study_config
from src.controller.types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
    StageConfig,
)
from src.controller.exceptions import StudyNameError, NoStagesError, TrialBudgetError, SurvivorBudgetMismatchError


def test_create_minimal_study_config() -> None:
    """
    Feature #2: Create a minimal Study definition with Nangate45 base case.

    Steps:
        1. Create Study configuration file with Nangate45 PDK reference
        2. Specify safety domain as 'sandbox'
        3. Define single stage with STA-only execution mode
        4. Validate Study configuration parses successfully
        5. Verify base case is identified correctly
    """
    # Step 1-3: Create Study with Nangate45 and sandbox domain
    config = create_study_config(
        name="test_nangate45_study",
        pdk="Nangate45",
        base_case_name="nangate45_base",
        snapshot_path="/tmp/snapshots/nangate45_base",
        safety_domain=SafetyDomain.SANDBOX,
    )

    # Step 4: Validate configuration parses successfully
    assert config.name == "test_nangate45_study"
    assert config.safety_domain == SafetyDomain.SANDBOX
    assert config.pdk == "Nangate45"

    # Step 5: Verify base case is identified correctly
    assert config.base_case_name == "nangate45_base"

    # Verify single stage with STA-only mode
    assert len(config.stages) == 1
    assert config.stages[0].execution_mode == ExecutionMode.STA_ONLY


def test_study_config_validation() -> None:
    """Test Study configuration validation rules."""
    # Valid configuration should pass
    config = create_study_config(
        name="valid_study",
        pdk="Nangate45",
        base_case_name="nangate45_base",
        snapshot_path="/tmp/test",
    )
    config.validate()  # Should not raise

    # Empty name should fail
    with pytest.raises(StudyNameError, match="name cannot be empty"):
        bad_config = create_study_config(
            name="",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="/tmp/test",
        )

    # No stages should fail
    with pytest.raises(NoStagesError, match="at least one stage"):
        bad_config = create_study_config(
            name="no_stages",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="/tmp/test",
            stages=[],
        )


def test_stage_config_validation() -> None:
    """Test Stage configuration validation."""
    # Invalid trial budget (zero)
    with pytest.raises(TrialBudgetError, match="trial_budget must be positive"):
        create_study_config(
            name="bad_budget",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="/tmp/test",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=0,  # Invalid
                    survivor_count=5,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )

    # Survivor count exceeds budget
    with pytest.raises(SurvivorBudgetMismatchError, match="cannot exceed trial_budget"):
        create_study_config(
            name="bad_survivors",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="/tmp/test",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=10,  # Exceeds budget
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
        )


def test_load_study_from_yaml() -> None:
    """Test loading Study configuration from YAML file."""
    yaml_content = """
name: nangate45_test_study
safety_domain: sandbox
base_case_name: nangate45_base
pdk: Nangate45
snapshot_path: /tmp/snapshots/nangate45

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes:
      - topology_neutral
      - placement_local
    visualization_enabled: false
    timeout_seconds: 3600
"""

    # Create temporary YAML file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        yaml_path = f.name

    try:
        # Load configuration
        config = load_study_config(yaml_path)

        # Verify loaded configuration
        assert config.name == "nangate45_test_study"
        assert config.safety_domain == SafetyDomain.SANDBOX
        assert config.base_case_name == "nangate45_base"
        assert config.pdk == "Nangate45"
        assert len(config.stages) == 1

        stage = config.stages[0]
        assert stage.name == "stage_0"
        assert stage.execution_mode == ExecutionMode.STA_ONLY
        assert stage.trial_budget == 10
        assert stage.survivor_count == 5
        assert ECOClass.TOPOLOGY_NEUTRAL in stage.allowed_eco_classes
        assert ECOClass.PLACEMENT_LOCAL in stage.allowed_eco_classes
    finally:
        # Cleanup
        Path(yaml_path).unlink()


def test_load_missing_file() -> None:
    """Test loading from non-existent file."""
    with pytest.raises(FileNotFoundError):
        load_study_config("/nonexistent/path/to/config.yaml")


def test_multi_stage_study() -> None:
    """Test creating a Study with multiple stages."""
    stages = [
        StageConfig(
            name="exploration",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=20,
            survivor_count=10,
            allowed_eco_classes=[
                ECOClass.TOPOLOGY_NEUTRAL,
                ECOClass.PLACEMENT_LOCAL,
            ],
        ),
        StageConfig(
            name="refinement",
            execution_mode=ExecutionMode.STA_CONGESTION,
            trial_budget=10,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
            visualization_enabled=True,
        ),
    ]

    config = create_study_config(
        name="multi_stage_study",
        pdk="ASAP7",
        base_case_name="asap7_base",
        snapshot_path="/tmp/asap7",
        safety_domain=SafetyDomain.GUARDED,
        stages=stages,
    )

    assert len(config.stages) == 2
    assert config.stages[0].name == "exploration"
    assert config.stages[1].name == "refinement"
    assert config.stages[1].visualization_enabled is True
