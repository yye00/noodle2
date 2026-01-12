"""
Tests for F265: Warm-start priors can be inspected before study execution.

Feature: noodle2 show-priors command displays loaded ECO priors
with provenance, weights, and confidence scores before study execution.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from src.controller.eco import ECOEffectiveness, ECOPrior
from src.controller.prior_sharing import PriorExporter, PriorProvenance, PriorRepository


class TestShowPriorsCommand:
    """Test show-priors CLI command."""

    @pytest.fixture
    def sample_prior_repository(self, tmp_path: Path) -> Path:
        """Create a sample prior repository file for testing.

        Returns:
            Path to the prior repository JSON file
        """
        # Create sample ECO effectiveness data
        eco_data = {
            "buffer_insertion": ECOEffectiveness(
                eco_name="buffer_insertion",
                total_applications=50,
                successful_applications=45,
                failed_applications=5,
                average_wns_improvement_ps=125.5,
                best_wns_improvement_ps=450.0,
                worst_wns_degradation_ps=-20.0,
                prior=ECOPrior.TRUSTED,
            ),
            "gate_sizing": ECOEffectiveness(
                eco_name="gate_sizing",
                total_applications=30,
                successful_applications=28,
                failed_applications=2,
                average_wns_improvement_ps=85.3,
                best_wns_improvement_ps=200.0,
                worst_wns_degradation_ps=-10.0,
                prior=ECOPrior.TRUSTED,
            ),
            "routing_detour": ECOEffectiveness(
                eco_name="routing_detour",
                total_applications=20,
                successful_applications=12,
                failed_applications=8,
                average_wns_improvement_ps=35.0,
                best_wns_improvement_ps=100.0,
                worst_wns_degradation_ps=-50.0,
                prior=ECOPrior.MIXED,
            ),
        }

        # Create repository with provenance
        output_path = tmp_path / "test_priors.json"
        exporter = PriorExporter()
        exporter.export_priors(
            study_id="nangate45_baseline",
            eco_effectiveness_map=eco_data,
            output_path=output_path,
            snapshot_hash="abc123def456",
            metadata={"completion_time": "2026-01-10T12:00:00Z"},
        )

        return output_path

    def test_step1_configure_warm_start(self, sample_prior_repository: Path) -> None:
        """Step 1: Configure warm-start (verified by fixture)."""
        # Repository file exists and is valid JSON
        assert sample_prior_repository.exists()

        with open(sample_prior_repository) as f:
            data = json.load(f)

        assert "eco_priors" in data
        assert "provenance" in data
        assert len(data["eco_priors"]) == 3

    def test_step2_execute_show_priors_command(self, sample_prior_repository: Path) -> None:
        """Step 2: Execute: noodle2 show-priors --study <repository>."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.cli",
                "show-priors",
                "--study",
                str(sample_prior_repository),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert len(result.stdout) > 0, "No output produced"

    def test_step3_verify_loaded_priors_displayed(
        self, sample_prior_repository: Path
    ) -> None:
        """Step 3: Verify loaded priors are displayed."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.cli",
                "show-priors",
                "--study",
                str(sample_prior_repository),
            ],
            capture_output=True,
            text=True,
        )

        output = result.stdout

        # All ECOs should be listed
        assert "buffer_insertion" in output
        assert "gate_sizing" in output
        assert "routing_detour" in output

        # Effectiveness data should be shown
        assert "Total Applications" in output or "total_applications" in output.lower()
        assert "Successful" in output or "successful" in output.lower()

    def test_step4_verify_source_study_provenance_shown(
        self, sample_prior_repository: Path
    ) -> None:
        """Step 4: Verify source study provenance is shown."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.cli",
                "show-priors",
                "--study",
                str(sample_prior_repository),
            ],
            capture_output=True,
            text=True,
        )

        output = result.stdout

        # Provenance information should be displayed
        assert "nangate45_baseline" in output
        assert "Source" in output or "Provenance" in output or "Study ID" in output
        assert "abc123def456" in output  # Snapshot hash

    def test_step5_verify_weights_and_confidence_displayed(
        self, sample_prior_repository: Path
    ) -> None:
        """Step 5: Verify weights and confidence scores are displayed."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.cli",
                "show-priors",
                "--study",
                str(sample_prior_repository),
            ],
            capture_output=True,
            text=True,
        )

        output = result.stdout

        # Prior/confidence information
        assert "trusted" in output.lower() or "TRUSTED" in output
        assert "mixed" in output.lower() or "MIXED" in output

        # Success rates (implicit confidence indicator)
        assert "Success" in output or "success" in output.lower()

    def test_step6_verify_operator_can_review_priors(
        self, sample_prior_repository: Path
    ) -> None:
        """Step 6: Verify operator can review priors before committing to study."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.cli",
                "show-priors",
                "--study",
                str(sample_prior_repository),
            ],
            capture_output=True,
            text=True,
        )

        output = result.stdout

        # Output should be human-readable and comprehensive
        assert len(output.split("\n")) >= 10, "Output should be multi-line"

        # Should show key metrics for decision-making
        assert "WNS" in output or "wns" in output.lower()
        assert "Improvement" in output or "improvement" in output.lower()

        # Should show all three ECOs with their stats
        for eco_name in ["buffer_insertion", "gate_sizing", "routing_detour"]:
            assert eco_name in output


class TestShowPriorsJSONFormat:
    """Test JSON output format for show-priors."""

    @pytest.fixture
    def sample_prior_repository(self, tmp_path: Path) -> Path:
        """Create sample repository."""
        eco_data = {
            "buffer_insertion": ECOEffectiveness(
                eco_name="buffer_insertion",
                total_applications=50,
                successful_applications=45,
                failed_applications=5,
                average_wns_improvement_ps=125.5,
                best_wns_improvement_ps=450.0,
                worst_wns_degradation_ps=-20.0,
                prior=ECOPrior.TRUSTED,
            ),
        }

        output_path = tmp_path / "test_priors.json"
        exporter = PriorExporter()
        exporter.export_priors(
            study_id="test_study",
            eco_effectiveness_map=eco_data,
            output_path=output_path,
        )

        return output_path

    def test_json_format_produces_valid_json(
        self, sample_prior_repository: Path
    ) -> None:
        """Test --format json produces valid JSON output."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.cli",
                "show-priors",
                "--study",
                str(sample_prior_repository),
                "--format",
                "json",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

        # Output should be valid JSON
        data = json.loads(result.stdout)
        assert "eco_priors" in data
        assert "provenance" in data


class TestShowPriorsSpecificECO:
    """Test filtering to show a specific ECO."""

    @pytest.fixture
    def sample_prior_repository(self, tmp_path: Path) -> Path:
        """Create sample repository with multiple ECOs."""
        eco_data = {
            "buffer_insertion": ECOEffectiveness(
                eco_name="buffer_insertion",
                total_applications=50,
                successful_applications=45,
                failed_applications=5,
                average_wns_improvement_ps=125.5,
                best_wns_improvement_ps=450.0,
                worst_wns_degradation_ps=-20.0,
                prior=ECOPrior.TRUSTED,
            ),
            "gate_sizing": ECOEffectiveness(
                eco_name="gate_sizing",
                total_applications=30,
                successful_applications=28,
                failed_applications=2,
                average_wns_improvement_ps=85.3,
                best_wns_improvement_ps=200.0,
                worst_wns_degradation_ps=-10.0,
                prior=ECOPrior.TRUSTED,
            ),
        }

        output_path = tmp_path / "test_priors.json"
        exporter = PriorExporter()
        exporter.export_priors(
            study_id="test_study",
            eco_effectiveness_map=eco_data,
            output_path=output_path,
        )

        return output_path

    def test_filter_to_specific_eco(self, sample_prior_repository: Path) -> None:
        """Test --eco flag filters to specific ECO."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.cli",
                "show-priors",
                "--study",
                str(sample_prior_repository),
                "--eco",
                "buffer_insertion",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = result.stdout

        # Should show buffer_insertion
        assert "buffer_insertion" in output

        # Should NOT show gate_sizing (filtered out)
        assert "gate_sizing" not in output

    def test_invalid_eco_shows_error(self, sample_prior_repository: Path) -> None:
        """Test invalid ECO name shows helpful error."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.cli",
                "show-priors",
                "--study",
                str(sample_prior_repository),
                "--eco",
                "nonexistent_eco",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        output = result.stdout + result.stderr

        # Should show error and list available ECOs
        assert "not found" in output.lower() or "error" in output.lower()
        assert "buffer_insertion" in output or "Available" in output


class TestShowPriorsErrorHandling:
    """Test error handling for show-priors command."""

    def test_nonexistent_file_shows_error(self, tmp_path: Path) -> None:
        """Test nonexistent file shows clear error."""
        nonexistent = tmp_path / "nonexistent.json"

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.cli",
                "show-priors",
                "--study",
                str(nonexistent),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "not exist" in output.lower() or "not found" in output.lower()

    def test_invalid_json_shows_error(self, tmp_path: Path) -> None:
        """Test invalid JSON file shows clear error."""
        invalid_json = tmp_path / "invalid.json"
        invalid_json.write_text("{ invalid json }")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.cli",
                "show-priors",
                "--study",
                str(invalid_json),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "json" in output.lower() or "invalid" in output.lower()

    def test_non_json_file_shows_error(self, tmp_path: Path) -> None:
        """Test non-JSON file shows helpful error."""
        text_file = tmp_path / "config.txt"
        text_file.write_text("Not a JSON file")

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.cli",
                "show-priors",
                "--study",
                str(text_file),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode != 0
        output = result.stdout + result.stderr
        assert "json" in output.lower() or "expected" in output.lower()


class TestShowPriorsCommandHelp:
    """Test show-priors command provides helpful documentation."""

    def test_show_priors_help_exists(self) -> None:
        """Test show-priors --help provides documentation."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "show-priors", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        help_text = result.stdout

        # Should explain the command
        assert "priors" in help_text.lower() or "warm-start" in help_text.lower()
        assert "--study" in help_text
        assert "--format" in help_text

    def test_help_explains_purpose(self) -> None:
        """Test help explains purpose of show-priors command."""
        result = subprocess.run(
            [sys.executable, "-m", "src.cli", "show-priors", "--help"],
            capture_output=True,
            text=True,
        )

        help_text = result.stdout

        # Should explain what priors are and why you'd inspect them
        has_explanation = (
            "inspect" in help_text.lower()
            or "review" in help_text.lower()
            or "before" in help_text.lower()
        )
        assert has_explanation, "Help should explain why to use this command"


class TestEndToEndShowPriors:
    """End-to-end validation of show-priors feature."""

    def test_complete_show_priors_workflow(self, tmp_path: Path) -> None:
        """Complete workflow: Create priors, inspect them before execution."""
        # Step 1: Create prior repository with realistic data
        eco_data = {
            "buffer_insertion": ECOEffectiveness(
                eco_name="buffer_insertion",
                total_applications=100,
                successful_applications=92,
                failed_applications=8,
                average_wns_improvement_ps=150.0,
                best_wns_improvement_ps=500.0,
                worst_wns_degradation_ps=-25.0,
                prior=ECOPrior.TRUSTED,
            ),
            "gate_sizing": ECOEffectiveness(
                eco_name="gate_sizing",
                total_applications=75,
                successful_applications=70,
                failed_applications=5,
                average_wns_improvement_ps=100.0,
                best_wns_improvement_ps=300.0,
                worst_wns_degradation_ps=-15.0,
                prior=ECOPrior.TRUSTED,
            ),
            "experimental_eco": ECOEffectiveness(
                eco_name="experimental_eco",
                total_applications=10,
                successful_applications=5,
                failed_applications=5,
                average_wns_improvement_ps=20.0,
                best_wns_improvement_ps=80.0,
                worst_wns_degradation_ps=-100.0,
                prior=ECOPrior.MIXED,
            ),
        }

        output_path = tmp_path / "complete_test_priors.json"
        exporter = PriorExporter()
        exporter.export_priors(
            study_id="nangate45_production",
            eco_effectiveness_map=eco_data,
            output_path=output_path,
            snapshot_hash="sha256:production123",
            metadata={
                "completion_time": "2026-01-10T15:30:00Z",
                "stage_count": 5,
            },
        )

        # Step 2: Inspect priors before execution
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.cli",
                "show-priors",
                "--study",
                str(output_path),
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        output = result.stdout

        # Step 3: Verify operator can make informed decision
        # Should see provenance
        assert "nangate45_production" in output
        assert "sha256:production123" in output

        # Should see all ECOs with their effectiveness
        assert "buffer_insertion" in output
        assert "gate_sizing" in output
        assert "experimental_eco" in output

        # Should see success rates to assess quality
        assert "92" in output  # buffer_insertion successful applications
        assert "70" in output  # gate_sizing successful applications
        assert "5" in output  # experimental_eco successful (risky)

        # Should see WNS improvements to assess potential impact
        assert "150" in output or "150.0" in output  # buffer_insertion avg
        assert "100" in output or "100.0" in output  # gate_sizing avg

        # Should see prior classifications
        assert "TRUSTED" in output or "trusted" in output.lower()
        assert "MIXED" in output or "mixed" in output.lower()

        # Output should be comprehensive enough for decision-making
        lines = output.split("\n")
        assert len(lines) >= 20, "Output should provide detailed information"
