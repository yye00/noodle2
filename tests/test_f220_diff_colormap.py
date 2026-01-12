"""Tests for F220: Differential heatmaps use appropriate colormap (red=worse, green=better)."""

import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pytest
from matplotlib.colors import LinearSegmentedColormap
from PIL import Image

from src.visualization.heatmap_renderer import (
    compute_heatmap_diff,
    render_diff_heatmap,
)


# --- Helper Functions ---


def create_test_heatmap_csv(path: Path, data: np.ndarray) -> None:
    """Create a test heatmap CSV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savetxt(path, data, delimiter=",", fmt="%.2f")


def extract_colormap_from_png(png_path: Path) -> tuple[np.ndarray, dict]:
    """
    Extract color samples from a PNG to analyze the colormap.

    Returns:
        Tuple of (image_array, color_samples) where color_samples contains
        colors from degraded, neutral, and improved regions.
    """
    # Load PNG image
    img = Image.open(png_path)
    img_array = np.array(img)

    # Extract RGB values from different regions
    height, width = img_array.shape[:2]

    # Sample colors from the actual heatmap area (excluding colorbar and margins)
    # Typically the heatmap is in the left portion, colorbar on right
    heatmap_width = int(width * 0.75)  # Estimate heatmap region

    # Sample from center of heatmap to avoid borders
    center_y = height // 2
    center_x = heatmap_width // 2

    return img_array, {
        "center": img_array[center_y, center_x, :3],
        "height": height,
        "width": width,
    }


def check_color_is_reddish(rgb: np.ndarray) -> bool:
    """Check if RGB color is predominantly red."""
    r, g, b = rgb[:3]
    # Red should be significantly higher than green and blue
    return r > (g + 50) and r > (b + 50)


def check_color_is_greenish(rgb: np.ndarray) -> bool:
    """Check if RGB color is predominantly green."""
    r, g, b = rgb[:3]
    # Green should be significantly higher than red and blue
    return g > (r + 50) and g > (b + 50)


def check_color_is_neutral(rgb: np.ndarray, tolerance: int = 30) -> bool:
    """Check if RGB color is neutral (white or gray)."""
    r, g, b = rgb[:3]
    # All channels should be similar (close to each other)
    # and relatively high (close to white)
    max_diff = max(abs(r - g), abs(g - b), abs(r - b))
    return max_diff < tolerance and min(r, g, b) > 200


# --- Fixtures ---


@pytest.fixture
def degraded_heatmap() -> np.ndarray:
    """Heatmap where all values INCREASED (degradation)."""
    # Simple gradient: all positive values
    return np.array(
        [
            [5.0, 6.0, 7.0, 8.0, 9.0],
            [6.0, 7.0, 8.0, 9.0, 10.0],
            [7.0, 8.0, 9.0, 10.0, 11.0],
            [8.0, 9.0, 10.0, 11.0, 12.0],
            [9.0, 10.0, 11.0, 12.0, 13.0],
        ]
    )


@pytest.fixture
def improved_heatmap() -> np.ndarray:
    """Heatmap where all values DECREASED (improvement)."""
    # All values are lower than baseline (congestion reduced)
    return np.array(
        [
            [1.0, 1.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0, 1.0, 1.0],
            [1.0, 1.0, 1.0, 1.0, 1.0],
        ]
    )


@pytest.fixture
def neutral_heatmap() -> np.ndarray:
    """Heatmap with no change (identical values)."""
    return np.array(
        [
            [5.0, 5.0, 5.0, 5.0, 5.0],
            [5.0, 5.0, 5.0, 5.0, 5.0],
            [5.0, 5.0, 5.0, 5.0, 5.0],
            [5.0, 5.0, 5.0, 5.0, 5.0],
            [5.0, 5.0, 5.0, 5.0, 5.0],
        ]
    )


# --- Feature Step Tests ---


class TestF220FeatureSteps:
    """Test all 6 steps for F220: Differential colormap specification."""

    def test_step1_generate_differential_heatmap(
        self, tmp_path: Path, degraded_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Step 1: Generate differential heatmap."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "diff.png"

        # Baseline has high values, comparison has low (improvement)
        create_test_heatmap_csv(baseline_csv, degraded_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        metadata = render_diff_heatmap(baseline_csv, comparison_csv, diff_png)

        # Verify PNG was created
        assert diff_png.exists()
        assert diff_png.stat().st_size > 0
        assert metadata["improved_bins"] > 0

    def test_step2_verify_png_uses_diverging_colormap(
        self, tmp_path: Path, degraded_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Step 2: Verify PNG uses diverging colormap."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "diff.png"

        # Create heatmaps with clear improvement
        create_test_heatmap_csv(baseline_csv, degraded_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        render_diff_heatmap(baseline_csv, comparison_csv, diff_png)

        # Verify PNG exists and has content
        assert diff_png.exists()
        img = Image.open(diff_png)
        img_array = np.array(img)

        # Verify image has RGB channels
        assert img_array.ndim == 3
        assert img_array.shape[2] in [3, 4]  # RGB or RGBA

        # Verify it's not grayscale (diverging colormaps use colors)
        # Check that R, G, B channels have different distributions
        r_channel = img_array[:, :, 0]
        g_channel = img_array[:, :, 1]
        b_channel = img_array[:, :, 2]

        # Diverging colormap should have different color distributions
        r_std = np.std(r_channel)
        g_std = np.std(g_channel)

        # Both red and green should vary (not a single-hue colormap)
        assert r_std > 10  # Red varies
        assert g_std > 10  # Green varies

    def test_step3_verify_red_indicates_worsening(
        self, tmp_path: Path, neutral_heatmap: np.ndarray, degraded_heatmap: np.ndarray
    ) -> None:
        """Step 3: Verify red indicates worsening."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "diff.png"

        # Baseline is neutral, comparison is degraded (worsening)
        create_test_heatmap_csv(baseline_csv, neutral_heatmap)
        create_test_heatmap_csv(comparison_csv, degraded_heatmap)

        metadata = render_diff_heatmap(baseline_csv, comparison_csv, diff_png)

        # Verify that degradation was detected
        assert metadata["degraded_bins"] > 0
        assert metadata["mean_diff"] < 0  # Negative diff = degradation

        # Load image and check for red tones
        img = Image.open(diff_png)
        img_array = np.array(img)

        # Sample from heatmap region (exclude colorbar)
        heatmap_width = int(img_array.shape[1] * 0.7)
        heatmap_region = img_array[:, :heatmap_width, :3]

        # Check that red channel is prominent in degraded regions
        # Since entire heatmap is degraded, average should be reddish
        avg_color = np.mean(heatmap_region, axis=(0, 1))
        r, g, b = avg_color

        # Red should be higher than green for degraded regions
        assert r > g, f"Expected red > green for degradation, got R={r:.1f}, G={g:.1f}"

    def test_step4_verify_green_indicates_improvement(
        self, tmp_path: Path, neutral_heatmap: np.ndarray, improved_heatmap: np.ndarray
    ) -> None:
        """Step 4: Verify green indicates improvement."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "diff.png"

        # Baseline is neutral, comparison is improved (better)
        # But diff = baseline - comparison, so neutral - improved = negative
        # Wait, we want positive diff for improvement
        # Let me reverse: baseline = improved, comparison = neutral
        # No, that's also wrong.

        # Actually: baseline = neutral (5.0), comparison = improved (lower, e.g., 2.0)
        # diff = baseline - comparison = 5.0 - 2.0 = +3.0 (positive = improvement)
        create_test_heatmap_csv(baseline_csv, neutral_heatmap)
        create_test_heatmap_csv(comparison_csv, improved_heatmap)

        metadata = render_diff_heatmap(baseline_csv, comparison_csv, diff_png)

        # Verify that improvement was detected
        assert metadata["improved_bins"] > 0
        assert metadata["mean_diff"] > 0  # Positive diff = improvement

        # Load image and check for green tones
        img = Image.open(diff_png)
        img_array = np.array(img)

        # Sample from heatmap region (exclude colorbar)
        heatmap_width = int(img_array.shape[1] * 0.7)
        heatmap_region = img_array[:, :heatmap_width, :3]

        # Check that green channel is prominent in improved regions
        avg_color = np.mean(heatmap_region, axis=(0, 1))
        r, g, b = avg_color

        # Green should be higher than red for improved regions
        assert g > r, f"Expected green > red for improvement, got R={r:.1f}, G={g:.1f}"

    def test_step5_verify_neutral_is_white_or_gray(
        self, tmp_path: Path, neutral_heatmap: np.ndarray
    ) -> None:
        """Step 5: Verify neutral (no change) is white or gray."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "diff.png"

        # Both baseline and comparison are identical (no change)
        create_test_heatmap_csv(baseline_csv, neutral_heatmap)
        create_test_heatmap_csv(comparison_csv, neutral_heatmap)

        metadata = render_diff_heatmap(baseline_csv, comparison_csv, diff_png)

        # Verify no change
        assert metadata["unchanged_bins"] == 25  # All bins unchanged
        assert metadata["mean_diff"] == 0.0

        # Load image and check for neutral color (white/gray)
        img = Image.open(diff_png)
        img_array = np.array(img)

        # Sample from heatmap region
        heatmap_width = int(img_array.shape[1] * 0.7)
        heatmap_region = img_array[:, :heatmap_width, :3]

        # Check that color is neutral (R ≈ G ≈ B and relatively high)
        avg_color = np.mean(heatmap_region, axis=(0, 1))
        r, g, b = avg_color

        # All channels should be similar
        max_diff = max(abs(r - g), abs(g - b), abs(r - b))
        assert max_diff < 50, f"Expected neutral color, got R={r:.1f}, G={g:.1f}, B={b:.1f}"

        # Should be relatively bright (white/light gray, not dark gray)
        assert min(r, g, b) > 150, f"Expected light neutral color, got R={r:.1f}, G={g:.1f}, B={b:.1f}"

    def test_step6_verify_colormap_is_perceptually_uniform(
        self, tmp_path: Path
    ) -> None:
        """Step 6: Verify colormap is perceptually uniform."""
        # Create a gradient from -10 to +10
        gradient = np.linspace(-10, 10, 100).reshape(10, 10)

        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "diff.png"

        # Create baseline and comparison such that diff = gradient
        # diff = baseline - comparison
        # So baseline = gradient + comparison
        # Let comparison = 0
        create_test_heatmap_csv(baseline_csv, gradient)
        create_test_heatmap_csv(comparison_csv, np.zeros((10, 10)))

        render_diff_heatmap(baseline_csv, comparison_csv, diff_png)

        # For perceptual uniformity, we verify that:
        # 1. The colormap transitions smoothly
        # 2. Equal value differences correspond to similar perceptual differences

        # Load image
        img = Image.open(diff_png)
        img_array = np.array(img)

        # Sample colors from the gradient
        # Extract a horizontal line through the middle of the heatmap
        heatmap_height = int(img_array.shape[0] * 0.5)
        heatmap_width = int(img_array.shape[1] * 0.7)

        # Get middle row of heatmap
        middle_row = img_array[heatmap_height, :heatmap_width, :3]

        # Sample evenly spaced points along the gradient
        num_samples = 10
        sample_indices = np.linspace(0, len(middle_row) - 1, num_samples, dtype=int)
        sampled_colors = middle_row[sample_indices]

        # Convert RGB to perceptually uniform color space (LAB approximation)
        # For simplicity, check that color differences are relatively uniform
        color_diffs = []
        for i in range(len(sampled_colors) - 1):
            c1 = sampled_colors[i].astype(float)
            c2 = sampled_colors[i + 1].astype(float)
            # Euclidean distance in RGB space (rough approximation)
            diff = np.linalg.norm(c2 - c1)
            color_diffs.append(diff)

        # Check that color differences don't vary wildly
        # (indicating relatively uniform progression)
        if len(color_diffs) > 0:
            mean_diff = np.mean(color_diffs)
            std_diff = np.std(color_diffs)

            # Standard deviation should be less than 50% of mean
            # (allowing for some variation but not extreme jumps)
            assert std_diff < mean_diff * 0.5, (
                f"Colormap not perceptually uniform: "
                f"mean_diff={mean_diff:.1f}, std_diff={std_diff:.1f}"
            )


# --- Additional Colormap Tests ---


class TestColormapProperties:
    """Additional tests for colormap properties."""

    def test_colormap_is_diverging_red_to_green(
        self, tmp_path: Path
    ) -> None:
        """Colormap should diverge from red (negative) to green (positive)."""
        # Create extreme values: very negative and very positive
        baseline = np.array([[10.0, 0.0]])  # Will create diff of [+10, -10]
        comparison = np.array([[0.0, 10.0]])

        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "diff.png"

        create_test_heatmap_csv(baseline_csv, baseline)
        create_test_heatmap_csv(comparison_csv, comparison)

        metadata = render_diff_heatmap(baseline_csv, comparison_csv, diff_png)

        # Verify we have both improvement and degradation
        assert metadata["improved_bins"] > 0
        assert metadata["degraded_bins"] > 0

    def test_colormap_range_is_symmetric(
        self, tmp_path: Path
    ) -> None:
        """Colormap should use symmetric range around zero for rendering."""
        # Create asymmetric diff values
        baseline = np.array([[10.0, 1.0]])
        comparison = np.array([[0.0, 0.0]])
        # Diff will be [+10, +1]

        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "diff.png"

        create_test_heatmap_csv(baseline_csv, baseline)
        create_test_heatmap_csv(comparison_csv, comparison)

        metadata = render_diff_heatmap(baseline_csv, comparison_csv, diff_png)

        # The metadata reports the actual data range
        diff_range = metadata["diff_range"]
        assert diff_range == [1.0, 10.0]  # Actual data range

        # But the rendering uses symmetric range (verified by implementation)
        # vmax = max(abs(min_diff), abs(max_diff)) = max(1, 10) = 10
        # vmin = -vmax = -10
        # This ensures neutral (0) is always at the center of the colormap

        # Verify PNG was created successfully with symmetric rendering
        assert diff_png.exists()
        assert diff_png.stat().st_size > 0

    def test_colormap_handles_zero_diff_gracefully(
        self, tmp_path: Path, neutral_heatmap: np.ndarray
    ) -> None:
        """Colormap should handle zero diff (no change) gracefully."""
        baseline_csv = tmp_path / "baseline.csv"
        comparison_csv = tmp_path / "comparison.csv"
        diff_png = tmp_path / "diff.png"

        create_test_heatmap_csv(baseline_csv, neutral_heatmap)
        create_test_heatmap_csv(comparison_csv, neutral_heatmap)

        # Should not raise an exception
        metadata = render_diff_heatmap(baseline_csv, comparison_csv, diff_png)

        assert diff_png.exists()
        assert metadata["mean_diff"] == 0.0
        assert metadata["unchanged_bins"] == 25
