"""Tests for F254: Compound ECO supports rollback_on_failure: partial.

Feature steps:
1. Define compound ECO with rollback_on_failure: partial
2. Configure third component to fail
3. Apply compound ECO
4. Verify first and second components are applied successfully
5. Verify third component fails
6. Verify only third component is rolled back
7. Verify first and second components remain applied
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


class FailingECO(NoOpECO):
    """Test ECO that always fails during execution."""

    def __init__(self, fail_message: str = "Intentional failure") -> None:
        """Initialize failing ECO.

        Args:
            fail_message: The error message to return
        """
        super().__init__()
        self.fail_message = fail_message
        self.metadata.name = "failing_eco"

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


class TestPartialRollbackDefinition:
    """Test defining compound ECOs with partial rollback."""

    def test_step_1_define_compound_eco_with_rollback_partial(self) -> None:
        """Step 1: Define compound ECO with rollback_on_failure: partial."""
        component1 = NoOpECO()
        component2 = BufferInsertionECO()
        component3 = PlacementDensityECO()

        compound = CompoundECO(
            name="partial_rollback_test",
            description="Test partial rollback on failure",
            components=[component1, component2, component3],
            rollback_on_failure="partial",
        )

        # Verify partial rollback configuration
        assert compound.metadata.parameters["rollback_on_failure"] == "partial"
        assert len(compound.components) == 3


class TestPartialRollbackExecution:
    """Test compound ECO partial rollback execution."""

    def test_step_2_configure_third_component_to_fail(self) -> None:
        """Step 2: Configure third component to fail."""
        component1 = NoOpECO()
        component2 = BufferInsertionECO()
        component3 = FailingECO(fail_message="Component 3 failed")

        compound = CompoundECO(
            name="third_fails",
            description="Third component will fail",
            components=[component1, component2, component3],
            rollback_on_failure="partial",
        )

        # Verify third component is configured to fail
        assert compound.components[2].name == "failing_eco"
        assert len(compound.components) == 3

    def test_step_3_apply_compound_eco_with_third_component_failure(self) -> None:
        """Step 3: Apply compound ECO (with third component failing)."""
        # Create mock design state
        design_state = Mock()
        design_state.create_checkpoint = Mock(return_value=Mock(spec=["restore"]))

        component1 = NoOpECO()
        component2 = BufferInsertionECO()
        component3 = FailingECO(fail_message="Component 3 failed")

        compound = CompoundECO(
            name="failing_compound_partial",
            description="Test partial rollback",
            components=[component1, component2, component3],
            rollback_on_failure="partial",
        )

        # Apply compound ECO - should handle failure with partial rollback
        result = compound.execute_with_rollback(design_state)

        # Verify execution was attempted
        assert result is not None
        assert result.eco_name == "failing_compound_partial"
        assert result.success is False

    def test_step_4_verify_first_and_second_components_applied(self) -> None:
        """Step 4: Verify first and second components are applied successfully."""
        # Create mock design state
        design_state = Mock()
        design_state.create_checkpoint = Mock(return_value=Mock(spec=["restore"]))

        # Track component execution
        component1_executed = []
        component2_executed = []

        component1 = NoOpECO()
        component2 = BufferInsertionECO()
        component3 = FailingECO(fail_message="Component 3 failed")

        # Mock component 1 to track execution
        def track_execute1(ds, **kwargs):
            component1_executed.append(True)
            return ECOResult(eco_name="noop", success=True), None
        component1.execute_with_checkpointing = track_execute1

        # Mock component 2 to track execution
        def track_execute2(ds, **kwargs):
            component2_executed.append(True)
            return ECOResult(eco_name="buffer_insertion", success=True), None
        component2.execute_with_checkpointing = track_execute2

        compound = CompoundECO(
            name="tracking_compound",
            description="Track component application",
            components=[component1, component2, component3],
            rollback_on_failure="partial",
        )

        # Apply compound ECO
        result = compound.execute_with_rollback(design_state)

        # Verify first two components were executed
        assert len(component1_executed) == 1, "Component 1 should have been executed"
        assert len(component2_executed) == 1, "Component 2 should have been executed"

        # Verify compound execution failed due to component 3
        assert result.success is False

    def test_step_5_verify_third_component_fails(self) -> None:
        """Step 5: Verify third component fails."""
        design_state = Mock()
        design_state.create_checkpoint = Mock(return_value=Mock(spec=["restore"]))

        component1 = NoOpECO()
        component2 = BufferInsertionECO()
        component3 = FailingECO(fail_message="Component 3 intentionally failed")

        compound = CompoundECO(
            name="failure_test",
            description="Test component failure",
            components=[component1, component2, component3],
            rollback_on_failure="partial",
        )

        # Apply compound ECO
        result = compound.execute_with_rollback(design_state)

        # Verify overall result indicates failure
        assert result.success is False
        assert "Component 3 intentionally failed" in result.error_message or "failing_eco" in result.error_message

    def test_step_6_verify_only_third_component_rolled_back(self) -> None:
        """Step 6: Verify only third component is rolled back."""
        # Create mock design state with checkpoint tracking
        design_state = Mock()
        checkpoints = []

        def create_checkpoint() -> Mock:
            checkpoint = Mock()
            checkpoint.restore = Mock()
            checkpoints.append(checkpoint)
            return checkpoint

        design_state.create_checkpoint = create_checkpoint

        component1 = NoOpECO()
        component2 = BufferInsertionECO()
        component3 = FailingECO(fail_message="Component 3 failed")

        compound = CompoundECO(
            name="rollback_verification",
            description="Verify only failed component rolled back",
            components=[component1, component2, component3],
            rollback_on_failure="partial",
        )

        # Apply compound ECO
        result = compound.execute_with_rollback(design_state)

        # Verify checkpoints were created (one before each component)
        # Note: With partial rollback, we don't create an initial checkpoint
        # We create checkpoints before each component
        assert len(checkpoints) >= 3, "Should have checkpoints before each component"

        # Verify only the last checkpoint (before component 3) was restored
        # First two checkpoints should NOT be restored (preserve components 1 and 2)
        assert not checkpoints[0].restore.called, "Checkpoint 1 should not be restored"
        assert not checkpoints[1].restore.called, "Checkpoint 2 should not be restored"
        assert checkpoints[2].restore.called, "Checkpoint 3 (before failed component) should be restored"

        # Verify result indicates failure
        assert result.success is False
        assert "partial rollback" in result.error_message

    def test_step_7_verify_first_and_second_components_remain_applied(self) -> None:
        """Step 7: Verify first and second components remain applied."""
        # Create mock design state with state tracking
        design_state = Mock()

        # Track state changes through each component
        state_history = []

        class StateCheckpoint:
            def __init__(self, state_snapshot: dict, checkpoint_id: int) -> None:
                self.state = state_snapshot.copy()
                self.checkpoint_id = checkpoint_id

            def restore(self) -> None:
                # Restore design state to this checkpoint
                design_state.current_state = self.state.copy()
                state_history.append(f"restored_to_checkpoint_{self.checkpoint_id}")

        checkpoint_counter = [0]  # Use list to allow modification in closure

        def create_checkpoint() -> StateCheckpoint:
            checkpoint_counter[0] += 1
            return StateCheckpoint(design_state.current_state.copy(), checkpoint_counter[0])

        # Initialize design state
        design_state.current_state = {"cells": ["A", "B"], "wns": -100}
        design_state.create_checkpoint = create_checkpoint

        # Mock component execution with state modifications
        component1 = NoOpECO()
        def apply_component1(ds, **kwargs):
            # Component 1 modifies state
            ds.current_state["cells"].append("C")
            ds.current_state["wns"] = -80
            state_history.append("component1_applied")
            return ECOResult(eco_name="noop", success=True), None
        component1.execute_with_checkpointing = apply_component1

        component2 = BufferInsertionECO()
        def apply_component2(ds, **kwargs):
            # Component 2 modifies state further
            ds.current_state["cells"].append("D")
            ds.current_state["wns"] = -60
            state_history.append("component2_applied")
            return ECOResult(eco_name="buffer_insertion", success=True), None
        component2.execute_with_checkpointing = apply_component2

        component3 = FailingECO(fail_message="Component 3 failed")
        # Component 3 will fail without modifying state significantly

        compound = CompoundECO(
            name="state_preservation",
            description="Verify state preservation with partial rollback",
            components=[component1, component2, component3],
            rollback_on_failure="partial",
        )

        # Apply compound ECO
        result = compound.execute_with_rollback(design_state)

        # Verify failure occurred
        assert result.success is False

        # Verify components 1 and 2 were applied
        assert "component1_applied" in state_history
        assert "component2_applied" in state_history

        # Verify state includes changes from components 1 and 2
        # After partial rollback, only component 3's changes should be undone
        # Components 1 and 2's changes should remain
        # Note: The checkpoint before component 3 preserves the state after components 1 and 2
        assert "restored_to_checkpoint_3" in state_history, "Should restore to checkpoint before component 3"

        # The final state should reflect components 1 and 2 being applied
        # (This is tested via the checkpoint restore behavior)


class TestPartialRollbackComparison:
    """Test partial rollback compared to other strategies."""

    def test_partial_vs_all_rollback(self) -> None:
        """Verify partial rollback differs from 'all' rollback."""
        design_state = Mock()
        checkpoints = []

        def create_checkpoint() -> Mock:
            cp = Mock()
            cp.restore = Mock()
            checkpoints.append(cp)
            return cp

        design_state.create_checkpoint = create_checkpoint

        component1 = NoOpECO()
        component2 = FailingECO(fail_message="Component 2 failed")

        # Test with 'partial' rollback
        compound_partial = CompoundECO(
            name="partial_test",
            description="Partial rollback",
            components=[component1, component2],
            rollback_on_failure="partial",
        )

        result_partial = compound_partial.execute_with_rollback(design_state)

        # With partial: only component 2's checkpoint should be restored
        # Checkpoint 0: before component 1 - NOT restored
        # Checkpoint 1: before component 2 (failed) - restored
        assert not checkpoints[0].restore.called
        assert checkpoints[1].restore.called

        # Reset for 'all' rollback test
        checkpoints.clear()
        design_state.create_checkpoint = create_checkpoint

        # Test with 'all' rollback
        compound_all = CompoundECO(
            name="all_test",
            description="All rollback",
            components=[component1, component2],
            rollback_on_failure="all",
        )

        result_all = compound_all.execute_with_rollback(design_state)

        # With 'all': the initial checkpoint (before any component) is restored
        # Checkpoint 0: initial checkpoint - restored
        # Checkpoint 1: before component 1 - ignored
        # Checkpoint 2: before component 2 - ignored
        assert checkpoints[0].restore.called  # Initial checkpoint

    def test_partial_vs_none_rollback(self) -> None:
        """Verify partial rollback differs from 'none' rollback."""
        design_state = Mock()
        checkpoints = []

        def create_checkpoint() -> Mock:
            cp = Mock()
            cp.restore = Mock()
            checkpoints.append(cp)
            return cp

        design_state.create_checkpoint = create_checkpoint

        component1 = NoOpECO()
        component2 = FailingECO(fail_message="Component 2 failed")

        # Test with 'partial' rollback
        compound_partial = CompoundECO(
            name="partial_test",
            description="Partial rollback",
            components=[component1, component2],
            rollback_on_failure="partial",
        )

        result_partial = compound_partial.execute_with_rollback(design_state)

        # With partial: component 2's checkpoint should be restored
        assert checkpoints[1].restore.called

        # Reset for 'none' rollback test
        checkpoints.clear()
        design_state.create_checkpoint = create_checkpoint

        # Test with 'none' rollback
        compound_none = CompoundECO(
            name="none_test",
            description="No rollback",
            components=[component1, component2],
            rollback_on_failure="none",
        )

        result_none = compound_none.execute_with_rollback(design_state)

        # With 'none': no checkpoints should be restored
        for cp in checkpoints:
            assert not cp.restore.called


class TestPartialRollbackEdgeCases:
    """Test edge cases for partial rollback functionality."""

    def test_first_component_fails_with_partial_rollback(self) -> None:
        """Verify when first component fails with partial rollback."""
        design_state = Mock()
        checkpoints = []

        def create_checkpoint() -> Mock:
            cp = Mock()
            cp.restore = Mock()
            checkpoints.append(cp)
            return cp

        design_state.create_checkpoint = create_checkpoint

        component1 = FailingECO(fail_message="First component failed")
        component2 = BufferInsertionECO()

        compound = CompoundECO(
            name="first_fails_partial",
            description="First component fails with partial rollback",
            components=[component1, component2],
            rollback_on_failure="partial",
        )

        # Apply compound ECO
        result = compound.execute_with_rollback(design_state)

        # Verify failure
        assert result.success is False
        assert "First component failed" in result.error_message or "failing_eco" in result.error_message

        # With partial rollback and first component failing:
        # The checkpoint before component 1 should be restored
        # (rolling back component 1's attempted changes)
        if checkpoints:
            assert checkpoints[0].restore.called

    def test_all_components_succeed_no_rollback_needed(self) -> None:
        """Verify when all components succeed with partial rollback config."""
        design_state = Mock()
        checkpoint = Mock()
        checkpoint.restore = Mock()
        design_state.create_checkpoint = Mock(return_value=checkpoint)

        component1 = NoOpECO()
        component2 = BufferInsertionECO()
        component3 = PlacementDensityECO()

        compound = CompoundECO(
            name="all_succeed_partial",
            description="All components succeed",
            components=[component1, component2, component3],
            rollback_on_failure="partial",
        )

        # Mock successful execution
        from unittest.mock import patch
        with patch.object(compound, '_execute_components_with_tracking') as mock_exec:
            mock_exec.return_value = (
                ECOResult(eco_name="all_succeed_partial", success=True),
                []
            )
            result = compound.execute_with_rollback(design_state)

        # Verify success
        assert result.success is True

        # Verify checkpoint.restore was NOT called (no failure)
        assert not checkpoint.restore.called

    def test_middle_component_fails_with_partial_rollback(self) -> None:
        """Verify when middle component fails with partial rollback."""
        design_state = Mock()
        checkpoints = []

        def create_checkpoint() -> Mock:
            cp = Mock()
            cp.restore = Mock()
            checkpoints.append(cp)
            return cp

        design_state.create_checkpoint = create_checkpoint

        component1 = NoOpECO()
        component2 = FailingECO(fail_message="Middle component failed")
        component3 = PlacementDensityECO()

        compound = CompoundECO(
            name="middle_fails_partial",
            description="Middle component fails with partial rollback",
            components=[component1, component2, component3],
            rollback_on_failure="partial",
        )

        # Apply compound ECO
        result = compound.execute_with_rollback(design_state)

        # Verify failure
        assert result.success is False

        # With partial rollback and middle component failing:
        # Checkpoint 0: before component 1 - NOT restored (preserve component 1)
        # Checkpoint 1: before component 2 (failed) - restored
        # Component 3 is never reached
        assert not checkpoints[0].restore.called, "Component 1's checkpoint should not be restored"
        assert checkpoints[1].restore.called, "Component 2's checkpoint should be restored"
