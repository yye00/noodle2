"""
Test suite for Safety Trace generation and auditable safety-gate evaluations.

This tests Feature #63: Generate safety trace showing all safety-gate evaluations during execution.
"""

import json
import tempfile
from pathlib import Path

import pytest

from src.controller.executor import StudyExecutor
from src.controller.safety_trace import (
    SafetyGateEvaluation,
    SafetyGateStatus,
    SafetyGateType,
    SafetyTrace,
)
from src.controller.study import StudyConfig
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig


class TestSafetyTraceRecording:
    """Test safety trace recording functionality."""

    def test_safety_trace_has_required_fields(self):
        """Safety trace has required fields (study_name, safety_domain, evaluations)."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        assert trace.study_name == "test_study"
        assert trace.safety_domain == SafetyDomain.GUARDED
        assert trace.evaluations == []
        assert isinstance(trace.metadata, dict)

    def test_record_legality_check_pass(self):
        """Safety trace can record successful legality check."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_legality_check(
            is_legal=True,
            violations=[],
            warnings=["Some warning"],
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.LEGALITY_CHECK
        assert eval.status == SafetyGateStatus.PASS
        assert "legal" in eval.rationale.lower()
        assert eval.context["is_legal"] is True
        assert eval.context["violation_count"] == 0
        assert eval.context["warning_count"] == 1

    def test_record_legality_check_fail(self):
        """Safety trace can record failed legality check."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.LOCKED,
        )

        violations = [
            {"stage_index": 0, "reason": "ECO class not allowed"},
        ]
        trace.record_legality_check(
            is_legal=False,
            violations=violations,
            warnings=[],
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.LEGALITY_CHECK
        assert eval.status == SafetyGateStatus.FAIL
        assert "violation" in eval.rationale.lower()
        assert eval.context["is_legal"] is False
        assert eval.context["violation_count"] == 1

    def test_record_base_case_verification_pass(self):
        """Safety trace can record successful base case verification."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
        )

        trace.record_base_case_verification(
            is_valid=True,
            failure_message="",
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.BASE_CASE_VERIFICATION
        assert eval.status == SafetyGateStatus.PASS
        assert "runnable" in eval.rationale.lower()
        assert eval.context["is_valid"] is True

    def test_record_base_case_verification_fail(self):
        """Safety trace can record failed base case verification."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_base_case_verification(
            is_valid=False,
            failure_message="Tool return code was 1",
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.BASE_CASE_VERIFICATION
        assert eval.status == SafetyGateStatus.FAIL
        assert "failed" in eval.rationale.lower()
        assert eval.context["is_valid"] is False
        assert "Tool return code" in eval.context["failure_message"]

    def test_record_eco_class_filter_allowed(self):
        """Safety trace can record ECO class allowed decision."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_eco_class_filter(
            eco_class=ECOClass.PLACEMENT_LOCAL,
            stage_index=0,
            is_allowed=True,
            reason="",
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.ECO_CLASS_FILTER
        assert eval.status == SafetyGateStatus.PASS
        assert "allowed" in eval.rationale.lower()
        assert eval.context["eco_class"] == ECOClass.PLACEMENT_LOCAL.value
        assert eval.context["stage_index"] == 0
        assert eval.context["is_allowed"] is True

    def test_record_eco_class_filter_blocked(self):
        """Safety trace can record ECO class blocked decision."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.LOCKED,
        )

        trace.record_eco_class_filter(
            eco_class=ECOClass.GLOBAL_DISRUPTIVE,
            stage_index=0,
            is_allowed=False,
            reason="Not allowed in LOCKED domain",
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.ECO_CLASS_FILTER
        assert eval.status == SafetyGateStatus.BLOCKED
        assert "blocked" in eval.rationale.lower()
        assert eval.context["eco_class"] == ECOClass.GLOBAL_DISRUPTIVE.value
        assert eval.context["is_allowed"] is False

    def test_record_stage_abort_check_pass(self):
        """Safety trace can record stage proceeding normally."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_stage_abort_check(
            stage_index=0,
            stage_name="stage_0",
            should_abort=False,
            abort_reason=None,
            details="All checks passed",
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.STAGE_ABORT_CHECK
        assert eval.status == SafetyGateStatus.PASS
        assert "proceeding" in eval.rationale.lower()
        assert eval.context["should_abort"] is False

    def test_record_stage_abort_check_fail(self):
        """Safety trace can record stage abort decision."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_stage_abort_check(
            stage_index=1,
            stage_name="stage_1",
            should_abort=True,
            abort_reason="wns_threshold_violated",
            details="WNS worse than -5000 ps",
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.STAGE_ABORT_CHECK
        assert eval.status == SafetyGateStatus.FAIL
        assert "ABORTED" in eval.rationale
        assert eval.context["should_abort"] is True
        assert eval.context["abort_reason"] == "wns_threshold_violated"

    def test_record_wns_threshold_check_no_threshold(self):
        """Safety trace can record WNS check when no threshold configured."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
        )

        trace.record_wns_threshold_check(
            stage_index=0,
            threshold_ps=None,
            worst_wns_ps=-1000,
            violating_trials=[],
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.WNS_THRESHOLD_CHECK
        assert eval.status == SafetyGateStatus.PASS
        assert "No WNS threshold" in eval.rationale
        assert eval.context["threshold_ps"] is None

    def test_record_wns_threshold_check_pass(self):
        """Safety trace can record WNS check pass."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_wns_threshold_check(
            stage_index=0,
            threshold_ps=-5000,
            worst_wns_ps=-3000,
            violating_trials=[],
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.WNS_THRESHOLD_CHECK
        assert eval.status == SafetyGateStatus.PASS
        assert "within WNS threshold" in eval.rationale
        assert eval.context["violation_count"] == 0

    def test_record_wns_threshold_check_fail(self):
        """Safety trace can record WNS check failure."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_wns_threshold_check(
            stage_index=0,
            threshold_ps=-5000,
            worst_wns_ps=-8000,
            violating_trials=["trial_0", "trial_1"],
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.WNS_THRESHOLD_CHECK
        assert eval.status == SafetyGateStatus.FAIL
        assert "violated" in eval.rationale.lower()
        assert eval.context["violation_count"] == 2
        assert eval.context["worst_wns_ps"] == -8000

    def test_record_catastrophic_failure_check_no_threshold(self):
        """Safety trace can record catastrophic failure check with no threshold."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
        )

        trace.record_catastrophic_failure_check(
            stage_index=0,
            catastrophic_count=2,
            total_trials=10,
            failure_rate=0.2,
            threshold=None,
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.CATASTROPHIC_FAILURE_CHECK
        assert eval.status == SafetyGateStatus.PASS
        assert "No catastrophic failure threshold" in eval.rationale

    def test_record_catastrophic_failure_check_pass(self):
        """Safety trace can record catastrophic failure check pass."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_catastrophic_failure_check(
            stage_index=0,
            catastrophic_count=1,
            total_trials=10,
            failure_rate=0.1,
            threshold=0.5,
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.CATASTROPHIC_FAILURE_CHECK
        assert eval.status == SafetyGateStatus.PASS
        assert "within threshold" in eval.rationale
        assert eval.context["failure_rate"] == 0.1
        assert eval.context["threshold"] == 0.5

    def test_record_catastrophic_failure_check_fail(self):
        """Safety trace can record catastrophic failure check failure."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_catastrophic_failure_check(
            stage_index=0,
            catastrophic_count=6,
            total_trials=10,
            failure_rate=0.6,
            threshold=0.5,
        )

        assert len(trace.evaluations) == 1
        eval = trace.evaluations[0]
        assert eval.gate_type == SafetyGateType.CATASTROPHIC_FAILURE_CHECK
        assert eval.status == SafetyGateStatus.FAIL
        assert "exceeds threshold" in eval.rationale
        assert eval.context["failure_rate"] == 0.6


class TestSafetyTraceChronologicalOrdering:
    """Test that safety trace maintains chronological order of evaluations."""

    def test_evaluations_maintain_chronological_order(self):
        """Safety trace evaluations are in chronological order."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        # Record multiple evaluations in sequence
        trace.record_legality_check(is_legal=True, violations=[], warnings=[])
        trace.record_base_case_verification(is_valid=True, failure_message="")
        trace.record_stage_abort_check(
            stage_index=0,
            stage_name="stage_0",
            should_abort=False,
        )

        assert len(trace.evaluations) == 3
        # Check that timestamps are in increasing order
        timestamps = [eval.timestamp for eval in trace.evaluations]
        assert timestamps == sorted(timestamps)

    def test_evaluations_have_timestamps(self):
        """All safety trace evaluations have ISO 8601 timestamps."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_legality_check(is_legal=True, violations=[], warnings=[])

        eval = trace.evaluations[0]
        # Timestamp should be in ISO 8601 format (contains 'T' separator)
        assert "T" in eval.timestamp
        assert ":" in eval.timestamp


class TestSafetyTraceSummary:
    """Test safety trace summary generation."""

    def test_summary_counts_total_checks(self):
        """Safety trace summary counts total number of checks."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_legality_check(is_legal=True, violations=[], warnings=[])
        trace.record_base_case_verification(is_valid=True, failure_message="")
        trace.record_stage_abort_check(
            stage_index=0,
            stage_name="stage_0",
            should_abort=False,
        )

        summary = trace._generate_summary()
        assert summary["total_checks"] == 3

    def test_summary_counts_by_status(self):
        """Safety trace summary counts checks by status."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_legality_check(is_legal=True, violations=[], warnings=[])
        trace.record_base_case_verification(is_valid=False, failure_message="Failed")
        trace.record_eco_class_filter(
            eco_class=ECOClass.GLOBAL_DISRUPTIVE,
            stage_index=0,
            is_allowed=False,
            reason="Not allowed",
        )

        summary = trace._generate_summary()
        assert summary["passed"] == 1  # legality check
        assert summary["failed"] == 1  # base case
        assert summary["blocked"] == 1  # ECO class filter

    def test_summary_counts_by_gate_type(self):
        """Safety trace summary counts checks by gate type."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_legality_check(is_legal=True, violations=[], warnings=[])
        trace.record_legality_check(is_legal=True, violations=[], warnings=[])
        trace.record_base_case_verification(is_valid=True, failure_message="")

        summary = trace._generate_summary()
        assert summary["by_gate_type"]["legality_check"] == 2
        assert summary["by_gate_type"]["base_case_verification"] == 1


class TestSafetyTraceSerialization:
    """Test safety trace serialization to dict/JSON."""

    def test_safety_trace_serializes_to_dict(self):
        """Safety trace can be serialized to dictionary."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_legality_check(is_legal=True, violations=[], warnings=[])

        trace_dict = trace.to_dict()
        assert trace_dict["study_name"] == "test_study"
        assert trace_dict["safety_domain"] == "guarded"
        assert len(trace_dict["evaluations"]) == 1
        assert "summary" in trace_dict

    def test_safety_trace_dict_includes_summary(self):
        """Safety trace dict includes summary statistics."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_legality_check(is_legal=True, violations=[], warnings=[])
        trace.record_base_case_verification(is_valid=True, failure_message="")

        trace_dict = trace.to_dict()
        assert "summary" in trace_dict
        assert trace_dict["summary"]["total_checks"] == 2
        assert trace_dict["summary"]["passed"] == 2

    def test_save_to_file_json(self):
        """Safety trace can be saved to JSON file."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_legality_check(is_legal=True, violations=[], warnings=[])

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "safety_trace.json"
            trace.save_to_file(filepath)

            assert filepath.exists()

            # Verify JSON is valid
            with open(filepath) as f:
                data = json.load(f)
                assert data["study_name"] == "test_study"
                assert len(data["evaluations"]) == 1

    def test_save_to_file_txt(self):
        """Safety trace can be saved to text file."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_legality_check(is_legal=True, violations=[], warnings=[])

        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / "safety_trace.txt"
            trace.save_to_file(filepath)

            assert filepath.exists()

            # Verify text content
            with open(filepath) as f:
                content = f.read()
                assert "SAFETY TRACE REPORT" in content
                assert "test_study" in content
                # Check for gate type (with or without underscore)
                assert "LEGALITY CHECK" in content or "LEGALITY_CHECK" in content


class TestSafetyTraceHumanReadable:
    """Test safety trace human-readable string representation."""

    def test_str_representation_has_header(self):
        """Safety trace string has report header."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        str_repr = str(trace)
        assert "SAFETY TRACE REPORT" in str_repr
        assert "test_study" in str_repr
        assert "guarded" in str_repr.lower()

    def test_str_representation_includes_summary(self):
        """Safety trace string includes summary section."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_legality_check(is_legal=True, violations=[], warnings=[])
        trace.record_base_case_verification(is_valid=True, failure_message="")

        str_repr = str(trace)
        assert "SUMMARY" in str_repr
        assert "Total safety checks: 2" in str_repr
        # Check for passed count (with or without symbol)
        assert "Passed:  2" in str_repr or "Passed: 2" in str_repr

    def test_str_representation_includes_chronological_log(self):
        """Safety trace string includes chronological evaluation log."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_legality_check(is_legal=True, violations=[], warnings=[])
        trace.record_base_case_verification(is_valid=True, failure_message="")

        str_repr = str(trace)
        assert "CHRONOLOGICAL EVALUATION LOG" in str_repr
        # Check for gate types (with or without underscore)
        assert "LEGALITY CHECK" in str_repr or "LEGALITY_CHECK" in str_repr
        assert "BASE CASE VERIFICATION" in str_repr or "BASE_CASE_VERIFICATION" in str_repr

    def test_str_representation_shows_pass_fail_status(self):
        """Safety trace string shows pass/fail status symbols."""
        trace = SafetyTrace(
            study_name="test_study",
            safety_domain=SafetyDomain.GUARDED,
        )

        trace.record_legality_check(is_legal=True, violations=[], warnings=[])
        trace.record_base_case_verification(is_valid=False, failure_message="Failed")

        str_repr = str(trace)
        # Check for status symbols
        assert "✓" in str_repr  # Pass symbol
        assert "✗" in str_repr  # Fail symbol


class TestSafetyTraceIntegrationWithStudyExecution:
    """Test safety trace integration with Study execution."""

    def test_study_executor_creates_safety_trace(self, tmp_path):
        """StudyExecutor creates a SafetyTrace during initialization."""
        config = StudyConfig(
            name="test_study",
            base_case_name="base",
            snapshot_path=str(tmp_path / "snapshot"),
            pdk="nangate45",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
            ],
        )

        executor = StudyExecutor(
            config,
            artifacts_root=str(tmp_path / "artifacts"),
            telemetry_root=str(tmp_path / "telemetry"),
            skip_base_case_verification=True,
        )

        assert hasattr(executor, "safety_trace")
        assert isinstance(executor.safety_trace, SafetyTrace)
        assert executor.safety_trace.study_name == "test_study"
        assert executor.safety_trace.safety_domain == SafetyDomain.SANDBOX

    def test_study_execution_records_legality_check_in_trace(self, tmp_path):
        """Study execution records legality check in safety trace."""
        # Create a minimal snapshot directory
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()
        (snapshot_dir / "run_sta.tcl").write_text("# Empty STA script")

        config = StudyConfig(
            name="test_study",
            base_case_name="base",
            snapshot_path=str(snapshot_dir),
            pdk="nangate45",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=1,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
            ],
        )

        executor = StudyExecutor(
            config,
            artifacts_root=str(tmp_path / "artifacts"),
            telemetry_root=str(tmp_path / "telemetry"),
            skip_base_case_verification=True,
        )

        # Execute study (will record legality check)
        result = executor.execute()

        # Check that legality check was recorded
        assert len(executor.safety_trace.evaluations) > 0
        legality_checks = [
            e
            for e in executor.safety_trace.evaluations
            if e.gate_type == SafetyGateType.LEGALITY_CHECK
        ]
        assert len(legality_checks) == 1
        assert legality_checks[0].status == SafetyGateStatus.PASS

    def test_safety_trace_saved_to_artifacts_on_completion(self, tmp_path):
        """Safety trace is saved to artifacts directory on Study completion."""
        # Create a minimal snapshot directory
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()
        (snapshot_dir / "run_sta.tcl").write_text("# Empty STA script")

        config = StudyConfig(
            name="test_study",
            base_case_name="base",
            snapshot_path=str(snapshot_dir),
            pdk="nangate45",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=1,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
            ],
        )

        artifacts_root = tmp_path / "artifacts"
        executor = StudyExecutor(
            config,
            artifacts_root=str(artifacts_root),
            telemetry_root=str(tmp_path / "telemetry"),
            skip_base_case_verification=True,
        )

        # Execute study
        result = executor.execute()

        # Check that safety trace files exist
        trace_json = artifacts_root / "test_study" / "safety_trace.json"
        trace_txt = artifacts_root / "test_study" / "safety_trace.txt"

        assert trace_json.exists()
        assert trace_txt.exists()

        # Verify JSON content
        with open(trace_json) as f:
            data = json.load(f)
            assert data["study_name"] == "test_study"
            assert "evaluations" in data
            assert "summary" in data

    def test_safety_trace_saved_on_illegal_study(self, tmp_path):
        """Safety trace is saved even when Study is illegal."""
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        # Create illegal Study (GLOBAL_DISRUPTIVE not allowed in LOCKED domain)
        config = StudyConfig(
            name="illegal_study",
            base_case_name="base",
            snapshot_path=str(snapshot_dir),
            pdk="nangate45",
            safety_domain=SafetyDomain.LOCKED,
            stages=[
                StageConfig(
                    name="stage_0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=1,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE],  # Illegal!
                ),
            ],
        )

        artifacts_root = tmp_path / "artifacts"
        executor = StudyExecutor(
            config,
            artifacts_root=str(artifacts_root),
            telemetry_root=str(tmp_path / "telemetry"),
            skip_base_case_verification=True,
        )

        # Execute study (should be blocked)
        result = executor.execute()

        assert result.aborted is True
        assert "ILLEGAL" in result.abort_reason

        # Check that safety trace was saved
        trace_json = artifacts_root / "illegal_study" / "safety_trace.json"
        assert trace_json.exists()

        # Verify it contains failed legality check
        with open(trace_json) as f:
            data = json.load(f)
            assert len(data["evaluations"]) > 0
            # Should have a failed legality check
            failed_checks = [
                e for e in data["evaluations"] if e["status"] == "fail"
            ]
            assert len(failed_checks) > 0
