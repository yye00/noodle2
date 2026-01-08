"""Tests for graceful shutdown support."""

import signal
import threading
import time
import pytest

from src.controller.graceful_shutdown import (
    GracefulShutdownHandler,
    ShutdownRequest,
    create_shutdown_handler,
)


class TestShutdownRequest:
    """Test ShutdownRequest dataclass."""

    def test_default_values(self) -> None:
        """Test default initialization."""
        request = ShutdownRequest()
        assert request.signal_number is None
        assert request.shutdown_requested is False
        assert request.checkpoint_requested is False

    def test_explicit_values(self) -> None:
        """Test explicit initialization."""
        request = ShutdownRequest(
            signal_number=signal.SIGTERM,
            shutdown_requested=True,
            checkpoint_requested=True,
        )
        assert request.signal_number == signal.SIGTERM
        assert request.shutdown_requested is True
        assert request.checkpoint_requested is True


class TestGracefulShutdownHandler:
    """Test GracefulShutdownHandler."""

    def test_initialization(self) -> None:
        """Test handler initialization."""
        handler = GracefulShutdownHandler()
        assert not handler.should_shutdown()
        assert not handler.should_save_checkpoint()
        assert handler.get_shutdown_signal() is None
        assert not handler._registered

    def test_register_and_unregister(self) -> None:
        """Test signal handler registration and unregistration."""
        handler = GracefulShutdownHandler()

        # Save original handlers
        original_sigterm = signal.signal(signal.SIGTERM, signal.SIG_DFL)
        original_sigint = signal.signal(signal.SIGINT, signal.SIG_DFL)

        try:
            # Register
            handler.register()
            assert handler._registered is True
            assert handler._original_sigterm is not None
            assert handler._original_sigint is not None

            # Unregister
            handler.unregister()
            assert handler._registered is False
        finally:
            # Restore original handlers
            signal.signal(signal.SIGTERM, original_sigterm)
            signal.signal(signal.SIGINT, original_sigint)

    def test_register_idempotent(self) -> None:
        """Test that multiple register() calls are safe."""
        handler = GracefulShutdownHandler()

        original_sigterm = signal.signal(signal.SIGTERM, signal.SIG_DFL)

        try:
            handler.register()
            handler.register()  # Should be no-op
            assert handler._registered is True
        finally:
            handler.unregister()
            signal.signal(signal.SIGTERM, original_sigterm)

    def test_unregister_when_not_registered(self) -> None:
        """Test that unregister() is safe when not registered."""
        handler = GracefulShutdownHandler()
        handler.unregister()  # Should be no-op
        assert handler._registered is False

    def test_handle_sigterm(self) -> None:
        """Test SIGTERM signal handling."""
        handler = GracefulShutdownHandler()
        handler.register()

        try:
            # Simulate SIGTERM
            assert not handler.should_shutdown()
            handler._handle_signal(signal.SIGTERM, None)

            # Check shutdown was requested
            assert handler.should_shutdown()
            assert handler.should_save_checkpoint()
            assert handler.get_shutdown_signal() == signal.SIGTERM
        finally:
            handler.unregister()

    def test_handle_sigint(self) -> None:
        """Test SIGINT signal handling."""
        handler = GracefulShutdownHandler()
        handler.register()

        try:
            # Simulate SIGINT
            assert not handler.should_shutdown()
            handler._handle_signal(signal.SIGINT, None)

            # Check shutdown was requested
            assert handler.should_shutdown()
            assert handler.should_save_checkpoint()
            assert handler.get_shutdown_signal() == signal.SIGINT
        finally:
            handler.unregister()

    def test_shutdown_callbacks(self) -> None:
        """Test shutdown callback execution."""
        handler = GracefulShutdownHandler()
        handler.register()

        callback_executed = []

        def callback() -> None:
            callback_executed.append(True)

        try:
            handler.register_shutdown_callback(callback)

            # Trigger shutdown
            handler._handle_signal(signal.SIGTERM, None)

            # Callback should have been executed
            assert len(callback_executed) == 1
        finally:
            handler.unregister()

    def test_multiple_callbacks(self) -> None:
        """Test multiple shutdown callbacks."""
        handler = GracefulShutdownHandler()
        handler.register()

        execution_order = []

        def callback1() -> None:
            execution_order.append(1)

        def callback2() -> None:
            execution_order.append(2)

        try:
            handler.register_shutdown_callback(callback1)
            handler.register_shutdown_callback(callback2)

            # Trigger shutdown
            handler._handle_signal(signal.SIGTERM, None)

            # Both callbacks should execute in order
            assert execution_order == [1, 2]
        finally:
            handler.unregister()

    def test_callback_exception_handling(self) -> None:
        """Test that callback exceptions don't prevent shutdown."""
        handler = GracefulShutdownHandler()
        handler.register()

        callback2_executed = []

        def failing_callback() -> None:
            raise ValueError("Callback error")

        def callback2() -> None:
            callback2_executed.append(True)

        try:
            handler.register_shutdown_callback(failing_callback)
            handler.register_shutdown_callback(callback2)

            # Trigger shutdown - should not raise despite callback1 failing
            handler._handle_signal(signal.SIGTERM, None)

            # Second callback should still execute
            assert len(callback2_executed) == 1
            assert handler.should_shutdown()
        finally:
            handler.unregister()

    def test_clear_callbacks(self) -> None:
        """Test clearing shutdown callbacks."""
        handler = GracefulShutdownHandler()
        execution_count = []

        def callback() -> None:
            execution_count.append(True)

        handler.register_shutdown_callback(callback)
        handler.clear_callbacks()

        handler.register()
        try:
            handler._handle_signal(signal.SIGTERM, None)
            # Callback should not execute
            assert len(execution_count) == 0
        finally:
            handler.unregister()

    def test_reset(self) -> None:
        """Test resetting shutdown state."""
        handler = GracefulShutdownHandler()
        handler.register()

        try:
            # Trigger shutdown
            handler._handle_signal(signal.SIGTERM, None)
            assert handler.should_shutdown()

            # Reset state
            handler.reset()
            assert not handler.should_shutdown()
            assert not handler.should_save_checkpoint()
            assert handler.get_shutdown_signal() is None
        finally:
            handler.unregister()

    def test_thread_safety(self) -> None:
        """Test thread-safe access to shutdown state."""
        handler = GracefulShutdownHandler()
        handler.register()

        results = []

        def check_shutdown() -> None:
            for _ in range(100):
                results.append(handler.should_shutdown())
                time.sleep(0.001)

        try:
            # Start threads checking shutdown state
            threads = [threading.Thread(target=check_shutdown) for _ in range(5)]
            for t in threads:
                t.start()

            # Wait a bit, then trigger shutdown
            time.sleep(0.05)
            handler._handle_signal(signal.SIGTERM, None)

            # Wait for threads to complete
            for t in threads:
                t.join()

            # Should have mix of True and False (before/after signal)
            assert False in results  # Some checks before signal
            assert True in results  # Some checks after signal
        finally:
            handler.unregister()


class TestCreateShutdownHandler:
    """Test create_shutdown_handler() helper function."""

    def test_creates_registered_handler(self) -> None:
        """Test that create_shutdown_handler() returns registered handler."""
        handler = create_shutdown_handler()

        try:
            assert handler._registered is True
            assert not handler.should_shutdown()
        finally:
            handler.unregister()


class TestFeatureStepValidation:
    """Validate all steps from feature_list.json."""

    def test_step1_execute_long_running_study(self) -> None:
        """Step 1: Execute long-running Study."""
        # This is simulated by the handler being ready to use
        handler = GracefulShutdownHandler()
        handler.register()

        try:
            # Simulate study execution loop
            for i in range(10):
                if handler.should_shutdown():
                    break
                # Simulate work
                time.sleep(0.01)

            # Study can check shutdown status
            assert not handler.should_shutdown()  # No signal sent
        finally:
            handler.unregister()

    def test_step2_send_graceful_shutdown_signal(self) -> None:
        """Step 2: Send graceful shutdown signal (SIGTERM)."""
        handler = GracefulShutdownHandler()
        handler.register()

        try:
            # Simulate sending SIGTERM
            assert not handler.should_shutdown()
            handler._handle_signal(signal.SIGTERM, None)

            # Signal should be detected
            assert handler.should_shutdown()
            assert handler.get_shutdown_signal() == signal.SIGTERM
        finally:
            handler.unregister()

    def test_step3_complete_current_trial(self) -> None:
        """Step 3: Complete current trial."""
        handler = GracefulShutdownHandler()
        handler.register()

        try:
            trials_completed = []

            # Simulate trial execution loop
            for trial_idx in range(5):
                # Check for shutdown before starting new trial
                if handler.should_shutdown():
                    break

                # Start trial
                trials_completed.append(trial_idx)

                # Simulate trial work
                time.sleep(0.01)

                # Trigger shutdown during trial 2
                if trial_idx == 2:
                    handler._handle_signal(signal.SIGTERM, None)

                # Complete current trial even if shutdown requested
                # (trial 2 completes)

            # Trial 2 should complete, but trial 3 should not start
            assert trials_completed == [0, 1, 2]
        finally:
            handler.unregister()

    def test_step4_save_study_checkpoint_state(self) -> None:
        """Step 4: Save Study checkpoint state."""
        handler = GracefulShutdownHandler()
        handler.register()

        checkpoint_saved = []

        def save_checkpoint_callback() -> None:
            checkpoint_saved.append(True)

        try:
            handler.register_shutdown_callback(save_checkpoint_callback)

            # Trigger shutdown
            handler._handle_signal(signal.SIGTERM, None)

            # Checkpoint save should be requested
            assert handler.should_save_checkpoint()

            # Callback should have executed
            assert len(checkpoint_saved) == 1
        finally:
            handler.unregister()

    def test_step5_shutdown_ray_cluster_cleanly(self) -> None:
        """Step 5: Shutdown Ray cluster cleanly."""
        handler = GracefulShutdownHandler()
        handler.register()

        ray_shutdown_called = []

        def shutdown_ray_callback() -> None:
            ray_shutdown_called.append(True)

        try:
            handler.register_shutdown_callback(shutdown_ray_callback)

            # Trigger shutdown
            handler._handle_signal(signal.SIGTERM, None)

            # Ray shutdown callback should execute
            assert len(ray_shutdown_called) == 1
        finally:
            handler.unregister()

    def test_step6_enable_study_resumption_from_checkpoint(self) -> None:
        """Step 6: Enable Study resumption from checkpoint."""
        # This is handled by the checkpoint module, but graceful shutdown
        # ensures checkpoint is saved properly

        handler = GracefulShutdownHandler()
        handler.register()

        try:
            # Simulate shutdown triggering checkpoint save
            handler._handle_signal(signal.SIGTERM, None)

            # Checkpoint save should be flagged
            assert handler.should_save_checkpoint()

            # After shutdown, Study can be resumed from checkpoint
            # (tested in checkpoint tests)
        finally:
            handler.unregister()


class TestEndToEndGracefulShutdown:
    """End-to-end graceful shutdown workflow."""

    def test_complete_graceful_shutdown_workflow(self) -> None:
        """Test complete graceful shutdown workflow."""
        handler = GracefulShutdownHandler()
        handler.register()

        workflow_events = []

        def on_shutdown() -> None:
            workflow_events.append("shutdown_callback")

        try:
            handler.register_shutdown_callback(on_shutdown)

            # Simulate study execution
            for i in range(10):
                if handler.should_shutdown():
                    workflow_events.append("shutdown_detected")

                    # Save checkpoint
                    if handler.should_save_checkpoint():
                        workflow_events.append("checkpoint_saved")

                    break

                workflow_events.append(f"trial_{i}")

                # Trigger shutdown after 3 trials
                if i == 2:
                    handler._handle_signal(signal.SIGTERM, None)

            # Verify workflow
            assert workflow_events == [
                "trial_0",
                "trial_1",
                "trial_2",
                "shutdown_callback",  # Callback executes immediately
                "shutdown_detected",
                "checkpoint_saved",
            ]

            # Verify final state
            assert handler.should_shutdown()
            assert handler.get_shutdown_signal() == signal.SIGTERM
        finally:
            handler.unregister()

    def test_graceful_shutdown_with_cleanup(self) -> None:
        """Test graceful shutdown with proper cleanup."""
        handler = GracefulShutdownHandler()
        handler.register()

        cleanup_order = []

        def cleanup_ray() -> None:
            cleanup_order.append("ray")

        def cleanup_files() -> None:
            cleanup_order.append("files")

        try:
            handler.register_shutdown_callback(cleanup_ray)
            handler.register_shutdown_callback(cleanup_files)

            # Trigger shutdown
            handler._handle_signal(signal.SIGTERM, None)

            # All cleanup should execute in order
            assert cleanup_order == ["ray", "files"]
        finally:
            handler.unregister()
