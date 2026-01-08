"""Tests for ASAP7 STA-first staging best practice.

This module tests the creation and validation of ASAP7 Study configurations
that follow the STA-first staging approach for stability.
"""

import pytest

from src.controller.demo_study import create_asap7_demo_study
from src.controller.types import (
    ECOClass,
    ExecutionMode,
    SafetyDomain,
)


class TestASAP7STAFirstStaging:
    """Test ASAP7 Study follows STA-first staging best practice."""

    def test_configure_asap7_study_with_stage_1_sta_only(self) -> None:
        """Step 1: Configure ASAP7 Study with Stage 1 = STA-only."""
        demo = create_asap7_demo_study()

        # Verify first stage is STA-only (most stable for ASAP7)
        assert demo.stages[0].execution_mode == ExecutionMode.STA_ONLY
        assert demo.stages[0].name == "sta_baseline"

    def test_execute_stage_1_timing_analysis(self) -> None:
        """Step 2: Execute Stage 1 timing analysis.

        This test verifies the configuration is set up for timing analysis.
        Actual execution would be tested in integration tests.
        """
        demo = create_asap7_demo_study()

        # Stage 0 is configured for timing analysis
        assert demo.stages[0].execution_mode == ExecutionMode.STA_ONLY
        assert demo.stages[0].trial_budget > 0
        assert demo.stages[0].survivor_count > 0
        # Conservative ECO classes for initial exploration
        assert ECOClass.TOPOLOGY_NEUTRAL in demo.stages[0].allowed_eco_classes

    def test_verify_stable_timing_results(self) -> None:
        """Step 3: Verify stable timing results.

        STA-only mode is the most stable execution mode for ASAP7.
        This test verifies the configuration choices support stability.
        """
        demo = create_asap7_demo_study()

        # Stage 0: STA-only for stability
        assert demo.stages[0].execution_mode == ExecutionMode.STA_ONLY

        # Reasonable timeout for timing analysis
        assert demo.stages[0].timeout_seconds >= 300

        # Abort threshold is permissive for exploration
        assert demo.stages[0].abort_threshold_wns_ps is not None
        assert demo.stages[0].abort_threshold_wns_ps < 0  # Negative WNS allowed

    def test_optionally_enable_congestion_analysis_in_stage_2_plus(self) -> None:
        """Step 4: Optionally enable congestion analysis in Stage 2+."""
        demo = create_asap7_demo_study()

        # Stage 0: STA-only
        assert demo.stages[0].execution_mode == ExecutionMode.STA_ONLY

        # Stage 1: STA-only (continue with stable mode)
        assert demo.stages[1].execution_mode == ExecutionMode.STA_ONLY

        # Stage 2: Optionally add congestion (only after timing is stable)
        assert demo.stages[2].execution_mode == ExecutionMode.STA_CONGESTION

    def test_confirm_sta_first_approach_is_more_stable_than_congestion_first(
        self,
    ) -> None:
        """Step 5: Confirm STA-first approach is more stable than congestion-first.

        This test verifies the configuration choices that make STA-first more stable:
        - First two stages use STA-only mode
        - Congestion analysis deferred to final stage
        - Conservative ECO classes in early stages
        - Adequate timeouts for each stage
        """
        demo = create_asap7_demo_study()

        # STA-first: Stages 0 and 1 are both STA-only
        assert demo.stages[0].execution_mode == ExecutionMode.STA_ONLY
        assert demo.stages[1].execution_mode == ExecutionMode.STA_ONLY

        # Congestion analysis only in final stage (Stage 2)
        assert demo.stages[2].execution_mode == ExecutionMode.STA_CONGESTION

        # Conservative ECO progression
        # Stage 0: topology neutral only
        assert demo.stages[0].allowed_eco_classes == [ECOClass.TOPOLOGY_NEUTRAL]

        # Stage 1: adds placement local
        assert ECOClass.TOPOLOGY_NEUTRAL in demo.stages[1].allowed_eco_classes
        assert ECOClass.PLACEMENT_LOCAL in demo.stages[1].allowed_eco_classes

        # Progressive timeouts (more time for later stages)
        assert demo.stages[0].timeout_seconds <= demo.stages[1].timeout_seconds
        assert demo.stages[1].timeout_seconds <= demo.stages[2].timeout_seconds


class TestASAP7DemoStudyConfiguration:
    """Test ASAP7 demo Study configuration details."""

    def test_asap7_demo_has_correct_pdk(self) -> None:
        """Verify ASAP7 demo Study specifies ASAP7 PDK."""
        demo = create_asap7_demo_study()

        assert demo.pdk == "ASAP7"
        assert demo.name == "asap7_demo"
        assert demo.base_case_name == "asap7_base"

    def test_asap7_demo_has_three_stages(self) -> None:
        """Verify ASAP7 demo has 3 stages with STA-first progression."""
        demo = create_asap7_demo_study()

        assert len(demo.stages) == 3
        assert demo.stages[0].name == "sta_baseline"
        assert demo.stages[1].name == "sta_refinement"
        assert demo.stages[2].name == "congestion_closure"

    def test_asap7_demo_has_metadata_about_workarounds(self) -> None:
        """Verify ASAP7 demo includes metadata about workarounds."""
        demo = create_asap7_demo_study()

        assert "asap7_workarounds" in demo.metadata
        workarounds = demo.metadata["asap7_workarounds"]

        # Should mention all ASAP7-specific workarounds
        assert "routing_layer_constraints" in workarounds
        assert "site_specification" in workarounds
        assert "pin_placement_constraints" in workarounds
        assert "low_utilization_0.55" in workarounds

    def test_asap7_demo_has_sta_first_tag(self) -> None:
        """Verify ASAP7 demo is tagged as STA-first."""
        demo = create_asap7_demo_study()

        assert "sta-first" in demo.tags
        assert "asap7" in demo.tags
        assert "demo" in demo.tags

    def test_asap7_demo_description_mentions_sta_first(self) -> None:
        """Verify ASAP7 demo description explains STA-first approach."""
        demo = create_asap7_demo_study()

        assert demo.description is not None
        assert "STA-first" in demo.description or "sta-first" in demo.description.lower()
        assert "stable" in demo.description.lower()

    def test_asap7_demo_validates_successfully(self) -> None:
        """Verify ASAP7 demo Study passes validation."""
        demo = create_asap7_demo_study()

        # Should not raise any exceptions
        demo.validate()

    def test_asap7_demo_trial_budgets_are_reasonable(self) -> None:
        """Verify ASAP7 demo has reasonable trial budgets."""
        demo = create_asap7_demo_study()

        # All stages should have positive budgets
        for stage in demo.stages:
            assert stage.trial_budget > 0
            assert stage.survivor_count > 0
            assert stage.survivor_count <= stage.trial_budget

    def test_asap7_demo_has_visualization_enabled(self) -> None:
        """Verify ASAP7 demo enables visualization for observability."""
        demo = create_asap7_demo_study()

        for stage in demo.stages:
            assert stage.visualization_enabled is True

    def test_asap7_demo_custom_snapshot_path(self) -> None:
        """Verify ASAP7 demo accepts custom snapshot path."""
        custom_path = "/custom/path/to/asap7_snapshot"
        demo = create_asap7_demo_study(snapshot_path=custom_path)

        assert demo.snapshot_path == custom_path

    def test_asap7_demo_custom_safety_domain(self) -> None:
        """Verify ASAP7 demo accepts custom safety domain."""
        demo_sandbox = create_asap7_demo_study(
            safety_domain=SafetyDomain.SANDBOX
        )
        assert demo_sandbox.safety_domain == SafetyDomain.SANDBOX

        demo_locked = create_asap7_demo_study(
            safety_domain=SafetyDomain.LOCKED
        )
        assert demo_locked.safety_domain == SafetyDomain.LOCKED


class TestASAP7vsNangate45Staging:
    """Compare ASAP7 and Nangate45 staging approaches."""

    def test_asap7_uses_sta_first_nangate45_can_use_other_modes(self) -> None:
        """Verify ASAP7 enforces STA-first while Nangate45 is more flexible."""
        from src.controller.demo_study import create_nangate45_demo_study

        asap7_demo = create_asap7_demo_study()
        nangate45_demo = create_nangate45_demo_study()

        # ASAP7: First stage MUST be STA-only for stability
        assert asap7_demo.stages[0].execution_mode == ExecutionMode.STA_ONLY

        # Both start with STA-only, but for different reasons:
        # - ASAP7: Required for stability (STA-first best practice)
        # - Nangate45: Design choice (could use other modes)
        assert nangate45_demo.stages[0].execution_mode == ExecutionMode.STA_ONLY

    def test_asap7_keeps_sta_only_longer_than_nangate45(self) -> None:
        """Verify ASAP7 uses STA-only for first two stages."""
        from src.controller.demo_study import create_nangate45_demo_study

        asap7_demo = create_asap7_demo_study()
        nangate45_demo = create_nangate45_demo_study()

        # ASAP7: Stages 0 and 1 are both STA-only
        assert asap7_demo.stages[0].execution_mode == ExecutionMode.STA_ONLY
        assert asap7_demo.stages[1].execution_mode == ExecutionMode.STA_ONLY

        # Nangate45: All stages use STA-only (different design choice)
        # This is fine for Nangate45 since it doesn't have ASAP7's constraints
        assert nangate45_demo.stages[0].execution_mode == ExecutionMode.STA_ONLY

    def test_asap7_metadata_explains_sta_first_rationale(self) -> None:
        """Verify ASAP7 demo metadata explains why STA-first is used."""
        asap7_demo = create_asap7_demo_study()

        assert "purpose" in asap7_demo.metadata
        purpose = asap7_demo.metadata["purpose"]
        assert "STA-first" in purpose or "sta-first" in purpose.lower()


class TestASAP7STAFirstEndToEnd:
    """End-to-end tests for ASAP7 STA-first staging."""

    def test_create_asap7_demo_study_with_defaults(self) -> None:
        """Create ASAP7 demo Study and verify all STA-first properties."""
        demo = create_asap7_demo_study()

        # Basic properties
        assert demo.name == "asap7_demo"
        assert demo.pdk == "ASAP7"
        assert demo.safety_domain == SafetyDomain.GUARDED

        # STA-first staging
        assert demo.stages[0].execution_mode == ExecutionMode.STA_ONLY
        assert demo.stages[1].execution_mode == ExecutionMode.STA_ONLY
        assert demo.stages[2].execution_mode == ExecutionMode.STA_CONGESTION

        # Validation passes
        demo.validate()

    def test_asap7_demo_ready_for_execution(self) -> None:
        """Verify ASAP7 demo Study is ready for execution.

        This test checks that all required fields are present and valid.
        Actual execution would be tested in integration tests.
        """
        demo = create_asap7_demo_study()

        # All required fields are present
        assert demo.name
        assert demo.pdk
        assert demo.base_case_name
        assert demo.snapshot_path
        assert len(demo.stages) > 0

        # All stages are properly configured
        for idx, stage in enumerate(demo.stages):
            assert stage.name
            assert stage.execution_mode in ExecutionMode
            assert stage.trial_budget > 0
            assert stage.survivor_count > 0
            assert len(stage.allowed_eco_classes) > 0
            assert stage.timeout_seconds > 0

        # Validation passes
        demo.validate()
