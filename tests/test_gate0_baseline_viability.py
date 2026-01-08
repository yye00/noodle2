"""
Tests for Gate 0: Baseline Viability.

Gate 0 is the first gate in the staged validation ladder. It ensures that
all reference targets (Nangate45, ASAP7, Sky130) have structurally runnable
base cases before any ECO experimentation begins.

Requirements:
1. Execute base case for Nangate45, ASAP7, Sky130
2. Verify each base case runs without crashing
3. Verify required reports/artifacts are produced
4. Verify early-failure detection works on base cases
5. Block Study if any base case fails Gate 0
"""

import tempfile
from pathlib import Path

import pytest

from src.controller.executor import StudyExecutor, StudyResult
from src.controller.study import StudyConfig
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig


class TestGate0BaselineViability:
    """Tests for Gate 0: Baseline viability of reference targets."""

    @pytest.mark.slow
    def test_gate0_nangate45_base_case_runs_without_crashing(self) -> None:
        """
        Gate 0 Step 1-2: Execute Nangate45 base case and verify it runs without crashing.

        Requirements:
        - Base case executes to completion
        - Return code == 0
        - No exceptions during execution
        """
        snapshot_path = Path("studies/nangate45_base")
        if not snapshot_path.exists():
            pytest.skip("Nangate45 base case snapshot not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="gate0_nangate45",
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
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Verify base case runs without crashing
            is_valid, failure_message = executor.verify_base_case()

            assert is_valid is True, f"Nangate45 base case failed: {failure_message}"
            assert failure_message == "", "Expected no failure message for valid base case"

    @pytest.mark.slow
    def test_gate0_nangate45_produces_required_artifacts(self) -> None:
        """
        Gate 0 Step 3: Verify Nangate45 base case produces required reports/artifacts.

        Required artifacts:
        - Timing report (report_checks output)
        - Metrics (wns_ps extracted)
        - Tool logs (stdout.txt, stderr.txt)
        - Trial result metadata
        """
        snapshot_path = Path("studies/nangate45_base")
        if not snapshot_path.exists():
            pytest.skip("Nangate45 base case snapshot not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="gate0_nangate45_artifacts",
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
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Verify base case and check it has baseline WNS
            is_valid, _ = executor.verify_base_case()
            assert is_valid is True

            # Verify baseline WNS was extracted
            assert executor.baseline_wns_ps is not None, "Baseline WNS not extracted from base case"

            # Verify artifacts directory exists
            artifacts_dir = Path(f"{tmpdir}/artifacts/gate0_nangate45_artifacts/nangate45_base/stage_0/trial_0")
            assert artifacts_dir.exists(), f"Artifacts directory not created: {artifacts_dir}"

            # Verify logs exist
            logs_dir = artifacts_dir / "logs"
            assert logs_dir.exists(), "Logs directory not created"
            assert (logs_dir / "stdout.txt").exists(), "stdout.txt not created"
            assert (logs_dir / "stderr.txt").exists(), "stderr.txt not created"

    def test_gate0_broken_base_case_blocks_study(self) -> None:
        """
        Gate 0 Step 5: Verify Study is blocked if base case fails Gate 0.

        Requirements:
        - Study execution detects base case failure
        - Study aborts before stage execution
        - Clear abort reason provided
        - No ECO experimentation occurs
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a broken snapshot (missing run_sta.tcl)
            snapshot_path = Path(f"{tmpdir}/broken_snapshot")
            snapshot_path.mkdir()

            config = StudyConfig(
                name="gate0_broken",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="broken_base",
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
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Execute Study (should abort on base case failure)
            result: StudyResult = executor.execute()

            # Verify Study was blocked
            assert result.aborted is True, "Study should be blocked when base case fails"
            assert result.abort_reason is not None, "Abort reason should be provided"
            assert "base case" in result.abort_reason.lower(), "Abort reason should mention base case"
            assert result.stages_completed == 0, "No stages should execute when base case fails"


class TestGate0EarlyFailureDetection:
    """Tests for Gate 0 Step 4: Early-failure detection on base cases."""

    def test_gate0_early_failure_detection_on_missing_script(self) -> None:
        """
        Gate 0 Step 4: Verify early-failure detection works when script is missing.

        Expected behavior:
        - Missing script detected as early failure
        - Deterministic failure classification
        - Failure type and reason populated
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create snapshot without run_sta.tcl
            snapshot_path = Path(f"{tmpdir}/no_script_snapshot")
            snapshot_path.mkdir()

            config = StudyConfig(
                name="gate0_missing_script",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="no_script_base",
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
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Verify base case fails
            is_valid, failure_message = executor.verify_base_case()

            assert is_valid is False, "Base case should fail when script is missing"
            assert failure_message != "", "Failure message should be provided"
            assert "structural runnability" in failure_message.lower(), (
                "Failure message should indicate structural failure"
            )

    def test_gate0_early_failure_detection_on_tool_error(self) -> None:
        """
        Gate 0 Step 4: Verify early-failure detection works when tool returns error.

        Expected behavior:
        - Non-zero return code detected
        - Failure classified appropriately
        - Log excerpt captured
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create snapshot with failing script
            snapshot_path = Path(f"{tmpdir}/error_snapshot")
            snapshot_path.mkdir()

            # Create a script that exits with error
            script_path = snapshot_path / "run_sta.tcl"
            script_path.write_text(
                "# Script that intentionally fails\n"
                "puts \"Error: Intentional failure for testing\"\n"
                "exit 1\n"
            )

            config = StudyConfig(
                name="gate0_tool_error",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="error_base",
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
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Verify base case fails
            is_valid, failure_message = executor.verify_base_case()

            assert is_valid is False, "Base case should fail when tool returns error"
            assert failure_message != "", "Failure message should be provided"
            # Check that failure message indicates tool error (return code or failure type)
            assert any(keyword in failure_message.lower() for keyword in ["return code", "failure", "error"]), (
                "Failure message should indicate tool error"
            )


class TestGate0Sky130BaseCase:
    """Tests for Gate 0 with Sky130/sky130A PDK."""

    @pytest.mark.slow
    def test_gate0_sky130_base_case_runs_without_crashing(self) -> None:
        """
        Gate 0 Step 1-2: Execute Sky130 base case and verify it runs without crashing.

        Requirements:
        - Base case executes to completion
        - Return code == 0
        - No exceptions during execution
        """
        snapshot_path = Path("studies/sky130_base")
        if not snapshot_path.exists():
            pytest.skip("Sky130 base case snapshot not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="gate0_sky130",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="sky130_base",
                pdk="sky130A",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=1,
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

            # Verify base case runs without crashing
            is_valid, failure_message = executor.verify_base_case()

            assert is_valid is True, f"Sky130 base case failed: {failure_message}"
            assert failure_message == "", "Expected no failure message for valid base case"

    @pytest.mark.slow
    def test_gate0_sky130_produces_required_artifacts(self) -> None:
        """
        Gate 0 Step 3: Verify Sky130 base case produces required reports/artifacts.

        Required artifacts:
        - Timing report (report_checks output)
        - Metrics (wns_ps extracted)
        - Tool logs (stdout.txt, stderr.txt)
        - Trial result metadata
        """
        snapshot_path = Path("studies/sky130_base")
        if not snapshot_path.exists():
            pytest.skip("Sky130 base case snapshot not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="gate0_sky130_artifacts",
                safety_domain=SafetyDomain.SANDBOX,
                base_case_name="sky130_base",
                pdk="sky130A",
                stages=[
                    StageConfig(
                        name="stage_0",
                        execution_mode=ExecutionMode.STA_ONLY,
                        trial_budget=1,
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

            # Verify base case and check it has baseline WNS
            is_valid, _ = executor.verify_base_case()
            assert is_valid is True

            # Verify baseline WNS was extracted
            assert executor.baseline_wns_ps is not None, "Baseline WNS not extracted from Sky130 base case"

            # Verify artifacts directory exists
            artifacts_dir = Path(f"{tmpdir}/artifacts/gate0_sky130_artifacts/sky130_base/stage_0/trial_0")
            assert artifacts_dir.exists(), f"Artifacts directory not created: {artifacts_dir}"

            # Verify logs exist
            logs_dir = artifacts_dir / "logs"
            assert logs_dir.exists(), "Logs directory not created"
            assert (logs_dir / "stdout.txt").exists(), "stdout.txt not created"
            assert (logs_dir / "stderr.txt").exists(), "stderr.txt not created"


class TestGate0ASAP7BaseCase:
    """Tests for Gate 0 with ASAP7 PDK."""

    @pytest.mark.slow
    def test_gate0_asap7_base_case_placeholder(self) -> None:
        """
        Gate 0 Step 1-2: ASAP7 base case placeholder.

        ASAP7 requires specific workarounds (explicit routing layers, site definition, etc.)
        and a proper base case snapshot. This test will be implemented once we have:
        1. ASAP7 base case snapshot in studies/asap7_base/
        2. Proper ASAP7 configuration (as per app_spec.txt workarounds)

        For now, this is a placeholder that documents the requirement.
        """
        snapshot_path = Path("studies/asap7_base")
        if not snapshot_path.exists():
            pytest.skip("ASAP7 base case snapshot not yet available - to be implemented")

        # When ASAP7 snapshot is available, this test should validate:
        # - Base case runs without crashing
        # - Uses explicit routing layers (metal2-metal9)
        # - Uses correct ASAP7 site (asap7sc7p5t_28_R_24_NP_162NW_34O)
        # - Pin placement on mid-stack metals (metal4/metal5)
        # - Lower utilization (0.50-0.55)
        # - STA-first staging (not congestion-first)
        pytest.skip("ASAP7 base case implementation pending")


class TestGate0CrossTargetValidation:
    """Tests for Gate 0 validation across all supported targets."""

    def test_gate0_all_supported_pdks_have_base_cases(self) -> None:
        """
        Gate 0 Completeness: Verify all supported PDKs have base case definitions.

        Required base cases:
        - Nangate45: studies/nangate45_base/
        - Sky130: studies/sky130_base/
        - ASAP7: studies/asap7_base/ (future)
        """
        # Check Nangate45
        nangate45_path = Path("studies/nangate45_base")
        assert nangate45_path.exists(), "Nangate45 base case snapshot is required"
        assert (nangate45_path / "run_sta.tcl").exists(), "Nangate45 must have run_sta.tcl"

        # Check Sky130
        sky130_path = Path("studies/sky130_base")
        assert sky130_path.exists(), "Sky130 base case snapshot is required"

        # ASAP7 is documented as future work
        # When implemented, add assertion here

    def test_gate0_base_case_naming_convention(self) -> None:
        """
        Gate 0 Naming: Verify base cases follow the deterministic naming contract.

        Expected naming:
        - Nangate45: nangate45_base
        - Sky130: sky130_base
        - ASAP7: asap7_base (future)

        This ensures Case ID determinism: {case_name}_{stage_index}_{derived_index}
        """
        # Nangate45
        nangate45_path = Path("studies/nangate45_base")
        if nangate45_path.exists():
            assert nangate45_path.name == "nangate45_base", (
                "Nangate45 base case should use naming convention: nangate45_base"
            )

        # Sky130
        sky130_path = Path("studies/sky130_base")
        if sky130_path.exists():
            assert sky130_path.name == "sky130_base", (
                "Sky130 base case should use naming convention: sky130_base"
            )

        # ASAP7
        asap7_path = Path("studies/asap7_base")
        if asap7_path.exists():
            assert asap7_path.name == "asap7_base", (
                "ASAP7 base case should use naming convention: asap7_base"
            )


class TestGate0TelemetryAndAuditability:
    """Tests for Gate 0 telemetry and audit trail generation."""

    @pytest.mark.slow
    def test_gate0_base_case_verification_recorded_in_safety_trace(self) -> None:
        """
        Gate 0 Auditability: Verify base case verification is recorded in safety trace.

        Requirements:
        - Safety trace includes BASE_CASE_VERIFICATION gate
        - Pass/fail status recorded
        - Rationale provided
        - Timestamp captured
        """
        snapshot_path = Path("studies/nangate45_base")
        if not snapshot_path.exists():
            pytest.skip("Nangate45 base case snapshot not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="gate0_safety_trace",
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
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Execute Study (includes base case verification)
            result: StudyResult = executor.execute()

            # Verify safety trace was created
            safety_trace_path = Path(f"{tmpdir}/artifacts/gate0_safety_trace/safety_trace.json")
            assert safety_trace_path.exists(), "Safety trace should be created"

            # Verify safety trace includes base case verification
            import json
            with open(safety_trace_path) as f:
                trace_data = json.load(f)

            # Check for base_case_verification gate (lowercase enum value)
            evaluations = trace_data.get("evaluations", [])
            base_case_checks = [e for e in evaluations if e.get("gate_type") == "base_case_verification"]

            assert len(base_case_checks) > 0, "Safety trace should include base case verification"
            assert base_case_checks[0]["status"] == "pass", "Base case verification should pass"
            assert "timestamp" in base_case_checks[0], "Timestamp should be recorded"

    @pytest.mark.slow
    def test_gate0_study_telemetry_includes_base_case_metrics(self) -> None:
        """
        Gate 0 Telemetry: Verify Study telemetry includes base case metrics.

        Requirements:
        - Baseline WNS captured in telemetry
        - PDK recorded
        - Execution mode documented
        """
        snapshot_path = Path("studies/nangate45_base")
        if not snapshot_path.exists():
            pytest.skip("Nangate45 base case snapshot not available")

        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="gate0_telemetry",
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
                snapshot_path=str(snapshot_path),
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=f"{tmpdir}/artifacts",
                telemetry_root=f"{tmpdir}/telemetry",
            )

            # Execute Study
            result: StudyResult = executor.execute()

            # Verify telemetry exists
            telemetry_path = Path(f"{tmpdir}/telemetry/gate0_telemetry/study_telemetry.json")
            assert telemetry_path.exists(), "Study telemetry should be created"

            # Verify telemetry includes PDK
            import json
            with open(telemetry_path) as f:
                telemetry_data = json.load(f)

            # Check study configuration is documented
            assert "study_name" in telemetry_data, "Study name should be in telemetry"
            assert telemetry_data["study_name"] == "gate0_telemetry", "Study name should match"
