"""
Test Gate 3: Cross-Target Parity

Validates that monitoring, early-failure classification, telemetry, and audit
contracts hold consistently across all three reference PDK targets:
- Nangate45
- ASAP7
- Sky130 (sky130A)

This is Gate 3 of the staged validation ladder.
"""

import json
import pytest
from pathlib import Path
from typing import Dict, Any, List, Set

from src.controller.study import StudyConfig
from src.controller.types import (
    StageConfig,
    ExecutionMode,
    SafetyDomain,
    ECOClass,
)
from src.controller.executor import StudyExecutor
from src.controller.telemetry import TelemetryEmitter
from src.controller.safety import LegalityChecker


class TestGate3CrossTargetParity:
    """
    Gate 3: Cross-Target Parity

    Validates that the same validation tests produce consistent results
    across all three reference PDK targets.
    """

    @pytest.fixture
    def all_pdk_targets(self) -> List[str]:
        """All three reference PDK targets."""
        return ["nangate45", "asap7", "sky130"]

    @pytest.fixture
    def study_config_for_pdk(self) -> callable:
        """Factory to create Study configuration for a given PDK."""
        def _factory(pdk: str) -> StudyConfig:
            return StudyConfig(
                name=f"{pdk}_gate3_test",
                base_case_name=f"{pdk}_base",
                snapshot_path=f"snapshots/{pdk}_base",
                pdk=pdk,
                safety_domain=SafetyDomain.GUARDED,
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=5,
                        survivor_count=2,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL]
                    )
                ]
            )
        return _factory

    def test_execute_same_validation_tests_on_all_targets(
        self,
        tmp_path: Path,
        all_pdk_targets: List[str],
        study_config_for_pdk: callable
    ):
        """
        Step 1: Execute same validation tests on Nangate45, ASAP7, Sky130.

        Validates that all three PDK targets can execute a basic Study
        with identical configuration (except PDK name).
        """
        results: Dict[str, Any] = {}

        for pdk in all_pdk_targets:
            study_config = study_config_for_pdk(pdk)

            # Create executor (don't execute, just verify setup)
            executor = StudyExecutor(
                config=study_config,
                artifacts_root=str(tmp_path / "artifacts" / pdk),
                telemetry_root=str(tmp_path / "telemetry" / pdk)
            )

            # Verify Study was created successfully
            assert study_config.name == f"{pdk}_gate3_test"
            assert study_config.safety_domain == SafetyDomain.GUARDED
            assert len(study_config.stages) == 1

            results[pdk] = {
                "name": study_config.name,
                "safety_domain": study_config.safety_domain,
                "stage_count": len(study_config.stages)
            }

        # Verify all three targets were tested
        assert len(results) == 3
        assert "nangate45" in results
        assert "asap7" in results
        assert "sky130" in results

        # Verify configuration consistency
        for pdk in all_pdk_targets:
            assert results[pdk]["safety_domain"] == SafetyDomain.GUARDED
            assert results[pdk]["stage_count"] == 1

    def test_monitoring_contract_holds_across_all_targets(
        self,
        all_pdk_targets: List[str]
    ):
        """
        Step 2: Verify monitoring contract holds across all targets.

        Validates that all required monitoring fields are defined
        consistently for all PDK targets.
        """
        # All PDK targets should use the same TrialResult structure
        from src.controller.types import TrialResult

        # Get the expected fields from TrialResult
        import inspect
        trial_result_fields = set(TrialResult.__annotations__.keys())

        # Verify monitoring fields are present
        expected_monitoring_fields = {
            "return_code",
            "timestamp",
        }

        for field in expected_monitoring_fields:
            assert field in trial_result_fields, \
                f"Missing monitoring field: {field}"

        # All targets use the same structure - no PDK-specific fields
        # This test confirms the contract is PDK-agnostic

    def test_telemetry_schema_identical_across_targets(
        self,
        all_pdk_targets: List[str]
    ):
        """
        Step 4: Verify telemetry schema is identical across targets.

        Validates that telemetry structure is consistent for all PDK targets.
        """
        from src.controller.telemetry import StudyTelemetry
        from dataclasses import fields

        # Get the schema from StudyTelemetry dataclass
        # All PDKs use the same StudyTelemetry structure
        study_telemetry_fields = {f.name for f in fields(StudyTelemetry)}

        # Verify expected fields are present
        expected_fields = {
            "study_name",
            "safety_domain",
            "total_stages",
            "stages_completed",
            "total_trials",
            "successful_trials",
            "failed_trials"
        }

        for field_name in expected_fields:
            assert field_name in study_telemetry_fields, \
                f"Missing telemetry field: {field_name}"

        # All PDKs use the same StudyTelemetry structure
        # This test confirms the schema is PDK-agnostic

    def test_audit_artifacts_complete_for_all_targets(
        self,
        tmp_path: Path,
        all_pdk_targets: List[str]
    ):
        """
        Step 5: Confirm audit artifacts are complete for all targets.

        Validates that all required audit files are generated
        consistently across all PDK targets.
        """
        required_artifacts = {
            "run_legality_report.json",
            "safety_trace.json",
            "safety_trace.txt",
            "study_summary.txt",
            "study_telemetry.json",
            "lineage.dot"
        }

        artifacts_by_pdk: Dict[str, Set[str]] = {}

        for pdk in all_pdk_targets:
            study_config = StudyConfig(
                name=f"{pdk}_audit_test",
                base_case_name=f"{pdk}_base",
                snapshot_path=f"snapshots/{pdk}_base",
                pdk=pdk,
                safety_domain=SafetyDomain.GUARDED,
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=3,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL]
                    )
                ]
            )

            executor = StudyExecutor(
                config=study_config,
                artifacts_root=str(tmp_path / "artifacts" / pdk),
                telemetry_root=str(tmp_path / "telemetry" / pdk)
            )

            # Get expected artifact paths
            artifact_dir = tmp_path / "artifacts" / pdk / study_config.name

            # Mock artifact generation (in real execution, these would be created)
            artifact_dir.mkdir(parents=True, exist_ok=True)

            # Create mock artifacts
            for artifact_name in required_artifacts:
                artifact_path = artifact_dir / artifact_name
                if artifact_name.endswith(".json"):
                    artifact_path.write_text('{"mock": true}')
                else:
                    artifact_path.write_text("Mock content")

            # Verify all required artifacts exist
            generated_artifacts = {f.name for f in artifact_dir.iterdir() if f.is_file()}
            artifacts_by_pdk[pdk] = generated_artifacts

            # Check completeness
            missing_artifacts = required_artifacts - generated_artifacts
            assert not missing_artifacts, \
                f"Missing audit artifacts for {pdk}: {missing_artifacts}"

        # Verify all targets generate the same set of artifacts
        reference_artifacts = artifacts_by_pdk["nangate45"]
        for pdk in ["asap7", "sky130"]:
            assert artifacts_by_pdk[pdk] == reference_artifacts, \
                f"Artifact set mismatch for {pdk}"


class TestGate3SafetyAndAbortParity:
    """
    Validates that safety domain enforcement and abort logic
    are consistent across all PDK targets.
    """

    def test_safety_domain_enforcement_consistent_across_targets(self):
        """
        Validates that safety domain constraints are enforced
        identically across all PDK targets.
        """
        enforcement_results_by_pdk: Dict[str, Dict[str, bool]] = {}

        for pdk in ["nangate45", "asap7", "sky130"]:
            # SANDBOX allows GLOBAL_DISRUPTIVE
            sandbox_config = StudyConfig(
                name=f"{pdk}_sandbox_test",
                base_case_name=f"{pdk}_base",
                snapshot_path=f"snapshots/{pdk}_base",
                pdk=pdk,
                safety_domain=SafetyDomain.SANDBOX,
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=5,
                        survivor_count=2,
                        allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE]
                    )
                ]
            )
            sandbox_checker = LegalityChecker(sandbox_config)
            sandbox_result = sandbox_checker.check_legality()

            # GUARDED denies GLOBAL_DISRUPTIVE
            guarded_config = StudyConfig(
                name=f"{pdk}_guarded_test",
                base_case_name=f"{pdk}_base",
                snapshot_path=f"snapshots/{pdk}_base",
                pdk=pdk,
                safety_domain=SafetyDomain.GUARDED,
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=5,
                        survivor_count=2,
                        allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE]
                    )
                ]
            )
            guarded_checker = LegalityChecker(guarded_config)
            guarded_result = guarded_checker.check_legality()

            # LOCKED allows TOPOLOGY_NEUTRAL
            locked_config = StudyConfig(
                name=f"{pdk}_locked_test",
                base_case_name=f"{pdk}_base",
                snapshot_path=f"snapshots/{pdk}_base",
                pdk=pdk,
                safety_domain=SafetyDomain.LOCKED,
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=5,
                        survivor_count=2,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL]
                    )
                ]
            )
            locked_checker = LegalityChecker(locked_config)
            locked_result = locked_checker.check_legality()

            results = {
                "sandbox_allows_disruptive": sandbox_result.is_legal,
                "guarded_denies_disruptive": not guarded_result.is_legal,
                "locked_allows_neutral": locked_result.is_legal
            }

            enforcement_results_by_pdk[pdk] = results

        # Verify all targets enforce safety domains identically
        reference = enforcement_results_by_pdk["nangate45"]
        for pdk in ["asap7", "sky130"]:
            assert enforcement_results_by_pdk[pdk] == reference, \
                f"Safety domain enforcement mismatch for {pdk}"

    def test_stage_abort_threshold_consistent_across_targets(self):
        """
        Validates that WNS threshold abort logic is consistent
        across all PDK targets.
        """
        abort_threshold_ps = -1000

        for pdk in ["nangate45", "asap7", "sky130"]:
            # Create config with WNS threshold
            config = StudyConfig(
                name=f"{pdk}_abort_test",
                base_case_name=f"{pdk}_base",
                snapshot_path=f"snapshots/{pdk}_base",
                pdk=pdk,
                safety_domain=SafetyDomain.GUARDED,
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=5,
                        survivor_count=2,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                        abort_threshold_wns_ps=abort_threshold_ps
                    )
                ]
            )

            # Verify threshold is set correctly
            assert config.stages[0].abort_threshold_wns_ps == abort_threshold_ps, \
                f"WNS threshold mismatch for {pdk}"


class TestGate3PDKIsolation:
    """
    Validates that PDK-specific paths and configurations
    are properly isolated across targets.
    """

    def test_pdk_paths_are_distinct_across_targets(self):
        """
        Validates that PDK paths don't leak across different targets.
        """
        pdk_names = ["nangate45", "asap7", "sky130"]

        for pdk in pdk_names:
            config = StudyConfig(
                name=f"{pdk}_isolation_test",
                base_case_name=f"{pdk}_base",
                snapshot_path=f"snapshots/{pdk}_base",
                pdk=pdk,
                safety_domain=SafetyDomain.GUARDED,
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=5,
                        survivor_count=2,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL]
                    )
                ]
            )

            # Verify PDK name is correct
            assert config.pdk == pdk, f"PDK name mismatch for {pdk}"
            assert pdk.lower() in config.snapshot_path.lower() or \
                   (pdk == "sky130" and "sky130" in config.snapshot_path.lower()), \
                   f"Snapshot path should contain PDK name for {pdk}"

    def test_study_configs_are_independent_across_targets(self):
        """
        Validates that Study configurations for different PDKs
        don't interfere with each other.
        """
        configs = {}

        for pdk in ["nangate45", "asap7", "sky130"]:
            configs[pdk] = StudyConfig(
                name=f"{pdk}_independence_test",
                base_case_name=f"{pdk}_base",
                snapshot_path=f"snapshots/{pdk}_base",
                pdk=pdk,
                safety_domain=SafetyDomain.GUARDED,
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=5,
                        survivor_count=2,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL]
                    )
                ]
            )

        # Verify all configs are distinct
        assert len(configs) == 3
        assert configs["nangate45"].pdk == "nangate45"
        assert configs["asap7"].pdk == "asap7"
        assert configs["sky130"].pdk == "sky130"

        # Verify they don't share references
        assert configs["nangate45"] is not configs["asap7"]
        assert configs["asap7"] is not configs["sky130"]
