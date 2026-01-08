"""Graceful shutdown support for long-running Studies.

Handles SIGTERM and SIGINT signals to enable clean shutdown:
- Complete current trial
- Save Study checkpoint
- Shutdown Ray cluster cleanly
- Enable Study resumption from checkpoint
"""

import signal
import threading
from dataclasses import dataclass
from typing import Callable


@dataclass
class ShutdownRequest:
    """
    Represents a shutdown request from a signal.

    Attributes:
        signal_number: Signal that triggered the request (SIGTERM, SIGINT, etc.)
        shutdown_requested: Whether shutdown has been requested
        checkpoint_requested: Whether checkpoint save was requested
    """

    signal_number: int | None = None
    shutdown_requested: bool = False
    checkpoint_requested: bool = False


class GracefulShutdownHandler:
    """
    Handles graceful shutdown signals for Study execution.

    Features:
    - Registers signal handlers for SIGTERM and SIGINT
    - Thread-safe shutdown request tracking
    - Callback support for custom cleanup logic
    - Prevents abrupt termination during critical operations

    Usage:
        handler = GracefulShutdownHandler()
        handler.register()

        # In execution loop:
        if handler.should_shutdown():
            # Complete current work
            handler.save_checkpoint()
            break

        handler.unregister()  # When done
    """

    def __init__(self) -> None:
        """Initialize graceful shutdown handler."""
        self._shutdown_request = ShutdownRequest()
        self._lock = threading.Lock()
        self._original_sigterm: signal.Handlers | None = None
        self._original_sigint: signal.Handlers | None = None
        self._shutdown_callbacks: list[Callable[[], None]] = []
        self._registered = False

    def register(self) -> None:
        """
        Register signal handlers for SIGTERM and SIGINT.

        This should be called before starting Study execution.
        Saves original signal handlers to restore later.
        """
        if self._registered:
            return  # Already registered

        # Save original handlers
        self._original_sigterm = signal.signal(signal.SIGTERM, self._handle_signal)
        self._original_sigint = signal.signal(signal.SIGINT, self._handle_signal)
        self._registered = True

    def unregister(self) -> None:
        """
        Unregister signal handlers and restore original handlers.

        This should be called after Study execution completes.
        """
        if not self._registered:
            return  # Not registered

        # Restore original handlers
        if self._original_sigterm is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm)
        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)

        self._registered = False

    def _handle_signal(self, signum: int, frame: object) -> None:
        """
        Signal handler callback.

        Args:
            signum: Signal number (SIGTERM=15, SIGINT=2)
            frame: Current stack frame (unused)
        """
        with self._lock:
            signal_name = signal.Signals(signum).name
            print(f"\n⚠️  Received {signal_name} signal - initiating graceful shutdown")
            print("   Current trial will complete, then checkpoint will be saved")
            print("   Send signal again to force immediate termination\n")

            # If already requested, force immediate termination
            if self._shutdown_request.shutdown_requested:
                print("⚠️  Shutdown already requested - forcing immediate termination")
                # Restore default signal handler and re-raise
                signal.signal(signum, signal.SIG_DFL)
                signal.raise_signal(signum)
                return

            # Mark shutdown as requested
            self._shutdown_request.signal_number = signum
            self._shutdown_request.shutdown_requested = True
            self._shutdown_request.checkpoint_requested = True

            # Execute registered callbacks
            for callback in self._shutdown_callbacks:
                try:
                    callback()
                except Exception as e:
                    print(f"Warning: Shutdown callback failed: {e}")

    def should_shutdown(self) -> bool:
        """
        Check if graceful shutdown has been requested.

        Returns:
            True if shutdown was requested, False otherwise

        This should be checked frequently during execution loops
        to enable responsive shutdown.
        """
        with self._lock:
            return self._shutdown_request.shutdown_requested

    def should_save_checkpoint(self) -> bool:
        """
        Check if checkpoint save was requested.

        Returns:
            True if checkpoint save was requested, False otherwise
        """
        with self._lock:
            return self._shutdown_request.checkpoint_requested

    def get_shutdown_signal(self) -> int | None:
        """
        Get the signal number that triggered shutdown.

        Returns:
            Signal number (e.g., 15 for SIGTERM) or None if no shutdown requested
        """
        with self._lock:
            return self._shutdown_request.signal_number

    def register_shutdown_callback(self, callback: Callable[[], None]) -> None:
        """
        Register a callback to be executed when shutdown is requested.

        Args:
            callback: Function to call on shutdown (no arguments)

        Callbacks are executed in the signal handler context, so they
        should be quick and thread-safe.
        """
        self._shutdown_callbacks.append(callback)

    def clear_callbacks(self) -> None:
        """Clear all registered shutdown callbacks."""
        self._shutdown_callbacks.clear()

    def reset(self) -> None:
        """
        Reset shutdown state.

        Useful for testing or reusing the handler.
        Does not unregister signal handlers.
        """
        with self._lock:
            self._shutdown_request = ShutdownRequest()


def create_shutdown_handler() -> GracefulShutdownHandler:
    """
    Create and register a graceful shutdown handler.

    Returns:
        GracefulShutdownHandler instance with handlers registered

    Usage:
        handler = create_shutdown_handler()
        try:
            # ... execute study ...
        finally:
            handler.unregister()
    """
    handler = GracefulShutdownHandler()
    handler.register()
    return handler
