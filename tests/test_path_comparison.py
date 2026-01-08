"""Tests for comparative timing path analysis."""

import pytest

from src.analysis.path_comparison import (
    PathComparisonResult,
    PathIdentity,
    PathSlackEvolution,
    classify_path_changes,
    compare_timing_paths,
    extract_top_paths,
    generate_path_comparison_report,
    identify_common_paths,
    track_path_slack_evolution,
)
from src.controller.types import TimingMetrics, TimingPath


@pytest.fixture
def sample_paths_base():
    """Sample timing paths for base case."""
    return [
        TimingPath(
            slack_ps=-1000,
            startpoint="reg1/Q",
            endpoint="reg2/D",
            path_group="clk",
            path_type="max",
        ),
        TimingPath(
            slack_ps=-800,
            startpoint="reg2/Q",
            endpoint="reg3/D",
            path_group="clk",
            path_type="max",
        ),
        TimingPath(
            slack_ps=-600,
            startpoint="input_A",
            endpoint="reg1/D",
            path_group="clk",
            path_type="max",
        ),
    ]


@pytest.fixture
def sample_paths_eco1():
    """Sample timing paths for ECO1 case."""
    return [
        TimingPath(
            slack_ps=-700,  # Improved by 300ps
            startpoint="reg1/Q",
            endpoint="reg2/D",
            path_group="clk",
            path_type="max",
        ),
        TimingPath(
            slack_ps=-900,  # Degraded by 100ps
            startpoint="reg2/Q",
            endpoint="reg3/D",
            path_group="clk",
            path_type="max",
        ),
        TimingPath(
            slack_ps=-600,  # Unchanged
            startpoint="input_A",
            endpoint="reg1/D",
            path_group="clk",
            path_type="max",
        ),
    ]


@pytest.fixture
def sample_paths_eco2():
    """Sample timing paths for ECO2 case."""
    return [
        TimingPath(
            slack_ps=-400,  # Further improved
            startpoint="reg1/Q",
            endpoint="reg2/D",
            path_group="clk",
            path_type="max",
        ),
        TimingPath(
            slack_ps=-850,  # Still degraded but stabilizing
            startpoint="reg2/Q",
            endpoint="reg3/D",
            path_group="clk",
            path_type="max",
        ),
        TimingPath(
            slack_ps=-550,  # Slightly improved
            startpoint="input_A",
            endpoint="reg1/D",
            path_group="clk",
            path_type="max",
        ),
    ]


@pytest.fixture
def case_metrics(sample_paths_base, sample_paths_eco1, sample_paths_eco2):
    """Sample case metrics with timing paths."""
    return {
        "base": TimingMetrics(wns_ps=-1000, top_paths=sample_paths_base),
        "eco1": TimingMetrics(wns_ps=-900, top_paths=sample_paths_eco1),
        "eco2": TimingMetrics(wns_ps=-850, top_paths=sample_paths_eco2),
    }


# Step 1: Execute multiple cases with different ECOs
def test_execute_multiple_cases_with_different_ecos(case_metrics):
    """Step 1: Execute multiple cases with different ECOs."""
    # Verify we have metrics for multiple cases
    assert len(case_metrics) == 3
    assert "base" in case_metrics
    assert "eco1" in case_metrics
    assert "eco2" in case_metrics

    # Verify each case has timing paths
    for case_id, metrics in case_metrics.items():
        assert metrics.top_paths is not None
        assert len(metrics.top_paths) > 0


# Step 2: Extract top N critical paths from each case
def test_extract_top_n_critical_paths(case_metrics):
    """Step 2: Extract top N critical paths from each case."""
    case_paths = extract_top_paths(case_metrics, top_n=3)

    # Verify paths extracted for all cases
    assert len(case_paths) == 3
    assert "base" in case_paths
    assert "eco1" in case_paths
    assert "eco2" in case_paths

    # Verify top N paths for each case
    for case_id, paths in case_paths.items():
        assert len(paths) == 3  # We asked for top 3
        # Verify paths are sorted by slack (most negative first)
        slacks = [p.slack_ps for p in paths]
        assert slacks == sorted(slacks)


def test_extract_top_paths_respects_limit():
    """Extract top paths respects the top_n limit."""
    metrics = {
        "case1": TimingMetrics(
            wns_ps=-500,
            top_paths=[
                TimingPath(slack_ps=-1000, startpoint="a", endpoint="b"),
                TimingPath(slack_ps=-800, startpoint="c", endpoint="d"),
                TimingPath(slack_ps=-600, startpoint="e", endpoint="f"),
                TimingPath(slack_ps=-400, startpoint="g", endpoint="h"),
                TimingPath(slack_ps=-200, startpoint="i", endpoint="j"),
            ],
        )
    }

    # Extract top 3
    case_paths = extract_top_paths(metrics, top_n=3)
    assert len(case_paths["case1"]) == 3
    assert case_paths["case1"][0].slack_ps == -1000
    assert case_paths["case1"][1].slack_ps == -800
    assert case_paths["case1"][2].slack_ps == -600


def test_extract_top_paths_handles_empty_paths():
    """Extract top paths handles cases with no paths."""
    metrics = {
        "case1": TimingMetrics(wns_ps=100, top_paths=[]),
        "case2": TimingMetrics(wns_ps=-500, top_paths=None),
    }

    case_paths = extract_top_paths(metrics, top_n=5)
    assert case_paths["case1"] == []
    assert case_paths["case2"] == []


# Step 3: Identify paths that appear across multiple cases
def test_identify_paths_across_multiple_cases(case_metrics):
    """Step 3: Identify paths that appear across multiple cases."""
    case_paths = extract_top_paths(case_metrics, top_n=10)
    common_paths = identify_common_paths(case_paths)

    # All 3 paths appear in all cases
    assert len(common_paths) == 3

    # Verify path identities
    startpoints = {p.startpoint for p in common_paths}
    assert "reg1/Q" in startpoints
    assert "reg2/Q" in startpoints
    assert "input_A" in startpoints


def test_identify_common_paths_partial_overlap():
    """Identify common paths with partial overlap."""
    case_paths = {
        "case1": [
            TimingPath(slack_ps=-1000, startpoint="a", endpoint="b", path_group="clk"),
            TimingPath(slack_ps=-800, startpoint="c", endpoint="d", path_group="clk"),
        ],
        "case2": [
            TimingPath(slack_ps=-900, startpoint="a", endpoint="b", path_group="clk"),
            TimingPath(
                slack_ps=-700, startpoint="e", endpoint="f", path_group="clk"
            ),  # Different path
        ],
    }

    common_paths = identify_common_paths(case_paths)

    # Only path a->b appears in both cases
    assert len(common_paths) == 1
    assert common_paths[0].startpoint == "a"
    assert common_paths[0].endpoint == "b"


def test_identify_common_paths_no_overlap():
    """Identify common paths with no overlap."""
    case_paths = {
        "case1": [
            TimingPath(slack_ps=-1000, startpoint="a", endpoint="b", path_group="clk"),
        ],
        "case2": [
            TimingPath(slack_ps=-900, startpoint="c", endpoint="d", path_group="clk"),
        ],
    }

    common_paths = identify_common_paths(case_paths)
    assert len(common_paths) == 0


def test_identify_common_paths_single_case():
    """Identify common paths with single case returns empty."""
    case_paths = {
        "case1": [
            TimingPath(slack_ps=-1000, startpoint="a", endpoint="b", path_group="clk"),
        ],
    }

    common_paths = identify_common_paths(case_paths)
    # Need at least 2 cases for comparison
    assert len(common_paths) == 0


# Step 4: Track path slack evolution across ECO sequence
def test_track_path_slack_evolution(case_metrics):
    """Step 4: Track path slack evolution across ECO sequence."""
    case_paths = extract_top_paths(case_metrics, top_n=10)
    common_paths = identify_common_paths(case_paths)
    evolutions = track_path_slack_evolution(case_paths, common_paths)

    # Verify we have evolution for all common paths
    assert len(evolutions) == 3

    # Find the reg1->reg2 path evolution
    reg1_reg2_evolution = next(
        (e for e in evolutions if e.identity.startpoint == "reg1/Q"), None
    )
    assert reg1_reg2_evolution is not None

    # Verify slack values
    assert reg1_reg2_evolution.case_slacks["base"] == -1000
    assert reg1_reg2_evolution.case_slacks["eco1"] == -700
    assert reg1_reg2_evolution.case_slacks["eco2"] == -400


def test_path_slack_evolution_get_slack_change():
    """PathSlackEvolution calculates slack changes correctly."""
    identity = PathIdentity(startpoint="a", endpoint="b", path_group="clk")
    evolution = PathSlackEvolution(
        identity=identity,
        case_slacks={"base": -1000, "eco1": -700, "eco2": -400},
    )

    # Check slack changes
    assert evolution.get_slack_change("base", "eco1") == 300  # Improved
    assert evolution.get_slack_change("eco1", "eco2") == 300  # Further improved
    assert evolution.get_slack_change("base", "eco2") == 600  # Total improvement

    # Check for non-existent cases
    assert evolution.get_slack_change("base", "eco99") is None
    assert evolution.get_slack_change("eco99", "eco1") is None


def test_path_slack_evolution_improved_and_degraded():
    """PathSlackEvolution correctly identifies improvements and degradations."""
    identity = PathIdentity(startpoint="a", endpoint="b")
    evolution = PathSlackEvolution(
        identity=identity,
        case_slacks={"base": -1000, "improved": -700, "degraded": -1200},
    )

    # Check improvements
    assert evolution.improved("base", "improved") is True
    assert evolution.improved("base", "degraded") is False

    # Check degradations
    assert evolution.degraded("base", "degraded") is True
    assert evolution.degraded("base", "improved") is False

    # Unchanged returns False for both
    evolution_unchanged = PathSlackEvolution(
        identity=identity, case_slacks={"case1": -1000, "case2": -1000}
    )
    assert evolution_unchanged.improved("case1", "case2") is False
    assert evolution_unchanged.degraded("case1", "case2") is False


# Step 5: Identify paths that improved vs degraded
def test_identify_paths_improved_vs_degraded(case_metrics):
    """Step 5: Identify paths that improved vs degraded."""
    case_paths = extract_top_paths(case_metrics, top_n=10)
    common_paths = identify_common_paths(case_paths)
    evolutions = track_path_slack_evolution(case_paths, common_paths)

    # Classify changes from base to eco2 (final case)
    improved, degraded = classify_path_changes(evolutions, "base", "eco2")

    # reg1->reg2: -1000 to -400 (improved by 600ps)
    # input_A->reg1: -600 to -550 (improved by 50ps)
    assert len(improved) == 2

    # reg2->reg3: -800 to -850 (degraded by 50ps)
    assert len(degraded) == 1

    # Verify specific paths
    improved_startpoints = {p.startpoint for p in improved}
    assert "reg1/Q" in improved_startpoints
    assert "input_A" in improved_startpoints

    degraded_startpoints = {p.startpoint for p in degraded}
    assert "reg2/Q" in degraded_startpoints


def test_classify_path_changes_intermediate():
    """Classify path changes at intermediate stage."""
    identity = PathIdentity(startpoint="a", endpoint="b")
    evolutions = [
        PathSlackEvolution(
            identity=identity,
            case_slacks={"base": -1000, "eco1": -700, "eco2": -400},
        )
    ]

    # base -> eco1 should show improvement
    improved, degraded = classify_path_changes(evolutions, "base", "eco1")
    assert len(improved) == 1
    assert len(degraded) == 0


# Step 6: Generate path-level comparison report
def test_generate_path_level_comparison_report(case_metrics):
    """Step 6: Generate path-level comparison report."""
    result = compare_timing_paths(case_metrics, baseline_case="base", top_n=10)
    report = generate_path_comparison_report(result)

    # Verify report contains key sections
    assert "TIMING PATH COMPARISON REPORT" in report
    assert "Cases analyzed: 3" in report
    assert "base, eco1, eco2" in report
    assert "Common paths across all cases: 3" in report
    assert "Improved paths: 2" in report
    assert "Degraded paths: 1" in report
    assert "PATH SLACK EVOLUTION" in report

    # Verify path details in report
    assert "reg1/Q -> reg2/D" in report
    assert "reg2/Q -> reg3/D" in report
    assert "input_A -> reg1/D" in report

    # Verify slack values
    assert "-1.000 ns" in report  # Base case slacks
    assert "IMPROVED" in report
    assert "DEGRADED" in report


# Step 7: Visualize path slack trends (data structure verification)
def test_visualize_path_slack_trends_data(case_metrics):
    """Step 7: Verify data structure supports visualization."""
    result = compare_timing_paths(case_metrics, baseline_case="base")

    # Verify result has necessary data for visualization
    assert result.case_ids == ["base", "eco1", "eco2"]
    assert len(result.path_evolutions) == 3

    # Verify each evolution has case_slacks for plotting
    for evolution in result.path_evolutions:
        assert len(evolution.case_slacks) == 3
        assert "base" in evolution.case_slacks
        assert "eco1" in evolution.case_slacks
        assert "eco2" in evolution.case_slacks

    # Verify serialization for external tools
    result_dict = result.to_dict()
    assert "case_ids" in result_dict
    assert "path_evolutions" in result_dict
    assert isinstance(result_dict["path_evolutions"], list)
    assert len(result_dict["path_evolutions"]) == 3


# Integration tests
def test_compare_timing_paths_end_to_end(case_metrics):
    """End-to-end test of compare_timing_paths."""
    result = compare_timing_paths(case_metrics, baseline_case="base", top_n=10)

    # Verify result structure
    assert isinstance(result, PathComparisonResult)
    assert result.case_ids == ["base", "eco1", "eco2"]
    assert len(result.common_paths) == 3
    assert len(result.improved_paths) == 2
    assert len(result.degraded_paths) == 1
    assert len(result.path_evolutions) == 3

    # Verify each evolution tracks all cases
    for evolution in result.path_evolutions:
        assert len(evolution.case_slacks) == 3


def test_compare_timing_paths_defaults_to_first_case():
    """compare_timing_paths defaults to first case as baseline."""
    metrics = {
        "case1": TimingMetrics(
            wns_ps=-1000,
            top_paths=[TimingPath(slack_ps=-1000, startpoint="a", endpoint="b")],
        ),
        "case2": TimingMetrics(
            wns_ps=-800,
            top_paths=[TimingPath(slack_ps=-800, startpoint="a", endpoint="b")],
        ),
    }

    result = compare_timing_paths(metrics)  # No baseline specified

    # Should use case1 as baseline
    assert result.case_ids[0] == "case1"


def test_compare_timing_paths_empty_metrics():
    """compare_timing_paths handles empty metrics."""
    result = compare_timing_paths({})

    assert result.case_ids == []
    assert result.path_evolutions == []
    assert result.improved_paths == []
    assert result.degraded_paths == []
    assert result.common_paths == []


def test_compare_timing_paths_invalid_baseline():
    """compare_timing_paths raises error for invalid baseline."""
    metrics = {
        "case1": TimingMetrics(wns_ps=-1000, top_paths=[]),
    }

    with pytest.raises(ValueError, match="Baseline case 'invalid' not in case_metrics"):
        compare_timing_paths(metrics, baseline_case="invalid")


def test_path_identity_matches():
    """PathIdentity.matches() correctly identifies matching paths."""
    identity = PathIdentity(startpoint="a", endpoint="b", path_group="clk")

    # Exact match
    matching_path = TimingPath(
        slack_ps=-1000, startpoint="a", endpoint="b", path_group="clk"
    )
    assert identity.matches(matching_path) is True

    # Different startpoint
    diff_start = TimingPath(
        slack_ps=-1000, startpoint="x", endpoint="b", path_group="clk"
    )
    assert identity.matches(diff_start) is False

    # Different endpoint
    diff_end = TimingPath(
        slack_ps=-1000, startpoint="a", endpoint="y", path_group="clk"
    )
    assert identity.matches(diff_end) is False

    # Different path group
    diff_group = TimingPath(
        slack_ps=-1000, startpoint="a", endpoint="b", path_group="other"
    )
    assert identity.matches(diff_group) is False


def test_path_slack_evolution_serialization():
    """PathSlackEvolution.to_dict() produces valid serializable output."""
    identity = PathIdentity(startpoint="a", endpoint="b", path_group="clk")
    evolution = PathSlackEvolution(
        identity=identity,
        case_slacks={"base": -1000, "eco1": -700},
    )

    result = evolution.to_dict()

    assert result["startpoint"] == "a"
    assert result["endpoint"] == "b"
    assert result["path_group"] == "clk"
    assert result["case_slacks"] == {"base": -1000, "eco1": -700}


def test_path_comparison_result_serialization():
    """PathComparisonResult.to_dict() produces valid serializable output."""
    identity = PathIdentity(startpoint="a", endpoint="b", path_group="clk")
    evolution = PathSlackEvolution(
        identity=identity,
        case_slacks={"base": -1000, "eco1": -700},
    )

    result = PathComparisonResult(
        case_ids=["base", "eco1"],
        path_evolutions=[evolution],
        improved_paths=[identity],
        degraded_paths=[],
        common_paths=[identity],
    )

    result_dict = result.to_dict()

    assert result_dict["case_ids"] == ["base", "eco1"]
    assert len(result_dict["path_evolutions"]) == 1
    assert len(result_dict["improved_paths"]) == 1
    assert len(result_dict["degraded_paths"]) == 0
    assert len(result_dict["common_paths"]) == 1


def test_generate_report_handles_many_paths():
    """Generate report handles many paths by limiting output."""
    # Create 30 path evolutions
    evolutions = []
    for i in range(30):
        identity = PathIdentity(startpoint=f"reg{i}/Q", endpoint=f"reg{i+1}/D")
        evolution = PathSlackEvolution(
            identity=identity,
            case_slacks={"base": -1000, "eco1": -800},
        )
        evolutions.append(evolution)

    result = PathComparisonResult(
        case_ids=["base", "eco1"],
        path_evolutions=evolutions,
        improved_paths=[],
        degraded_paths=[],
        common_paths=[],
    )

    report = generate_path_comparison_report(result)

    # Report should limit to top 20 paths
    # Count how many "Path:" lines appear
    path_count = report.count("Path: reg")
    assert path_count == 20


def test_compare_timing_paths_with_missing_paths_in_some_cases():
    """compare_timing_paths handles paths missing in some cases."""
    metrics = {
        "case1": TimingMetrics(
            wns_ps=-1000,
            top_paths=[
                TimingPath(slack_ps=-1000, startpoint="a", endpoint="b"),
                TimingPath(slack_ps=-800, startpoint="c", endpoint="d"),
            ],
        ),
        "case2": TimingMetrics(
            wns_ps=-900,
            top_paths=[
                TimingPath(slack_ps=-900, startpoint="a", endpoint="b"),
                # Path c->d is missing in case2
            ],
        ),
    }

    result = compare_timing_paths(metrics, baseline_case="case1")

    # Only path a->b should be in common_paths (appears in all cases)
    assert len(result.common_paths) == 1
    assert result.common_paths[0].startpoint == "a"

    # Only common paths are tracked in evolutions
    # Path c->d doesn't appear in all cases, so it's not in evolutions
    assert len(result.path_evolutions) == 1
    assert result.path_evolutions[0].identity.startpoint == "a"

    # Verify the common path has data from both cases
    ab_evolution = result.path_evolutions[0]
    assert "case1" in ab_evolution.case_slacks
    assert "case2" in ab_evolution.case_slacks
