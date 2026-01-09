"""
End-to-end tests for safety domain enforcement across all three domains.

Tests comprehensive safety domain behavior comparing sandbox, guarded, and locked
domains with identical Study configurations to verify proper enforcement.
"""

import json
import pytest
from pathlib import Path
from typing import Any

from src.controller.safety import (
    SAFETY_POLICY,
    LegalityChecker,
    generate_legality_report,
)
from src.controller.study import create_study_config
from src.controller.types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
    StageConfig,
    StudyConfig,
)


class TestSafetyDomainE2EComparison:
    """Compare identical Studies across all three safety domains."""

    def create_base_stages(self) -> list[StageConfig]:
        """Create a standard set of stages for testing."""
        return [
            StageConfig(
                name="stage_0_exploration",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                ],
            ),
            StageConfig(
                name="stage_1_refinement",
                execution_mode=ExecutionMode.STA_CONGESTION,
                trial_budget=10,
                survivor_count=3,
                allowed_eco_classes=[
                    ECOClass.ROUTING_AFFECTING,
                ],
            ),
        ]

    def create_aggressive_stages(self) -> list[StageConfig]:
        """Create stages with all ECO classes for testing."""
        return [
            StageConfig(
                name="aggressive_exploration",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=20,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                    ECOClass.ROUTING_AFFECTING,
                    ECOClass.GLOBAL_DISRUPTIVE,
                ],
            ),
        ]

    def test_create_identical_study_in_sandbox(self):
        """Step 1: Create identical Study in 'sandbox' safety domain."""
        stages = self.create_base_stages()
        config = create_study_config(
            name="safety_domain_e2e_sandbox",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.SANDBOX,
            stages=stages,
        )

        assert config.safety_domain == SafetyDomain.SANDBOX
        assert len(config.stages) == 2
        config.validate()

    def test_sandbox_permits_all_eco_classes(self):
        """Step 2: Verify all ECO classes are permitted in sandbox."""
        allowed = SAFETY_POLICY[SafetyDomain.SANDBOX]

        # All 4 ECO classes should be allowed
        assert ECOClass.TOPOLOGY_NEUTRAL in allowed
        assert ECOClass.PLACEMENT_LOCAL in allowed
        assert ECOClass.ROUTING_AFFECTING in allowed
        assert ECOClass.GLOBAL_DISRUPTIVE in allowed
        assert len(allowed) == 4

    def test_sandbox_abort_sensitivity_relaxed(self):
        """Step 3: Verify abort sensitivity is relaxed in sandbox."""
        # In sandbox, we can use aggressive abort thresholds or disable them entirely
        stage = StageConfig(
            name="relaxed_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE],
            abort_threshold_wns_ps=None,  # No abort threshold (relaxed)
        )
        config = create_study_config(
            name="sandbox_relaxed",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[stage],
        )

        checker = LegalityChecker(config)
        result = checker.check_legality()
        assert result.is_legal
        assert stage.abort_threshold_wns_ps is None

    def test_sandbox_aggressive_eco_exploration_legal(self):
        """Step 4: Execute Study with aggressive ECO exploration."""
        stages = self.create_aggressive_stages()
        config = create_study_config(
            name="sandbox_aggressive",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.SANDBOX,
            stages=stages,
        )

        checker = LegalityChecker(config)
        result = checker.check_legality()

        # Should be legal - sandbox allows everything
        assert result.is_legal
        assert result.violation_count == 0

        # Should have a warning about GLOBAL_DISRUPTIVE
        assert len(result.warnings) > 0
        assert any("GLOBAL_DISRUPTIVE" in w for w in result.warnings)

    def test_create_same_study_in_guarded(self):
        """Step 5: Create same Study in 'guarded' safety domain."""
        stages = self.create_base_stages()
        config = create_study_config(
            name="safety_domain_e2e_guarded",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.GUARDED,
            stages=stages,
        )

        assert config.safety_domain == SafetyDomain.GUARDED
        assert len(config.stages) == 2
        config.validate()

    def test_guarded_restricts_global_disruptive(self):
        """Step 6: Verify global_disruptive ECOs are restricted."""
        allowed = SAFETY_POLICY[SafetyDomain.GUARDED]

        # Only 3 ECO classes should be allowed (not GLOBAL_DISRUPTIVE)
        assert ECOClass.TOPOLOGY_NEUTRAL in allowed
        assert ECOClass.PLACEMENT_LOCAL in allowed
        assert ECOClass.ROUTING_AFFECTING in allowed
        assert ECOClass.GLOBAL_DISRUPTIVE not in allowed
        assert len(allowed) == 3

    def test_guarded_abort_criteria_standard(self):
        """Step 7: Verify abort criteria are standard."""
        # In guarded mode, we typically have standard abort thresholds
        stage = StageConfig(
            name="standard_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.ROUTING_AFFECTING],
            abort_threshold_wns_ps=-5000,  # Standard threshold
        )
        config = create_study_config(
            name="guarded_standard",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.GUARDED,
            stages=[stage],
        )

        checker = LegalityChecker(config)
        result = checker.check_legality()
        assert result.is_legal
        assert stage.abort_threshold_wns_ps == -5000

    def test_guarded_balanced_exploration_legal(self):
        """Step 8: Execute Study with balanced exploration."""
        stages = self.create_base_stages()  # Uses safe ECO classes
        config = create_study_config(
            name="guarded_balanced",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.GUARDED,
            stages=stages,
        )

        checker = LegalityChecker(config)
        result = checker.check_legality()

        # Should be legal - all ECOs are within guarded limits
        assert result.is_legal
        assert result.violation_count == 0

    def test_create_same_study_in_locked(self):
        """Step 9: Create same Study in 'locked' safety domain."""
        # Create stages with only safe ECO classes for locked mode
        stages = [
            StageConfig(
                name="locked_stage",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                ],
            ),
        ]
        config = create_study_config(
            name="safety_domain_e2e_locked",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.LOCKED,
            stages=stages,
        )

        assert config.safety_domain == SafetyDomain.LOCKED
        assert len(config.stages) == 1
        config.validate()

    def test_locked_permits_only_regression_safe_ecos(self):
        """Step 10: Verify only regression-safe ECOs are permitted."""
        allowed = SAFETY_POLICY[SafetyDomain.LOCKED]

        # Only 2 ECO classes should be allowed
        assert ECOClass.TOPOLOGY_NEUTRAL in allowed
        assert ECOClass.PLACEMENT_LOCAL in allowed
        assert ECOClass.ROUTING_AFFECTING not in allowed
        assert ECOClass.GLOBAL_DISRUPTIVE not in allowed
        assert len(allowed) == 2

    def test_locked_abort_criteria_strict(self):
        """Step 11: Verify abort criteria are strict."""
        # In locked mode, we have strict abort thresholds
        stage = StageConfig(
            name="strict_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=5,
            survivor_count=2,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
            abort_threshold_wns_ps=-1000,  # Strict threshold
        )
        config = create_study_config(
            name="locked_strict",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.LOCKED,
            stages=[stage],
        )

        checker = LegalityChecker(config)
        result = checker.check_legality()
        assert result.is_legal
        assert stage.abort_threshold_wns_ps == -1000

    def test_locked_conservative_changes_only(self):
        """Step 12: Execute Study with conservative changes only."""
        stage = StageConfig(
            name="conservative",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=5,
            survivor_count=2,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
        )
        config = create_study_config(
            name="locked_conservative",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.LOCKED,
            stages=[stage],
        )

        checker = LegalityChecker(config)
        result = checker.check_legality()

        # Should be legal with only TOPOLOGY_NEUTRAL
        assert result.is_legal
        assert result.violation_count == 0

    def test_compare_outcomes_across_all_three_domains(self):
        """Step 13: Compare outcomes across all three domains."""
        # Create comparable configurations for all three domains
        configs = {}

        # Sandbox: allows all ECO classes
        sandbox_stages = [
            StageConfig(
                name="test_stage",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                    ECOClass.ROUTING_AFFECTING,
                    ECOClass.GLOBAL_DISRUPTIVE,
                ],
            ),
        ]
        configs["sandbox"] = create_study_config(
            name="comparison_sandbox",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.SANDBOX,
            stages=sandbox_stages,
        )

        # Guarded: restricts GLOBAL_DISRUPTIVE
        guarded_stages = [
            StageConfig(
                name="test_stage",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                    ECOClass.ROUTING_AFFECTING,
                ],
            ),
        ]
        configs["guarded"] = create_study_config(
            name="comparison_guarded",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.GUARDED,
            stages=guarded_stages,
        )

        # Locked: only safe ECO classes
        locked_stages = [
            StageConfig(
                name="test_stage",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                ],
            ),
        ]
        configs["locked"] = create_study_config(
            name="comparison_locked",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.LOCKED,
            stages=locked_stages,
        )

        # Check legality for all three
        results = {}
        for domain, config in configs.items():
            checker = LegalityChecker(config)
            results[domain] = checker.check_legality()

        # All should be legal when configured appropriately
        assert all(r.is_legal for r in results.values())

        # Verify ECO class counts differ appropriately
        assert len(SAFETY_POLICY[SafetyDomain.SANDBOX]) == 4
        assert len(SAFETY_POLICY[SafetyDomain.GUARDED]) == 3
        assert len(SAFETY_POLICY[SafetyDomain.LOCKED]) == 2

    def test_verify_safety_domain_compliance_in_all_cases(self):
        """Step 14: Verify safety domain compliance in all cases."""
        # Test that illegal configurations are properly rejected
        test_cases = [
            {
                "domain": SafetyDomain.GUARDED,
                "eco_class": ECOClass.GLOBAL_DISRUPTIVE,
                "should_be_legal": False,
            },
            {
                "domain": SafetyDomain.LOCKED,
                "eco_class": ECOClass.ROUTING_AFFECTING,
                "should_be_legal": False,
            },
            {
                "domain": SafetyDomain.LOCKED,
                "eco_class": ECOClass.GLOBAL_DISRUPTIVE,
                "should_be_legal": False,
            },
            {
                "domain": SafetyDomain.SANDBOX,
                "eco_class": ECOClass.GLOBAL_DISRUPTIVE,
                "should_be_legal": True,
            },
        ]

        for test_case in test_cases:
            stage = StageConfig(
                name="compliance_test",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[test_case["eco_class"]],
            )
            config = create_study_config(
                name=f"compliance_{test_case['domain'].value}",
                pdk="Nangate45",
                base_case_name="nangate45_base",
                snapshot_path="/tmp/snapshot",
                safety_domain=test_case["domain"],
                stages=[stage],
            )

            checker = LegalityChecker(config)
            result = checker.check_legality()

            if test_case["should_be_legal"]:
                assert result.is_legal, (
                    f"{test_case['eco_class'].value} should be legal in "
                    f"{test_case['domain'].value}"
                )
            else:
                assert not result.is_legal, (
                    f"{test_case['eco_class'].value} should be illegal in "
                    f"{test_case['domain'].value}"
                )

    def test_generate_safety_domain_comparison_report(self, tmp_path: Path):
        """Step 15: Generate safety domain comparison report."""
        reports = {}

        # Generate reports for all three domains
        for domain in [SafetyDomain.SANDBOX, SafetyDomain.GUARDED, SafetyDomain.LOCKED]:
            # Configure appropriately for each domain
            if domain == SafetyDomain.SANDBOX:
                eco_classes = [
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                    ECOClass.ROUTING_AFFECTING,
                    ECOClass.GLOBAL_DISRUPTIVE,
                ]
            elif domain == SafetyDomain.GUARDED:
                eco_classes = [
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                    ECOClass.ROUTING_AFFECTING,
                ]
            else:  # LOCKED
                eco_classes = [
                    ECOClass.TOPOLOGY_NEUTRAL,
                    ECOClass.PLACEMENT_LOCAL,
                ]

            stage = StageConfig(
                name="comparison_stage",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=eco_classes,
            )
            config = create_study_config(
                name=f"comparison_{domain.value}",
                pdk="Nangate45",
                base_case_name="nangate45_base",
                snapshot_path="/tmp/snapshot",
                safety_domain=domain,
                stages=[stage],
            )

            report = generate_legality_report(config, timestamp="2024-01-01T00:00:00Z")
            reports[domain.value] = report

            # Write individual reports
            report_path = tmp_path / f"legality_report_{domain.value}.txt"
            report_path.write_text(str(report))

            # Write JSON version
            json_path = tmp_path / f"legality_report_{domain.value}.json"
            json_path.write_text(json.dumps(report.to_dict(), indent=2))

        # Verify all reports were generated
        assert len(reports) == 3
        assert all(r.is_legal for r in reports.values())

        # Verify comparison file structure
        comparison_data = {
            "comparison_timestamp": "2024-01-01T00:00:00Z",
            "domains": {
                domain_name: report.to_dict()
                for domain_name, report in reports.items()
            },
            "summary": {
                "sandbox_eco_count": len(SAFETY_POLICY[SafetyDomain.SANDBOX]),
                "guarded_eco_count": len(SAFETY_POLICY[SafetyDomain.GUARDED]),
                "locked_eco_count": len(SAFETY_POLICY[SafetyDomain.LOCKED]),
            },
        }

        comparison_path = tmp_path / "safety_domain_comparison.json"
        comparison_path.write_text(json.dumps(comparison_data, indent=2))

        # Verify comparison file exists and is valid
        assert comparison_path.exists()
        loaded_data = json.loads(comparison_path.read_text())
        assert loaded_data["summary"]["sandbox_eco_count"] == 4
        assert loaded_data["summary"]["guarded_eco_count"] == 3
        assert loaded_data["summary"]["locked_eco_count"] == 2


class TestCrossConstraintViolations:
    """Test illegal configurations that violate safety domain constraints."""

    def test_guarded_rejects_global_disruptive(self):
        """GUARDED should reject GLOBAL_DISRUPTIVE ECOs."""
        stage = StageConfig(
            name="illegal_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE],
        )
        config = create_study_config(
            name="guarded_illegal",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.GUARDED,
            stages=[stage],
        )

        checker = LegalityChecker(config)
        result = checker.check_legality()

        assert not result.is_legal
        assert result.violation_count == 1
        assert result.violations[0].eco_class == ECOClass.GLOBAL_DISRUPTIVE

    def test_locked_rejects_routing_affecting(self):
        """LOCKED should reject ROUTING_AFFECTING ECOs."""
        stage = StageConfig(
            name="illegal_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.ROUTING_AFFECTING],
        )
        config = create_study_config(
            name="locked_illegal",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.LOCKED,
            stages=[stage],
        )

        checker = LegalityChecker(config)
        result = checker.check_legality()

        assert not result.is_legal
        assert result.violation_count == 1
        assert result.violations[0].eco_class == ECOClass.ROUTING_AFFECTING

    def test_locked_rejects_global_disruptive(self):
        """LOCKED should reject GLOBAL_DISRUPTIVE ECOs."""
        stage = StageConfig(
            name="illegal_stage",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE],
        )
        config = create_study_config(
            name="locked_illegal_global",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.LOCKED,
            stages=[stage],
        )

        checker = LegalityChecker(config)
        result = checker.check_legality()

        assert not result.is_legal
        assert result.violation_count == 1
        assert result.violations[0].eco_class == ECOClass.GLOBAL_DISRUPTIVE

    def test_multiple_violations_in_single_study(self):
        """Test Study with multiple safety violations."""
        stages = [
            StageConfig(
                name="stage_0",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[ECOClass.ROUTING_AFFECTING],
            ),
            StageConfig(
                name="stage_1",
                execution_mode=ExecutionMode.STA_ONLY,
                trial_budget=10,
                survivor_count=5,
                allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE],
            ),
        ]
        config = create_study_config(
            name="locked_multiple_violations",
            pdk="Nangate45",
            base_case_name="nangate45_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.LOCKED,
            stages=stages,
        )

        checker = LegalityChecker(config)
        result = checker.check_legality()

        assert not result.is_legal
        assert result.violation_count == 2  # Two illegal ECO classes


class TestSafetyDomainProgressiveRestriction:
    """Test that safety domains form a progressive restriction hierarchy."""

    def test_sandbox_is_most_permissive(self):
        """SANDBOX should be the most permissive domain."""
        sandbox_allowed = set(SAFETY_POLICY[SafetyDomain.SANDBOX])
        guarded_allowed = set(SAFETY_POLICY[SafetyDomain.GUARDED])
        locked_allowed = set(SAFETY_POLICY[SafetyDomain.LOCKED])

        # Sandbox should be a superset of guarded
        assert guarded_allowed.issubset(sandbox_allowed)

        # Sandbox should be a superset of locked
        assert locked_allowed.issubset(sandbox_allowed)

    def test_guarded_is_middle_ground(self):
        """GUARDED should be more permissive than LOCKED but less than SANDBOX."""
        sandbox_allowed = set(SAFETY_POLICY[SafetyDomain.SANDBOX])
        guarded_allowed = set(SAFETY_POLICY[SafetyDomain.GUARDED])
        locked_allowed = set(SAFETY_POLICY[SafetyDomain.LOCKED])

        # Guarded should be a subset of sandbox
        assert guarded_allowed.issubset(sandbox_allowed)

        # Guarded should be a superset of locked
        assert locked_allowed.issubset(guarded_allowed)

        # Guarded should have more allowed than locked but less than sandbox
        assert len(locked_allowed) < len(guarded_allowed) < len(sandbox_allowed)

    def test_locked_is_most_restrictive(self):
        """LOCKED should be the most restrictive domain."""
        sandbox_allowed = set(SAFETY_POLICY[SafetyDomain.SANDBOX])
        guarded_allowed = set(SAFETY_POLICY[SafetyDomain.GUARDED])
        locked_allowed = set(SAFETY_POLICY[SafetyDomain.LOCKED])

        # Locked should be a subset of both sandbox and guarded
        assert locked_allowed.issubset(sandbox_allowed)
        assert locked_allowed.issubset(guarded_allowed)

        # Locked should have the smallest set
        assert len(locked_allowed) <= len(guarded_allowed)
        assert len(locked_allowed) <= len(sandbox_allowed)
