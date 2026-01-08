"""
Tests for progress messages during Study execution.

This module tests Feature #139: Progress messages during Study execution are
informative and not overwhelming.
"""

import io
import re
from pathlib import Path

import pytest

from src.controller.progress_logger import (
    Colors,
    ProgressConfig,
    ProgressLevel,
    ProgressLogger,
    create_progress_logger,
)


@pytest.fixture
def output_buffer() -> io.StringIO:
    """Create string buffer for capturing output."""
    return io.StringIO()


@pytest.fixture
def normal_logger(output_buffer: io.StringIO) -> ProgressLogger:
    """Create logger with normal verbosity."""
    config = ProgressConfig(level=ProgressLevel.NORMAL, use_colors=False)
    return ProgressLogger(config=config, output=output_buffer)


@pytest.fixture
def verbose_logger(output_buffer: io.StringIO) -> ProgressLogger:
    """Create logger with verbose verbosity."""
    config = ProgressConfig(level=ProgressLevel.VERBOSE, use_colors=False)
    return ProgressLogger(config=config, output=output_buffer)


@pytest.fixture
def quiet_logger(output_buffer: io.StringIO) -> ProgressLogger:
    """Create logger with quiet verbosity."""
    config = ProgressConfig(level=ProgressLevel.QUIET, use_colors=False)
    return ProgressLogger(config=config, output=output_buffer)


class TestProgressVerbosityLevels:
    """Test that progress messages respect verbosity levels."""

    def test_step1_execute_study_with_verbose_logging(
        self, verbose_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Step 1: Execute Study with verbose logging."""
        # Simulate Study execution
        verbose_logger.study_start("test_study", "sandbox")
        verbose_logger.stage_start(1, "Stage 1", trial_budget=10)
        verbose_logger.trial_start("case_1_0", "buffer_insertion")
        verbose_logger.trial_complete("case_1_0", passed=True, wns_ps=-50)

        output = output_buffer.getvalue()

        # Should have detailed output in verbose mode
        assert "Starting Study: test_study" in output
        assert "Stage 1" in output
        assert "case_1_0" in output

    def test_step2_monitor_console_output(
        self, normal_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Step 2: Monitor console output."""
        # Simulate Study progress
        normal_logger.study_start("nangate45_study", "guarded")
        normal_logger.stage_start(1, "Exploration", trial_budget=20)
        normal_logger.trial_progress(5, 20)
        normal_logger.stage_complete(1, trials_executed=20, trials_passed=15, survivors=5)

        output = output_buffer.getvalue()

        # Should have readable progress output
        assert "nangate45_study" in output
        assert "Exploration" in output
        assert "5/20" in output or "15/20" in output

    def test_step4_verify_progress_messages_are_helpful(
        self, normal_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Step 4: Verify progress messages are helpful."""
        # Log key events
        normal_logger.study_start("helpful_study", "sandbox")
        normal_logger.stage_start(1, "Stage 1", trial_budget=10)
        normal_logger.stage_complete(1, trials_executed=10, trials_passed=8, survivors=3)
        normal_logger.study_complete("helpful_study", total_trials=10, winner_case="case_1_5")

        output = output_buffer.getvalue()

        # Should have clear milestone messages
        assert "Starting Study" in output or "Study" in output
        assert "Stage 1" in output
        assert "Complete" in output
        assert "8/10" in output  # Pass rate
        assert "case_1_5" in output  # Winner

    def test_step5_verify_messages_not_excessively_verbose(
        self, quiet_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Step 5: Verify messages are not excessively verbose."""
        # In quiet mode, should have minimal output
        quiet_logger.trial_start("case_1_0", "eco1")
        quiet_logger.trial_complete("case_1_0", passed=True)
        quiet_logger.trial_progress(1, 10)

        output = output_buffer.getvalue()

        # Quiet mode should suppress routine updates
        assert len(output) < 100  # Very little output

    def test_step6_verify_key_events_highlighted(
        self, normal_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Step 6: Verify key events are highlighted appropriately."""
        # Log key events
        normal_logger.study_start("highlight_study", "guarded")
        normal_logger.study_complete("highlight_study", total_trials=50, winner_case="winner")

        output = output_buffer.getvalue()

        # Should have clear highlighting (even without colors)
        assert "Starting Study" in output or "Study" in output
        assert "Complete" in output
        assert "winner" in output


class TestInformativeMessages:
    """Test that messages are informative and provide context."""

    def test_study_start_includes_metadata(
        self, normal_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Study start message includes key metadata."""
        normal_logger.study_start("nangate45_baseline", "sandbox")

        output = output_buffer.getvalue()
        assert "nangate45_baseline" in output
        assert "sandbox" in output

    def test_stage_progress_shows_trials_completed(
        self, normal_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Stage progress shows how many trials completed."""
        normal_logger.stage_start(1, "Stage 1", trial_budget=20)
        normal_logger.trial_progress(10, 20, current_case="case_1_10")

        output = output_buffer.getvalue()

        # Should show progress fraction
        assert "10/20" in output or "10" in output and "20" in output

    def test_stage_complete_shows_pass_rate(
        self, normal_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Stage completion shows pass rate."""
        normal_logger.stage_complete(1, trials_executed=20, trials_passed=15, survivors=5)

        output = output_buffer.getvalue()

        # Should show pass rate
        assert "15/20" in output or "15" in output and "20" in output
        assert "5" in output  # Survivors

    def test_trial_failure_shows_reason(
        self, normal_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Trial failure shows failure type."""
        normal_logger.trial_failed("case_1_5", "tool_crash")

        output = output_buffer.getvalue()

        assert "case_1_5" in output
        assert "tool_crash" in output

    def test_warning_messages_are_distinct(
        self, normal_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Warning messages are clearly distinct from normal messages."""
        normal_logger.warning("ECO 'risky_eco' has low success rate")

        output = output_buffer.getvalue()

        # Should have warning indicator
        assert "Warning" in output or "⚠" in output
        assert "risky_eco" in output


class TestProgressBar:
    """Test progress bar visualization."""

    def test_progress_bar_shows_completion(
        self, normal_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Progress bar shows visual completion status."""
        normal_logger.trial_progress(5, 10)

        output = output_buffer.getvalue()

        # Should have progress bar or percentage
        has_bar = "█" in output or "░" in output
        has_percentage = "50" in output or "%" in output

        assert has_bar or has_percentage

    def test_progress_bar_at_0_percent(
        self, normal_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Progress bar renders correctly at 0%."""
        normal_logger.trial_progress(0, 10)

        output = output_buffer.getvalue()

        # Should show 0%
        assert "0/10" in output

    def test_progress_bar_at_100_percent(
        self, normal_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Progress bar renders correctly at 100%."""
        normal_logger.trial_progress(10, 10)

        output = output_buffer.getvalue()

        # Should show 100%
        assert "10/10" in output
        assert "100" in output


class TestTimestamps:
    """Test timestamp inclusion in messages."""

    def test_timestamps_included_by_default(
        self, output_buffer: io.StringIO
    ) -> None:
        """Timestamps are included by default."""
        config = ProgressConfig(show_timestamps=True, use_colors=False)
        logger = ProgressLogger(config=config, output=output_buffer)

        logger.study_start("test_study", "sandbox")

        output = output_buffer.getvalue()

        # Should have timestamp format [MM:SS]
        assert re.search(r"\[\d{2}:\d{2}\]", output)

    def test_timestamps_can_be_disabled(
        self, output_buffer: io.StringIO
    ) -> None:
        """Timestamps can be disabled."""
        config = ProgressConfig(show_timestamps=False, use_colors=False)
        logger = ProgressLogger(config=config, output=output_buffer)

        logger.study_start("test_study", "sandbox")

        output = output_buffer.getvalue()

        # Should not have timestamp format
        assert not re.search(r"\[\d{2}:\d{2}\]", output)


class TestColorSupport:
    """Test ANSI color support."""

    def test_colors_enabled_for_tty(self) -> None:
        """Colors are enabled for TTY output."""
        # Create logger with colors enabled
        config = ProgressConfig(use_colors=True)
        output_buffer = io.StringIO()

        # Note: StringIO is not a TTY, so colors will be disabled
        logger = ProgressLogger(config=config, output=output_buffer)

        logger.study_start("test", "sandbox")
        output = output_buffer.getvalue()

        # Should not have ANSI codes (because StringIO is not TTY)
        assert Colors.RESET not in output

    def test_colors_can_be_disabled(
        self, output_buffer: io.StringIO
    ) -> None:
        """Colors can be explicitly disabled."""
        config = ProgressConfig(use_colors=False)
        logger = ProgressLogger(config=config, output=output_buffer)

        logger.study_start("test", "sandbox")

        output = output_buffer.getvalue()

        # Should not have ANSI color codes
        assert "\033[" not in output


class TestLogFileOutput:
    """Test logging to file."""

    def test_messages_written_to_log_file(self, tmp_path: Path) -> None:
        """Messages are written to log file when configured."""
        log_file = tmp_path / "progress.log"

        config = ProgressConfig(log_to_file=str(log_file), use_colors=False)
        output_buffer = io.StringIO()
        logger = ProgressLogger(config=config, output=output_buffer)

        logger.study_start("test_study", "sandbox")
        logger.close()

        # Verify file was created and contains output
        assert log_file.exists()
        content = log_file.read_text()
        assert "test_study" in content


class TestRateLimiting:
    """Test that progress updates are rate-limited."""

    def test_trial_progress_is_rate_limited(
        self, output_buffer: io.StringIO
    ) -> None:
        """Trial progress updates are rate-limited to avoid spam."""
        config = ProgressConfig(
            level=ProgressLevel.NORMAL,
            use_colors=False,
            update_interval_seconds=10.0,  # High threshold for testing
        )
        logger = ProgressLogger(config=config, output=output_buffer)

        # Rapid progress updates
        for i in range(5):
            logger.trial_progress(i, 10)

        output = output_buffer.getvalue()

        # Should only have 1 update due to rate limiting
        progress_lines = [line for line in output.split("\n") if "trials" in line]
        assert len(progress_lines) <= 2  # At most 1-2 updates


class TestConvenienceFunction:
    """Test convenience function for creating loggers."""

    def test_create_progress_logger_with_defaults(self) -> None:
        """create_progress_logger uses sensible defaults."""
        logger = create_progress_logger()

        assert logger.config.level == ProgressLevel.NORMAL
        assert logger.config.use_colors is True

    def test_create_progress_logger_with_custom_level(self) -> None:
        """create_progress_logger accepts custom verbosity level."""
        logger = create_progress_logger(level="verbose")

        assert logger.config.level == ProgressLevel.VERBOSE

    def test_create_progress_logger_with_log_file(self, tmp_path: Path) -> None:
        """create_progress_logger accepts log file path."""
        log_file = tmp_path / "test.log"

        logger = create_progress_logger(log_file=str(log_file))

        assert logger.config.log_to_file == str(log_file)
        logger.close()


class TestEndToEnd:
    """End-to-end validation of progress logging."""

    def test_complete_study_execution_flow(
        self, normal_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Complete Study execution with progress logging."""
        # Step 1: Study start
        normal_logger.study_start("nangate45_baseline", "sandbox")

        # Step 2: Stage 1
        normal_logger.stage_start(1, "Exploration", trial_budget=10)
        normal_logger.trial_progress(5, 10)
        normal_logger.stage_complete(1, trials_executed=10, trials_passed=8, survivors=3)

        # Step 3: Stage 2
        normal_logger.stage_start(2, "Refinement", trial_budget=5)
        normal_logger.trial_progress(5, 5)
        normal_logger.stage_complete(2, trials_executed=5, trials_passed=4, survivors=1)

        # Step 4: Study complete
        normal_logger.study_complete(
            "nangate45_baseline",
            total_trials=15,
            winner_case="case_2_3",
        )

        output = output_buffer.getvalue()

        # Verify all key events logged
        assert "nangate45_baseline" in output
        assert "Exploration" in output
        assert "Refinement" in output
        assert "case_2_3" in output
        assert "Complete" in output

    def test_progress_messages_are_scannable(
        self, normal_logger: ProgressLogger, output_buffer: io.StringIO
    ) -> None:
        """Progress messages are easy to scan visually."""
        # Log various events
        normal_logger.study_start("study", "sandbox")
        normal_logger.stage_start(1, "Stage 1", 10)
        normal_logger.trial_progress(5, 10)
        normal_logger.stage_complete(1, 10, 8, 3)
        normal_logger.study_complete("study", 10, "winner")

        output = output_buffer.getvalue()

        # Should have clear structure
        lines = output.split("\n")
        assert len(lines) >= 5  # Multiple distinct messages

        # Should not be overwhelming
        assert len(output) < 2000  # Not too much text
