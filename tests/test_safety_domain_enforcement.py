"""Tests for safety domain enforcement across sandbox/guarded/locked domains."""

import pytest
from pathlib import Path

from src.controller.executor import StudyExecutor
from src.controller.safety import (
    SAFETY_POLICY,
    LegalityChecker,
    check_study_legality,
    generate_legality_report,
)
from src.controller.study import create_study_config
from src.controller.types import ECOClass, ExecutionMode, SafetyDomain, StageConfig


class TestSafetyPolicyDefinitions:
    """Test that SAFETY_POLICY is correctly defined."""

    def test_sandbox_allows_all_eco_classes(self):
        """SANDBOX domain should allow all ECO classes."""
        allowed = SAFETY_POLICY[SafetyDomain.SANDBOX]
        assert ECOClass.TOPOLOGY_NEUTRAL in allowed
        assert ECOClass.PLACEMENT_LOCAL in allowed
        assert ECOClass.ROUTING_AFFECTING in allowed
        assert ECOClass.GLOBAL_DISRUPTIVE in allowed
        assert len(allowed) == 4

    def test_guarded_prohibits_global_disruptive(self):
        """GUARDED domain should prohibit GLOBAL_DISRUPTIVE."""
        allowed = SAFETY_POLICY[SafetyDomain.GUARDED]
        assert ECOClass.TOPOLOGY_NEUTRAL in allowed
        assert ECOClass.PLACEMENT_LOCAL in allowed
        assert ECOClass.ROUTING_AFFECTING in allowed
        assert ECOClass.GLOBAL_DISRUPTIVE not in allowed
        assert len(allowed) == 3

    def test_locked_allows_only_safe_eco_classes(self):
        """LOCKED domain should allow only TOPOLOGY_NEUTRAL and PLACEMENT_LOCAL."""
        allowed = SAFETY_POLICY[SafetyDomain.LOCKED]
        assert ECOClass.TOPOLOGY_NEUTRAL in allowed
        assert ECOClass.PLACEMENT_LOCAL in allowed
        assert ECOClass.ROUTING_AFFECTING not in allowed
        assert ECOClass.GLOBAL_DISRUPTIVE not in allowed
        assert len(allowed) == 2


class TestSandboxSafetyDomain:
    """Test sandbox safety domain behavior (exploratory, permissive)."""

    def test_sandbox_allows_topology_neutral(self):
        """SANDBOX should allow topology_neutral ECOs."""
        stage = StageConfig(
            name="exploration",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
        )
        config = create_study_config(
            name="sandbox_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[stage],
        )

        checker = LegalityChecker(config)
        result = checker.check_legality()
        assert result.is_legal
        assert result.violation_count == 0

    def test_sandbox_allows_placement_local(self):
        """SANDBOX should allow placement_local ECOs."""
        stage = StageConfig(
            name="exploration",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
        )
        config = create_study_config(
            name="sandbox_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[stage],
        )

        result = check_study_legality(config)
        assert result.is_legal

    def test_sandbox_allows_routing_affecting(self):
        """SANDBOX should allow routing_affecting ECOs."""
        stage = StageConfig(
            name="exploration",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.ROUTING_AFFECTING],
        )
        config = create_study_config(
            name="sandbox_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[stage],
        )

        result = check_study_legality(config)
        assert result.is_legal

    def test_sandbox_allows_global_disruptive(self):
        """SANDBOX should allow global_disruptive ECOs (exploratory work)."""
        stage = StageConfig(
            name="exploration",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE],
        )
        config = create_study_config(
            name="sandbox_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[stage],
        )

        result = check_study_legality(config)
        assert result.is_legal
        # Should have a warning about GLOBAL_DISRUPTIVE
        assert len(result.warnings) > 0
        assert "GLOBAL_DISRUPTIVE" in result.warnings[0]

    def test_sandbox_allows_all_eco_classes_together(self):
        """SANDBOX should allow all ECO classes simultaneously."""
        stage = StageConfig(
            name="exploration",
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
        config = create_study_config(
            name="sandbox_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.SANDBOX,
            stages=[stage],
        )

        result = check_study_legality(config)
        assert result.is_legal
        assert len(result.warnings) > 0  # Warning about GLOBAL_DISRUPTIVE


class TestGuardedSafetyDomain:
    """Test guarded safety domain behavior (default, production-like)."""

    def test_guarded_allows_topology_neutral(self):
        """GUARDED should allow topology_neutral ECOs."""
        stage = StageConfig(
            name="refinement",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
        )
        config = create_study_config(
            name="guarded_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.GUARDED,
            stages=[stage],
        )

        result = check_study_legality(config)
        assert result.is_legal

    def test_guarded_allows_placement_local(self):
        """GUARDED should allow placement_local ECOs."""
        stage = StageConfig(
            name="refinement",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
        )
        config = create_study_config(
            name="guarded_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.GUARDED,
            stages=[stage],
        )

        result = check_study_legality(config)
        assert result.is_legal

    def test_guarded_allows_routing_affecting(self):
        """GUARDED should allow routing_affecting ECOs."""
        stage = StageConfig(
            name="refinement",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.ROUTING_AFFECTING],
        )
        config = create_study_config(
            name="guarded_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.GUARDED,
            stages=[stage],
        )

        result = check_study_legality(config)
        assert result.is_legal

    def test_guarded_prohibits_global_disruptive(self):
        """GUARDED should prohibit global_disruptive ECOs."""
        stage = StageConfig(
            name="refinement",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE],
        )
        config = create_study_config(
            name="guarded_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.GUARDED,
            stages=[stage],
        )

        # Should raise ValueError
        with pytest.raises(ValueError, match="ILLEGAL"):
            check_study_legality(config)

    def test_guarded_violation_is_reported_in_result(self):
        """GUARDED violations should be reported in LegalityCheckResult."""
        stage = StageConfig(
            name="refinement",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE],
        )
        config = create_study_config(
            name="guarded_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.GUARDED,
            stages=[stage],
        )

        checker = LegalityChecker(config)
        result = checker.check_legality()
        assert not result.is_legal
        assert result.violation_count == 1
        assert result.violations[0].eco_class == ECOClass.GLOBAL_DISRUPTIVE
        assert "guarded" in result.violations[0].reason


class TestLockedSafetyDomain:
    """Test locked safety domain behavior (conservative, regression-only)."""

    def test_locked_allows_topology_neutral(self):
        """LOCKED should allow topology_neutral ECOs."""
        stage = StageConfig(
            name="regression",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
        )
        config = create_study_config(
            name="locked_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.LOCKED,
            stages=[stage],
        )

        result = check_study_legality(config)
        assert result.is_legal

    def test_locked_allows_placement_local(self):
        """LOCKED should allow placement_local ECOs."""
        stage = StageConfig(
            name="regression",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.PLACEMENT_LOCAL],
        )
        config = create_study_config(
            name="locked_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.LOCKED,
            stages=[stage],
        )

        result = check_study_legality(config)
        assert result.is_legal

    def test_locked_prohibits_routing_affecting(self):
        """LOCKED should prohibit routing_affecting ECOs."""
        stage = StageConfig(
            name="regression",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.ROUTING_AFFECTING],
        )
        config = create_study_config(
            name="locked_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.LOCKED,
            stages=[stage],
        )

        with pytest.raises(ValueError, match="ILLEGAL"):
            check_study_legality(config)

    def test_locked_prohibits_global_disruptive(self):
        """LOCKED should prohibit global_disruptive ECOs."""
        stage = StageConfig(
            name="regression",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE],
        )
        config = create_study_config(
            name="locked_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.LOCKED,
            stages=[stage],
        )

        with pytest.raises(ValueError, match="ILLEGAL"):
            check_study_legality(config)

    def test_locked_allows_only_safe_classes(self):
        """LOCKED should only allow topology_neutral and placement_local."""
        stage = StageConfig(
            name="regression",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[
                ECOClass.TOPOLOGY_NEUTRAL,
                ECOClass.PLACEMENT_LOCAL,
            ],
        )
        config = create_study_config(
            name="locked_test",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.LOCKED,
            stages=[stage],
        )

        result = check_study_legality(config)
        assert result.is_legal


class TestRunLegalityReport:
    """Test Run Legality Report generation."""

    def test_generate_legality_report_for_legal_study(self):
        """Generate report for a legal Study configuration."""
        stage = StageConfig(
            name="stage_0",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
        )
        config = create_study_config(
            name="test_study",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.GUARDED,
            stages=[stage],
        )

        report = generate_legality_report(config, timestamp="2024-01-01 12:00:00")

        assert report.study_name == "test_study"
        assert report.safety_domain == SafetyDomain.GUARDED
        assert report.is_legal
        assert len(report.violations) == 0
        assert report.stage_count == 1
        assert report.total_trial_budget == 10

        # Check string representation
        report_str = str(report)
        assert "RUN LEGALITY REPORT" in report_str
        assert "test_study" in report_str
        assert "guarded" in report_str
        assert "LEGAL" in report_str

    def test_generate_legality_report_for_illegal_study(self):
        """Generate report for an illegal Study configuration."""
        stage = StageConfig(
            name="stage_0",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE],
        )
        config = create_study_config(
            name="illegal_study",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.LOCKED,
            stages=[stage],
        )

        report = generate_legality_report(config)

        assert not report.is_legal
        assert len(report.violations) == 1
        assert report.violations[0].eco_class == ECOClass.GLOBAL_DISRUPTIVE

        # Check string representation
        report_str = str(report)
        assert "ILLEGAL" in report_str
        assert "global_disruptive" in report_str

    def test_legality_report_to_dict(self):
        """Test JSON serialization of legality report."""
        stage = StageConfig(
            name="stage_0",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=10,
            survivor_count=5,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
        )
        config = create_study_config(
            name="test_study",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path="/tmp/snapshot",
            safety_domain=SafetyDomain.GUARDED,
            stages=[stage],
        )

        report = generate_legality_report(config)
        report_dict = report.to_dict()

        assert report_dict["study_name"] == "test_study"
        assert report_dict["safety_domain"] == "guarded"
        assert report_dict["is_legal"] is True
        assert isinstance(report_dict["allowed_eco_classes"], list)
        assert isinstance(report_dict["violations"], list)


class TestStudyExecutorSafetyEnforcement:
    """Test that StudyExecutor enforces safety domain constraints."""

    def test_executor_blocks_illegal_study(self, tmp_path):
        """StudyExecutor should block execution of illegal Study."""
        # Create illegal study (LOCKED domain with GLOBAL_DISRUPTIVE)
        stage = StageConfig(
            name="stage_0",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=5,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE],
        )
        config = create_study_config(
            name="illegal_study",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path=str(tmp_path / "snapshot"),
            safety_domain=SafetyDomain.LOCKED,
            stages=[stage],
        )

        # Create snapshot directory
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        # Create executor and attempt to execute
        executor = StudyExecutor(
            config,
            artifacts_root=tmp_path / "artifacts",
            telemetry_root=tmp_path / "telemetry",
            skip_base_case_verification=True,  # Focus on safety domain check
        )

        result = executor.execute()

        # Study should be aborted due to illegal configuration
        assert result.aborted
        assert "ILLEGAL" in result.abort_reason
        assert result.stages_completed == 0

    def test_executor_allows_legal_sandbox_study(self, tmp_path):
        """StudyExecutor should allow legal SANDBOX Study."""
        stage = StageConfig(
            name="stage_0",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=5,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.GLOBAL_DISRUPTIVE],
        )
        config = create_study_config(
            name="sandbox_study",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path=str(tmp_path / "snapshot"),
            safety_domain=SafetyDomain.SANDBOX,
            stages=[stage],
        )

        # Create snapshot directory with minimal script
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()
        script = snapshot_dir / "run_sta.tcl"
        script.write_text("# Placeholder\n")

        # Create executor
        executor = StudyExecutor(
            config,
            artifacts_root=tmp_path / "artifacts",
            telemetry_root=tmp_path / "telemetry",
            skip_base_case_verification=True,
        )

        # Should not block (will fail later for other reasons, but not safety)
        # We're just checking that safety check passes
        result = executor.execute()

        # If it's blocked due to safety, it would be aborted with "ILLEGAL" in reason
        # Since we skip base case verification, it should get past safety check
        if result.aborted:
            assert "ILLEGAL" not in result.abort_reason

    def test_executor_saves_legality_report(self, tmp_path):
        """StudyExecutor should save Run Legality Report to artifacts."""
        stage = StageConfig(
            name="stage_0",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=5,
            survivor_count=3,
            allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
        )
        config = create_study_config(
            name="test_study",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path=str(tmp_path / "snapshot"),
            safety_domain=SafetyDomain.GUARDED,
            stages=[stage],
        )

        # Create snapshot directory
        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()
        script = snapshot_dir / "run_sta.tcl"
        script.write_text("# Placeholder\n")

        artifacts_root = tmp_path / "artifacts"
        executor = StudyExecutor(
            config,
            artifacts_root=artifacts_root,
            telemetry_root=tmp_path / "telemetry",
            skip_base_case_verification=True,
        )

        executor.execute()

        # Check that legality report was saved
        report_path = artifacts_root / "test_study" / "run_legality_report.txt"
        assert report_path.exists()

        report_content = report_path.read_text()
        assert "RUN LEGALITY REPORT" in report_content
        assert "test_study" in report_content
        assert "LEGAL" in report_content

    def test_is_eco_class_allowed_method(self, tmp_path):
        """Test the is_eco_class_allowed helper method."""
        stage = StageConfig(
            name="stage_0",
            execution_mode=ExecutionMode.STA_ONLY,
            trial_budget=5,
            survivor_count=3,
            allowed_eco_classes=[
                ECOClass.TOPOLOGY_NEUTRAL,
                ECOClass.PLACEMENT_LOCAL,
            ],
        )
        config = create_study_config(
            name="test_study",
            pdk="Nangate45",
            base_case_name="test_base",
            snapshot_path=str(tmp_path / "snapshot"),
            safety_domain=SafetyDomain.GUARDED,
            stages=[stage],
        )

        snapshot_dir = tmp_path / "snapshot"
        snapshot_dir.mkdir()

        executor = StudyExecutor(
            config,
            artifacts_root=tmp_path / "artifacts",
            telemetry_root=tmp_path / "telemetry",
        )

        # Test allowed ECO classes
        assert executor.is_eco_class_allowed(ECOClass.TOPOLOGY_NEUTRAL, 0)
        assert executor.is_eco_class_allowed(ECOClass.PLACEMENT_LOCAL, 0)

        # Test prohibited ECO class (not in stage config)
        assert not executor.is_eco_class_allowed(ECOClass.ROUTING_AFFECTING, 0)

        # Test prohibited ECO class (not in safety domain)
        assert not executor.is_eco_class_allowed(ECOClass.GLOBAL_DISRUPTIVE, 0)
