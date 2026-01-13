"""
Tests for F071: Illegal run is rejected before consuming compute.

Feature Requirements:
1. Create study with safety_domain: locked and ECO class: global_disruptive
2. Attempt to start study
3. Verify study is rejected immediately
4. Verify no trials are executed
5. Verify rejection reason is clear in error message
"""

import pytest
import tempfile
from pathlib import Path
import time

from src.controller.executor import StudyExecutor
from src.controller.study import create_study_config
from src.controller.types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
    StageConfig,
)


class TestIllegalRunRejection:
    """Test F071 - Illegal run rejection before consuming compute."""

    def test_step_1_create_illegal_study_config(self):
        """Step 1: Create study with safety_domain: locked and ECO class: global_disruptive."""
        # Create illegal configuration:
        # LOCKED domain only allows TOPOLOGY_NEUTRAL and PLACEMENT_LOCAL
        # GLOBAL_DISRUPTIVE is not allowed
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.GLOBAL_DISRUPTIVE,  # ILLEGAL in LOCKED domain!
                ],
            )
        ]

        config = create_study_config(
            name="illegal_locked_study",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.LOCKED,
            stages=stages,
        )

        # Verify configuration was created
        assert config is not None
        assert config.safety_domain == SafetyDomain.LOCKED
        assert ECOClass.GLOBAL_DISRUPTIVE in config.stages[0].allowed_eco_classes

    def test_step_2_3_attempt_start_and_verify_rejection(self):
        """Step 2 & 3: Attempt to start study and verify it's rejected immediately."""
        # Create illegal configuration
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.GLOBAL_DISRUPTIVE,  # ILLEGAL in LOCKED domain!
                ],
            )
        ]

        config = create_study_config(
            name="illegal_study_immediate_rejection",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.LOCKED,
            stages=stages,
        )

        # Create executor with temp artifacts directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=Path(tmp_dir),
                skip_base_case_verification=True,  # Skip base case to test only legality
            )

            # Measure execution time
            start_time = time.time()

            # Execute study - should be rejected immediately
            result = executor.execute()

            execution_time = time.time() - start_time

            # Verify study was rejected immediately (should take < 1 second)
            assert execution_time < 1.0, f"Study should be rejected immediately, took {execution_time:.2f}s"

            # Verify study result indicates abortion
            assert result.aborted is True
            assert "ILLEGAL" in result.abort_reason

    def test_step_4_verify_no_trials_executed(self):
        """Step 4: Verify no trials are executed."""
        # Create illegal configuration
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=20,  # Would execute 20 trials if not blocked
                survivor_count=10,
                allowed_eco_classes=[
                    ECOClass.ROUTING_AFFECTING,  # ILLEGAL in LOCKED domain!
                ],
            )
        ]

        config = create_study_config(
            name="illegal_study_no_trials",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.LOCKED,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=Path(tmp_dir),
                skip_base_case_verification=True,
            )

            result = executor.execute()

            # Verify no stages were completed
            assert result.stages_completed == 0

            # Verify no stage results exist
            assert len(result.stage_results) == 0

            # Verify no survivors exist
            assert len(result.final_survivors) == 0

            # Verify study was aborted
            assert result.aborted is True

    def test_step_5_verify_clear_rejection_reason(self):
        """Step 5: Verify rejection reason is clear in error message."""
        # Create illegal configuration with specific ECO class
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.GLOBAL_DISRUPTIVE,  # This specific class is illegal
                ],
            )
        ]

        config = create_study_config(
            name="illegal_study_clear_reason",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.LOCKED,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=Path(tmp_dir),
                skip_base_case_verification=True,
            )

            result = executor.execute()

            # Verify abort reason is present
            assert result.abort_reason is not None
            assert result.abort_reason != ""

            # Verify abort reason contains key information
            abort_reason_lower = result.abort_reason.lower()
            assert "illegal" in abort_reason_lower
            assert "global_disruptive" in abort_reason_lower
            assert "locked" in abort_reason_lower

            # Verify it explains WHY it's illegal
            assert "not allowed" in abort_reason_lower or "is not allowed" in abort_reason_lower


class TestLegalRunPasses:
    """Test that legal configurations are not rejected."""

    def test_legal_guarded_configuration_not_rejected(self):
        """Verify that legal GUARDED configurations are not rejected."""
        # Create legal configuration
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=5,
                survivor_count=3,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                    ECOClass.ROUTING_AFFECTING,  # Legal in GUARDED
                ],
            )
        ]

        config = create_study_config(
            name="legal_guarded_study",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.GUARDED,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=Path(tmp_dir),
                skip_base_case_verification=True,
            )

            # This would execute if we had a real snapshot
            # For this test, we just verify it doesn't abort due to illegality
            # The execution will fail due to missing snapshot, but that's different from illegality

            # We can't easily test full execution here without real infrastructure,
            # but we can verify the config passes legality checks
            from src.controller.safety import check_study_legality

            # Should not raise ValueError
            legality_result = check_study_legality(config)
            assert legality_result.is_legal

    def test_legal_locked_configuration_not_rejected(self):
        """Verify that legal LOCKED configurations are not rejected."""
        # Create legal LOCKED configuration
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=5,
                survivor_count=3,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,  # Legal in LOCKED
                ],
            )
        ]

        config = create_study_config(
            name="legal_locked_study",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.LOCKED,
            stages=stages,
        )

        from src.controller.safety import check_study_legality

        # Should not raise ValueError
        legality_result = check_study_legality(config)
        assert legality_result.is_legal


class TestDifferentIllegalConfigurations:
    """Test various illegal configurations are rejected."""

    def test_guarded_rejects_global_disruptive(self):
        """GUARDED domain should reject GLOBAL_DISRUPTIVE."""
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.GLOBAL_DISRUPTIVE,  # ILLEGAL in GUARDED
                ],
            )
        ]

        config = create_study_config(
            name="guarded_illegal",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.GUARDED,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=Path(tmp_dir),
                skip_base_case_verification=True,
            )

            result = executor.execute()

            assert result.aborted is True
            assert "illegal" in result.abort_reason.lower()

    def test_locked_rejects_routing_affecting(self):
        """LOCKED domain should reject ROUTING_AFFECTING."""
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.ROUTING_AFFECTING,  # ILLEGAL in LOCKED
                ],
            )
        ]

        config = create_study_config(
            name="locked_illegal",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.LOCKED,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=Path(tmp_dir),
                skip_base_case_verification=True,
            )

            result = executor.execute()

            assert result.aborted is True
            assert "illegal" in result.abort_reason.lower()

    def test_multiple_illegal_eco_classes_rejected(self):
        """Study with multiple illegal ECO classes should be rejected."""
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,  # Legal
                    ECOClass.ROUTING_AFFECTING,  # ILLEGAL in LOCKED
                    ECOClass.GLOBAL_DISRUPTIVE,  # ILLEGAL in LOCKED
                ],
            )
        ]

        config = create_study_config(
            name="multiple_violations",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.LOCKED,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            executor = StudyExecutor(
                config=config,
                artifacts_root=Path(tmp_dir),
                skip_base_case_verification=True,
            )

            result = executor.execute()

            assert result.aborted is True
            assert "illegal" in result.abort_reason.lower()


class TestArtifactsGeneratedOnRejection:
    """Test that appropriate artifacts are generated even when study is rejected."""

    def test_safety_trace_saved_on_rejection(self):
        """Verify safety trace is saved when study is rejected."""
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.GLOBAL_DISRUPTIVE,  # ILLEGAL in LOCKED
                ],
            )
        ]

        config = create_study_config(
            name="rejected_with_trace",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.LOCKED,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            executor = StudyExecutor(
                config=config,
                artifacts_root=tmp_path,
                skip_base_case_verification=True,
            )

            result = executor.execute()

            # Verify study result was saved
            study_dir = tmp_path / config.name
            assert study_dir.exists()

            # Verify safety trace was saved
            safety_trace_json = study_dir / "safety_trace.json"
            safety_trace_txt = study_dir / "safety_trace.txt"

            assert safety_trace_json.exists(), "Safety trace JSON should be saved"
            assert safety_trace_txt.exists(), "Safety trace TXT should be saved"

            # Verify study summary was saved
            study_summary = study_dir / "study_summary.json"
            assert study_summary.exists(), "Study summary should be saved"

    def test_study_summary_contains_abort_info(self):
        """Verify study summary contains abortion information."""
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.GLOBAL_DISRUPTIVE,  # ILLEGAL in LOCKED
                ],
            )
        ]

        config = create_study_config(
            name="rejected_summary_check",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.LOCKED,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            executor = StudyExecutor(
                config=config,
                artifacts_root=tmp_path,
                skip_base_case_verification=True,
            )

            result = executor.execute()

            # Load study summary
            import json
            study_summary_path = tmp_path / config.name / "study_summary.json"
            with open(study_summary_path) as f:
                summary = json.load(f)

            # Verify abort information is present
            assert summary["aborted"] is True
            assert "abort_reason" in summary
            assert "ILLEGAL" in summary["abort_reason"]
            assert summary["stages_completed"] == 0


class TestEndToEndIllegalRunRejection:
    """End-to-end integration test for illegal run rejection."""

    def test_complete_illegal_run_rejection_workflow(self):
        """Complete workflow: create illegal config, attempt execution, verify rejection."""
        # Step 1: Create illegal study configuration
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=15,
                survivor_count=8,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.GLOBAL_DISRUPTIVE,  # ILLEGAL in LOCKED
                ],
            ),
            StageConfig(
                name="stage_1",
                execution_mode=ExecutionMode.STA_CONGESTION,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.ROUTING_AFFECTING,  # ILLEGAL in LOCKED
                ],
            ),
        ]

        config = create_study_config(
            name="e2e_illegal_rejection",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.LOCKED,
            stages=stages,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            # Step 2: Attempt to start study
            executor = StudyExecutor(
                config=config,
                artifacts_root=tmp_path,
                skip_base_case_verification=True,
            )

            start_time = time.time()
            result = executor.execute()
            execution_time = time.time() - start_time

            # Step 3: Verify study was rejected immediately
            assert execution_time < 1.0, "Study should be rejected in < 1 second"
            assert result.aborted is True

            # Step 4: Verify no trials were executed
            assert result.stages_completed == 0
            assert len(result.stage_results) == 0
            assert len(result.final_survivors) == 0

            # Step 5: Verify rejection reason is clear
            assert "ILLEGAL" in result.abort_reason
            assert "global_disruptive" in result.abort_reason.lower() or \
                   "routing_affecting" in result.abort_reason.lower()
            assert "locked" in result.abort_reason.lower()

            # Verify artifacts were generated
            study_dir = tmp_path / config.name
            assert (study_dir / "safety_trace.json").exists()
            assert (study_dir / "study_summary.json").exists()
