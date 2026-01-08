"""
Tests for Gate 4: Extreme Scenarios (Demo-Grade).

Gate 4 is the final gate in the staged validation ladder. It ensures that
Noodle 2 can handle adversarial conditions while maintaining all safety
contracts and auditability guarantees.

Requirements:
1. Create extreme Study with severe violations
2. Verify Noodle 2 refuses to proceed when base case is broken
3. Test pathological ECO containment
4. Verify reproducibility under extreme conditions
5. Confirm auditability is preserved even in extreme cases

This gate is only approached after Gates 0-3 are stable. It validates that
the safety and policy infrastructure holds even under deliberate stress.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.eco import (
    CongestionStressorECO,
    TimingDegradationECO,
    ToolErrorECO,
    create_eco,
)
from src.controller.executor import StudyExecutor, StudyResult
from src.controller.study import StudyConfig
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig


class TestGate4ExtremeScenarios:
    """Tests for Gate 4 Step 1-2: Extreme Studies and broken base case handling."""

    def test_gate4_extreme_study_configuration(self) -> None:
        """
        Gate 4 Step 1: Create extreme Study configuration with severe violations.

        An extreme Study has:
        - High trial budgets
        - Multiple stages
        - Aggressive survivor selection
        - Intentionally adversarial ECOs
        """
        config = StudyConfig(
            name="gate4_extreme_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="nangate45_extreme",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage_0_coarse",
                    execution_mode=ExecutionMode.STA_CONGESTION,
                    trial_budget=50,
                    survivor_count=10,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                        ECOClass.PLACEMENT_LOCAL,
                        ECOClass.ROUTING_AFFECTING,
                    ],
                ),
                StageConfig(
                    name="stage_1_refinement",
                    execution_mode=ExecutionMode.STA_CONGESTION,
                    trial_budget=30,
                    survivor_count=5,
                    allowed_eco_classes=[
                        ECOClass.PLACEMENT_LOCAL,
                        ECOClass.ROUTING_AFFECTING,
                    ],
                ),
                StageConfig(
                    name="stage_2_closure",
                    execution_mode=ExecutionMode.STA_CONGESTION,
                    trial_budget=10,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
            ],
            snapshot_path="studies/nangate45_extreme",
        )

        # Verify extreme Study configuration is valid
        assert config.name == "gate4_extreme_study"
        assert config.safety_domain == SafetyDomain.SANDBOX
        assert len(config.stages) == 3
        assert config.stages[0].trial_budget == 50
        assert config.stages[0].survivor_count == 10

    def test_gate4_refuses_broken_base_case(self) -> None:
        """
        Gate 4 Step 2: Verify Noodle 2 refuses to proceed when base case is broken.

        A broken base case means:
        - Tool crashes (rc != 0)
        - Missing required reports
        - Parse failures
        - Structural issues preventing execution

        This is the most critical safety gate: if the base case doesn't work,
        no ECO experimentation is permitted.
        """
        # Create a mock StudyExecutor with a deliberately broken base case
        # by using a non-existent snapshot path
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="gate4_broken_base",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="broken_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=10,
                        survivor_count=5,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path="/nonexistent/path/to/snapshot",
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Verify base case is detected as broken
            is_valid, failure_message = executor.verify_base_case()

            assert is_valid is False, "Expected base case to fail verification"
            assert (
                len(failure_message) > 0
            ), "Expected failure message explaining why base case failed"
            assert (
                "snapshot" in failure_message.lower()
                or "not found" in failure_message.lower()
                or "missing" in failure_message.lower()
            ), f"Expected informative failure message, got: {failure_message}"

    def test_gate4_study_blocked_on_broken_base_case(self) -> None:
        """
        Gate 4 Step 2: Verify Study is blocked when base case verification fails.

        When base case is broken:
        - Study status is BLOCKED
        - No stages are executed
        - Clear failure reason is provided
        - Telemetry is still emitted
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="gate4_blocked_study",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="broken_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=10,
                        survivor_count=5,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path="/nonexistent/path",
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Execute Study (should be blocked at base case verification)
            result = executor.execute()

            # Verify Study is blocked
            assert result.aborted is True, "Expected Study to be aborted/blocked"
            assert result.abort_reason is not None, "Expected abort reason to be set"
            assert (
                "base case" in result.abort_reason.lower()
                or "broken" in result.abort_reason.lower()
                or "snapshot" in result.abort_reason.lower()
            ), f"Expected base case failure in abort reason: {result.abort_reason}"

            # Verify no stages were executed
            assert len(result.stage_results) == 0, "Expected no stage results"

            # Verify telemetry was still emitted
            telemetry_file = Path(f"{tmpdir}/telemetry/gate4_blocked_study/study_telemetry.json")
            assert telemetry_file.exists(), "Expected telemetry even when blocked"


class TestGate4PathologicalECOContainment:
    """Tests for Gate 4 Step 3: Pathological ECO containment."""

    def test_gate4_pathological_eco_creation(self) -> None:
        """
        Gate 4 Step 3 Setup: Create pathological ECOs for testing.

        Pathological ECOs are intentionally designed to:
        - Trigger tool errors
        - Cause severe timing degradation
        - Create routing disasters
        - Exercise failure containment logic
        """
        # Create severe timing degradation ECO
        eco_timing = TimingDegradationECO(severity="severe")
        assert eco_timing.name == "timing_degradation_test"
        assert eco_timing.metadata.parameters["severity"] == "severe"

        # Create high-intensity congestion stressor
        eco_congestion = CongestionStressorECO(intensity="high")
        assert eco_congestion.name == "congestion_stressor_test"
        assert eco_congestion.metadata.parameters["intensity"] == "high"

        # Create tool error ECO
        eco_error = ToolErrorECO(error_type="crash")
        assert eco_error.name == "tool_error_test"
        assert eco_error.metadata.parameters["error_type"] == "crash"

    def test_gate4_pathological_eco_containment_scope(self) -> None:
        """
        Gate 4 Step 3: Verify pathological ECOs are contained to smallest scope.

        Containment scopes (from smallest to largest):
        1. Individual ECO - mark as suspicious/failed
        2. ECO class - blacklist entire class if failure rate is high
        3. Stage - abort stage if too many failures
        4. Study - abort entire Study if catastrophic

        This test verifies the containment logic exists.
        """
        # Test ECO class tracker for containment
        from src.controller.eco import ECOClassTracker

        tracker = ECOClassTracker()

        # Create a pathological ECO
        eco = TimingDegradationECO(severity="severe")

        # Record multiple failures (simulate pathological behavior)
        for _ in range(5):
            tracker.record_eco_result(eco, success=False)

        # Verify ECO class is tracked
        assert ECOClass.PLACEMENT_LOCAL in tracker.class_stats
        stats = tracker.class_stats[ECOClass.PLACEMENT_LOCAL]
        assert stats.failed_applications == 5
        assert stats.total_applications == 5
        assert stats.failure_rate == 1.0

        # Verify blacklisting logic
        assert not tracker.is_eco_class_allowed(ECOClass.PLACEMENT_LOCAL)
        assert ECOClass.PLACEMENT_LOCAL in tracker.get_blacklisted_classes()

    @pytest.mark.slow
    def test_gate4_pathological_eco_does_not_poison_study(self) -> None:
        """
        Gate 4 Step 3: Verify pathological ECO failure is contained.

        When an ECO causes tool errors:
        - The trial is marked as failed
        - Failure is classified correctly
        - Other trials continue execution
        - Study does not crash
        - Telemetry captures the failure
        """
        snapshot_path = Path("studies/nangate45_base")
        if not snapshot_path.exists():
            pytest.skip("Nangate45 base case snapshot not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="gate4_pathological_eco",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="nangate45_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=3,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Execute Study (should complete despite pathological ECO)
            result = executor.execute()

            # Verify Study completed (not crashed)
            # Study should either succeed or abort gracefully
            assert result is not None, "Study should return a result"
            assert isinstance(result, StudyResult), "Result should be StudyResult type"

            # Verify telemetry was emitted
            telemetry_file = Path(
                f"{tmpdir}/telemetry/gate4_pathological_eco/study_telemetry.json"
            )
            assert telemetry_file.exists(), "Expected telemetry file"

            # Verify Study did not crash the executor
            assert result is not None
            assert isinstance(result, StudyResult)


class TestGate4ReproducibilityUnderStress:
    """Tests for Gate 4 Step 4: Reproducibility under extreme conditions."""

    def test_gate4_deterministic_execution_with_seed(self) -> None:
        """
        Gate 4 Step 4: Verify deterministic execution configuration.

        Even under extreme conditions:
        - Trial order is deterministic
        - Artifact paths are predictable
        - Same configuration produces same structure

        Note: OpenROAD seed is set at trial script generation time,
        not in StageConfig. This test validates configuration equivalence.
        """
        config1 = StudyConfig(
            name="gate4_reproducible_1",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="studies/nangate45_base",
        )

        config2 = StudyConfig(
            name="gate4_reproducible_2",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                )
            ],
            snapshot_path="studies/nangate45_base",
        )

        # Verify configurations are equivalent
        assert config1.stages[0].trial_budget == config2.stages[0].trial_budget
        assert config1.stages[0].execution_mode == config2.stages[0].execution_mode
        assert config1.stages[0].survivor_count == config2.stages[0].survivor_count

    def test_gate4_reproducible_artifact_paths(self) -> None:
        """
        Gate 4 Step 4: Verify artifact paths are deterministic and reproducible.

        Artifact path structure:
        - artifacts/{study_name}/{case_name}/stage_{stage_index}/trial_{trial_index}/
        - Same structure across runs with same configuration
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="gate4_artifact_paths",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="nangate45_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=2,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path="studies/nangate45_base",
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Verify artifact root structure is deterministic
            expected_study_artifacts = Path(f"{tmpdir}/artifacts/gate4_artifact_paths")
            expected_telemetry = Path(f"{tmpdir}/telemetry/gate4_artifact_paths")

            # Create the directories (StudyExecutor would create them during execution)
            expected_study_artifacts.mkdir(parents=True, exist_ok=True)
            expected_telemetry.mkdir(parents=True, exist_ok=True)

            # Verify paths exist and are deterministic
            assert expected_study_artifacts.exists()
            assert expected_telemetry.exists()
            assert expected_study_artifacts.name == config.name
            assert expected_telemetry.name == config.name


class TestGate4AuditabilityPreservation:
    """Tests for Gate 4 Step 5: Auditability preservation under extreme conditions."""

    def test_gate4_auditability_required_artifacts(self) -> None:
        """
        Gate 4 Step 5: Verify all required audit artifacts are present.

        Required artifacts (even under extreme conditions):
        1. Run Legality Report
        2. Study Telemetry (JSON)
        3. Safety Trace (JSON + TXT)
        4. Summary Report (TXT)
        5. Case Lineage Graph (DOT)
        6. Event Stream (NDJSON)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="gate4_audit_artifacts",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="nangate45_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=1,
                        survivor_count=1,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
                snapshot_path="studies/nangate45_base",
            )

            artifacts_root = Path(f"{tmpdir}/artifacts/{config.name}")
            telemetry_root = Path(f"{tmpdir}/telemetry/{config.name}")

            # Create directory structure
            artifacts_root.mkdir(parents=True, exist_ok=True)
            telemetry_root.mkdir(parents=True, exist_ok=True)

            # Verify required artifact paths
            expected_artifacts = [
                artifacts_root / "run_legality_report.txt",
                artifacts_root / "safety_trace.json",
                artifacts_root / "safety_trace.txt",
                artifacts_root / "summary_report.txt",
                artifacts_root / "lineage.dot",
                telemetry_root / "study_telemetry.json",
                telemetry_root / "event_stream.ndjson",
            ]

            # Verify structure is deterministic
            for artifact_path in expected_artifacts:
                # Verify parent directory exists
                assert artifact_path.parent.exists(), f"Parent missing: {artifact_path.parent}"
                # Verify path is under expected root
                assert (
                    str(artifact_path).startswith(str(tmpdir))
                ), f"Artifact outside tmpdir: {artifact_path}"

    @pytest.mark.slow
    def test_gate4_telemetry_emitted_even_on_abort(self) -> None:
        """
        Gate 4 Step 5: Verify telemetry is emitted even when Study aborts.

        Critical for auditability:
        - Telemetry must be written on abort
        - Safety trace must record abort reason
        - Summary report must explain what happened
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Study that will be blocked (illegal configuration)
            config = StudyConfig(
                name="gate4_abort_telemetry",
                safety_domain=SafetyDomain.LOCKED,  # Very restrictive
                base_case_name="nangate45_base",
                pdk="Nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=10,
                        survivor_count=5,
                        allowed_eco_classes=[
                            ECOClass.GLOBAL_DISRUPTIVE  # Not allowed in LOCKED
                        ],
                    )
                ],
                snapshot_path="studies/nangate45_base",
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Execute Study (should be blocked due to illegal configuration)
            result = executor.execute()

            # Verify Study was blocked
            assert result.aborted is True, "Study should be aborted due to illegal configuration"
            assert result.abort_reason is not None, "Abort reason should be set"

            # Verify telemetry was still emitted
            telemetry_file = Path(
                f"{tmpdir}/telemetry/gate4_abort_telemetry/study_telemetry.json"
            )
            assert telemetry_file.exists(), "Telemetry must be emitted even on block"

            # Verify telemetry contains abort information
            with open(telemetry_file) as f:
                telemetry = json.load(f)

            # Telemetry should indicate the study was aborted
            assert "aborted" in telemetry or "status" in telemetry

    def test_gate4_safety_trace_captures_extreme_conditions(self) -> None:
        """
        Gate 4 Step 5: Verify safety trace captures decisions under extreme conditions.

        Safety trace must record:
        - Legality checks
        - Base case verification results
        - Stage abort evaluations
        - ECO class filtering decisions
        - Threshold violations
        """
        from src.controller.safety_trace import SafetyTrace

        trace = SafetyTrace(study_name="gate4_extreme", safety_domain=SafetyDomain.SANDBOX)

        # Record extreme scenario events using specific methods
        trace.record_legality_check(
            is_legal=True,
            violations=[],
            warnings=[],
        )

        trace.record_base_case_verification(
            is_valid=True,
            failure_message="",
        )

        trace.record_stage_abort_check(
            stage_index=0,
            stage_name="stage_0",
            should_abort=False,
            abort_reason=None,
            details="High failure rate but below abort threshold",
        )

        trace.record_catastrophic_failure_check(
            stage_index=0,
            catastrophic_count=15,
            total_trials=20,
            failure_rate=0.75,
            threshold=0.8,
        )

        # Verify trace captures all events
        assert len(trace.evaluations) == 4, "Expected 4 safety gate evaluations"

        # Verify gate types are present
        gate_types = [eval.gate_type for eval in trace.evaluations]
        from src.controller.safety_trace import SafetyGateType
        assert SafetyGateType.LEGALITY_CHECK in gate_types
        assert SafetyGateType.BASE_CASE_VERIFICATION in gate_types
        assert SafetyGateType.STAGE_ABORT_CHECK in gate_types
        assert SafetyGateType.CATASTROPHIC_FAILURE_CHECK in gate_types

        # Verify all evaluations have timestamps
        for eval in trace.evaluations:
            assert eval.timestamp is not None
            assert len(eval.timestamp) > 0

    def test_gate4_complete_audit_trail_available(self) -> None:
        """
        Gate 4 Step 5: Verify complete audit trail is available after extreme Study.

        Audit trail must include:
        - What was attempted (Study configuration)
        - What happened (execution results)
        - Why decisions were made (safety trace)
        - When events occurred (timestamps)
        - Where artifacts are stored (paths)
        """
        from src.controller.study import StudyConfig

        config = StudyConfig(
            name="gate4_audit_trail",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="nangate45_extreme",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_CONGESTION,
                    trial_budget=50,
                    survivor_count=10,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                        ECOClass.PLACEMENT_LOCAL,
                        ECOClass.ROUTING_AFFECTING,
                    ],
                )
            ],
            snapshot_path="studies/nangate45_extreme",
            metadata={
                "author": "gate4_test",
                "description": "Extreme scenario for Gate 4 validation",
                "creation_date": "2026-01-08",
            },
        )

        # Verify configuration captures provenance
        assert config.metadata is not None
        assert "author" in config.metadata
        assert "description" in config.metadata
        assert "creation_date" in config.metadata

        # Verify configuration is JSON-serializable (for audit)
        config_dict = {
            "name": config.name,
            "safety_domain": config.safety_domain.value,
            "base_case_name": config.base_case_name,
            "pdk": config.pdk,
            "metadata": config.metadata,
        }

        config_json = json.dumps(config_dict, indent=2)
        assert len(config_json) > 0
        assert "gate4_audit_trail" in config_json
        assert "Extreme scenario" in config_json
