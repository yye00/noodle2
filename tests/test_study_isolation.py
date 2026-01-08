"""Tests for Study isolation - Feature #22.

Ensures that telemetry, priors, and state do not leak across Studies.
Each Study must maintain complete isolation from other Studies.
"""

import json
from pathlib import Path

import pytest

from src.controller.telemetry import TelemetryEmitter, StudyTelemetry, StageTelemetry
from src.controller.types import SafetyDomain


class TestStudyTelemetryIsolation:
    """Test that telemetry is properly isolated between Studies."""

    def test_studies_have_separate_telemetry_directories(self, tmp_path: Path) -> None:
        """Each Study should have its own telemetry directory."""
        telemetry_root = tmp_path / "telemetry"

        emitter_a = TelemetryEmitter("study_a", telemetry_root)
        emitter_b = TelemetryEmitter("study_b", telemetry_root)

        # Verify separate directories exist
        assert (telemetry_root / "study_a").exists()
        assert (telemetry_root / "study_b").exists()
        assert emitter_a.study_dir != emitter_b.study_dir

    def test_study_telemetry_does_not_leak_across_studies(self, tmp_path: Path) -> None:
        """Study A telemetry should not be accessible to Study B."""
        telemetry_root = tmp_path / "telemetry"

        # Execute Study A
        emitter_a = TelemetryEmitter("study_a", telemetry_root)
        study_a_telemetry = StudyTelemetry(
            study_name="study_a",
            safety_domain="sandbox",
            total_stages=1,
        )
        study_a_telemetry.metadata["custom_field"] = "study_a_data"
        emitter_a.emit_study_telemetry(study_a_telemetry)

        # Execute Study B
        emitter_b = TelemetryEmitter("study_b", telemetry_root)
        study_b_telemetry = StudyTelemetry(
            study_name="study_b",
            safety_domain="guarded",
            total_stages=2,
        )
        study_b_telemetry.metadata["custom_field"] = "study_b_data"
        emitter_b.emit_study_telemetry(study_b_telemetry)

        # Verify Study A telemetry is separate
        study_a_file = telemetry_root / "study_a" / "study_telemetry.json"
        study_b_file = telemetry_root / "study_b" / "study_telemetry.json"

        assert study_a_file.exists()
        assert study_b_file.exists()

        # Load and verify they are independent
        with open(study_a_file) as f:
            data_a = json.load(f)
        with open(study_b_file) as f:
            data_b = json.load(f)

        assert data_a["study_name"] == "study_a"
        assert data_b["study_name"] == "study_b"
        assert data_a["metadata"]["custom_field"] == "study_a_data"
        assert data_b["metadata"]["custom_field"] == "study_b_data"

    def test_stage_telemetry_isolated_by_study(self, tmp_path: Path) -> None:
        """Stage telemetry should be isolated within each Study."""
        telemetry_root = tmp_path / "telemetry"

        # Study A - Stage 0
        emitter_a = TelemetryEmitter("study_a", telemetry_root)
        stage_a = StageTelemetry(
            stage_index=0,
            stage_name="exploration",
            trial_budget=10,
            survivor_count=5,
        )
        stage_a.trials_executed = 10
        emitter_a.emit_stage_telemetry(stage_a)

        # Study B - Stage 0
        emitter_b = TelemetryEmitter("study_b", telemetry_root)
        stage_b = StageTelemetry(
            stage_index=0,
            stage_name="refinement",
            trial_budget=20,
            survivor_count=3,
        )
        stage_b.trials_executed = 15
        emitter_b.emit_stage_telemetry(stage_b)

        # Verify isolation
        stage_a_file = telemetry_root / "study_a" / "stage_0_telemetry.json"
        stage_b_file = telemetry_root / "study_b" / "stage_0_telemetry.json"

        with open(stage_a_file) as f:
            data_a = json.load(f)
        with open(stage_b_file) as f:
            data_b = json.load(f)

        assert data_a["stage_name"] == "exploration"
        assert data_a["trials_executed"] == 10
        assert data_b["stage_name"] == "refinement"
        assert data_b["trials_executed"] == 15

    def test_case_telemetry_isolated_by_study(self, tmp_path: Path) -> None:
        """Case telemetry should be isolated within each Study."""
        telemetry_root = tmp_path / "telemetry"

        # Study A - Case
        emitter_a = TelemetryEmitter("study_a", telemetry_root)
        case_a = emitter_a.get_or_create_case_telemetry(
            case_id="nangate45_0_0",
            base_case="nangate45",
            stage_index=0,
            derived_index=0,
        )
        case_a.best_wns_ps = -500.0
        emitter_a.emit_case_telemetry(case_a)

        # Study B - Same case ID but different study
        emitter_b = TelemetryEmitter("study_b", telemetry_root)
        case_b = emitter_b.get_or_create_case_telemetry(
            case_id="nangate45_0_0",
            base_case="nangate45",
            stage_index=0,
            derived_index=0,
        )
        case_b.best_wns_ps = -300.0
        emitter_b.emit_case_telemetry(case_b)

        # Verify isolation - same case ID in different studies
        case_a_file = telemetry_root / "study_a" / "cases" / "nangate45_0_0_telemetry.json"
        case_b_file = telemetry_root / "study_b" / "cases" / "nangate45_0_0_telemetry.json"

        with open(case_a_file) as f:
            data_a = json.load(f)
        with open(case_b_file) as f:
            data_b = json.load(f)

        assert data_a["best_wns_ps"] == -500.0
        assert data_b["best_wns_ps"] == -300.0


class TestStudyPriorIsolation:
    """Test that priors and learned information don't leak between Studies."""

    def test_studies_start_with_fresh_priors(self, tmp_path: Path) -> None:
        """Study B should not have access to Study A's learned priors."""
        # This test verifies conceptual isolation
        # In the current implementation, each TelemetryEmitter is independent

        telemetry_root = tmp_path / "telemetry"

        emitter_a = TelemetryEmitter("study_a", telemetry_root)
        emitter_b = TelemetryEmitter("study_b", telemetry_root)

        # Add case telemetry to Study A
        case_a = emitter_a.get_or_create_case_telemetry(
            case_id="test_0_0",
            base_case="test",
            stage_index=0,
            derived_index=0,
        )

        # Verify Study B has no access to Study A's case telemetry
        assert "test_0_0" in emitter_a.case_telemetry
        assert "test_0_0" not in emitter_b.case_telemetry

        # Study B should have empty priors
        assert len(emitter_b.case_telemetry) == 0

    def test_study_state_isolation(self, tmp_path: Path) -> None:
        """Each Study maintains completely independent state."""
        telemetry_root = tmp_path / "telemetry"

        emitter_a = TelemetryEmitter("study_a", telemetry_root)
        emitter_b = TelemetryEmitter("study_b", telemetry_root)

        # Populate Study A with multiple cases
        for i in range(5):
            case = emitter_a.get_or_create_case_telemetry(
                case_id=f"case_{i}",
                base_case="base",
                stage_index=0,
                derived_index=i,
            )

        # Verify Study B is unaffected
        assert len(emitter_a.case_telemetry) == 5
        assert len(emitter_b.case_telemetry) == 0


class TestStudyNamespaceIsolation:
    """Test that Studies are properly namespaced and cannot interfere."""

    def test_study_names_are_unique_identifiers(self, tmp_path: Path) -> None:
        """Study names serve as unique namespace identifiers."""
        telemetry_root = tmp_path / "telemetry"

        emitter_1 = TelemetryEmitter("nangate45_experiment_1", telemetry_root)
        emitter_2 = TelemetryEmitter("nangate45_experiment_2", telemetry_root)

        assert emitter_1.study_name != emitter_2.study_name
        assert emitter_1.study_dir != emitter_2.study_dir

    def test_concurrent_studies_are_isolated(self, tmp_path: Path) -> None:
        """Multiple concurrent Studies should not interfere with each other."""
        telemetry_root = tmp_path / "telemetry"

        # Simulate concurrent studies
        studies = []
        for i in range(3):
            emitter = TelemetryEmitter(f"concurrent_study_{i}", telemetry_root)
            study_telemetry = StudyTelemetry(
                study_name=f"concurrent_study_{i}",
                safety_domain="sandbox",
                total_stages=1,
            )
            study_telemetry.total_trials = i * 10
            emitter.emit_study_telemetry(study_telemetry)
            studies.append((emitter, study_telemetry))

        # Verify each study maintained its own state
        for i, (emitter, _) in enumerate(studies):
            study_file = telemetry_root / f"concurrent_study_{i}" / "study_telemetry.json"
            with open(study_file) as f:
                data = json.load(f)
            assert data["study_name"] == f"concurrent_study_{i}"
            assert data["total_trials"] == i * 10

    def test_study_cannot_access_other_study_files(self, tmp_path: Path) -> None:
        """A Study should not be able to access another Study's files."""
        telemetry_root = tmp_path / "telemetry"

        emitter_a = TelemetryEmitter("study_a", telemetry_root)
        emitter_b = TelemetryEmitter("study_b", telemetry_root)

        # Study A emits telemetry
        study_a = StudyTelemetry(
            study_name="study_a",
            safety_domain="sandbox",
            total_stages=1,
        )
        emitter_a.emit_study_telemetry(study_a)

        # Study B should not find Study A's files in its directory
        study_b_dir = emitter_b.study_dir
        study_a_file_in_b = study_b_dir / "study_telemetry.json"

        # Study B's telemetry file shouldn't exist yet
        assert not study_a_file_in_b.exists()

        # Study A's file exists in its own directory
        study_a_file = emitter_a.study_dir / "study_telemetry.json"
        assert study_a_file.exists()


class TestStudyMemoryIsolation:
    """Test that in-memory state is isolated between Studies."""

    def test_case_telemetry_memory_isolation(self, tmp_path: Path) -> None:
        """Case telemetry tracked in memory should be study-specific."""
        telemetry_root = tmp_path / "telemetry"

        emitter_a = TelemetryEmitter("study_a", telemetry_root)
        emitter_b = TelemetryEmitter("study_b", telemetry_root)

        # Create case in Study A
        emitter_a.get_or_create_case_telemetry("case_1", "base", 0, 0)

        # Verify it's not in Study B's memory
        assert "case_1" in emitter_a.case_telemetry
        assert "case_1" not in emitter_b.case_telemetry

        # Verify they have separate dictionaries
        assert emitter_a.case_telemetry is not emitter_b.case_telemetry

    def test_multiple_emitters_for_same_study_share_nothing(self, tmp_path: Path) -> None:
        """
        Even if two TelemetryEmitters are created for the same study name,
        they should have independent in-memory state.
        """
        telemetry_root = tmp_path / "telemetry"

        emitter_1 = TelemetryEmitter("same_study", telemetry_root)
        emitter_2 = TelemetryEmitter("same_study", telemetry_root)

        # They point to the same directory
        assert emitter_1.study_dir == emitter_2.study_dir

        # But have separate in-memory state
        emitter_1.get_or_create_case_telemetry("case_x", "base", 0, 0)

        assert "case_x" in emitter_1.case_telemetry
        assert "case_x" not in emitter_2.case_telemetry
