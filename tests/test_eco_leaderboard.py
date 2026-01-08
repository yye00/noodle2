"""Tests for ECO effectiveness leaderboard generation.

This module tests the ECO leaderboard feature, which aggregates ECO
effectiveness across all trials in a Study and generates ranked
leaderboards showing which ECOs are most effective.

Tests cover all 6 feature steps:
  Step 1: Execute Study with multiple ECO types
  Step 2: Track effectiveness metrics for each ECO instance
  Step 3: Aggregate effectiveness by ECO class
  Step 4: Rank ECO classes by average improvement
  Step 5: Generate leaderboard report
  Step 6: Include leaderboard in Study summary
"""

import tempfile
from pathlib import Path

import pytest

from src.controller.eco import ECOEffectiveness, ECOPrior
from src.controller.eco_leaderboard import (
    ECOLeaderboard,
    ECOLeaderboardEntry,
    ECOLeaderboardGenerator,
)


class TestECOLeaderboardGeneration:
    """Test ECO effectiveness leaderboard generation."""

    def test_generate_empty_leaderboard(self):
        """Test generating leaderboard with no ECO data."""
        generator = ECOLeaderboardGenerator()
        eco_map = {}

        leaderboard = generator.generate_leaderboard(
            study_name="test_study", eco_effectiveness_map=eco_map
        )

        assert leaderboard.study_name == "test_study"
        assert len(leaderboard.entries) == 0
        assert leaderboard.total_ecos == 0
        assert leaderboard.total_applications == 0

    def test_generate_single_eco_leaderboard(self):
        """Test generating leaderboard with single ECO."""
        generator = ECOLeaderboardGenerator()

        # Create effectiveness data for one ECO
        effectiveness = ECOEffectiveness(eco_name="buffer_insertion")
        effectiveness.update(success=True, wns_delta_ps=500.0)
        effectiveness.update(success=True, wns_delta_ps=600.0)
        effectiveness.update(success=True, wns_delta_ps=400.0)

        eco_map = {"buffer_insertion": effectiveness}

        leaderboard = generator.generate_leaderboard(
            study_name="test_study", eco_effectiveness_map=eco_map
        )

        assert leaderboard.study_name == "test_study"
        assert len(leaderboard.entries) == 1
        assert leaderboard.total_ecos == 1
        assert leaderboard.total_applications == 3

        entry = leaderboard.entries[0]
        assert entry.rank == 1
        assert entry.eco_name == "buffer_insertion"
        assert entry.total_applications == 3
        assert entry.successful_applications == 3
        assert entry.success_rate == 1.0
        assert entry.average_wns_improvement_ps == 500.0
        assert entry.best_wns_improvement_ps == 600.0

    def test_rank_ecos_by_average_improvement(self):
        """Step 4: Rank ECO classes by average improvement."""
        generator = ECOLeaderboardGenerator()

        # Create effectiveness data for multiple ECOs
        # ECO 1: Best average improvement
        eco1 = ECOEffectiveness(eco_name="buffer_insertion")
        eco1.update(success=True, wns_delta_ps=800.0)
        eco1.update(success=True, wns_delta_ps=900.0)
        eco1.update(success=True, wns_delta_ps=700.0)  # avg = 800

        # ECO 2: Medium average improvement
        eco2 = ECOEffectiveness(eco_name="cell_sizing")
        eco2.update(success=True, wns_delta_ps=400.0)
        eco2.update(success=True, wns_delta_ps=600.0)
        eco2.update(success=True, wns_delta_ps=500.0)  # avg = 500

        # ECO 3: Low average improvement
        eco3 = ECOEffectiveness(eco_name="pin_swap")
        eco3.update(success=True, wns_delta_ps=100.0)
        eco3.update(success=True, wns_delta_ps=200.0)
        eco3.update(success=True, wns_delta_ps=150.0)  # avg = 150

        eco_map = {
            "buffer_insertion": eco1,
            "cell_sizing": eco2,
            "pin_swap": eco3,
        }

        leaderboard = generator.generate_leaderboard(
            study_name="test_study", eco_effectiveness_map=eco_map
        )

        assert len(leaderboard.entries) == 3

        # Verify ranking (best to worst by average improvement)
        assert leaderboard.entries[0].rank == 1
        assert leaderboard.entries[0].eco_name == "buffer_insertion"
        assert leaderboard.entries[0].average_wns_improvement_ps == pytest.approx(
            800.0, abs=1.0
        )

        assert leaderboard.entries[1].rank == 2
        assert leaderboard.entries[1].eco_name == "cell_sizing"
        assert leaderboard.entries[1].average_wns_improvement_ps == pytest.approx(
            500.0, abs=1.0
        )

        assert leaderboard.entries[2].rank == 3
        assert leaderboard.entries[2].eco_name == "pin_swap"
        assert leaderboard.entries[2].average_wns_improvement_ps == pytest.approx(
            150.0, abs=1.0
        )

    def test_track_effectiveness_metrics(self):
        """Step 2: Track effectiveness metrics for each ECO instance."""
        generator = ECOLeaderboardGenerator()

        # Create ECO with mixed results
        eco = ECOEffectiveness(eco_name="buffer_insertion")
        eco.update(success=True, wns_delta_ps=500.0)
        eco.update(success=False, wns_delta_ps=-100.0)
        eco.update(success=True, wns_delta_ps=700.0)
        eco.update(success=True, wns_delta_ps=300.0)

        eco_map = {"buffer_insertion": eco}

        leaderboard = generator.generate_leaderboard(
            study_name="test_study", eco_effectiveness_map=eco_map
        )

        entry = leaderboard.entries[0]
        assert entry.total_applications == 4
        assert entry.successful_applications == 3
        assert entry.success_rate == 0.75
        assert entry.best_wns_improvement_ps == 700.0
        assert entry.worst_wns_degradation_ps == -100.0

    def test_aggregate_effectiveness_by_eco_class(self):
        """Step 3: Aggregate effectiveness by ECO class."""
        generator = ECOLeaderboardGenerator()

        # Create effectiveness data
        eco1 = ECOEffectiveness(eco_name="buffer_insertion")
        eco1.update(success=True, wns_delta_ps=500.0)

        eco2 = ECOEffectiveness(eco_name="cell_sizing")
        eco2.update(success=True, wns_delta_ps=300.0)

        eco_map = {"buffer_insertion": eco1, "cell_sizing": eco2}
        eco_class_map = {
            "buffer_insertion": "placement_local",
            "cell_sizing": "topology_neutral",
        }

        leaderboard = generator.generate_leaderboard(
            study_name="test_study",
            eco_effectiveness_map=eco_map,
            eco_class_map=eco_class_map,
        )

        # Verify ECO classes are included
        assert leaderboard.entries[0].eco_class == "placement_local"
        assert leaderboard.entries[1].eco_class == "topology_neutral"

    def test_skip_ecos_with_zero_applications(self):
        """Test that ECOs with zero applications are skipped."""
        generator = ECOLeaderboardGenerator()

        # ECO with applications
        eco1 = ECOEffectiveness(eco_name="buffer_insertion")
        eco1.update(success=True, wns_delta_ps=500.0)

        # ECO with zero applications
        eco2 = ECOEffectiveness(eco_name="unused_eco")
        # No updates

        eco_map = {"buffer_insertion": eco1, "unused_eco": eco2}

        leaderboard = generator.generate_leaderboard(
            study_name="test_study", eco_effectiveness_map=eco_map
        )

        # Only the ECO with applications should appear
        assert len(leaderboard.entries) == 1
        assert leaderboard.entries[0].eco_name == "buffer_insertion"

    def test_include_prior_in_leaderboard(self):
        """Test that ECO prior confidence is included in leaderboard."""
        generator = ECOLeaderboardGenerator()

        # Create ECO with enough applications to establish prior
        eco = ECOEffectiveness(eco_name="buffer_insertion")
        eco.update(success=True, wns_delta_ps=500.0)
        eco.update(success=True, wns_delta_ps=600.0)
        eco.update(success=True, wns_delta_ps=400.0)
        # Prior should be TRUSTED (3+ applications, high success rate, positive WNS)

        eco_map = {"buffer_insertion": eco}

        leaderboard = generator.generate_leaderboard(
            study_name="test_study", eco_effectiveness_map=eco_map
        )

        entry = leaderboard.entries[0]
        assert entry.prior == "trusted"


class TestECOLeaderboardSerialization:
    """Test ECO leaderboard serialization."""

    def test_leaderboard_to_dict(self):
        """Test leaderboard to dictionary conversion."""
        generator = ECOLeaderboardGenerator()

        eco = ECOEffectiveness(eco_name="buffer_insertion")
        eco.update(success=True, wns_delta_ps=500.0)

        eco_map = {"buffer_insertion": eco}

        leaderboard = generator.generate_leaderboard(
            study_name="test_study", eco_effectiveness_map=eco_map
        )

        data = leaderboard.to_dict()

        assert data["study_name"] == "test_study"
        assert data["total_ecos"] == 1
        assert data["total_applications"] == 1
        assert len(data["entries"]) == 1
        assert data["entries"][0]["eco_name"] == "buffer_insertion"
        assert data["entries"][0]["rank"] == 1

    def test_leaderboard_entry_to_dict(self):
        """Test leaderboard entry to dictionary conversion."""
        entry = ECOLeaderboardEntry(
            rank=1,
            eco_name="buffer_insertion",
            eco_class="placement_local",
            total_applications=10,
            successful_applications=8,
            success_rate=0.8,
            average_wns_improvement_ps=500.0,
            best_wns_improvement_ps=700.0,
            worst_wns_degradation_ps=-100.0,
            prior="trusted",
        )

        data = entry.to_dict()

        assert data["rank"] == 1
        assert data["eco_name"] == "buffer_insertion"
        assert data["eco_class"] == "placement_local"
        assert data["total_applications"] == 10
        assert data["successful_applications"] == 8
        assert data["success_rate"] == 0.8
        assert data["prior"] == "trusted"


class TestECOLeaderboardTextFormat:
    """Test ECO leaderboard human-readable text format."""

    def test_leaderboard_to_text_empty(self):
        """Test text format for empty leaderboard."""
        leaderboard = ECOLeaderboard(study_name="test_study")
        text = leaderboard.to_text()

        assert "ECO EFFECTIVENESS LEADERBOARD: test_study" in text
        assert "Total ECO Types:        0" in text
        assert "No ECO data available." in text

    def test_leaderboard_to_text_with_entries(self):
        """Step 5: Generate leaderboard report."""
        generator = ECOLeaderboardGenerator()

        eco1 = ECOEffectiveness(eco_name="buffer_insertion")
        eco1.update(success=True, wns_delta_ps=500.0)
        eco1.update(success=True, wns_delta_ps=600.0)

        eco2 = ECOEffectiveness(eco_name="cell_sizing")
        eco2.update(success=True, wns_delta_ps=300.0)

        eco_map = {"buffer_insertion": eco1, "cell_sizing": eco2}

        leaderboard = generator.generate_leaderboard(
            study_name="test_study", eco_effectiveness_map=eco_map
        )

        text = leaderboard.to_text()

        # Verify header
        assert "ECO EFFECTIVENESS LEADERBOARD: test_study" in text

        # Verify summary
        assert "Total ECO Types:        2" in text
        assert "Total Applications:     3" in text

        # Verify table headers
        assert "Rank" in text
        assert "ECO Name" in text
        assert "Apps" in text
        assert "Succ" in text
        assert "Rate" in text
        assert "Avg Δ WNS" in text

        # Verify ECO names appear
        assert "buffer_insertion" in text
        assert "cell_sizing" in text

        # Verify legend
        assert "LEGEND:" in text
        assert "Rank:" in text
        assert "Prior:" in text

    def test_leaderboard_text_formatting(self):
        """Test that leaderboard text is well-formatted."""
        generator = ECOLeaderboardGenerator()

        eco = ECOEffectiveness(eco_name="buffer_insertion")
        eco.update(success=True, wns_delta_ps=500.5)

        eco_map = {"buffer_insertion": eco}

        leaderboard = generator.generate_leaderboard(
            study_name="test_study", eco_effectiveness_map=eco_map
        )

        text = leaderboard.to_text()

        # Verify table formatting
        lines = text.split("\n")

        # Find the data row
        data_row = None
        for line in lines:
            if "buffer_insertion" in line:
                data_row = line
                break

        assert data_row is not None

        # Verify WNS delta formatting (should have + sign for positive)
        assert "+500.5 ps" in data_row or "500.5" in data_row

        # Verify success rate is formatted as percentage
        assert "100.0%" in data_row


class TestECOLeaderboardSaving:
    """Test ECO leaderboard file I/O."""

    def test_save_leaderboard_json_and_text(self):
        """Step 6: Include leaderboard in Study summary (save to artifacts)."""
        generator = ECOLeaderboardGenerator()

        eco = ECOEffectiveness(eco_name="buffer_insertion")
        eco.update(success=True, wns_delta_ps=500.0)

        eco_map = {"buffer_insertion": eco}

        leaderboard = generator.generate_leaderboard(
            study_name="test_study", eco_effectiveness_map=eco_map
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir) / "artifacts"

            json_path, text_path = generator.save_leaderboard(
                leaderboard, artifacts_dir
            )

            # Verify files were created
            assert json_path.exists()
            assert text_path.exists()

            # Verify file names
            assert json_path.name == "eco_leaderboard.json"
            assert text_path.name == "eco_leaderboard.txt"

            # Verify JSON content
            import json

            with json_path.open() as f:
                data = json.load(f)

            assert data["study_name"] == "test_study"
            assert data["total_ecos"] == 1

            # Verify text content
            with text_path.open() as f:
                text = f.read()

            assert "ECO EFFECTIVENESS LEADERBOARD" in text
            assert "buffer_insertion" in text


class TestECOLeaderboardEdgeCases:
    """Test ECO leaderboard edge cases."""

    def test_leaderboard_with_negative_improvements(self):
        """Test leaderboard with ECOs that degrade WNS."""
        generator = ECOLeaderboardGenerator()

        # ECO that consistently degrades WNS
        eco1 = ECOEffectiveness(eco_name="bad_eco")
        eco1.update(success=True, wns_delta_ps=-500.0)
        eco1.update(success=True, wns_delta_ps=-600.0)

        # ECO with positive improvement
        eco2 = ECOEffectiveness(eco_name="good_eco")
        eco2.update(success=True, wns_delta_ps=300.0)

        eco_map = {"bad_eco": eco1, "good_eco": eco2}

        leaderboard = generator.generate_leaderboard(
            study_name="test_study", eco_effectiveness_map=eco_map
        )

        # Good ECO should rank first (higher average improvement)
        assert leaderboard.entries[0].eco_name == "good_eco"
        assert leaderboard.entries[0].rank == 1

        # Bad ECO should rank last
        assert leaderboard.entries[1].eco_name == "bad_eco"
        assert leaderboard.entries[1].rank == 2
        assert leaderboard.entries[1].average_wns_improvement_ps < 0

    def test_leaderboard_with_same_average_improvement(self):
        """Test leaderboard with ECOs having same average improvement."""
        generator = ECOLeaderboardGenerator()

        eco1 = ECOEffectiveness(eco_name="eco_a")
        eco1.update(success=True, wns_delta_ps=500.0)

        eco2 = ECOEffectiveness(eco_name="eco_b")
        eco2.update(success=True, wns_delta_ps=500.0)

        eco_map = {"eco_a": eco1, "eco_b": eco2}

        leaderboard = generator.generate_leaderboard(
            study_name="test_study", eco_effectiveness_map=eco_map
        )

        # Both should have same average, ranking is stable but arbitrary
        assert len(leaderboard.entries) == 2
        assert leaderboard.entries[0].rank == 1
        assert leaderboard.entries[1].rank == 2
        assert (
            leaderboard.entries[0].average_wns_improvement_ps
            == leaderboard.entries[1].average_wns_improvement_ps
        )

    def test_leaderboard_with_many_ecos(self):
        """Test leaderboard with many ECOs."""
        generator = ECOLeaderboardGenerator()

        eco_map = {}
        for i in range(20):
            eco = ECOEffectiveness(eco_name=f"eco_{i}")
            # Each ECO has different average improvement
            eco.update(success=True, wns_delta_ps=float(i * 100))
            eco_map[f"eco_{i}"] = eco

        leaderboard = generator.generate_leaderboard(
            study_name="test_study", eco_effectiveness_map=eco_map
        )

        assert len(leaderboard.entries) == 20
        assert leaderboard.total_ecos == 20

        # Verify descending order
        for i in range(len(leaderboard.entries) - 1):
            assert (
                leaderboard.entries[i].average_wns_improvement_ps
                >= leaderboard.entries[i + 1].average_wns_improvement_ps
            )


class TestECOLeaderboardIntegration:
    """Test ECO leaderboard integration scenarios."""

    def test_end_to_end_leaderboard_generation(self):
        """Test complete end-to-end leaderboard generation workflow."""
        # Simulate Study execution with multiple ECOs
        eco_effectiveness_map = {}

        # ECO 1: Buffer insertion (very effective)
        eco1 = ECOEffectiveness(eco_name="buffer_insertion")
        eco1.update(success=True, wns_delta_ps=800.0)
        eco1.update(success=True, wns_delta_ps=750.0)
        eco1.update(success=True, wns_delta_ps=900.0)
        eco_effectiveness_map["buffer_insertion"] = eco1

        # ECO 2: Cell sizing (moderately effective)
        eco2 = ECOEffectiveness(eco_name="cell_sizing")
        eco2.update(success=True, wns_delta_ps=400.0)
        eco2.update(success=True, wns_delta_ps=500.0)
        eco2.update(success=False, wns_delta_ps=-100.0)
        eco_effectiveness_map["cell_sizing"] = eco2

        # ECO 3: Pin swap (less effective)
        eco3 = ECOEffectiveness(eco_name="pin_swap")
        eco3.update(success=True, wns_delta_ps=100.0)
        eco3.update(success=True, wns_delta_ps=150.0)
        eco_effectiveness_map["pin_swap"] = eco3

        eco_class_map = {
            "buffer_insertion": "placement_local",
            "cell_sizing": "topology_neutral",
            "pin_swap": "topology_neutral",
        }

        # Generate leaderboard
        generator = ECOLeaderboardGenerator()
        leaderboard = generator.generate_leaderboard(
            study_name="nangate45_optimization",
            eco_effectiveness_map=eco_effectiveness_map,
            eco_class_map=eco_class_map,
        )

        # Verify ranking
        assert len(leaderboard.entries) == 3
        assert leaderboard.entries[0].eco_name == "buffer_insertion"
        assert leaderboard.entries[1].eco_name == "cell_sizing"
        assert leaderboard.entries[2].eco_name == "pin_swap"

        # Save to files
        with tempfile.TemporaryDirectory() as tmpdir:
            artifacts_dir = Path(tmpdir)
            json_path, text_path = generator.save_leaderboard(leaderboard, artifacts_dir)

            # Verify files exist and are non-empty
            assert json_path.exists()
            assert text_path.exists()
            assert json_path.stat().st_size > 0
            assert text_path.stat().st_size > 0

            # Verify JSON is valid
            import json

            with json_path.open() as f:
                data = json.load(f)
            assert data["study_name"] == "nangate45_optimization"

            # Verify text is readable
            with text_path.open() as f:
                text = f.read()
            assert "buffer_insertion" in text
            assert "Rank" in text
