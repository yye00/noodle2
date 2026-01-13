"""Tests for F073: Compound ECO supports rollback_on_failure modes.

Feature steps:
1. Create compound ECO with rollback_on_failure: all
2. Force one component ECO to fail
3. Verify all components are rolled back
4. Test rollback_on_failure: partial (rollback failed component only)
5. Test rollback_on_failure: none (no rollback)
"""

import pytest
from unittest.mock import Mock

from src.controller.eco import (
    BufferInsertionECO,
    CompoundECO,
    ECOResult,
    NoOpECO,
    PlacementDensityECO,
)


class FailingTestECO(NoOpECO):
    """Test ECO that always fails during execution."""

    def __init__(self, fail_message: str = "Intentional test failure") -> None:
        """Initialize failing ECO.

        Args:
            fail_message: The error message to return
        """
        super().__init__()
        self.fail_message = fail_message
        self.metadata.name = "failing_test_eco"

    def execute_with_checkpointing(
        self, design_state: Mock, **kwargs
    ) -> tuple[ECOResult, Mock | None]:
        """Execute ECO that always fails.

        Args:
            design_state: Mock design state
            **kwargs: Additional arguments

        Returns:
            Tuple of (failed ECOResult, checkpoint taken before execution)
        """
        # Take checkpoint before failing
        checkpoint = design_state.create_checkpoint() if hasattr(design_state, 'create_checkpoint') else None

        # Return failure result
        result = ECOResult(
            eco_name=self.name,
            success=False,
            error_message=self.fail_message,
        )
        return result, checkpoint


class TestF073CompoundECORollbackAll:
    """Test F073: Compound ECO supports rollback_on_failure modes."""

    def test_step_1_create_compound_eco_with_rollback_all(self) -> None:
        """Step 1: Create compound ECO with rollback_on_failure: all."""
        component1 = NoOpECO()
        component2 = BufferInsertionECO(max_capacitance=0.2)
        component3 = PlacementDensityECO(target_density=0.7)

        compound = CompoundECO(
            name="rollback_all_test",
            description="Test rollback all mode",
            components=[component1, component2, component3],
            rollback_on_failure="all",
        )

        # Verify rollback_on_failure is set to "all"
        assert compound.metadata.parameters["rollback_on_failure"] == "all"
        assert len(compound.components) == 3

    def test_step_2_force_one_component_eco_to_fail(self) -> None:
        """Step 2: Force one component ECO to fail."""
        # Create components with one failing component
        component1 = NoOpECO()
        component2 = FailingTestECO(fail_message="Component 2 intentionally failed")
        component3 = PlacementDensityECO()

        compound = CompoundECO(
            name="failing_compound",
            description="One component will fail",
            components=[component1, component2, component3],
            rollback_on_failure="all",
        )

        # Verify second component is configured to fail
        assert compound.components[1].name == "failing_test_eco"

    def test_step_3_verify_all_components_are_rolled_back(self) -> None:
        """Step 3: Verify all components are rolled back."""
        # Create mock design state with checkpoint tracking
        design_state = Mock()
        checkpoint = Mock()
        checkpoint.restore = Mock()
        design_state.create_checkpoint = Mock(return_value=checkpoint)

        # Create compound with failing component
        component1 = NoOpECO()
        component2 = FailingTestECO(fail_message="Component 2 failed")
        component3 = PlacementDensityECO()

        compound = CompoundECO(
            name="rollback_all_verification",
            description="Verify all components rolled back",
            components=[component1, component2, component3],
            rollback_on_failure="all",
        )

        # Execute compound ECO
        result = compound.execute_with_rollback(design_state)

        # Verify execution failed
        assert result.success is False
        assert "Component 2 failed" in result.error_message or "failing_test_eco" in result.error_message

        # Verify checkpoint was created
        assert design_state.create_checkpoint.called

        # Verify checkpoint.restore was called (all components rolled back)
        assert checkpoint.restore.called, "All components should be rolled back with rollback_on_failure=all"

        # Verify error message indicates rollback happened
        assert "rolled back all changes" in result.error_message


class TestF073CompoundECORollbackPartial:
    """Test rollback_on_failure: partial mode."""

    def test_step_4_test_rollback_partial(self) -> None:
        """Step 4: Test rollback_on_failure: partial (rollback failed component only)."""
        # Create mock design state with checkpoint tracking
        design_state = Mock()
        checkpoints = []

        def create_checkpoint() -> Mock:
            cp = Mock()
            cp.restore = Mock()
            checkpoints.append(cp)
            return cp

        design_state.create_checkpoint = create_checkpoint

        # Create compound with failing component (component 2 fails)
        component1 = NoOpECO()  # Will succeed
        component2 = FailingTestECO(fail_message="Component 2 failed")  # Will fail
        component3 = PlacementDensityECO()  # Won't be reached

        compound = CompoundECO(
            name="rollback_partial_test",
            description="Test partial rollback mode",
            components=[component1, component2, component3],
            rollback_on_failure="partial",
        )

        # Execute compound ECO
        result = compound.execute_with_rollback(design_state)

        # Verify execution failed
        assert result.success is False

        # Verify error message indicates partial rollback
        assert "partial rollback" in result.error_message

        # With partial rollback:
        # - Initial checkpoint for "all" strategy should not be created
        # - Only the failed component's checkpoint should be restored
        # - Component 1's changes should be preserved

    def test_partial_rollback_preserves_successful_components(self) -> None:
        """Verify partial rollback preserves successful components."""
        design_state = Mock()
        checkpoints = []

        def create_checkpoint() -> Mock:
            cp = Mock()
            cp.restore = Mock()
            checkpoints.append(cp)
            return cp

        design_state.create_checkpoint = create_checkpoint

        component1 = NoOpECO()
        component2 = BufferInsertionECO()
        component3 = FailingTestECO(fail_message="Component 3 failed")

        compound = CompoundECO(
            name="partial_rollback_preserve",
            description="Preserve successful components",
            components=[component1, component2, component3],
            rollback_on_failure="partial",
        )

        result = compound.execute_with_rollback(design_state)

        # Verify failure
        assert result.success is False

        # Verify error message indicates partial rollback with preservation
        assert "partial rollback" in result.error_message
        assert "preserved successful components" in result.error_message


class TestF073CompoundECORollbackNone:
    """Test rollback_on_failure: none mode."""

    def test_step_5_test_rollback_none(self) -> None:
        """Step 5: Test rollback_on_failure: none (no rollback)."""
        # Create mock design state
        design_state = Mock()
        checkpoint = Mock()
        checkpoint.restore = Mock()
        design_state.create_checkpoint = Mock(return_value=checkpoint)

        # Create compound with failing component
        component1 = NoOpECO()
        component2 = FailingTestECO(fail_message="Component 2 failed")
        component3 = PlacementDensityECO()

        compound = CompoundECO(
            name="no_rollback_test",
            description="Test no rollback mode",
            components=[component1, component2, component3],
            rollback_on_failure="none",
        )

        # Execute compound ECO
        result = compound.execute_with_rollback(design_state)

        # Verify execution failed
        assert result.success is False
        assert "Component 2 failed" in result.error_message or "failing_test_eco" in result.error_message

        # Verify checkpoint.restore was NOT called (no rollback with rollback=none)
        assert not checkpoint.restore.called, "No rollback should occur with rollback_on_failure=none"

    def test_rollback_none_keeps_all_changes(self) -> None:
        """Verify rollback_on_failure: none keeps all changes."""
        design_state = Mock()
        checkpoint = Mock()
        checkpoint.restore = Mock()
        design_state.create_checkpoint = Mock(return_value=checkpoint)

        component1 = NoOpECO()
        component2 = BufferInsertionECO()
        component3 = FailingTestECO(fail_message="Component 3 failed")

        compound = CompoundECO(
            name="no_rollback_keep_changes",
            description="Keep all changes",
            components=[component1, component2, component3],
            rollback_on_failure="none",
        )

        result = compound.execute_with_rollback(design_state)

        # Verify failure
        assert result.success is False

        # Verify NO restore was called (all changes kept)
        assert not checkpoint.restore.called


class TestF073RollbackModeValidation:
    """Test validation of rollback modes."""

    def test_valid_rollback_modes(self) -> None:
        """Test all valid rollback modes."""
        for mode in ["all", "partial", "none"]:
            compound = CompoundECO(
                name=f"rollback_{mode}",
                description=f"Test {mode} mode",
                components=[NoOpECO(), BufferInsertionECO()],
                rollback_on_failure=mode,
            )
            assert compound.metadata.parameters["rollback_on_failure"] == mode
            assert compound.validate_parameters() is True

    def test_invalid_rollback_mode_raises_error(self) -> None:
        """Test invalid rollback mode raises error."""
        with pytest.raises(ValueError, match="Invalid rollback_on_failure"):
            CompoundECO(
                name="invalid_rollback",
                description="Invalid mode",
                components=[NoOpECO()],
                rollback_on_failure="invalid_mode",
            )

    def test_default_rollback_mode_is_all(self) -> None:
        """Test default rollback mode is 'all'."""
        compound = CompoundECO(
            name="default_rollback",
            description="Default mode",
            components=[NoOpECO(), BufferInsertionECO()],
        )
        assert compound.metadata.parameters["rollback_on_failure"] == "all"


class TestF073RollbackIntegration:
    """Integration tests for rollback modes."""

    def test_complete_rollback_all_workflow(self) -> None:
        """Test complete workflow for rollback_on_failure: all."""
        # Step 1: Create compound with rollback_on_failure: all
        component1 = NoOpECO()
        component2 = FailingTestECO(fail_message="Intentional failure")

        compound = CompoundECO(
            name="complete_rollback_all",
            description="Complete rollback all test",
            components=[component1, component2],
            rollback_on_failure="all",
        )

        assert compound.metadata.parameters["rollback_on_failure"] == "all"

        # Step 2: Execute with mock design state
        design_state = Mock()
        checkpoint = Mock()
        checkpoint.restore = Mock()
        design_state.create_checkpoint = Mock(return_value=checkpoint)

        # Step 3: Execute compound ECO (will fail)
        result = compound.execute_with_rollback(design_state)

        # Verify failure and rollback
        assert result.success is False
        assert checkpoint.restore.called

    def test_complete_rollback_partial_workflow(self) -> None:
        """Test complete workflow for rollback_on_failure: partial."""
        component1 = NoOpECO()
        component2 = FailingTestECO(fail_message="Intentional failure")

        compound = CompoundECO(
            name="complete_rollback_partial",
            description="Complete rollback partial test",
            components=[component1, component2],
            rollback_on_failure="partial",
        )

        assert compound.metadata.parameters["rollback_on_failure"] == "partial"

        design_state = Mock()
        checkpoints = []

        def create_checkpoint() -> Mock:
            cp = Mock()
            cp.restore = Mock()
            checkpoints.append(cp)
            return cp

        design_state.create_checkpoint = create_checkpoint

        result = compound.execute_with_rollback(design_state)

        assert result.success is False
        assert "partial rollback" in result.error_message

    def test_complete_rollback_none_workflow(self) -> None:
        """Test complete workflow for rollback_on_failure: none."""
        component1 = NoOpECO()
        component2 = FailingTestECO(fail_message="Intentional failure")

        compound = CompoundECO(
            name="complete_rollback_none",
            description="Complete rollback none test",
            components=[component1, component2],
            rollback_on_failure="none",
        )

        assert compound.metadata.parameters["rollback_on_failure"] == "none"

        design_state = Mock()
        checkpoint = Mock()
        checkpoint.restore = Mock()
        design_state.create_checkpoint = Mock(return_value=checkpoint)

        result = compound.execute_with_rollback(design_state)

        assert result.success is False
        assert not checkpoint.restore.called  # No rollback

    def test_serialization_includes_rollback_mode(self) -> None:
        """Test compound ECO serialization includes rollback mode."""
        for mode in ["all", "partial", "none"]:
            compound = CompoundECO(
                name=f"serialization_{mode}",
                description=f"Test {mode}",
                components=[NoOpECO(), BufferInsertionECO()],
                rollback_on_failure=mode,
            )

            compound_dict = compound.to_dict()
            assert compound_dict["parameters"]["rollback_on_failure"] == mode
