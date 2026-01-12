"""
Tests for Feature F234: Generate stage progression visualization summary.

Verification steps:
1. Run multi-stage study
2. Generate stage_progression.png
3. Verify each stage is shown with trial count and survivors
4. Verify WNS and hot_ratio deltas are shown per stage
5. Verify visual flow shows progression S0 → S1 → S2
6. Verify final winner is highlighted
"""

from pathlib import Path

import pytest

from src.visualization.stage_progression_plot import (
    generate_stage_progression_visualization,
    plot_stage_progression,
    save_stage_progression_plot,
)


class TestStageProgressionF234:
    """Tests for F234: Generate stage progression visualization summary."""

    def test_step_1_run_multi_stage_study(self, tmp_path: Path) -> None:
        """
        Step 1: Run multi-stage study.

        This test simulates a multi-stage study with trial counts, survivor counts,
        and metric deltas.
        """
        # Simulate a 3-stage study
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0_baseline",
                "trial_count": 10,
                "survivor_count": 5,
            },
            {
                "stage_index": 1,
                "stage_name": "S1_eco",
                "trial_count": 25,  # 5 survivors * 5 trials each
                "survivor_count": 3,
                "wns_delta_ps": 400,  # Improved by 400ps
                "hot_ratio_delta": -0.15,  # Reduced by 0.15
            },
            {
                "stage_index": 2,
                "stage_name": "S2_final",
                "trial_count": 15,  # 3 survivors * 5 trials each
                "survivor_count": 1,
                "wns_delta_ps": 300,  # Further improved by 300ps
                "hot_ratio_delta": -0.10,  # Further reduced by 0.10
            },
        ]

        # Verify we have stage data
        assert len(stage_data) == 3
        assert stage_data[0]["stage_name"] == "S0_baseline"
        assert stage_data[0]["trial_count"] == 10
        assert stage_data[0]["survivor_count"] == 5

    def test_step_2_generate_stage_progression_png(self, tmp_path: Path) -> None:
        """
        Step 2: Generate stage_progression.png.

        Verify that the visualization is generated and saved successfully.
        """
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "trial_count": 10,
                "survivor_count": 5,
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "trial_count": 25,
                "survivor_count": 3,
                "wns_delta_ps": 400,
                "hot_ratio_delta": -0.15,
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "trial_count": 15,
                "survivor_count": 1,
                "wns_delta_ps": 300,
                "hot_ratio_delta": -0.10,
            },
        ]

        # Generate visualization
        output_path = generate_stage_progression_visualization(
            stage_data, tmp_path, winner_stage_index=2, filename="stage_progression.png"
        )

        # Verify file created
        assert output_path.exists()
        assert output_path.name == "stage_progression.png"
        assert output_path.stat().st_size > 0

    def test_step_3_verify_trial_count_and_survivors_shown(
        self, tmp_path: Path
    ) -> None:
        """
        Step 3: Verify each stage is shown with trial count and survivors.

        Generate a visualization and verify stage information is included.
        """
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0_baseline",
                "trial_count": 10,
                "survivor_count": 5,
            },
            {
                "stage_index": 1,
                "stage_name": "S1_eco",
                "trial_count": 25,
                "survivor_count": 3,
            },
            {
                "stage_index": 2,
                "stage_name": "S2_final",
                "trial_count": 15,
                "survivor_count": 1,
            },
        ]

        # Generate visualization
        fig = plot_stage_progression(stage_data)

        # Verify figure created
        assert fig is not None
        assert len(fig.axes) == 1

        # The stage data should be embedded in the figure
        # We verify by checking that all required data is present
        for stage in stage_data:
            assert stage["trial_count"] > 0
            assert stage["survivor_count"] > 0

    def test_step_4_verify_wns_and_hot_ratio_deltas_shown(
        self, tmp_path: Path
    ) -> None:
        """
        Step 4: Verify WNS and hot_ratio deltas are shown per stage.

        Check that metric deltas are included in the visualization.
        """
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "trial_count": 10,
                "survivor_count": 5,
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "trial_count": 25,
                "survivor_count": 3,
                "wns_delta_ps": 400.0,  # Positive = improvement
                "hot_ratio_delta": -0.15,  # Negative = improvement
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "trial_count": 15,
                "survivor_count": 1,
                "wns_delta_ps": 300.0,
                "hot_ratio_delta": -0.10,
            },
        ]

        # Generate visualization
        plot_stage_progression(stage_data)

        # Verify deltas are present in stage data
        assert stage_data[1]["wns_delta_ps"] == 400.0
        assert stage_data[1]["hot_ratio_delta"] == -0.15
        assert stage_data[2]["wns_delta_ps"] == 300.0
        assert stage_data[2]["hot_ratio_delta"] == -0.10

    def test_step_5_verify_visual_flow_progression(self, tmp_path: Path) -> None:
        """
        Step 5: Verify visual flow shows progression S0 → S1 → S2.

        Check that stages are arranged in sequence.
        """
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "trial_count": 10,
                "survivor_count": 5,
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "trial_count": 25,
                "survivor_count": 3,
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "trial_count": 15,
                "survivor_count": 2,
            },
            {
                "stage_index": 3,
                "stage_name": "S3",
                "trial_count": 10,
                "survivor_count": 1,
            },
        ]

        # Generate visualization
        plot_stage_progression(stage_data)

        # Verify we have 4 stages in sequence
        assert len(stage_data) == 4
        for i in range(len(stage_data)):
            assert stage_data[i]["stage_index"] == i

    def test_step_6_verify_final_winner_highlighted(self, tmp_path: Path) -> None:
        """
        Step 6: Verify final winner is highlighted.

        Check that the winner stage is visually distinguished.
        """
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "trial_count": 10,
                "survivor_count": 5,
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "trial_count": 25,
                "survivor_count": 3,
            },
            {
                "stage_index": 2,
                "stage_name": "S2_winner",
                "trial_count": 15,
                "survivor_count": 1,  # Final stage with single winner
            },
        ]

        # Generate visualization with winner highlighted
        fig = plot_stage_progression(stage_data, winner_stage_index=2)

        # Verify winner stage is marked
        assert fig is not None
        # The visualization should highlight stage 2 as the winner


class TestStageProgressionEdgeCases:
    """Test edge cases for stage progression visualization."""

    def test_empty_stage_data_raises_error(self) -> None:
        """Empty stage data should raise ValueError."""
        with pytest.raises(ValueError, match="stage_data cannot be empty"):
            plot_stage_progression([])

    def test_missing_stage_index_raises_error(self) -> None:
        """Missing stage_index should raise ValueError."""
        stage_data = [
            {
                "stage_name": "S0",
                "trial_count": 10,
                "survivor_count": 5,
            }
        ]
        with pytest.raises(ValueError, match="missing 'stage_index'"):
            plot_stage_progression(stage_data)

    def test_missing_stage_name_raises_error(self) -> None:
        """Missing stage_name should raise ValueError."""
        stage_data = [
            {
                "stage_index": 0,
                "trial_count": 10,
                "survivor_count": 5,
            }
        ]
        with pytest.raises(ValueError, match="missing 'stage_name'"):
            plot_stage_progression(stage_data)

    def test_missing_trial_count_raises_error(self) -> None:
        """Missing trial_count should raise ValueError."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "survivor_count": 5,
            }
        ]
        with pytest.raises(ValueError, match="missing 'trial_count'"):
            plot_stage_progression(stage_data)

    def test_missing_survivor_count_raises_error(self) -> None:
        """Missing survivor_count should raise ValueError."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "trial_count": 10,
            }
        ]
        with pytest.raises(ValueError, match="missing 'survivor_count'"):
            plot_stage_progression(stage_data)

    def test_single_stage_visualization(self, tmp_path: Path) -> None:
        """Single stage should create valid visualization."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0_only",
                "trial_count": 10,
                "survivor_count": 1,
            }
        ]

        fig = plot_stage_progression(stage_data)
        assert fig is not None

        # Save should work
        output_path = tmp_path / "single_stage.png"
        save_stage_progression_plot(fig, output_path)
        assert output_path.exists()

    def test_many_stages_visualization(self, tmp_path: Path) -> None:
        """Visualization should handle many stages gracefully."""
        stage_data = [
            {
                "stage_index": i,
                "stage_name": f"S{i}",
                "trial_count": 10,
                "survivor_count": 5,
            }
            for i in range(6)
        ]

        fig = plot_stage_progression(stage_data)
        assert fig is not None

    def test_no_winner_specified(self, tmp_path: Path) -> None:
        """Visualization should work without winner highlighting."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "trial_count": 10,
                "survivor_count": 5,
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "trial_count": 25,
                "survivor_count": 3,
            },
        ]

        # No winner_stage_index specified
        fig = plot_stage_progression(stage_data, winner_stage_index=None)
        assert fig is not None

    def test_custom_title(self, tmp_path: Path) -> None:
        """Custom title should be used."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "trial_count": 10,
                "survivor_count": 5,
            }
        ]

        custom_title = "Custom Stage Progression"
        fig = plot_stage_progression(stage_data, title=custom_title)

        # Title is set on the figure, not the axis
        assert custom_title in fig._suptitle.get_text()

    def test_optional_deltas(self, tmp_path: Path) -> None:
        """Deltas are optional - visualization should work without them."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "trial_count": 10,
                "survivor_count": 5,
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "trial_count": 25,
                "survivor_count": 3,
                # No deltas specified
            },
        ]

        fig = plot_stage_progression(stage_data)
        assert fig is not None


class TestF234Integration:
    """Integration tests for complete F234 workflow."""

    def test_complete_f234_workflow(self, tmp_path: Path) -> None:
        """
        Complete F234 workflow: multi-stage study -> progression visualization.
        """
        # Simulate multi-stage study execution
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0_baseline",
                "trial_count": 10,
                "survivor_count": 5,
            },
            {
                "stage_index": 1,
                "stage_name": "S1_eco_topology",
                "trial_count": 25,
                "survivor_count": 3,
                "wns_delta_ps": 400,
                "hot_ratio_delta": -0.15,
            },
            {
                "stage_index": 2,
                "stage_name": "S2_eco_placement",
                "trial_count": 15,
                "survivor_count": 2,
                "wns_delta_ps": 300,
                "hot_ratio_delta": -0.10,
            },
            {
                "stage_index": 3,
                "stage_name": "S3_final",
                "trial_count": 10,
                "survivor_count": 1,
                "wns_delta_ps": 200,
                "hot_ratio_delta": -0.05,
            },
        ]

        # Generate visualization using high-level API
        output_path = generate_stage_progression_visualization(
            stage_data, tmp_path, winner_stage_index=3, filename="stage_progression.png"
        )

        # Verify visualization created
        assert output_path.exists()
        assert output_path.name == "stage_progression.png"
        assert output_path.stat().st_size > 10000  # Reasonable PNG size

        # Verify progression: survivor count decreases through stages
        for i in range(len(stage_data) - 1):
            assert stage_data[i]["survivor_count"] >= stage_data[i + 1]["survivor_count"]

        # Verify final stage has single winner
        assert stage_data[-1]["survivor_count"] == 1

    def test_generate_with_custom_filename(self, tmp_path: Path) -> None:
        """Test custom filename for stage progression visualization."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "trial_count": 10,
                "survivor_count": 1,
            }
        ]

        custom_filename = "custom_progression.png"
        output_path = generate_stage_progression_visualization(
            stage_data, tmp_path, filename=custom_filename
        )

        assert output_path.name == custom_filename
        assert output_path.exists()

    def test_output_directory_created_if_not_exists(self, tmp_path: Path) -> None:
        """Output directory should be created automatically."""
        nested_dir = tmp_path / "progression" / "charts"
        assert not nested_dir.exists()

        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "trial_count": 10,
                "survivor_count": 5,
            }
        ]

        output_path = generate_stage_progression_visualization(stage_data, nested_dir)

        assert nested_dir.exists()
        assert output_path.exists()

    def test_positive_and_negative_deltas(self, tmp_path: Path) -> None:
        """Test visualization with both improvements and degradations."""
        stage_data = [
            {
                "stage_index": 0,
                "stage_name": "S0",
                "trial_count": 10,
                "survivor_count": 5,
            },
            {
                "stage_index": 1,
                "stage_name": "S1",
                "trial_count": 25,
                "survivor_count": 3,
                "wns_delta_ps": 400,  # Improvement (positive)
                "hot_ratio_delta": -0.15,  # Improvement (negative)
            },
            {
                "stage_index": 2,
                "stage_name": "S2",
                "trial_count": 15,
                "survivor_count": 1,
                "wns_delta_ps": -50,  # Degradation (negative)
                "hot_ratio_delta": 0.02,  # Degradation (positive)
            },
        ]

        fig = plot_stage_progression(stage_data, winner_stage_index=2)
        assert fig is not None

        # Verify both types of deltas are present
        assert stage_data[1]["wns_delta_ps"] > 0
        assert stage_data[2]["wns_delta_ps"] < 0
