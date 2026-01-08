"""Comparative timing path analysis across multiple cases."""

from dataclasses import dataclass
from typing import Any

from src.controller.types import TimingMetrics, TimingPath


@dataclass
class PathIdentity:
    """Identifies a unique timing path across cases."""

    startpoint: str
    endpoint: str
    path_group: str | None = None

    def matches(self, path: TimingPath) -> bool:
        """Check if a timing path matches this identity."""
        return (
            self.startpoint == path.startpoint
            and self.endpoint == path.endpoint
            and self.path_group == path.path_group
        )


@dataclass
class PathSlackEvolution:
    """Tracks slack evolution for a single path across multiple cases."""

    identity: PathIdentity
    case_slacks: dict[str, int]  # case_id -> slack_ps

    def get_slack_change(self, from_case: str, to_case: str) -> int | None:
        """Calculate slack change between two cases."""
        if from_case not in self.case_slacks or to_case not in self.case_slacks:
            return None
        return self.case_slacks[to_case] - self.case_slacks[from_case]

    def improved(self, from_case: str, to_case: str) -> bool:
        """Check if path improved between cases."""
        change = self.get_slack_change(from_case, to_case)
        return change is not None and change > 0

    def degraded(self, from_case: str, to_case: str) -> bool:
        """Check if path degraded between cases."""
        change = self.get_slack_change(from_case, to_case)
        return change is not None and change < 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "startpoint": self.identity.startpoint,
            "endpoint": self.identity.endpoint,
            "path_group": self.identity.path_group,
            "case_slacks": self.case_slacks,
        }


@dataclass
class PathComparisonResult:
    """Results of comparative path analysis across cases."""

    case_ids: list[str]
    path_evolutions: list[PathSlackEvolution]
    improved_paths: list[PathIdentity]  # Paths that improved
    degraded_paths: list[PathIdentity]  # Paths that degraded
    common_paths: list[PathIdentity]  # Paths appearing in all cases

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "case_ids": self.case_ids,
            "path_evolutions": [p.to_dict() for p in self.path_evolutions],
            "improved_paths": [
                {
                    "startpoint": p.startpoint,
                    "endpoint": p.endpoint,
                    "path_group": p.path_group,
                }
                for p in self.improved_paths
            ],
            "degraded_paths": [
                {
                    "startpoint": p.startpoint,
                    "endpoint": p.endpoint,
                    "path_group": p.path_group,
                }
                for p in self.degraded_paths
            ],
            "common_paths": [
                {
                    "startpoint": p.startpoint,
                    "endpoint": p.endpoint,
                    "path_group": p.path_group,
                }
                for p in self.common_paths
            ],
        }


def extract_top_paths(
    case_metrics: dict[str, TimingMetrics], top_n: int = 10
) -> dict[str, list[TimingPath]]:
    """
    Extract top N critical paths from each case.

    Args:
        case_metrics: Dictionary mapping case_id to TimingMetrics
        top_n: Number of critical paths to extract (default: 10)

    Returns:
        Dictionary mapping case_id to list of top paths
    """
    case_paths: dict[str, list[TimingPath]] = {}

    for case_id, metrics in case_metrics.items():
        if not metrics.top_paths:
            case_paths[case_id] = []
            continue

        # Sort paths by slack (most negative first)
        sorted_paths = sorted(metrics.top_paths, key=lambda p: p.slack_ps)
        case_paths[case_id] = sorted_paths[:top_n]

    return case_paths


def identify_common_paths(
    case_paths: dict[str, list[TimingPath]]
) -> list[PathIdentity]:
    """
    Identify paths that appear across all cases.

    A path is considered "common" if it appears in all cases based on
    startpoint, endpoint, and path_group.

    Args:
        case_paths: Dictionary mapping case_id to list of paths

    Returns:
        List of PathIdentity objects for common paths
    """
    if not case_paths:
        return []

    # Get all case IDs
    case_ids = list(case_paths.keys())
    if len(case_ids) < 2:
        # Need at least 2 cases for comparison
        return []

    # Create path identities for the first case
    first_case_paths = case_paths[case_ids[0]]
    candidate_identities = [
        PathIdentity(
            startpoint=p.startpoint, endpoint=p.endpoint, path_group=p.path_group
        )
        for p in first_case_paths
    ]

    # Filter to paths that appear in ALL cases
    common_identities = []
    for identity in candidate_identities:
        appears_in_all = True
        for case_id in case_ids[1:]:
            case_has_path = any(identity.matches(p) for p in case_paths[case_id])
            if not case_has_path:
                appears_in_all = False
                break

        if appears_in_all:
            common_identities.append(identity)

    return common_identities


def track_path_slack_evolution(
    case_paths: dict[str, list[TimingPath]], path_identities: list[PathIdentity]
) -> list[PathSlackEvolution]:
    """
    Track slack evolution for specific paths across cases.

    Args:
        case_paths: Dictionary mapping case_id to list of paths
        path_identities: List of path identities to track

    Returns:
        List of PathSlackEvolution objects
    """
    evolutions = []

    for identity in path_identities:
        case_slacks: dict[str, int] = {}

        # Find slack for this path in each case
        for case_id, paths in case_paths.items():
            for path in paths:
                if identity.matches(path):
                    case_slacks[case_id] = path.slack_ps
                    break

        # Only create evolution if path appears in at least one case
        if case_slacks:
            evolutions.append(
                PathSlackEvolution(identity=identity, case_slacks=case_slacks)
            )

    return evolutions


def classify_path_changes(
    path_evolutions: list[PathSlackEvolution], baseline_case: str, target_case: str
) -> tuple[list[PathIdentity], list[PathIdentity]]:
    """
    Classify paths as improved or degraded between two cases.

    Args:
        path_evolutions: List of path slack evolutions
        baseline_case: Baseline case ID
        target_case: Target case ID

    Returns:
        Tuple of (improved_paths, degraded_paths)
    """
    improved: list[PathIdentity] = []
    degraded: list[PathIdentity] = []

    for evolution in path_evolutions:
        if evolution.improved(baseline_case, target_case):
            improved.append(evolution.identity)
        elif evolution.degraded(baseline_case, target_case):
            degraded.append(evolution.identity)

    return improved, degraded


def compare_timing_paths(
    case_metrics: dict[str, TimingMetrics],
    baseline_case: str | None = None,
    top_n: int = 10,
) -> PathComparisonResult:
    """
    Perform comparative timing path analysis across multiple cases.

    This analyzes how timing paths evolve across different ECO applications:
    - Extracts top N critical paths from each case
    - Identifies paths that appear across multiple cases
    - Tracks slack evolution for common paths
    - Classifies paths as improved or degraded

    Args:
        case_metrics: Dictionary mapping case_id to TimingMetrics
        baseline_case: Optional baseline case for comparison (defaults to first case)
        top_n: Number of top critical paths to analyze per case (default: 10)

    Returns:
        PathComparisonResult with evolution analysis

    Example:
        >>> metrics = {
        ...     "base": TimingMetrics(wns_ps=-1000, top_paths=[...]),
        ...     "eco1": TimingMetrics(wns_ps=-800, top_paths=[...]),
        ... }
        >>> result = compare_timing_paths(metrics, baseline_case="base")
        >>> print(f"Improved paths: {len(result.improved_paths)}")
    """
    if not case_metrics:
        return PathComparisonResult(
            case_ids=[],
            path_evolutions=[],
            improved_paths=[],
            degraded_paths=[],
            common_paths=[],
        )

    # Get case IDs in order
    case_ids = list(case_metrics.keys())

    # Use first case as baseline if not specified
    if baseline_case is None:
        baseline_case = case_ids[0]
    elif baseline_case not in case_ids:
        raise ValueError(f"Baseline case '{baseline_case}' not in case_metrics")

    # Extract top N paths from each case
    case_paths = extract_top_paths(case_metrics, top_n=top_n)

    # Identify common paths across all cases
    common_identities = identify_common_paths(case_paths)

    # Track slack evolution for common paths
    path_evolutions = track_path_slack_evolution(case_paths, common_identities)

    # Classify improvements and degradations relative to baseline
    # For multiple cases, we compare the last case to the baseline
    target_case = case_ids[-1] if len(case_ids) > 1 else baseline_case
    improved, degraded = classify_path_changes(
        path_evolutions, baseline_case, target_case
    )

    return PathComparisonResult(
        case_ids=case_ids,
        path_evolutions=path_evolutions,
        improved_paths=improved,
        degraded_paths=degraded,
        common_paths=common_identities,
    )


def generate_path_comparison_report(result: PathComparisonResult) -> str:
    """
    Generate a human-readable report from path comparison results.

    Args:
        result: PathComparisonResult from compare_timing_paths

    Returns:
        Formatted text report
    """
    lines = []
    lines.append("=" * 80)
    lines.append("TIMING PATH COMPARISON REPORT")
    lines.append("=" * 80)
    lines.append("")

    # Summary
    lines.append(f"Cases analyzed: {len(result.case_ids)}")
    lines.append(f"  {', '.join(result.case_ids)}")
    lines.append("")
    lines.append(f"Common paths across all cases: {len(result.common_paths)}")
    lines.append(f"Improved paths: {len(result.improved_paths)}")
    lines.append(f"Degraded paths: {len(result.degraded_paths)}")
    lines.append("")

    # Path evolutions
    if result.path_evolutions:
        lines.append("-" * 80)
        lines.append("PATH SLACK EVOLUTION")
        lines.append("-" * 80)
        lines.append("")

        for evolution in result.path_evolutions[:20]:  # Show top 20
            lines.append(
                f"Path: {evolution.identity.startpoint} -> {evolution.identity.endpoint}"
            )
            if evolution.identity.path_group:
                lines.append(f"  Group: {evolution.identity.path_group}")

            # Show slack for each case
            for case_id in result.case_ids:
                if case_id in evolution.case_slacks:
                    slack_ps = evolution.case_slacks[case_id]
                    slack_ns = slack_ps / 1000.0
                    lines.append(f"  {case_id}: {slack_ns:8.3f} ns")

            # Show delta if multiple cases
            if len(result.case_ids) >= 2:
                first_case = result.case_ids[0]
                last_case = result.case_ids[-1]
                delta = evolution.get_slack_change(first_case, last_case)
                if delta is not None:
                    delta_ns = delta / 1000.0
                    status = "IMPROVED" if delta > 0 else "DEGRADED" if delta < 0 else "UNCHANGED"
                    lines.append(f"  Delta: {delta_ns:+8.3f} ns ({status})")

            lines.append("")

    lines.append("=" * 80)
    return "\n".join(lines)
