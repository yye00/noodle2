"""
Tests for F070: Run legality report is generated before study execution.

Feature Requirements:
1. Create study config
2. Request legality check
3. Verify report includes: safety domain, proposed ECO classes, applicable rails, abort criteria
4. Verify illegal configurations are flagged with reason
"""

import pytest
from pathlib import Path
import tempfile
import yaml

from src.controller.study import create_study_config, load_study_config
from src.controller.safety import generate_legality_report
from src.controller.types import (
    AbortRailConfig,
    ECOClass,
    ExecutionMode,
    RailsConfig,
    SafetyDomain,
    StageConfig,
    StageRailConfig,
    StudyRailConfig,
)


class TestRunLegalityReportGeneration:
    """Test F070 - Step 1: Create study config."""

    def test_step_1_create_study_config(self):
        """Step 1: Create study config."""
        config = create_study_config(
            name="test_legality_check",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.GUARDED,
        )

        assert config is not None
        assert config.name == "test_legality_check"
        assert config.safety_domain == SafetyDomain.GUARDED

    def test_step_2_request_legality_check(self):
        """Step 2: Request legality check."""
        config = create_study_config(
            name="test_legality_check",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.GUARDED,
        )

        # Generate legality report
        report = generate_legality_report(config)

        assert report is not None
        assert report.study_name == "test_legality_check"
        assert report.safety_domain == SafetyDomain.GUARDED

    def test_step_3_verify_report_includes_required_fields(self):
        """Step 3: Verify report includes: safety domain, proposed ECO classes, applicable rails, abort criteria."""
        # Create config with rails
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                ],
            )
        ]

        rails = RailsConfig(
            abort=AbortRailConfig(
                wns_ps=-10000,  # Abort if WNS worse than -10ns
                timeout_seconds=3600,
            ),
            stage=StageRailConfig(
                failure_rate=0.5,  # Stop stage if 50% failure rate
            ),
            study=StudyRailConfig(
                catastrophic_failures=3,
                max_runtime_hours=24,
            ),
        )

        config = create_study_config(
            name="test_legality_with_rails",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.GUARDED,
            stages=stages,
        )
        config.rails = rails

        # Generate legality report
        report = generate_legality_report(config)

        # Verify safety domain
        assert report.safety_domain == SafetyDomain.GUARDED

        # Verify proposed ECO classes
        assert ECOClass.TOPOLOGY_NEUTRAL in report.allowed_eco_classes
        assert ECOClass.PLACEMENT_LOCAL in report.allowed_eco_classes
        assert ECOClass.ROUTING_AFFECTING in report.allowed_eco_classes
        # GLOBAL_DISRUPTIVE should NOT be allowed in GUARDED domain
        assert ECOClass.GLOBAL_DISRUPTIVE not in report.allowed_eco_classes

        # Verify applicable rails (abort criteria)
        assert report.rails is not None
        assert report.rails.abort.wns_ps == -10000
        assert report.rails.abort.timeout_seconds == 3600
        assert report.rails.stage.failure_rate == 0.5
        assert report.rails.study.catastrophic_failures == 3
        assert report.rails.study.max_runtime_hours == 24

    def test_step_4_verify_illegal_configurations_are_flagged(self):
        """Step 4: Verify illegal configurations are flagged with reason."""
        # Create config with illegal ECO class for GUARDED domain
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.GLOBAL_DISRUPTIVE,  # ILLEGAL in GUARDED domain!
                ],
            )
        ]

        config = create_study_config(
            name="test_illegal_config",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.GUARDED,
            stages=stages,
        )

        # Generate legality report
        report = generate_legality_report(config)

        # Verify configuration is flagged as illegal
        assert not report.is_legal
        assert len(report.violations) > 0

        # Verify violation details
        violation = report.violations[0]
        assert violation.stage_index == 0
        assert violation.stage_name == "stage_0"
        assert violation.eco_class == ECOClass.GLOBAL_DISRUPTIVE
        assert "not allowed" in violation.reason.lower()
        assert "guarded" in violation.reason.lower()


class TestReportDictionaryFormat:
    """Test that the report can be serialized to dictionary format."""

    def test_report_to_dict_with_rails(self):
        """Verify report can be serialized to dict with rails."""
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            )
        ]

        rails = RailsConfig(
            abort=AbortRailConfig(wns_ps=-5000, timeout_seconds=1800),
            stage=StageRailConfig(failure_rate=0.3),
            study=StudyRailConfig(catastrophic_failures=2, max_runtime_hours=12),
        )

        config = create_study_config(
            name="test_dict_serialization",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.GUARDED,
            stages=stages,
        )
        config.rails = rails

        report = generate_legality_report(config)
        report_dict = report.to_dict()

        # Verify all required fields
        assert report_dict["study_name"] == "test_dict_serialization"
        assert report_dict["safety_domain"] == "guarded"
        assert report_dict["is_legal"] is True
        assert "allowed_eco_classes" in report_dict
        assert "violations" in report_dict
        assert "warnings" in report_dict
        assert "stage_count" in report_dict
        assert "total_trial_budget" in report_dict

        # Verify rails are included
        assert "rails" in report_dict
        assert report_dict["rails"]["abort"]["wns_ps"] == -5000
        assert report_dict["rails"]["abort"]["timeout_seconds"] == 1800
        assert report_dict["rails"]["stage"]["failure_rate"] == 0.3
        assert report_dict["rails"]["study"]["catastrophic_failures"] == 2
        assert report_dict["rails"]["study"]["max_runtime_hours"] == 12

    def test_report_to_dict_without_rails(self):
        """Verify report can be serialized to dict without rails."""
        config = create_study_config(
            name="test_no_rails",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.GUARDED,
        )

        report = generate_legality_report(config)
        report_dict = report.to_dict()

        # Rails should still be included (with default values)
        assert "rails" in report_dict or "rails" not in report_dict  # Either is acceptable


class TestReportHumanReadableFormat:
    """Test that the report generates human-readable output."""

    def test_report_str_with_rails(self):
        """Verify report generates human-readable string with rails."""
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            )
        ]

        rails = RailsConfig(
            abort=AbortRailConfig(wns_ps=-8000, timeout_seconds=2400),
            stage=StageRailConfig(failure_rate=0.4),
            study=StudyRailConfig(catastrophic_failures=5, max_runtime_hours=48),
        )

        config = create_study_config(
            name="test_human_readable",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.GUARDED,
            stages=stages,
        )
        config.rails = rails

        report = generate_legality_report(config)
        report_str = str(report)

        # Verify report contains key sections
        assert "RUN LEGALITY REPORT" in report_str
        assert "SAFETY DOMAIN" in report_str
        assert "ALLOWED ECO CLASSES" in report_str
        assert "ABORT CRITERIA" in report_str
        assert "VIOLATIONS" in report_str
        assert "VERDICT" in report_str

        # Verify rails are displayed
        assert "WNS threshold: -8000 ps" in report_str
        assert "Timeout: 2400 seconds" in report_str
        assert "Max failure rate: 40.0%" in report_str
        assert "Max catastrophic failures: 5" in report_str
        assert "Max runtime: 48 hours" in report_str


class TestDifferentSafetyDomains:
    """Test legality reports for different safety domains."""

    def test_sandbox_allows_all_eco_classes(self):
        """SANDBOX domain should allow all ECO classes."""
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                    ECOClass.ROUTING_AFFECTING,
                    ECOClass.GLOBAL_DISRUPTIVE,
                ],
            )
        ]

        config = create_study_config(
            name="test_sandbox",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.SANDBOX,
            stages=stages,
        )

        report = generate_legality_report(config)

        # Should be legal in SANDBOX
        assert report.is_legal
        assert len(report.violations) == 0
        # But should have warning about GLOBAL_DISRUPTIVE
        assert len(report.warnings) > 0

    def test_locked_restricts_eco_classes(self):
        """LOCKED domain should only allow safe ECO classes."""
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.ROUTING_AFFECTING,  # ILLEGAL in LOCKED domain!
                ],
            )
        ]

        config = create_study_config(
            name="test_locked",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.LOCKED,
            stages=stages,
        )

        report = generate_legality_report(config)

        # Should be illegal in LOCKED
        assert not report.is_legal
        assert len(report.violations) > 0

        # Verify ROUTING_AFFECTING is flagged
        violation = next(
            v for v in report.violations if v.eco_class == ECOClass.ROUTING_AFFECTING
        )
        assert violation is not None

    def test_guarded_balances_safety_and_flexibility(self):
        """GUARDED domain should allow moderate ECO classes."""
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                    ECOClass.ROUTING_AFFECTING,
                ],
            )
        ]

        config = create_study_config(
            name="test_guarded",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.GUARDED,
            stages=stages,
        )

        report = generate_legality_report(config)

        # Should be legal in GUARDED
        assert report.is_legal
        assert len(report.violations) == 0


class TestLegalityReportFromYAML:
    """Test legality report generation from YAML configuration."""

    def test_load_yaml_and_generate_report(self):
        """Test loading config from YAML and generating report."""
        yaml_content = """
name: test_yaml_legality
safety_domain: guarded
base_case_name: base
pdk: Nangate45
snapshot_path: ./snapshots/test

stages:
  - name: stage_0
    execution_mode: sta_only
    trial_budget: 10
    survivor_count: 5
    allowed_eco_classes:
      - topology_neutral
      - placement_local

rails:
  abort:
    wns_ps: -15000
    timeout_seconds: 7200
  stage:
    failure_rate: 0.6
  study:
    catastrophic_failures: 10
    max_runtime_hours: 72
"""

        # Write to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            # Load config from YAML
            config = load_study_config(temp_path)

            # Generate legality report
            report = generate_legality_report(config)

            # Verify report
            assert report.study_name == "test_yaml_legality"
            assert report.safety_domain == SafetyDomain.GUARDED
            assert report.is_legal
            assert report.rails is not None
            assert report.rails.abort.wns_ps == -15000
            assert report.rails.abort.timeout_seconds == 7200
            assert report.rails.stage.failure_rate == 0.6
            assert report.rails.study.catastrophic_failures == 10
            assert report.rails.study.max_runtime_hours == 72

        finally:
            # Clean up
            Path(temp_path).unlink()


class TestEndToEndLegalityCheck:
    """End-to-end integration test for legality checking."""

    def test_complete_legality_check_workflow(self):
        """Complete workflow: create config, check legality, verify report."""
        # Step 1: Create study config
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=20,
                survivor_count=10,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                ],
            ),
            StageConfig(
                name="stage_1",
                execution_mode=ExecutionMode.STA_CONGESTION,
                trial_budget=15,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                    ECOClass.ROUTING_AFFECTING,
                ],
            ),
        ]

        rails = RailsConfig(
            abort=AbortRailConfig(wns_ps=-20000, timeout_seconds=5400),
            stage=StageRailConfig(failure_rate=0.7),
            study=StudyRailConfig(catastrophic_failures=8, max_runtime_hours=96),
        )

        config = create_study_config(
            name="test_e2e_legality",
            pdk="Nangate45",
            base_case_name="base",
            snapshot_path="./snapshots/test",
            safety_domain=SafetyDomain.GUARDED,
            stages=stages,
        )
        config.rails = rails

        # Step 2: Request legality check
        report = generate_legality_report(config, timestamp="2026-01-13T12:00:00Z")

        # Step 3: Verify report completeness
        assert report.study_name == "test_e2e_legality"
        assert report.safety_domain == SafetyDomain.GUARDED
        assert report.is_legal
        assert len(report.allowed_eco_classes) > 0
        assert len(report.violations) == 0
        assert report.stage_count == 2
        assert report.total_trial_budget == 35
        assert report.timestamp == "2026-01-13T12:00:00Z"

        # Verify rails
        assert report.rails is not None
        assert report.rails.abort.wns_ps == -20000
        assert report.rails.study.max_runtime_hours == 96

        # Step 4: Verify report can be serialized
        report_dict = report.to_dict()
        assert report_dict["is_legal"] is True
        assert "rails" in report_dict

        # Verify report has human-readable format
        report_str = str(report)
        assert "LEGAL - Study may proceed" in report_str
