"""
Progress logging for Study execution.

This module provides informative, non-overwhelming progress messages during
Study execution, making it easy for operators to track progress without being
flooded with details.
"""

import logging
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TextIO


class ProgressLevel(str, Enum):
    """Verbosity level for progress messages."""

    QUIET = "quiet"  # Only critical events
    NORMAL = "normal"  # Key milestones
    VERBOSE = "verbose"  # Detailed progress
    DEBUG = "debug"  # All events


@dataclass
class ProgressConfig:
    """Configuration for progress logging."""

    level: ProgressLevel = ProgressLevel.NORMAL
    show_timestamps: bool = True
    use_colors: bool = True  # Use ANSI colors if terminal supports it
    log_to_file: str | None = None  # Optional log file path
    update_interval_seconds: float = 5.0  # Min time between trial progress updates


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright variants
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"


class ProgressLogger:
    """Logger for Study execution progress."""

    def __init__(
        self,
        config: ProgressConfig | None = None,
        output: TextIO = sys.stdout,
    ):
        """
        Initialize progress logger.

        Args:
            config: Progress configuration (uses defaults if None)
            output: Output stream (default: stdout)
        """
        self.config = config or ProgressConfig()
        self.output = output
        self.start_time = time.time()
        self.last_trial_update = 0.0

        # File logging
        self.log_file: TextIO | None = None
        if self.config.log_to_file:
            self.log_file = open(self.config.log_to_file, "w")

        # Color support detection
        self.use_colors = self.config.use_colors and hasattr(output, "isatty") and output.isatty()

    def _colorize(self, text: str, color: str) -> str:
        """Apply color to text if colors enabled."""
        if self.use_colors:
            return f"{color}{text}{Colors.RESET}"
        return text

    def _emit(self, message: str, prefix: str = "", color: str = "") -> None:
        """Emit a progress message."""
        # Build timestamp
        timestamp = ""
        if self.config.show_timestamps:
            elapsed = time.time() - self.start_time
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            timestamp = f"[{minutes:02d}:{seconds:02d}] "

        # Apply color if requested
        if color and self.use_colors:
            prefix = self._colorize(prefix, color)

        # Format full message
        full_message = f"{timestamp}{prefix}{message}"

        # Output to console
        print(full_message, file=self.output, flush=True)

        # Log to file if configured
        if self.log_file:
            print(full_message, file=self.log_file, flush=True)

    def study_start(self, study_name: str, safety_domain: str) -> None:
        """Log Study start."""
        if self.config.level == ProgressLevel.QUIET:
            return

        header = self._colorize("=" * 70, Colors.BOLD)
        self._emit("")
        self._emit(header)
        self._emit(
            f"  Starting Study: {study_name}",
            color=Colors.BOLD + Colors.BRIGHT_CYAN,
        )
        self._emit(f"  Safety Domain: {safety_domain}", color=Colors.CYAN)
        self._emit(header)
        self._emit("")

    def study_complete(
        self,
        study_name: str,
        total_trials: int,
        winner_case: str | None = None,
    ) -> None:
        """Log Study completion."""
        if self.config.level == ProgressLevel.QUIET:
            return

        elapsed = time.time() - self.start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        self._emit("")
        self._emit(
            "✓ Study Complete!",
            color=Colors.BOLD + Colors.BRIGHT_GREEN,
        )
        self._emit(f"  Total trials: {total_trials}", color=Colors.GREEN)
        self._emit(f"  Time elapsed: {minutes}m {seconds}s", color=Colors.GREEN)

        if winner_case:
            self._emit(f"  Winner: {winner_case}", color=Colors.BOLD + Colors.GREEN)

        self._emit("")

    def study_failed(self, study_name: str, error: str) -> None:
        """Log Study failure."""
        self._emit("")
        self._emit(
            "✗ Study Failed",
            color=Colors.BOLD + Colors.BRIGHT_RED,
        )
        self._emit(f"  Study: {study_name}", color=Colors.RED)
        self._emit(f"  Error: {error}", color=Colors.RED)
        self._emit("")

    def stage_start(self, stage_index: int, stage_name: str, trial_budget: int) -> None:
        """Log stage start."""
        if self.config.level == ProgressLevel.QUIET:
            return

        self._emit("")
        self._emit(
            f"▶ Stage {stage_index}: {stage_name}",
            color=Colors.BOLD + Colors.BRIGHT_BLUE,
        )
        self._emit(f"  Trial budget: {trial_budget}", color=Colors.BLUE)

    def stage_complete(
        self,
        stage_index: int,
        trials_executed: int,
        trials_passed: int,
        survivors: int,
    ) -> None:
        """Log stage completion."""
        if self.config.level == ProgressLevel.QUIET:
            return

        pass_rate = (trials_passed / trials_executed * 100) if trials_executed > 0 else 0

        self._emit(
            f"✓ Stage {stage_index} Complete",
            color=Colors.BOLD + Colors.GREEN,
        )
        self._emit(
            f"  {trials_passed}/{trials_executed} trials passed ({pass_rate:.1f}%)",
            color=Colors.GREEN,
        )
        self._emit(f"  {survivors} survivor(s) advancing", color=Colors.GREEN)

    def stage_gated(self, stage_index: int, reason: str) -> None:
        """Log stage gate failure."""
        self._emit(
            f"⚠ Stage {stage_index} Gated",
            color=Colors.BOLD + Colors.YELLOW,
        )
        self._emit(f"  Reason: {reason}", color=Colors.YELLOW)

    def trial_progress(
        self,
        completed: int,
        total: int,
        current_case: str | None = None,
    ) -> None:
        """Log trial progress (rate-limited)."""
        if self.config.level == ProgressLevel.QUIET:
            return

        # Rate limit updates
        now = time.time()
        if now - self.last_trial_update < self.config.update_interval_seconds:
            return
        self.last_trial_update = now

        percentage = (completed / total * 100) if total > 0 else 0

        # Generate progress bar
        bar_width = 30
        filled = int(bar_width * completed / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_width - filled)

        message = f"  [{bar}] {completed}/{total} trials ({percentage:.1f}%)"
        if current_case:
            message += f" - {current_case}"

        self._emit(message, color=Colors.CYAN)

    def trial_start(self, case_name: str, eco_name: str | None = None) -> None:
        """Log individual trial start."""
        if self.config.level not in [ProgressLevel.VERBOSE, ProgressLevel.DEBUG]:
            return

        message = f"  → {case_name}"
        if eco_name:
            message += f" (ECO: {eco_name})"

        self._emit(message, color=Colors.DIM)

    def trial_complete(
        self,
        case_name: str,
        passed: bool,
        wns_ps: float | None = None,
    ) -> None:
        """Log individual trial completion."""
        if self.config.level not in [ProgressLevel.VERBOSE, ProgressLevel.DEBUG]:
            return

        status = "✓" if passed else "✗"
        status_color = Colors.GREEN if passed else Colors.RED

        message = f"  {status} {case_name}"
        if wns_ps is not None:
            message += f" (WNS: {wns_ps:+.0f} ps)"

        self._emit(message, color=status_color)

    def trial_failed(self, case_name: str, failure_type: str) -> None:
        """Log trial failure."""
        if self.config.level == ProgressLevel.QUIET:
            return

        self._emit(
            f"  ✗ {case_name} - {failure_type}",
            color=Colors.RED,
        )

    def safety_gate_check(self, gate_name: str, passed: bool) -> None:
        """Log safety gate check."""
        if self.config.level not in [ProgressLevel.VERBOSE, ProgressLevel.DEBUG]:
            return

        status = "✓" if passed else "✗"
        status_color = Colors.GREEN if passed else Colors.YELLOW

        self._emit(
            f"  Safety gate: {gate_name} - {status}",
            color=status_color,
        )

    def eco_effectiveness(self, eco_name: str, success_rate: float) -> None:
        """Log ECO effectiveness update."""
        if self.config.level not in [ProgressLevel.VERBOSE, ProgressLevel.DEBUG]:
            return

        self._emit(
            f"  ECO '{eco_name}' success rate: {success_rate * 100:.1f}%",
            color=Colors.CYAN,
        )

    def warning(self, message: str) -> None:
        """Log a warning message."""
        self._emit(
            f"⚠ Warning: {message}",
            color=Colors.BOLD + Colors.YELLOW,
        )

    def info(self, message: str) -> None:
        """Log an informational message."""
        if self.config.level == ProgressLevel.QUIET:
            return

        self._emit(message, color=Colors.DIM)

    def debug(self, message: str) -> None:
        """Log a debug message."""
        if self.config.level != ProgressLevel.DEBUG:
            return

        self._emit(f"  [DEBUG] {message}", color=Colors.DIM)

    def close(self) -> None:
        """Close log file if open."""
        if self.log_file:
            self.log_file.close()
            self.log_file = None


def create_progress_logger(
    level: str = "normal",
    log_file: str | None = None,
    use_colors: bool = True,
) -> ProgressLogger:
    """
    Create a progress logger with the specified configuration.

    Args:
        level: Verbosity level ('quiet', 'normal', 'verbose', 'debug')
        log_file: Optional path to log file
        use_colors: Whether to use ANSI colors in output

    Returns:
        Configured ProgressLogger instance
    """
    config = ProgressConfig(
        level=ProgressLevel(level),
        log_to_file=log_file,
        use_colors=use_colors,
    )
    return ProgressLogger(config=config)
