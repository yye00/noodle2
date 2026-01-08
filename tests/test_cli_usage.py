"""
Tests for command-line interface usage messages and examples.

This module tests Feature #135: Command-line tool provides helpful
usage messages and examples.
"""

import subprocess
import sys
from pathlib import Path
from typing import List

import pytest


class TestCLIHelpMessage:
    """Test that CLI provides comprehensive help messages."""

    def test_run_help_command(self) -> None:
        """Step 1: Run noodle2 --help."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "Noodle 2" in result.stdout
        assert "noodle2" in result.stdout

    def test_help_output_is_clear_and_complete(self) -> None:
        """Step 3: Verify usage message is clear and complete."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
        )

        help_text = result.stdout

        # Check for essential components
        assert "usage:" in help_text.lower() or "noodle2" in help_text
        assert "Safety-aware" in help_text or "orchestration" in help_text
        assert "options:" in help_text.lower() or "arguments:" in help_text.lower()

        # Check that description explains what Noodle 2 does
        assert (
            "OpenROAD" in help_text
            or "physical design" in help_text.lower()
            or "ECO" in help_text
        )

    def test_subcommands_are_listed(self) -> None:
        """Step 4: Verify subcommands are listed with descriptions."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
        )

        help_text = result.stdout

        # Check for key subcommands
        expected_commands = ["run", "validate", "list", "show", "export", "progress"]

        found_commands = []
        for cmd in expected_commands:
            if cmd in help_text.lower():
                found_commands.append(cmd)

        # Should have at least 4 of these commands documented
        assert len(found_commands) >= 4, f"Only found commands: {found_commands}"

    def test_examples_are_provided(self) -> None:
        """Step 5: Verify examples are provided for common workflows."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
        )

        help_text = result.stdout

        # Check for examples section
        assert "example" in help_text.lower()

        # Check for at least one concrete example command
        has_example_command = (
            "noodle2 run" in help_text
            or "noodle2 validate" in help_text
            or "noodle2 show" in help_text
        )
        assert has_example_command, "No example commands found in help"


class TestSubcommandHelp:
    """Test that each subcommand has detailed help."""

    def test_run_command_help(self) -> None:
        """Test 'noodle2 run --help' provides detailed usage."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "run", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        help_text = result.stdout

        # Should explain what 'run' does
        assert "study" in help_text.lower()
        assert "execute" in help_text.lower() or "run" in help_text.lower()

        # Should list required arguments
        assert "--study" in help_text

    def test_validate_command_help(self) -> None:
        """Test 'noodle2 validate --help' provides detailed usage."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "validate", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        help_text = result.stdout

        assert "validate" in help_text.lower()
        assert "--study" in help_text

    def test_export_command_help(self) -> None:
        """Test 'noodle2 export --help' provides detailed usage."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "export", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        help_text = result.stdout

        assert "export" in help_text.lower()
        assert "--study" in help_text
        assert "--format" in help_text or "format" in help_text.lower()


class TestCLIVersionInfo:
    """Test that CLI provides version information."""

    def test_version_flag(self) -> None:
        """Test 'noodle2 --version' shows version."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--version"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "noodle2" in result.stdout.lower() or "0." in result.stdout


class TestCLIStructure:
    """Test that CLI has good structure and organization."""

    def test_cli_has_multiple_subcommands(self) -> None:
        """Verify CLI organizes functionality into subcommands."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
        )

        help_text = result.stdout.lower()

        # Count how many standard subcommands are mentioned
        subcommands = ["run", "validate", "list", "show", "export", "init"]
        found = sum(1 for cmd in subcommands if cmd in help_text)

        assert found >= 4, f"Only found {found} subcommands"

    def test_help_is_well_formatted(self) -> None:
        """Verify help output is readable and well-formatted."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
        )

        help_text = result.stdout

        # Check reasonable length (not too short, not too long)
        lines = help_text.split("\n")
        assert len(lines) >= 10, "Help message too short"
        assert len(lines) <= 200, "Help message too long"

        # Check for proper sections
        has_sections = (
            "usage" in help_text.lower()
            or "description" in help_text.lower()
            or "examples" in help_text.lower()
        )
        assert has_sections


class TestCLIUsability:
    """Test CLI usability features."""

    def test_no_args_shows_help(self) -> None:
        """Test that running 'noodle2' with no args shows help."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli"],
            capture_output=True,
            text=True,
        )

        # Should exit cleanly and show help
        assert result.returncode == 0
        assert len(result.stdout) > 100  # Should show help text

    def test_invalid_command_shows_error(self) -> None:
        """Test that invalid commands show helpful error."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "invalid_command"],
            capture_output=True,
            text=True,
        )

        # Should exit with error
        assert result.returncode != 0

        # Should show error message and/or help
        output = result.stdout + result.stderr
        assert len(output) > 0


class TestCLIExamples:
    """Test that CLI provides practical examples."""

    def test_help_includes_study_example(self) -> None:
        """Verify help includes example Study invocation."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
        )

        help_text = result.stdout

        # Should show how to run a Study
        has_study_example = (
            "noodle2 run" in help_text
            and ("--study" in help_text or ".yaml" in help_text)
        )
        assert has_study_example, "No Study execution example found"

    def test_help_includes_validation_example(self) -> None:
        """Verify help includes validation example."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
        )

        help_text = result.stdout

        # Should show validation workflow
        has_validation = (
            "validate" in help_text.lower()
            or "noodle2 validate" in help_text
        )
        assert has_validation, "No validation example or command found"

    def test_examples_are_concrete(self) -> None:
        """Verify examples use concrete file names, not placeholders."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
        )

        help_text = result.stdout

        # Should have concrete examples (not just <study> placeholders)
        has_concrete_examples = (
            "nangate45" in help_text.lower()
            or "asap7" in help_text.lower()
            or ".yaml" in help_text
        )
        assert has_concrete_examples, "Examples should use concrete file names"


class TestEndToEnd:
    """End-to-end tests for CLI feature validation."""

    def test_cli_provides_helpful_usage_messages(self) -> None:
        """Complete validation: CLI provides helpful usage messages."""
        # Run --help
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        help_text = result.stdout

        # Must have clear description
        assert "noodle2" in help_text.lower()
        assert len(help_text) >= 500  # Substantial help content

        # Must list subcommands
        assert "run" in help_text.lower()

        # Must provide examples
        assert "example" in help_text.lower()

        # Examples must be concrete
        assert "noodle2" in help_text

    def test_subcommand_help_is_comprehensive(self) -> None:
        """Verify subcommand help is detailed and useful."""
        # Test at least 3 subcommands
        subcommands = ["run", "validate", "export"]

        for cmd in subcommands:
            result = subprocess.run(
                [sys.executable, "-m", "src.cli", cmd, "--help"],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0, f"Failed for {cmd}"
            assert len(result.stdout) >= 100, f"Help too short for {cmd}"

    def test_cli_is_production_quality(self) -> None:
        """Verify overall CLI quality meets production standards."""
        # Main help
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
        )

        help_text = result.stdout

        # Should have all key components
        quality_checks = [
            "noodle2" in help_text.lower(),
            "example" in help_text.lower(),
            len(help_text.split("\n")) >= 20,  # Multi-line, detailed
            "run" in help_text.lower(),
            "--help" in help_text or "help" in help_text.lower(),
        ]

        passed = sum(quality_checks)
        assert passed >= 4, f"Only {passed}/5 quality checks passed"


class TestCLIDocumentation:
    """Test that CLI serves as self-documentation."""

    def test_help_explains_safety_domains(self) -> None:
        """Verify help explains key Noodle 2 concepts."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "--help"],
            capture_output=True,
            text=True,
        )

        help_text = result.stdout

        # Should mention key concepts
        has_concepts = (
            "safety" in help_text.lower()
            or "study" in help_text.lower()
            or "eco" in help_text
        )
        assert has_concepts, "Help should explain key Noodle 2 concepts"

    def test_subcommand_explains_workflow(self) -> None:
        """Verify subcommands explain their role in workflow."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "run", "--help"],
            capture_output=True,
            text=True,
        )

        help_text = result.stdout

        # Should explain what 'run' does in the Study workflow
        explains_workflow = (
            "execute" in help_text.lower()
            or "trial" in help_text.lower()
            or "stage" in help_text.lower()
        )
        assert explains_workflow, "'run' help should explain workflow"
