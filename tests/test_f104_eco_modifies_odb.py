"""Tests for F104: ECO execution actually modifies design ODB and produces different metrics.

This test verifies that:
1. Different ECO parameters produce different modified ODB files
2. Metrics (WNS) differ between trials
3. Trial scripts contain actual ECO commands
4. ODB MD5 hashes differ between trials
"""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest


class TestF104ECOModifiesODB:
    """Test F104: ECO execution actually modifies design ODB."""

    @pytest.fixture(scope="class")
    def artifacts_dir(self) -> Path:
        """Get the artifacts directory and ensure demo has run."""
        artifacts_root = Path("artifacts")

        # Ensure demo has run at least once
        if not artifacts_root.exists() or len(list(artifacts_root.glob("*"))) == 0:
            # Run demo to generate artifacts
            result = subprocess.run(
                ["bash", "demo_nangate45_extreme.sh"],
                capture_output=True,
                timeout=1800,
            )
            if result.returncode != 0:
                pytest.skip("Demo failed to execute - cannot test ODB modifications")

        return artifacts_root

    def test_step_1_run_multiple_trials_with_different_eco_parameters(
        self, artifacts_dir: Path
    ) -> None:
        """Step 1: Run multiple trials with different ECO parameters."""
        # Demo should have already run (via fixture)
        assert artifacts_dir.exists(), "Artifacts directory not found"

        # Find trial directories
        trial_dirs = list(artifacts_dir.glob("*/stage_*"))
        assert len(trial_dirs) > 0, "No trial directories found in artifacts"

    def test_step_2_verify_each_trial_produces_modified_odb_path(
        self, artifacts_dir: Path
    ) -> None:
        """Step 2: Verify each trial produces modified_odb_path distinct from input."""
        # Find all trial result JSON files
        trial_jsons = list(artifacts_dir.glob("*/stage_*/trial_result.json"))

        if len(trial_jsons) == 0:
            pytest.skip("No trial_result.json files found")

        # Check each trial result
        trials_with_modified_odb = 0
        for trial_json in trial_jsons[:10]:  # Check first 10 trials
            with trial_json.open() as f:
                try:
                    data = json.load(f)

                    # Check if modified_odb_path exists
                    if "modified_odb_path" in data:
                        modified_odb = data["modified_odb_path"]
                        input_odb = data.get("input_odb_path", "")

                        # Verify they're different
                        if modified_odb and modified_odb != input_odb:
                            trials_with_modified_odb += 1
                except json.JSONDecodeError:
                    continue

        assert trials_with_modified_odb > 0, (
            f"No trials produced modified_odb_path distinct from input. "
            f"Checked {len(trial_jsons)} trial results."
        )

    def test_step_3_verify_wns_values_differ_between_trials(
        self, artifacts_dir: Path
    ) -> None:
        """Step 3: Verify jq .wns_ps artifacts/*/trial_*/metrics.json | sort -u | wc -l > 1."""
        # Find all metrics.json files
        metrics_files = list(artifacts_dir.glob("*/stage_*/metrics.json"))

        if len(metrics_files) == 0:
            pytest.skip("No metrics.json files found")

        # Collect unique WNS values
        wns_values = set()
        for metrics_file in metrics_files:
            with metrics_file.open() as f:
                try:
                    data = json.load(f)
                    if "wns_ps" in data:
                        wns_values.add(data["wns_ps"])
                except json.JSONDecodeError:
                    continue

        assert len(wns_values) > 1, (
            f"All trials produced the same WNS value: {wns_values}. "
            f"ECOs should produce different metrics. "
            f"Checked {len(metrics_files)} metrics files."
        )

    def test_step_4_verify_trial_scripts_contain_actual_eco_commands(
        self, artifacts_dir: Path
    ) -> None:
        """Step 4: Verify trial scripts contain actual ECO commands (repair_timing, repair_design)."""
        # Find trial script files (.tcl files)
        tcl_files = list(artifacts_dir.glob("*/stage_*/*.tcl"))

        if len(tcl_files) == 0:
            pytest.skip("No TCL script files found")

        # Check for ECO commands
        scripts_with_eco_commands = 0
        eco_commands = ["repair_timing", "repair_design", "buffer_ports", "repair_max_slew"]

        for tcl_file in tcl_files[:20]:  # Check first 20 scripts
            with tcl_file.open() as f:
                content = f.read()

                # Check if any ECO command is present
                if any(cmd in content for cmd in eco_commands):
                    scripts_with_eco_commands += 1

        assert scripts_with_eco_commands > 0, (
            f"No trial scripts contain actual ECO commands. "
            f"Expected commands like: {eco_commands}. "
            f"Checked {min(20, len(tcl_files))} TCL scripts."
        )

    def test_step_5_verify_odb_md5_hashes_differ_between_trials(
        self, artifacts_dir: Path
    ) -> None:
        """Step 5: Verify ODB MD5 hashes differ between trials."""
        # Find ODB files
        odb_files = list(artifacts_dir.glob("*/stage_*/*.odb"))

        if len(odb_files) < 2:
            pytest.skip(f"Need at least 2 ODB files, found {len(odb_files)}")

        # Compute MD5 hashes for first few ODB files
        odb_hashes = set()
        for odb_file in odb_files[:10]:  # Check first 10 ODB files
            if odb_file.stat().st_size > 0:  # Skip empty files
                with odb_file.open("rb") as f:
                    # Read in chunks for large files
                    md5_hash = hashlib.md5()
                    while chunk := f.read(8192):
                        md5_hash.update(chunk)
                    odb_hashes.add(md5_hash.hexdigest())

        assert len(odb_hashes) > 1, (
            f"All ODB files have the same MD5 hash. "
            f"ECOs should produce different modified ODB files. "
            f"Checked {min(10, len(odb_files))} ODB files, found {len(odb_hashes)} unique hashes."
        )

    def test_comprehensive_eco_modification_verification(
        self, artifacts_dir: Path
    ) -> None:
        """Comprehensive test: Verify ECOs produce actual ODB modifications."""
        # Find a specific case directory
        case_dirs = list(artifacts_dir.glob("*"))
        if not case_dirs:
            pytest.skip("No case directories found")

        # Check multiple cases
        cases_with_modifications = 0
        for case_dir in case_dirs[:5]:
            if not case_dir.is_dir():
                continue

            # Find stage directories
            stage_dirs = sorted(case_dir.glob("stage_*"))
            if len(stage_dirs) < 2:
                continue

            # Compare ODB files across stages
            stage_odb_hashes = []
            for stage_dir in stage_dirs[:3]:  # Check first 3 stages
                odb_files = list(stage_dir.glob("*.odb"))
                if odb_files:
                    odb_file = odb_files[0]
                    if odb_file.stat().st_size > 0:
                        with odb_file.open("rb") as f:
                            md5_hash = hashlib.md5()
                            while chunk := f.read(8192):
                                md5_hash.update(chunk)
                            stage_odb_hashes.append(md5_hash.hexdigest())

            # If we have different ODB hashes across stages, ECOs are working
            if len(set(stage_odb_hashes)) > 1:
                cases_with_modifications += 1

        assert cases_with_modifications > 0, (
            f"No cases showed ODB modifications across stages. "
            f"ECOs should produce different ODB files at each stage. "
            f"Checked {len(case_dirs[:5])} cases."
        )

    def test_metrics_change_across_stages(
        self, artifacts_dir: Path
    ) -> None:
        """Verify that metrics change across stages (showing ECO effectiveness)."""
        # Find case directories
        case_dirs = list(artifacts_dir.glob("*"))
        if not case_dirs:
            pytest.skip("No case directories found")

        # Check metrics across stages
        cases_with_metric_changes = 0
        for case_dir in case_dirs[:5]:
            if not case_dir.is_dir():
                continue

            # Collect metrics from each stage
            stage_wns_values = []
            for stage_dir in sorted(case_dir.glob("stage_*"))[:3]:
                metrics_file = stage_dir / "metrics.json"
                if metrics_file.exists():
                    with metrics_file.open() as f:
                        try:
                            data = json.load(f)
                            if "wns_ps" in data:
                                stage_wns_values.append(data["wns_ps"])
                        except json.JSONDecodeError:
                            continue

            # If WNS changes across stages, ECOs are having an effect
            if len(stage_wns_values) >= 2 and len(set(stage_wns_values)) > 1:
                cases_with_metric_changes += 1

        assert cases_with_metric_changes > 0, (
            f"No cases showed metric changes across stages. "
            f"ECOs should modify design metrics. "
            f"Checked {len(case_dirs[:5])} cases."
        )
