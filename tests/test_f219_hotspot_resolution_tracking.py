"""Tests for F219: Track hotspot resolution in differential congestion heatmaps."""

import json
import tempfile
from pathlib import Path

import numpy as np
import pytest

from src.visualization.heatmap_renderer import (
    generate_improvement_summary_with_hotspots,
    track_hotspot_resolution,
)


def create_test_heatmap_csv(path: Path, data: np.ndarray) -> None:
    """Create a test heatmap CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, data, delimiter=",", fmt="%.2f")


class TestHotspotResolutionTrackingF219:
    """
    Test suite for Feature F219: Track hotspot resolution in differential congestion heatmaps.

    Steps from feature_list.json:
    1. Run congestion diagnosis identifying hotspot IDs
    2. Apply ECO targeting hotspot
    3. Generate differential congestion heatmap
    4. Verify resolved_hotspots list in improvement summary
    5. Verify new_hotspots list (should be empty or minimal)
    6. Cross-reference with diagnosis hotspot IDs
    """

    def test_step_1_run_congestion_diagnosis_identifying_hotspot_ids(self) -> None:
        """Step 1: Run congestion diagnosis identifying hotspot IDs."""
        # Create baseline congestion diagnosis with hotspot IDs
        baseline_diagnosis = {
            "hot_ratio": 0.42,
            "overflow_total": 5000,
            "hotspot_count": 3,
            "hotspots": [
                {
                    "id": 1,
                    "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 200},
                    "severity": "critical",
                    "cause": "placement_density",
                    "affected_layers": ["M2", "M3"],
                    "suggested_ecos": ["spread_cells"],
                },
                {
                    "id": 2,
                    "bbox": {"x1": 300, "y1": 300, "x2": 400, "y2": 400},
                    "severity": "moderate",
                    "cause": "pin_crowding",
                    "affected_layers": ["M4"],
                    "suggested_ecos": ["buffer_insertion"],
                },
                {
                    "id": 3,
                    "bbox": {"x1": 500, "y1": 500, "x2": 600, "y2": 600},
                    "severity": "minor",
                    "cause": "routing_detour",
                    "affected_layers": ["M2"],
                    "suggested_ecos": ["optimize_routing"],
                },
            ],
        }

        # Verify hotspots have IDs
        assert "hotspots" in baseline_diagnosis
        assert len(baseline_diagnosis["hotspots"]) == 3

        for hotspot in baseline_diagnosis["hotspots"]:
            assert "id" in hotspot, "Hotspot must have ID"
            assert "bbox" in hotspot, "Hotspot must have bounding box"
            assert "severity" in hotspot, "Hotspot must have severity"

    def test_step_2_apply_eco_targeting_hotspot(self) -> None:
        """Step 2: Apply ECO targeting hotspot."""
        # Simulate ECO that resolves hotspot ID 1 (critical)
        baseline_diagnosis = {
            "hotspots": [
                {
                    "id": 1,
                    "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 200},
                    "severity": "critical",
                    "cause": "placement_density",
                },
                {
                    "id": 2,
                    "bbox": {"x1": 300, "y1": 300, "x2": 400, "y2": 400},
                    "severity": "moderate",
                    "cause": "pin_crowding",
                },
            ],
        }

        # After ECO: hotspot 1 resolved, hotspot 2 persists
        comparison_diagnosis = {
            "hotspots": [
                {
                    "id": 2,
                    "bbox": {"x1": 300, "y1": 300, "x2": 400, "y2": 400},
                    "severity": "moderate",
                    "cause": "pin_crowding",
                },
            ],
        }

        # Verify ECO effect
        assert len(baseline_diagnosis["hotspots"]) == 2
        assert len(comparison_diagnosis["hotspots"]) == 1

    def test_step_3_generate_differential_congestion_heatmap(self) -> None:
        """Step 3: Generate differential congestion heatmap."""
        # Create baseline and comparison congestion heatmaps
        baseline_congestion = np.array(
            [
                [0.3, 0.4, 0.5],
                [0.4, 0.9, 0.4],  # Hotspot
                [0.3, 0.4, 0.5],
            ]
        )

        comparison_congestion = np.array(
            [
                [0.3, 0.4, 0.5],
                [0.4, 0.6, 0.4],  # Hotspot reduced
                [0.3, 0.4, 0.5],
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_csv = Path(tmpdir) / "baseline_congestion.csv"
            comparison_csv = Path(tmpdir) / "comparison_congestion.csv"

            create_test_heatmap_csv(baseline_csv, baseline_congestion)
            create_test_heatmap_csv(comparison_csv, comparison_congestion)

            # Verify files created
            assert baseline_csv.exists()
            assert comparison_csv.exists()

    def test_step_4_verify_resolved_hotspots_list(self) -> None:
        """Step 4: Verify resolved_hotspots list in improvement summary."""
        baseline_diagnosis = {
            "hotspots": [
                {
                    "id": 1,
                    "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 200},
                    "severity": "critical",
                },
                {
                    "id": 2,
                    "bbox": {"x1": 300, "y1": 300, "x2": 400, "y2": 400},
                    "severity": "moderate",
                },
                {
                    "id": 3,
                    "bbox": {"x1": 500, "y1": 500, "x2": 600, "y2": 600},
                    "severity": "minor",
                },
            ],
        }

        # ECO resolves hotspots 1 and 3
        comparison_diagnosis = {
            "hotspots": [
                {
                    "id": 2,
                    "bbox": {"x1": 300, "y1": 300, "x2": 400, "y2": 400},
                    "severity": "moderate",
                },
            ],
        }

        tracking = track_hotspot_resolution(baseline_diagnosis, comparison_diagnosis)

        # Verify resolved_hotspots list
        assert "resolved_hotspots" in tracking
        assert len(tracking["resolved_hotspots"]) == 2
        assert 1 in tracking["resolved_hotspots"], "Hotspot 1 should be resolved"
        assert 3 in tracking["resolved_hotspots"], "Hotspot 3 should be resolved"
        assert 2 not in tracking["resolved_hotspots"], "Hotspot 2 should persist"

    def test_step_5_verify_new_hotspots_list(self) -> None:
        """Step 5: Verify new_hotspots list (should be empty or minimal)."""
        baseline_diagnosis = {
            "hotspots": [
                {
                    "id": 1,
                    "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 200},
                    "severity": "critical",
                },
            ],
        }

        # Good ECO: resolves hotspot 1, no new hotspots
        comparison_diagnosis_good = {"hotspots": []}

        tracking_good = track_hotspot_resolution(
            baseline_diagnosis, comparison_diagnosis_good
        )

        assert "new_hotspots" in tracking_good
        assert (
            len(tracking_good["new_hotspots"]) == 0
        ), "Good ECO should not create new hotspots"

        # Bad ECO: creates new hotspot
        comparison_diagnosis_bad = {
            "hotspots": [
                {
                    "id": 2,
                    "bbox": {"x1": 700, "y1": 700, "x2": 800, "y2": 800},
                    "severity": "moderate",
                },
            ],
        }

        tracking_bad = track_hotspot_resolution(
            baseline_diagnosis, comparison_diagnosis_bad
        )

        assert len(tracking_bad["new_hotspots"]) == 1, "Bad ECO created new hotspot"
        assert 2 in tracking_bad["new_hotspots"]

    def test_step_6_cross_reference_with_diagnosis_hotspot_ids(self) -> None:
        """Step 6: Cross-reference with diagnosis hotspot IDs."""
        baseline_diagnosis = {
            "hotspots": [
                {
                    "id": 10,
                    "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 200},
                    "severity": "critical",
                },
                {
                    "id": 20,
                    "bbox": {"x1": 300, "y1": 300, "x2": 400, "y2": 400},
                    "severity": "moderate",
                },
            ],
        }

        comparison_diagnosis = {
            "hotspots": [
                {
                    "id": 20,
                    "bbox": {"x1": 300, "y1": 300, "x2": 400, "y2": 400},
                    "severity": "minor",  # Severity improved
                },
            ],
        }

        tracking = track_hotspot_resolution(baseline_diagnosis, comparison_diagnosis)

        # Cross-reference IDs
        baseline_ids = {h["id"] for h in baseline_diagnosis["hotspots"]}
        comparison_ids = {h["id"] for h in comparison_diagnosis["hotspots"]}

        # Verify resolved IDs match
        assert 10 in tracking["resolved_hotspots"]
        assert 10 in baseline_ids
        assert 10 not in comparison_ids

        # Verify persisting IDs match
        assert 20 in tracking["persisting_hotspots"]
        assert 20 in baseline_ids
        assert 20 in comparison_ids

    def test_complete_f219_workflow(self) -> None:
        """Test complete F219 workflow: diagnosis -> ECO -> diff -> tracking."""
        # Step 1: Baseline diagnosis with hotspots
        baseline_diagnosis = {
            "hot_ratio": 0.5,
            "overflow_total": 8000,
            "hotspot_count": 4,
            "hotspots": [
                {
                    "id": 1,
                    "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 200},
                    "severity": "critical",
                },
                {
                    "id": 2,
                    "bbox": {"x1": 250, "y1": 250, "x2": 350, "y2": 350},
                    "severity": "critical",
                },
                {
                    "id": 3,
                    "bbox": {"x1": 400, "y1": 400, "x2": 500, "y2": 500},
                    "severity": "moderate",
                },
                {
                    "id": 4,
                    "bbox": {"x1": 550, "y1": 550, "x2": 650, "y2": 650},
                    "severity": "minor",
                },
            ],
        }

        # Step 2: Apply ECO targeting hotspots 1 and 2
        # Result: hotspots 1 and 2 resolved, hotspot 3 reduced severity, hotspot 4 persists
        comparison_diagnosis = {
            "hot_ratio": 0.25,
            "overflow_total": 2000,
            "hotspot_count": 2,
            "hotspots": [
                {
                    "id": 3,
                    "bbox": {"x1": 400, "y1": 400, "x2": 500, "y2": 500},
                    "severity": "minor",  # Improved from moderate
                },
                {
                    "id": 4,
                    "bbox": {"x1": 550, "y1": 550, "x2": 650, "y2": 650},
                    "severity": "minor",  # Unchanged
                },
            ],
        }

        # Step 3: Generate differential heatmap
        baseline_congestion = np.array(
            [
                [0.2, 0.3, 0.4, 0.3, 0.2],
                [0.3, 0.8, 0.9, 0.5, 0.3],  # Critical hotspots
                [0.4, 0.7, 0.6, 0.5, 0.4],
                [0.3, 0.5, 0.4, 0.3, 0.3],
                [0.2, 0.3, 0.3, 0.2, 0.2],
            ]
        )

        comparison_congestion = np.array(
            [
                [0.2, 0.3, 0.4, 0.3, 0.2],
                [0.3, 0.4, 0.4, 0.4, 0.3],  # Hotspots resolved
                [0.4, 0.4, 0.4, 0.4, 0.4],
                [0.3, 0.4, 0.3, 0.3, 0.3],
                [0.2, 0.3, 0.3, 0.2, 0.2],
            ]
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_csv = Path(tmpdir) / "baseline_congestion.csv"
            comparison_csv = Path(tmpdir) / "comparison_congestion.csv"
            summary_json = Path(tmpdir) / "improvement_summary.json"

            create_test_heatmap_csv(baseline_csv, baseline_congestion)
            create_test_heatmap_csv(comparison_csv, comparison_congestion)

            # Step 4-6: Generate improvement summary with hotspot tracking
            summary = generate_improvement_summary_with_hotspots(
                baseline_csv=baseline_csv,
                comparison_csv=comparison_csv,
                baseline_diagnosis=baseline_diagnosis,
                comparison_diagnosis=comparison_diagnosis,
                output_path=summary_json,
            )

            # Verify summary structure
            assert "hotspot_resolution" in summary
            tracking = summary["hotspot_resolution"]

            # Step 4: Verify resolved_hotspots
            assert "resolved_hotspots" in tracking
            assert set(tracking["resolved_hotspots"]) == {1, 2}

            # Step 5: Verify new_hotspots (should be empty)
            assert "new_hotspots" in tracking
            assert len(tracking["new_hotspots"]) == 0

            # Step 6: Cross-reference with diagnosis IDs
            assert "persisting_hotspots" in tracking
            assert set(tracking["persisting_hotspots"]) == {3, 4}

            # Verify severity changes tracked
            assert "severity_changes" in tracking
            assert tracking["severity_changes"][3] == "improved"
            assert tracking["severity_changes"][4] == "same"

            # Verify JSON export
            assert summary_json.exists()
            with open(summary_json) as f:
                loaded = json.load(f)
            assert "hotspot_resolution" in loaded

    def test_hotspot_resolution_rate_calculation(self) -> None:
        """Test that resolution rate is correctly calculated."""
        baseline_diagnosis = {
            "hotspots": [
                {"id": i, "bbox": {"x1": i * 100, "y1": 0, "x2": i * 100 + 50, "y2": 50}}
                for i in range(10)  # 10 hotspots
            ],
        }

        # Resolve 7 out of 10 hotspots (70% resolution rate)
        comparison_diagnosis = {
            "hotspots": [
                {"id": i, "bbox": {"x1": i * 100, "y1": 0, "x2": i * 100 + 50, "y2": 50}}
                for i in range(7, 10)  # Keep only hotspots 7, 8, 9
            ],
        }

        tracking = track_hotspot_resolution(baseline_diagnosis, comparison_diagnosis)

        assert tracking["resolution_rate"] == 70.0
        assert len(tracking["resolved_hotspots"]) == 7
        assert len(tracking["persisting_hotspots"]) == 3

    def test_hotspot_severity_improvement_tracking(self) -> None:
        """Test that severity improvements are tracked."""
        baseline_diagnosis = {
            "hotspots": [
                {
                    "id": 1,
                    "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 200},
                    "severity": "critical",
                },
                {
                    "id": 2,
                    "bbox": {"x1": 300, "y1": 300, "x2": 400, "y2": 400},
                    "severity": "moderate",
                },
            ],
        }

        # Hotspot 1: critical -> minor (improved)
        # Hotspot 2: moderate -> moderate (same)
        comparison_diagnosis = {
            "hotspots": [
                {
                    "id": 1,
                    "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 200},
                    "severity": "minor",
                },
                {
                    "id": 2,
                    "bbox": {"x1": 300, "y1": 300, "x2": 400, "y2": 400},
                    "severity": "moderate",
                },
            ],
        }

        tracking = track_hotspot_resolution(baseline_diagnosis, comparison_diagnosis)

        assert tracking["severity_changes"][1] == "improved"
        assert tracking["severity_changes"][2] == "same"

    def test_hotspot_severity_worsening_detection(self) -> None:
        """Test that severity worsening is detected."""
        baseline_diagnosis = {
            "hotspots": [
                {
                    "id": 1,
                    "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 200},
                    "severity": "minor",
                },
            ],
        }

        # Hotspot worsens to critical
        comparison_diagnosis = {
            "hotspots": [
                {
                    "id": 1,
                    "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 200},
                    "severity": "critical",
                },
            ],
        }

        tracking = track_hotspot_resolution(baseline_diagnosis, comparison_diagnosis)

        assert tracking["severity_changes"][1] == "worsened"

    def test_net_hotspot_reduction_metric(self) -> None:
        """Test that net hotspot reduction is calculated."""
        baseline_diagnosis = {"hotspots": [{"id": i, "bbox": {}} for i in range(5)]}

        comparison_diagnosis = {"hotspots": [{"id": i, "bbox": {}} for i in range(2)]}

        tracking = track_hotspot_resolution(baseline_diagnosis, comparison_diagnosis)

        assert tracking["baseline_hotspot_count"] == 5
        assert tracking["comparison_hotspot_count"] == 2
        assert tracking["net_hotspot_reduction"] == 3

    def test_empty_hotspots_handling(self) -> None:
        """Test handling when no hotspots exist."""
        baseline_diagnosis = {"hotspots": []}
        comparison_diagnosis = {"hotspots": []}

        tracking = track_hotspot_resolution(baseline_diagnosis, comparison_diagnosis)

        assert tracking["resolved_hotspots"] == []
        assert tracking["persisting_hotspots"] == []
        assert tracking["new_hotspots"] == []
        assert tracking["resolution_rate"] == 0.0

    def test_all_hotspots_resolved(self) -> None:
        """Test scenario where all hotspots are resolved."""
        baseline_diagnosis = {
            "hotspots": [
                {"id": 1, "bbox": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}},
                {"id": 2, "bbox": {"x1": 200, "y1": 200, "x2": 300, "y2": 300}},
            ],
        }

        comparison_diagnosis = {"hotspots": []}

        tracking = track_hotspot_resolution(baseline_diagnosis, comparison_diagnosis)

        assert tracking["resolution_rate"] == 100.0
        assert len(tracking["resolved_hotspots"]) == 2
        assert len(tracking["persisting_hotspots"]) == 0
        assert len(tracking["new_hotspots"]) == 0

    def test_improvement_summary_json_includes_hotspot_tracking(self) -> None:
        """Test that improvement summary JSON includes hotspot tracking."""
        baseline_diagnosis = {
            "hotspots": [
                {
                    "id": 1,
                    "bbox": {"x1": 100, "y1": 100, "x2": 200, "y2": 200},
                    "severity": "critical",
                },
            ],
        }

        comparison_diagnosis = {"hotspots": []}

        baseline_congestion = np.array([[0.8, 0.7], [0.7, 0.8]])
        comparison_congestion = np.array([[0.3, 0.3], [0.3, 0.3]])

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_csv = Path(tmpdir) / "baseline.csv"
            comparison_csv = Path(tmpdir) / "comparison.csv"
            summary_json = Path(tmpdir) / "summary.json"

            create_test_heatmap_csv(baseline_csv, baseline_congestion)
            create_test_heatmap_csv(comparison_csv, comparison_congestion)

            summary = generate_improvement_summary_with_hotspots(
                baseline_csv,
                comparison_csv,
                baseline_diagnosis,
                comparison_diagnosis,
                summary_json,
            )

            # Verify hotspot tracking in summary
            assert "hotspot_resolution" in summary
            assert summary["hotspot_resolution"]["resolution_rate"] == 100.0

            # Verify JSON export
            with open(summary_json) as f:
                loaded = json.load(f)

            assert "hotspot_resolution" in loaded
            assert "resolved_hotspots" in loaded["hotspot_resolution"]
            assert "new_hotspots" in loaded["hotspot_resolution"]
            assert "resolution_rate" in loaded["hotspot_resolution"]
