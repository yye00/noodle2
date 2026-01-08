"""Tests for safety model and legality checking."""

import pytest

from controller.safety import (
    LegalityChecker,
    SAFETY_POLICY,
    check_study_legality,
    generate_legality_report,
)
from controller.study import StudyConfig
from controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig


class TestSafetyPolicy:
    """Test safety policy definitions."""

    def test_sandbox_allows_all_eco_classes(self):
        """Test SANDBOX domain allows all ECO classes."""
        allowed = SAFETY_POLICY[SafetyDomain.SANDBOX]

        assert ECOClass.TOPOLOGY_NEUTRAL in allowed
        assert ECOClass.PLACEMENT_LOCAL in allowed
        assert ECOClass.ROUTING_AFFECTING in allowed
        assert ECOClass.GLOBAL_DISRUPTIVE in allowed

    def test_guarded_blocks_global_disruptive(self):
        """Test GUARDED domain blocks GLOBAL_DISRUPTIVE."""
        allowed = SAFETY_POLICY[SafetyDomain.GUARDED]

        assert ECOClass.TOPOLOGY_NEUTRAL in allowed
        assert ECOClass.PLACEMENT_LOCAL in allowed
        assert ECOClass.ROUTING_AFFECTING in allowed
        assert ECOClass.GLOBAL_DISRUPTIVE not in allowed

    def test_locked_only_allows_safe_classes(self):
        """Test LOCKED domain only allows conservative ECO classes."""
        allowed = SAFETY_POLICY[SafetyDomain.LOCKED]

        assert ECOClass.TOPOLOGY_NEUTRAL in allowed
        assert ECOClass.PLACEMENT_LOCAL in allowed
        assert ECOClass.ROUTING_AFFECTING not in allowed
        assert ECOClass.GLOBAL_DISRUPTIVE not in allowed


class TestLegalityChecker:
    """Test LegalityChecker for Study validation."""

    def test_legal_sandbox_study(self):
        """Test legal SANDBOX study with all ECO classes."""
        study = StudyConfig(
            name="test_sandbox",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="exploration",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                        ECOClass.GLOBAL_DISRUPTIVE,
                    ],
                ),
            ],
        )

        checker = LegalityChecker(study)
        result = checker.check_legality()

        assert result.is_legal
        assert result.violation_count == 0

    def test_legal_guarded_study(self):
        """Test legal GUARDED study without GLOBAL_DISRUPTIVE."""
        study = StudyConfig(
            name="test_guarded",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="refinement",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                        ECOClass.ROUTING_AFFECTING,
                    ],
                ),
            ],
        )

        checker = LegalityChecker(study)
        result = checker.check_legality()

        assert result.is_legal
        assert result.violation_count == 0

    def test_legal_locked_study(self):
        """Test legal LOCKED study with only safe ECO classes."""
        study = StudyConfig(
            name="test_locked",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="regression",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=1,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                    ],
                ),
            ],
        )

        checker = LegalityChecker(study)
        result = checker.check_legality()

        assert result.is_legal
        assert result.violation_count == 0

    def test_illegal_guarded_with_global_disruptive(self):
        """Test GUARDED study with GLOBAL_DISRUPTIVE is illegal."""
        study = StudyConfig(
            name="test_illegal_guarded",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="bad_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.GLOBAL_DISRUPTIVE,
                    ],
                ),
            ],
        )

        checker = LegalityChecker(study)
        result = checker.check_legality()

        assert not result.is_legal
        assert result.violation_count == 1
        assert result.violations[0].eco_class == ECOClass.GLOBAL_DISRUPTIVE
        assert result.violations[0].stage_index == 0

    def test_illegal_locked_with_routing_affecting(self):
        """Test LOCKED study with ROUTING_AFFECTING is illegal."""
        study = StudyConfig(
            name="test_illegal_locked",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="risky_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=1,
                    allowed_eco_classes=[
                        ECOClass.ROUTING_AFFECTING,
                    ],
                ),
            ],
        )

        checker = LegalityChecker(study)
        result = checker.check_legality()

        assert not result.is_legal
        assert result.violation_count == 1
        assert result.violations[0].eco_class == ECOClass.ROUTING_AFFECTING

    def test_multiple_violations_across_stages(self):
        """Test multiple violations across different stages."""
        study = StudyConfig(
            name="test_multi_violation",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.ROUTING_AFFECTING,
                    ],
                ),
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=1,
                    allowed_eco_classes=[
                        ECOClass.GLOBAL_DISRUPTIVE,
                    ],
                ),
            ],
        )

        checker = LegalityChecker(study)
        result = checker.check_legality()

        assert not result.is_legal
        assert result.violation_count == 2
        assert result.violations[0].stage_index == 0
        assert result.violations[1].stage_index == 1

    def test_get_allowed_eco_classes(self):
        """Test getting allowed ECO classes for safety domain."""
        study = StudyConfig(
            name="test",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[],
                ),
            ],
        )

        checker = LegalityChecker(study)
        allowed = checker.get_allowed_eco_classes()

        assert ECOClass.TOPOLOGY_NEUTRAL in allowed
        assert ECOClass.PLACEMENT_LOCAL in allowed
        assert ECOClass.ROUTING_AFFECTING in allowed
        assert ECOClass.GLOBAL_DISRUPTIVE not in allowed

    def test_warnings_for_global_disruptive_in_sandbox(self):
        """Test warnings are generated for risky SANDBOX configs."""
        study = StudyConfig(
            name="test_risky_sandbox",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="risky",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.GLOBAL_DISRUPTIVE,
                    ],
                ),
            ],
        )

        checker = LegalityChecker(study)
        result = checker.check_legality()

        assert result.is_legal  # Still legal, just risky
        assert len(result.warnings) > 0
        assert "GLOBAL_DISRUPTIVE" in result.warnings[0]


class TestRunLegalityReport:
    """Test Run Legality Report generation."""

    def test_generate_legal_report(self):
        """Test generating report for legal Study."""
        study = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=10,
                    survivor_count=3,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                    ],
                ),
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.PLACEMENT_LOCAL,
                    ],
                ),
            ],
        )

        report = generate_legality_report(study, timestamp="2026-01-07T12:00:00")

        assert report.study_name == "test_study"
        assert report.safety_domain == SafetyDomain.GUARDED
        assert report.is_legal
        assert report.stage_count == 2
        assert report.total_trial_budget == 15
        assert report.timestamp == "2026-01-07T12:00:00"

    def test_generate_illegal_report(self):
        """Test generating report for illegal Study."""
        study = StudyConfig(
            name="illegal_study",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="bad_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.GLOBAL_DISRUPTIVE,
                    ],
                ),
            ],
        )

        report = generate_legality_report(study)

        assert report.study_name == "illegal_study"
        assert not report.is_legal
        assert len(report.violations) == 1
        assert report.violations[0].eco_class == ECOClass.GLOBAL_DISRUPTIVE

    def test_report_str_formatting(self):
        """Test human-readable report formatting."""
        study = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                    ],
                ),
            ],
        )

        report = generate_legality_report(study)
        report_str = str(report)

        assert "RUN LEGALITY REPORT" in report_str
        assert "test_study" in report_str
        assert "sandbox" in report_str
        assert "LEGAL" in report_str
        assert "Stages: 1" in report_str
        assert "Total trial budget: 5" in report_str

    def test_report_with_violations_str(self):
        """Test report formatting with violations."""
        study = StudyConfig(
            name="illegal_study",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="bad_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.ROUTING_AFFECTING,
                    ],
                ),
            ],
        )

        report = generate_legality_report(study)
        report_str = str(report)

        assert "ILLEGAL" in report_str
        assert "BLOCKED" in report_str
        assert "routing_affecting" in report_str
        assert "Violations: 1" in report_str

    def test_report_to_dict(self):
        """Test report serialization to dict."""
        study = StudyConfig(
            name="test_study",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                    ],
                ),
            ],
        )

        report = generate_legality_report(study)
        report_dict = report.to_dict()

        assert report_dict["study_name"] == "test_study"
        assert report_dict["safety_domain"] == "guarded"
        assert report_dict["is_legal"] is True
        assert report_dict["stage_count"] == 1
        assert "topology_neutral" in report_dict["allowed_eco_classes"]


class TestCheckStudyLegality:
    """Test convenience function for checking legality."""

    def test_check_legal_study_no_exception(self):
        """Test legal study passes without exception."""
        study = StudyConfig(
            name="legal_study",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.TOPOLOGY_NEUTRAL,
                    ],
                ),
            ],
        )

        # Should not raise
        result = check_study_legality(study)
        assert result.is_legal

    def test_check_illegal_study_raises_exception(self):
        """Test illegal study raises ValueError."""
        study = StudyConfig(
            name="illegal_study",
            safety_domain=SafetyDomain.LOCKED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="bad_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.GLOBAL_DISRUPTIVE,
                    ],
                ),
            ],
        )

        with pytest.raises(ValueError, match="ILLEGAL"):
            check_study_legality(study)

    def test_check_illegal_study_error_message(self):
        """Test error message includes violation details."""
        study = StudyConfig(
            name="illegal_study",
            safety_domain=SafetyDomain.GUARDED,
            base_case_name="nangate45_base",
            pdk="Nangate45",
            snapshot_path="/path/to/snapshot",
            stages=[
                StageConfig(
                    name="bad_stage",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[
                        ECOClass.GLOBAL_DISRUPTIVE,
                    ],
                ),
            ],
        )

        with pytest.raises(ValueError) as exc_info:
            check_study_legality(study)

        error_msg = str(exc_info.value)
        assert "illegal_study" in error_msg
        assert "Stage 0" in error_msg
        assert "bad_stage" in error_msg
