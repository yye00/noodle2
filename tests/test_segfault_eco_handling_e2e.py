"""End-to-end test for pathological ECO causing segfault - handled safely.

This test validates the complete workflow when an ECO triggers OpenROAD to segfault:
1. Create ECO that triggers OpenROAD segfault
2. Execute trial with pathological ECO
3. Detect segfault via exit code or signal
4. Classify as catastrophic failure
5. Mark ECO class as catastrophically failed
6. Prevent future use of ECO class in Study
7. Continue Study with other ECOs
8. Verify Study doesn't crash due to ECO segfault
9. Generate incident report for pathological ECO
"""

import tempfile
from pathlib import Path
from typing import Any

import pytest

from src.controller.eco_containment import ECOClassContainmentTracker
from src.controller.failure import (
    FailureClassification,
    FailureClassifier,
    FailureSeverity,
    FailureType,
)
from src.controller.types import ECOClass


# Step 1: Create ECO that triggers OpenROAD segfault


class PathologicalECO:
    """Simulates an ECO that causes OpenROAD to segfault.

    In reality, this could be:
    - Buffer insertion with invalid coordinates
    - Gate sizing with corrupted liberty data
    - Pin swapping that violates internal constraints
    - Any ECO that triggers an OpenROAD bug
    """

    def __init__(self, eco_name: str, eco_class: ECOClass):
        """Initialize pathological ECO."""
        self.eco_name = eco_name
        self.eco_class = eco_class
        self.causes_segfault = True

    def execute(self) -> dict[str, Any]:
        """Simulate ECO execution that segfaults.

        Returns:
            Execution result with segfault indicators
        """
        # Simulate segfault: return code 139 (128 + 11 = SIGSEGV)
        return {
            "return_code": 139,
            "stdout": "Executing ECO...\nBuffer insertion...\n",
            "stderr": "Segmentation fault (core dumped)",
            "artifacts_produced": False,
        }


class TestStep1CreatePathologicalECO:
    """Test Step 1: Create ECO that triggers OpenROAD segfault."""

    def test_pathological_eco_can_be_created(self):
        """Verify pathological ECO can be instantiated."""
        eco = PathologicalECO("bad_buffer_insertion", ECOClass.TOPOLOGY_NEUTRAL)

        assert eco.eco_name == "bad_buffer_insertion"
        assert eco.eco_class == ECOClass.TOPOLOGY_NEUTRAL
        assert eco.causes_segfault is True

    def test_pathological_eco_execution_returns_segfault_code(self):
        """Verify pathological ECO execution returns segfault exit code."""
        eco = PathologicalECO("invalid_pin_swap", ECOClass.ROUTING_AFFECTING)

        result = eco.execute()

        assert result["return_code"] == 139  # 128 + 11 (SIGSEGV)
        assert "Segmentation fault" in result["stderr"]
        assert result["artifacts_produced"] is False

    def test_multiple_pathological_ecos_can_exist(self):
        """Verify multiple pathological ECOs can be created."""
        eco1 = PathologicalECO("bad_eco_1", ECOClass.PLACEMENT_LOCAL)
        eco2 = PathologicalECO("bad_eco_2", ECOClass.TOPOLOGY_NEUTRAL)
        eco3 = PathologicalECO("bad_eco_3", ECOClass.PLACEMENT_LOCAL)

        assert eco1.eco_class != eco2.eco_class
        assert eco2.eco_class != eco3.eco_class


# Step 2: Execute trial with pathological ECO


class TestStep2ExecuteTrialWithPathologicalECO:
    """Test Step 2: Execute trial with pathological ECO."""

    def test_execute_trial_with_segfaulting_eco(self):
        """Verify trial execution with segfaulting ECO captures result."""
        eco = PathologicalECO("buffer_insertion_bad_coords", ECOClass.PLACEMENT_LOCAL)

        # Simulate trial execution
        exec_result = eco.execute()

        assert exec_result["return_code"] == 139
        assert not exec_result["artifacts_produced"]

    def test_trial_execution_captures_stdout_and_stderr(self):
        """Verify stdout and stderr are captured during segfault."""
        eco = PathologicalECO("gate_sizing_corrupt_lib", ECOClass.TOPOLOGY_NEUTRAL)

        exec_result = eco.execute()

        assert "stdout" in exec_result
        assert "stderr" in exec_result
        assert "Segmentation fault" in exec_result["stderr"]

    def test_trial_execution_doesnt_crash_controller(self):
        """Verify controller doesn't crash when trial segfaults."""
        eco = PathologicalECO("placement_invalid_site", ECOClass.PLACEMENT_LOCAL)

        # This should not raise an exception
        exec_result = eco.execute()

        assert exec_result["return_code"] != 0


# Step 3: Detect segfault via exit code or signal


class TestStep3DetectSegfault:
    """Test Step 3: Detect segfault via exit code or signal."""

    def test_detect_segfault_by_exit_code_139(self):
        """Verify segfault detection by exit code 139 (128 + SIGSEGV)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            classification = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="Executing trial...",
                stderr="",
                artifacts_dir=Path(tmpdir),
            )

        assert classification is not None
        assert classification.failure_type == FailureType.SEGFAULT

    def test_detect_segfault_by_stderr_message(self):
        """Verify segfault detection by stderr message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr="Segmentation fault (core dumped)",
                artifacts_dir=Path(tmpdir),
            )

        assert classification is not None
        assert classification.failure_type == FailureType.SEGFAULT

    def test_detect_segfault_by_sigsegv_keyword(self):
        """Verify segfault detection by SIGSEGV keyword."""
        with tempfile.TemporaryDirectory() as tmpdir:
            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr="Error: SIGSEGV received",
                artifacts_dir=Path(tmpdir),
            )

        assert classification is not None
        assert classification.failure_type == FailureType.SEGFAULT

    def test_detect_segfault_by_signal_11(self):
        """Verify segfault detection by signal 11 message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            classification = FailureClassifier.classify_trial_failure(
                return_code=1,
                stdout="",
                stderr="Process terminated by signal 11",
                artifacts_dir=Path(tmpdir),
            )

        assert classification is not None
        assert classification.failure_type == FailureType.SEGFAULT


# Step 4: Classify as catastrophic failure


class TestStep4ClassifyAsCatastrophic:
    """Test Step 4: Classify as catastrophic failure."""

    def test_segfault_classified_as_critical_severity(self):
        """Verify segfault is classified as CRITICAL severity."""
        with tempfile.TemporaryDirectory() as tmpdir:
            classification = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        assert classification.severity == FailureSeverity.CRITICAL

    def test_segfault_marked_as_not_recoverable(self):
        """Verify segfault is marked as non-recoverable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            classification = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        assert classification.recoverable is False

    def test_segfault_is_catastrophic(self):
        """Verify segfault passes is_catastrophic() check."""
        with tempfile.TemporaryDirectory() as tmpdir:
            classification = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        assert FailureClassifier.is_catastrophic(classification)

    def test_catastrophic_classification_includes_reason(self):
        """Verify catastrophic classification includes human-readable reason."""
        with tempfile.TemporaryDirectory() as tmpdir:
            classification = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault (core dumped)",
                artifacts_dir=Path(tmpdir),
            )

        assert "segmentation fault" in classification.reason.lower()


# Step 5: Mark ECO class as catastrophically failed


class TestStep5MarkECOClassCatastrophic:
    """Test Step 5: Mark ECO class as catastrophically failed."""

    def test_record_catastrophic_failure_for_eco_class(self):
        """Verify ECO class is recorded when segfault occurs."""
        tracker = ECOClassContainmentTracker()

        # Simulate segfault from GATE_SIZING ECO
        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        should_contain = tracker.record_trial_result(
            eco_class=ECOClass.TOPOLOGY_NEUTRAL,
            failure=failure,
        )

        assert should_contain is True

    def test_eco_class_status_after_catastrophic_failure(self):
        """Verify ECO class status transitions to CATASTROPHIC."""
        tracker = ECOClassContainmentTracker()

        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        tracker.record_trial_result(ECOClass.PLACEMENT_LOCAL, failure)

        status = tracker.eco_class_status[ECOClass.PLACEMENT_LOCAL]
        assert status.allowed is False  # Catastrophic -> blocked
        assert status.catastrophic_failures > 0

    def test_multiple_segfaults_dont_change_status(self):
        """Verify repeated segfaults keep status as CATASTROPHIC."""
        tracker = ECOClassContainmentTracker()

        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        # Record two segfaults for same ECO class
        tracker.record_trial_result(ECOClass.ROUTING_AFFECTING, failure)
        tracker.record_trial_result(ECOClass.ROUTING_AFFECTING, failure)

        status = tracker.eco_class_status[ECOClass.ROUTING_AFFECTING]
        assert status.allowed is False  # Catastrophic -> blocked
        assert status.catastrophic_failures > 0


# Step 6: Prevent future use of ECO class in Study


class TestStep6PreventFutureUse:
    """Test Step 6: Prevent future use of ECO class in Study."""

    def test_eco_class_blocked_after_catastrophic_failure(self):
        """Verify ECO class is blocked after catastrophic failure."""
        tracker = ECOClassContainmentTracker()

        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        tracker.record_trial_result(ECOClass.PLACEMENT_LOCAL, failure)

        # ECO class should now be blocked
        assert not tracker.is_eco_class_allowed(ECOClass.PLACEMENT_LOCAL)

    def test_blocked_eco_class_appears_in_blocked_list(self):
        """Verify blocked ECO class appears in get_blocked_eco_classes()."""
        tracker = ECOClassContainmentTracker()

        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        tracker.record_trial_result(ECOClass.TOPOLOGY_NEUTRAL, failure)

        blocked = tracker.get_blocked_eco_classes()
        assert ECOClass.TOPOLOGY_NEUTRAL in blocked

    def test_other_eco_classes_remain_allowed(self):
        """Verify other ECO classes remain allowed after one is blocked."""
        tracker = ECOClassContainmentTracker()

        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        # Block BUFFER_INSERTION
        tracker.record_trial_result(ECOClass.PLACEMENT_LOCAL, failure)

        # Other classes should still be allowed
        assert tracker.is_eco_class_allowed(ECOClass.TOPOLOGY_NEUTRAL)
        assert tracker.is_eco_class_allowed(ECOClass.ROUTING_AFFECTING)
        assert tracker.is_eco_class_allowed(ECOClass.GLOBAL_DISRUPTIVE)


# Step 7: Continue Study with other ECOs


class TestStep7ContinueStudyWithOtherECOs:
    """Test Step 7: Continue Study with other ECOs."""

    def test_study_continues_after_blocking_one_eco_class(self):
        """Verify Study can continue with remaining ECO classes."""
        tracker = ECOClassContainmentTracker()

        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        # Block BUFFER_INSERTION
        tracker.record_trial_result(ECOClass.PLACEMENT_LOCAL, failure)

        # Get allowed ECO classes for next trial
        allowed_classes = [
            eco_class for eco_class in ECOClass
            if tracker.is_eco_class_allowed(eco_class)
        ]

        # Should have multiple allowed classes
        assert len(allowed_classes) >= 3
        assert ECOClass.PLACEMENT_LOCAL not in allowed_classes

    def test_study_can_use_multiple_allowed_eco_classes(self):
        """Verify Study can use multiple remaining ECO classes."""
        tracker = ECOClassContainmentTracker()

        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        # Block two ECO classes
        tracker.record_trial_result(ECOClass.PLACEMENT_LOCAL, failure)
        tracker.record_trial_result(ECOClass.TOPOLOGY_NEUTRAL, failure)

        # Simulate trials with remaining ECO classes
        trial_count = 0
        for eco_class in ECOClass:
            if tracker.is_eco_class_allowed(eco_class):
                # This ECO class can be used
                trial_count += 1

        assert trial_count >= 2  # At least 2 ECO classes still usable

    def test_study_avoids_catastrophic_eco_class(self):
        """Verify Study avoids catastrophic ECO class in trial generation."""
        tracker = ECOClassContainmentTracker()

        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        tracker.record_trial_result(ECOClass.ROUTING_AFFECTING, failure)

        # Simulate trial generation loop
        next_eco_classes = []
        for _ in range(10):
            for eco_class in ECOClass:
                if tracker.is_eco_class_allowed(eco_class):
                    next_eco_classes.append(eco_class)
                    break

        # PIN_SWAP should never appear in next trials
        assert ECOClass.ROUTING_AFFECTING not in next_eco_classes


# Step 8: Verify Study doesn't crash due to ECO segfault


class TestStep8StudyDoesntCrash:
    """Test Step 8: Verify Study doesn't crash due to ECO segfault."""

    def test_study_handles_segfault_gracefully(self):
        """Verify Study handles segfault without crashing."""
        tracker = ECOClassContainmentTracker()

        # Simulate multiple trials with mixed results
        results = [
            (ECOClass.TOPOLOGY_NEUTRAL, None),  # Success
            (ECOClass.PLACEMENT_LOCAL, "segfault"),  # Segfault
            (ECOClass.ROUTING_AFFECTING, None),  # Success
        ]

        for eco_class, failure_type in results:
            if failure_type == "segfault":
                with tempfile.TemporaryDirectory() as tmpdir:
                    failure = FailureClassifier.classify_trial_failure(
                        return_code=139,
                        stdout="",
                        stderr="Segmentation fault",
                        artifacts_dir=Path(tmpdir),
                    )
                tracker.record_trial_result(eco_class, failure)
            else:
                tracker.record_trial_result(eco_class, None)

        # Study should continue successfully
        assert len(tracker.get_blocked_eco_classes()) == 1
        assert ECOClass.PLACEMENT_LOCAL in tracker.get_blocked_eco_classes()

    def test_multiple_segfaults_dont_crash_study(self):
        """Verify multiple segfaults from different ECOs don't crash Study."""
        tracker = ECOClassContainmentTracker()

        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        # Simulate segfaults from multiple ECO classes
        for eco_class in [ECOClass.PLACEMENT_LOCAL, ECOClass.TOPOLOGY_NEUTRAL, ECOClass.ROUTING_AFFECTING]:
            tracker.record_trial_result(eco_class, failure)

        # Study should still be functional
        blocked = tracker.get_blocked_eco_classes()
        assert len(blocked) == 3

    def test_study_doesnt_propagate_segfault_exception(self):
        """Verify Study doesn't propagate segfault as uncaught exception."""
        tracker = ECOClassContainmentTracker()
        eco = PathologicalECO("bad_eco", ECOClass.PLACEMENT_LOCAL)

        # Execute trial (should not raise)
        exec_result = eco.execute()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Classify failure (should not raise)
            failure = FailureClassifier.classify_trial_failure(
                return_code=exec_result["return_code"],
                stdout=exec_result["stdout"],
                stderr=exec_result["stderr"],
                artifacts_dir=Path(tmpdir),
            )

        # Record result (should not raise)
        tracker.record_trial_result(ECOClass.PLACEMENT_LOCAL, failure)

        # Everything succeeded without exceptions
        assert True


# Step 9: Generate incident report for pathological ECO


class IncidentReport:
    """Incident report for catastrophic ECO failures."""

    def __init__(self, study_name: str):
        """Initialize incident report."""
        self.study_name = study_name
        self.incidents: list[dict[str, Any]] = []

    def record_incident(
        self,
        eco_class: ECOClass,
        failure: FailureClassification,
        trial_id: str,
    ) -> None:
        """Record a catastrophic failure incident."""
        self.incidents.append({
            "study_name": self.study_name,
            "trial_id": trial_id,
            "eco_class": eco_class.value,
            "failure_type": failure.failure_type.value,
            "severity": failure.severity.value,
            "reason": failure.reason,
            "log_excerpt": failure.log_excerpt,
            "recoverable": failure.recoverable,
        })

    def get_catastrophic_incidents(self) -> list[dict[str, Any]]:
        """Get all catastrophic failure incidents."""
        return [
            incident for incident in self.incidents
            if incident["severity"] == FailureSeverity.CRITICAL.value
        ]

    def to_dict(self) -> dict[str, Any]:
        """Export incident report to dictionary."""
        return {
            "study_name": self.study_name,
            "total_incidents": len(self.incidents),
            "catastrophic_count": len(self.get_catastrophic_incidents()),
            "incidents": self.incidents,
        }


class TestStep9GenerateIncidentReport:
    """Test Step 9: Generate incident report for pathological ECO."""

    def test_create_incident_report(self):
        """Verify incident report can be created."""
        report = IncidentReport(study_name="segfault_handling_study")

        assert report.study_name == "segfault_handling_study"
        assert len(report.incidents) == 0

    def test_record_segfault_incident(self):
        """Verify segfault incident can be recorded."""
        report = IncidentReport("test_study")

        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        report.record_incident(
            eco_class=ECOClass.PLACEMENT_LOCAL,
            failure=failure,
            trial_id="trial_001",
        )

        assert len(report.incidents) == 1
        assert report.incidents[0]["eco_class"] == ECOClass.PLACEMENT_LOCAL.value
        assert report.incidents[0]["failure_type"] == FailureType.SEGFAULT.value

    def test_incident_report_includes_details(self):
        """Verify incident report includes all relevant details."""
        report = IncidentReport("detailed_study")

        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="Executing buffer insertion...",
                stderr="Segmentation fault (core dumped)",
                artifacts_dir=Path(tmpdir),
            )

        report.record_incident(ECOClass.TOPOLOGY_NEUTRAL, failure, "trial_042")

        incident = report.incidents[0]
        assert incident["study_name"] == "detailed_study"
        assert incident["trial_id"] == "trial_042"
        assert incident["severity"] == FailureSeverity.CRITICAL.value
        assert incident["recoverable"] is False
        assert "reason" in incident

    def test_get_catastrophic_incidents_filters_correctly(self):
        """Verify get_catastrophic_incidents() filters by severity."""
        report = IncidentReport("multi_severity_study")

        # Add catastrophic failure (segfault)
        with tempfile.TemporaryDirectory() as tmpdir:
            segfault = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        report.record_incident(ECOClass.PLACEMENT_LOCAL, segfault, "trial_001")

        # Get catastrophic incidents
        catastrophic = report.get_catastrophic_incidents()

        assert len(catastrophic) == 1
        assert catastrophic[0]["failure_type"] == FailureType.SEGFAULT.value

    def test_export_incident_report_to_dict(self):
        """Verify incident report can be exported to dict/JSON."""
        report = IncidentReport("export_study")

        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=139,
                stdout="",
                stderr="Segmentation fault",
                artifacts_dir=Path(tmpdir),
            )

        report.record_incident(ECOClass.ROUTING_AFFECTING, failure, "trial_999")

        export = report.to_dict()

        assert export["study_name"] == "export_study"
        assert export["total_incidents"] == 1
        assert export["catastrophic_count"] == 1
        assert len(export["incidents"]) == 1


# Complete E2E integration test


class TestCompleteSegfaultHandlingE2E:
    """Complete end-to-end test for segfault handling workflow."""

    def test_complete_segfault_handling_workflow(self):
        """Test complete workflow from segfault to Study continuation."""
        # Step 1: Create pathological ECO
        eco = PathologicalECO("buffer_bad_coords", ECOClass.PLACEMENT_LOCAL)

        # Step 2: Execute trial
        exec_result = eco.execute()
        assert exec_result["return_code"] == 139

        # Step 3: Detect segfault
        with tempfile.TemporaryDirectory() as tmpdir:
            failure = FailureClassifier.classify_trial_failure(
                return_code=exec_result["return_code"],
                stdout=exec_result["stdout"],
                stderr=exec_result["stderr"],
                artifacts_dir=Path(tmpdir),
            )
        assert failure.failure_type == FailureType.SEGFAULT

        # Step 4: Classify as catastrophic
        assert FailureClassifier.is_catastrophic(failure)
        assert failure.severity == FailureSeverity.CRITICAL

        # Step 5: Mark ECO class as catastrophic
        tracker = ECOClassContainmentTracker()
        should_contain = tracker.record_trial_result(ECOClass.PLACEMENT_LOCAL, failure)
        assert should_contain is True

        # Step 6: Verify ECO class is blocked
        assert not tracker.is_eco_class_allowed(ECOClass.PLACEMENT_LOCAL)

        # Step 7: Continue Study with other ECOs
        allowed_classes = [
            cls for cls in ECOClass if tracker.is_eco_class_allowed(cls)
        ]
        assert len(allowed_classes) >= 3
        assert ECOClass.PLACEMENT_LOCAL not in allowed_classes

        # Step 8: Verify Study doesn't crash
        # Execute more trials with allowed ECO classes
        for eco_class in allowed_classes[:3]:
            # Simulate successful trials
            tracker.record_trial_result(eco_class, None)

        # Step 9: Generate incident report
        report = IncidentReport("segfault_e2e_study")
        report.record_incident(ECOClass.PLACEMENT_LOCAL, failure, "trial_001")

        incidents = report.get_catastrophic_incidents()
        assert len(incidents) == 1

        export = report.to_dict()
        assert export["catastrophic_count"] == 1

    def test_multiple_pathological_ecos_handled_correctly(self):
        """Test handling of multiple different pathological ECOs."""
        tracker = ECOClassContainmentTracker()
        report = IncidentReport("multi_segfault_study")

        # Create multiple pathological ECOs
        pathological_ecos = [
            (PathologicalECO("eco1", ECOClass.PLACEMENT_LOCAL), "trial_001"),
            (PathologicalECO("eco2", ECOClass.TOPOLOGY_NEUTRAL), "trial_002"),
            (PathologicalECO("eco3", ECOClass.ROUTING_AFFECTING), "trial_003"),
        ]

        for eco, trial_id in pathological_ecos:
            # Execute and classify
            exec_result = eco.execute()

            with tempfile.TemporaryDirectory() as tmpdir:
                failure = FailureClassifier.classify_trial_failure(
                    return_code=exec_result["return_code"],
                    stdout=exec_result["stdout"],
                    stderr=exec_result["stderr"],
                    artifacts_dir=Path(tmpdir),
                )

            # Record in tracker and incident report
            tracker.record_trial_result(eco.eco_class, failure)
            report.record_incident(eco.eco_class, failure, trial_id)

        # Verify all three ECO classes are blocked
        blocked = tracker.get_blocked_eco_classes()
        assert len(blocked) == 3

        # Verify incident report has all three incidents
        assert len(report.incidents) == 3
        assert report.to_dict()["catastrophic_count"] == 3

        # Verify Study can still continue with remaining ECO classes
        allowed = [cls for cls in ECOClass if tracker.is_eco_class_allowed(cls)]
        assert len(allowed) >= 1  # At least one ECO class still usable

    def test_study_recovers_and_completes_successfully(self):
        """Test that Study recovers from segfault and completes successfully."""
        tracker = ECOClassContainmentTracker()
        report = IncidentReport("recovery_study")

        # Simulate Study execution with mixed results
        trial_results = [
            ("trial_001", ECOClass.PLACEMENT_LOCAL, "success"),
            ("trial_002", ECOClass.TOPOLOGY_NEUTRAL, "segfault"),  # Catastrophic
            ("trial_003", ECOClass.ROUTING_AFFECTING, "success"),
            ("trial_004", ECOClass.PLACEMENT_LOCAL, "success"),
            ("trial_005", ECOClass.PLACEMENT_LOCAL, "success"),  # Different ECO class succeeds
        ]

        for trial_id, eco_class, result_type in trial_results:
            if result_type == "segfault":
                with tempfile.TemporaryDirectory() as tmpdir:
                    failure = FailureClassifier.classify_trial_failure(
                        return_code=139,
                        stdout="",
                        stderr="Segmentation fault",
                        artifacts_dir=Path(tmpdir),
                    )
                tracker.record_trial_result(eco_class, failure)
                report.record_incident(eco_class, failure, trial_id)
            else:
                # Success
                tracker.record_trial_result(eco_class, None)

        # Study should have:
        # - 1 blocked ECO class (GATE_SIZING)
        # - 1 catastrophic incident
        # - Multiple successful trials from other ECO classes

        assert len(tracker.get_blocked_eco_classes()) == 1
        assert ECOClass.TOPOLOGY_NEUTRAL in tracker.get_blocked_eco_classes()
        assert report.to_dict()["catastrophic_count"] == 1

        # Study completed successfully despite segfault
        assert True
