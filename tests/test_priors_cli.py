"""Tests for CLI priors export and import commands (F091, F092)."""

import json
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest


class TestPriorsExportCLI:
    """Tests for F091: noodle2 priors export command."""

    def test_priors_export_command_exists(self) -> None:
        """Test that the priors export command is available in CLI."""
        result = subprocess.run(
            ["uv", "run", "python", "-m", "src.cli", "priors", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "export" in result.stdout
        assert "import" in result.stdout

    def test_priors_export_with_mock_telemetry(self) -> None:
        """Test exporting priors from study telemetry."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create mock telemetry structure
            study_dir = tmpdir_path / "telemetry" / "test_study"
            study_dir.mkdir(parents=True)

            # Create mock ECO effectiveness data
            eco_effectiveness = {
                "BufferInsertionECO": {
                    "eco_name": "BufferInsertionECO",
                    "total_applications": 10,
                    "successful_applications": 8,
                    "failed_applications": 2,
                    "average_wns_improvement_ps": 75.5,
                    "best_wns_improvement_ps": 120.0,
                    "worst_wns_degradation_ps": -10.0,
                    "prior": "trusted",
                },
                "CellSizeUpECO": {
                    "eco_name": "CellSizeUpECO",
                    "total_applications": 5,
                    "successful_applications": 3,
                    "failed_applications": 2,
                    "average_wns_improvement_ps": 45.2,
                    "best_wns_improvement_ps": 80.0,
                    "worst_wns_degradation_ps": -5.0,
                    "prior": "mixed",
                },
            }

            eco_file = study_dir / "eco_effectiveness.json"
            with open(eco_file, "w") as f:
                json.dump(eco_effectiveness, f, indent=2)

            # Run export command
            output_file = tmpdir_path / "exported_priors.json"

            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "src.cli",
                    "priors",
                    "export",
                    "--study",
                    str(study_dir),
                    "--output",
                    str(output_file),
                ],
                capture_output=True,
                text=True,
                cwd=Path.cwd(),
            )

            # Verify command succeeded
            assert result.returncode == 0, f"Export failed: {result.stderr}"
            assert output_file.exists()

            # Verify exported file structure
            with open(output_file) as f:
                exported_data = json.load(f)

            assert "eco_priors" in exported_data
            assert "provenance" in exported_data

            # Verify ECO priors are present
            assert "BufferInsertionECO" in exported_data["eco_priors"]
            assert "CellSizeUpECO" in exported_data["eco_priors"]

            # Verify statistics
            buffer_eco = exported_data["eco_priors"]["BufferInsertionECO"]
            assert buffer_eco["total_applications"] == 10
            assert buffer_eco["successful_applications"] == 8
            assert buffer_eco["average_wns_improvement_ps"] == 75.5
            assert buffer_eco["prior"] == "trusted"

    def test_priors_export_with_snapshot_hash(self) -> None:
        """Test exporting priors with snapshot hash metadata."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create mock telemetry
            study_dir = tmpdir_path / "telemetry" / "test_study"
            study_dir.mkdir(parents=True)

            eco_effectiveness = {
                "TestECO": {
                    "eco_name": "TestECO",
                    "total_applications": 5,
                    "successful_applications": 4,
                    "failed_applications": 1,
                    "average_wns_improvement_ps": 50.0,
                    "best_wns_improvement_ps": 80.0,
                    "worst_wns_degradation_ps": 0.0,
                    "prior": "trusted",
                },
            }

            with open(study_dir / "eco_effectiveness.json", "w") as f:
                json.dump(eco_effectiveness, f)

            output_file = tmpdir_path / "priors.json"
            snapshot_hash = "sha256:abc123def456"

            # Export with snapshot hash
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "src.cli",
                    "priors",
                    "export",
                    "--study",
                    str(study_dir),
                    "--output",
                    str(output_file),
                    "--snapshot-hash",
                    snapshot_hash,
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            assert output_file.exists()

            # Verify snapshot hash in provenance
            with open(output_file) as f:
                data = json.load(f)

            assert data["provenance"]["source_study_snapshot_hash"] == snapshot_hash

    def test_priors_export_nonexistent_study(self) -> None:
        """Test export with nonexistent study path."""
        with TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "priors.json"

            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "src.cli",
                    "priors",
                    "export",
                    "--study",
                    "nonexistent_study",
                    "--output",
                    str(output_file),
                ],
                capture_output=True,
                text=True,
            )

            # Should fail with error
            assert result.returncode != 0
            assert "not found" in result.stdout.lower() or "not found" in result.stderr.lower()


class TestPriorsImportCLI:
    """Tests for F092: noodle2 priors import command."""

    def test_priors_import_command_exists(self) -> None:
        """Test that the priors import command is available."""
        result = subprocess.run(
            ["uv", "run", "python", "-m", "src.cli", "priors", "import", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "input" in result.stdout.lower()
        assert "weight" in result.stdout.lower()

    def test_priors_import_from_json(self) -> None:
        """Test importing priors from JSON file."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create a priors JSON file
            priors_data = {
                "eco_priors": {
                    "BufferInsertionECO": {
                        "eco_name": "BufferInsertionECO",
                        "total_applications": 10,
                        "successful_applications": 8,
                        "failed_applications": 2,
                        "average_wns_improvement_ps": 75.5,
                        "best_wns_improvement_ps": 120.0,
                        "worst_wns_degradation_ps": -10.0,
                        "prior": "trusted",
                    }
                },
                "provenance": {
                    "source_study_id": "nangate45_baseline",
                    "export_timestamp": "2024-01-01T00:00:00Z",
                    "source_study_snapshot_hash": "sha256:abc123",
                    "export_metadata": {},
                },
                "repository_metadata": {"version": "1.0"},
            }

            input_file = tmpdir_path / "priors.json"
            with open(input_file, "w") as f:
                json.dump(priors_data, f, indent=2)

            # Import priors
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "src.cli",
                    "priors",
                    "import",
                    "--input",
                    str(input_file),
                    "--weight",
                    "0.8",
                ],
                capture_output=True,
                text=True,
            )

            # Verify import succeeded
            assert result.returncode == 0, f"Import failed: {result.stderr}"
            assert "Successfully imported" in result.stdout
            assert "BufferInsertionECO" in result.stdout

    def test_priors_import_with_custom_weight(self) -> None:
        """Test importing priors with custom weight."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            priors_data = {
                "eco_priors": {
                    "TestECO": {
                        "eco_name": "TestECO",
                        "total_applications": 5,
                        "successful_applications": 4,
                        "failed_applications": 1,
                        "average_wns_improvement_ps": 50.0,
                        "best_wns_improvement_ps": 80.0,
                        "worst_wns_degradation_ps": 0.0,
                        "prior": "trusted",
                    }
                },
                "provenance": {
                    "source_study_id": "test_study",
                    "export_timestamp": "2024-01-01T00:00:00Z",
                    "export_metadata": {},
                },
                "repository_metadata": {},
            }

            input_file = tmpdir_path / "priors.json"
            with open(input_file, "w") as f:
                json.dump(priors_data, f)

            # Import with weight 0.5
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "src.cli",
                    "priors",
                    "import",
                    "--input",
                    str(input_file),
                    "--weight",
                    "0.5",
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            assert "Weight: 0.5" in result.stdout

    def test_priors_import_json_format(self) -> None:
        """Test importing priors with JSON output format."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            priors_data = {
                "eco_priors": {
                    "TestECO": {
                        "eco_name": "TestECO",
                        "total_applications": 5,
                        "successful_applications": 4,
                        "failed_applications": 1,
                        "average_wns_improvement_ps": 50.0,
                        "best_wns_improvement_ps": 80.0,
                        "worst_wns_degradation_ps": 0.0,
                        "prior": "trusted",
                    }
                },
                "provenance": {
                    "source_study_id": "test_study",
                    "export_timestamp": "2024-01-01T00:00:00Z",
                    "export_metadata": {},
                },
                "repository_metadata": {},
            }

            input_file = tmpdir_path / "priors.json"
            with open(input_file, "w") as f:
                json.dump(priors_data, f)

            # Import with JSON format
            result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "src.cli",
                    "priors",
                    "import",
                    "--input",
                    str(input_file),
                    "--format",
                    "json",
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0

            # Verify output is valid JSON
            output_data = json.loads(result.stdout)
            assert "eco_priors" in output_data
            assert "TestECO" in output_data["eco_priors"]

    def test_priors_import_nonexistent_file(self) -> None:
        """Test import with nonexistent file."""
        result = subprocess.run(
            [
                "uv",
                "run",
                "python",
                "-m",
                "src.cli",
                "priors",
                "import",
                "--input",
                "/nonexistent/priors.json",
            ],
            capture_output=True,
            text=True,
        )

        # Should fail with error
        assert result.returncode != 0
        assert "not found" in result.stdout.lower() or "not found" in result.stderr.lower()


class TestPriorsEndToEnd:
    """End-to-end tests for priors export/import workflow."""

    def test_export_then_import_workflow(self) -> None:
        """Test complete workflow: export from study, then import."""
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Step 1: Create mock study telemetry
            study_dir = tmpdir_path / "telemetry" / "test_study"
            study_dir.mkdir(parents=True)

            eco_effectiveness = {
                "BufferInsertionECO": {
                    "eco_name": "BufferInsertionECO",
                    "total_applications": 10,
                    "successful_applications": 8,
                    "failed_applications": 2,
                    "average_wns_improvement_ps": 75.5,
                    "best_wns_improvement_ps": 120.0,
                    "worst_wns_degradation_ps": -10.0,
                    "prior": "trusted",
                },
                "CellSizeUpECO": {
                    "eco_name": "CellSizeUpECO",
                    "total_applications": 5,
                    "successful_applications": 3,
                    "failed_applications": 2,
                    "average_wns_improvement_ps": 45.2,
                    "best_wns_improvement_ps": 80.0,
                    "worst_wns_degradation_ps": -5.0,
                    "prior": "mixed",
                },
            }

            with open(study_dir / "eco_effectiveness.json", "w") as f:
                json.dump(eco_effectiveness, f)

            # Step 2: Export priors
            priors_file = tmpdir_path / "priors.json"

            export_result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "src.cli",
                    "priors",
                    "export",
                    "--study",
                    str(study_dir),
                    "--output",
                    str(priors_file),
                    "--snapshot-hash",
                    "sha256:test123",
                ],
                capture_output=True,
                text=True,
            )

            assert export_result.returncode == 0
            assert priors_file.exists()

            # Step 3: Import priors
            import_result = subprocess.run(
                [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "src.cli",
                    "priors",
                    "import",
                    "--input",
                    str(priors_file),
                    "--weight",
                    "0.9",
                ],
                capture_output=True,
                text=True,
            )

            assert import_result.returncode == 0
            assert "Successfully imported 2 ECO priors" in import_result.stdout
            assert "BufferInsertionECO" in import_result.stdout
            assert "CellSizeUpECO" in import_result.stdout

            # Step 4: Verify provenance
            assert "test_study" in import_result.stdout
            assert "sha256:test123" in import_result.stdout
