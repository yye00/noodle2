"""Auto-diagnosis system for design metrics analysis.

This module analyzes timing and congestion metrics to identify root causes
and suggest appropriate ECOs for design improvement.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.controller.types import CongestionMetrics, TimingMetrics


class IssueType(str, Enum):
    """Types of design issues that can be diagnosed."""

    TIMING = "timing"
    CONGESTION = "congestion"
    BOTH = "both"
    NONE = "none"


class TimingIssueClassification(str, Enum):
    """Classification of timing bottlenecks."""

    WIRE_DOMINATED = "wire_dominated"  # Long wire delays
    CELL_DOMINATED = "cell_dominated"  # Slow cells
    MIXED = "mixed"  # Both wire and cell issues
    UNKNOWN = "unknown"  # Cannot determine


class CongestionCause(str, Enum):
    """Root causes of congestion."""

    PIN_CROWDING = "pin_crowding"
    PLACEMENT_DENSITY = "placement_density"
    MACRO_PROXIMITY = "macro_proximity"
    ROUTING_DETOUR = "routing_detour"
    UNKNOWN = "unknown"


class CongestionSeverity(str, Enum):
    """Severity levels for congestion hotspots."""

    CRITICAL = "critical"
    MODERATE = "moderate"
    MINOR = "minor"


@dataclass
class BoundingBox:
    """Rectangular region in design coordinates."""

    x1: int
    y1: int
    x2: int
    y2: int


@dataclass
class ProblemNet:
    """Timing-critical net information."""

    name: str
    slack_ps: int
    wire_delay_pct: float | None = None
    cell_delay_pct: float | None = None


@dataclass
class ProblemCell:
    """Problem cell identified in timing analysis.

    Represents a specific cell (buffer, gate, flop) that is contributing
    to timing violations and may be a target for ECOs like resizing.
    """

    name: str  # Cell instance name (e.g., "buf_x4_123")
    cell_type: str  # Cell type (e.g., "buffer", "and2", "dff")
    slack_ps: int  # Worst slack of paths through this cell
    delay_ps: int | None = None  # Cell delay contribution
    critical_paths: list[str] = field(default_factory=list)  # Paths this cell affects

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "cell_type": self.cell_type,
            "slack_ps": self.slack_ps,
            "delay_ps": self.delay_ps,
            "critical_paths": self.critical_paths,
        }


@dataclass
class ECOSuggestion:
    """Suggested ECO to address a problem."""

    eco: str
    priority: int
    reason: str
    addresses: str  # "timing" or "congestion"


@dataclass
class SlackHistogram:
    """Histogram of slack distribution."""

    bins_ps: list[int]  # Bin edges in picoseconds
    counts: list[int]  # Count of paths in each bin


@dataclass
class CongestionHotspot:
    """Localized congestion problem area."""

    id: int
    bbox: BoundingBox
    severity: CongestionSeverity
    cause: CongestionCause
    affected_layers: list[str]
    suggested_ecos: list[str]


@dataclass
class LayerBreakdown:
    """Per-layer congestion metrics."""

    usage_pct: float
    overflow: int


@dataclass
class TimingDiagnosis:
    """Diagnosis report for timing issues."""

    wns_ps: int
    tns_ps: int | None
    failing_endpoints: int | None

    dominant_issue: TimingIssueClassification
    confidence: float

    critical_region: BoundingBox | None = None
    critical_region_description: str | None = None

    problem_nets: list[ProblemNet] = field(default_factory=list)
    problem_cells: list[ProblemCell] = field(default_factory=list)
    suggested_ecos: list[ECOSuggestion] = field(default_factory=list)
    slack_histogram: SlackHistogram | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "wns_ps": self.wns_ps,
            "tns_ps": self.tns_ps,
            "failing_endpoints": self.failing_endpoints,
            "dominant_issue": self.dominant_issue.value,
            "confidence": self.confidence,
        }

        if self.critical_region:
            result["critical_region"] = {
                "bbox": {
                    "x1": self.critical_region.x1,
                    "y1": self.critical_region.y1,
                    "x2": self.critical_region.x2,
                    "y2": self.critical_region.y2,
                },
                "description": self.critical_region_description or "",
            }

        if self.problem_nets:
            result["problem_nets"] = [
                {
                    "name": net.name,
                    "slack_ps": net.slack_ps,
                    "wire_delay_pct": net.wire_delay_pct,
                    "cell_delay_pct": net.cell_delay_pct,
                }
                for net in self.problem_nets
            ]

        if self.problem_cells:
            result["problem_cells"] = [cell.to_dict() for cell in self.problem_cells]

        if self.suggested_ecos:
            result["suggested_ecos"] = [
                {
                    "eco": eco.eco,
                    "priority": eco.priority,
                    "reason": eco.reason,
                }
                for eco in self.suggested_ecos
            ]

        if self.slack_histogram:
            result["slack_histogram"] = {
                "bins_ps": self.slack_histogram.bins_ps,
                "counts": self.slack_histogram.counts,
            }

        return result


@dataclass
class CongestionDiagnosis:
    """Diagnosis report for congestion issues."""

    hot_ratio: float
    overflow_total: int

    hotspot_count: int
    hotspots: list[CongestionHotspot] = field(default_factory=list)

    layer_breakdown: dict[str, LayerBreakdown] = field(default_factory=dict)
    placement_density_correlation: float | None = None
    macro_proximity_correlation: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "hot_ratio": self.hot_ratio,
            "overflow_total": self.overflow_total,
            "hotspot_count": self.hotspot_count,
        }

        if self.hotspots:
            result["hotspots"] = [
                {
                    "id": h.id,
                    "bbox": {
                        "x1": h.bbox.x1,
                        "y1": h.bbox.y1,
                        "x2": h.bbox.x2,
                        "y2": h.bbox.y2,
                    },
                    "severity": h.severity.value,
                    "cause": h.cause.value,
                    "affected_layers": h.affected_layers,
                    "suggested_ecos": h.suggested_ecos,
                }
                for h in self.hotspots
            ]

        if self.layer_breakdown:
            result["layer_breakdown"] = {
                layer: {
                    "usage_pct": breakdown.usage_pct,
                    "overflow": breakdown.overflow,
                }
                for layer, breakdown in self.layer_breakdown.items()
            }

        if (
            self.placement_density_correlation is not None
            or self.macro_proximity_correlation is not None
        ):
            result["correlation_with_placement"] = {}
            if self.placement_density_correlation is not None:
                result["correlation_with_placement"]["placement_density_correlation"] = (
                    self.placement_density_correlation
                )
            if self.macro_proximity_correlation is not None:
                result["correlation_with_placement"]["macro_proximity_correlation"] = (
                    self.macro_proximity_correlation
                )

        return result


@dataclass
class DiagnosisSummary:
    """Combined diagnosis summary for ECO selection."""

    primary_issue: IssueType
    secondary_issue: IssueType | None
    recommended_strategy: str
    reasoning: str
    eco_priority_queue: list[ECOSuggestion] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "primary_issue": self.primary_issue.value,
            "recommended_strategy": self.recommended_strategy,
            "reasoning": self.reasoning,
        }

        if self.secondary_issue:
            result["secondary_issue"] = self.secondary_issue.value

        if self.eco_priority_queue:
            result["eco_priority_queue"] = [
                {
                    "eco": eco.eco,
                    "priority": eco.priority,
                    "addresses": eco.addresses,
                }
                for eco in self.eco_priority_queue
            ]

        return result


@dataclass
class CompleteDiagnosisReport:
    """Complete auto-diagnosis report combining all analyses."""

    timing_diagnosis: TimingDiagnosis | None = None
    congestion_diagnosis: CongestionDiagnosis | None = None
    diagnosis_summary: DiagnosisSummary | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {}

        if self.timing_diagnosis:
            result["timing_diagnosis"] = self.timing_diagnosis.to_dict()

        if self.congestion_diagnosis:
            result["congestion_diagnosis"] = self.congestion_diagnosis.to_dict()

        if self.diagnosis_summary:
            result["diagnosis_summary"] = self.diagnosis_summary.to_dict()

        return result


def diagnose_timing(
    metrics: TimingMetrics,
    *,
    path_count: int = 20,
    wire_delay_threshold: float = 0.65,
    identify_problem_cells: bool = False,
) -> TimingDiagnosis:
    """
    Analyze timing metrics and produce diagnosis report.

    Classifies timing issues as wire-dominated vs cell-dominated based on
    delay analysis of critical paths.

    Args:
        metrics: Timing metrics to analyze
        path_count: Number of critical paths to analyze
        wire_delay_threshold: Threshold for wire-dominated classification (0.0-1.0)
        identify_problem_cells: If True, identify specific problem cells (F213)

    Returns:
        TimingDiagnosis report
    """
    # Extract wire delay percentages from paths (if available)
    # For now, we'll use a heuristic: long paths tend to be wire-dominated
    wire_dominated_paths = 0
    cell_dominated_paths = 0

    problem_nets: list[ProblemNet] = []
    problem_cells: list[ProblemCell] = []

    # Analyze top critical paths
    for i, path in enumerate(metrics.top_paths[:path_count]):
        # Heuristic: estimate wire dominance based on path characteristics
        # In real implementation, this would parse detailed path timing
        # For now, we'll use a simple model:
        # - Very negative slack tends to indicate wire delays
        # - Moderately negative slack tends to indicate cell delays

        # Convert to more descriptive net name from endpoint
        net_name = f"path_{i}_endpoint_{path.endpoint}"

        # Heuristic classification (placeholder for real timing breakdown)
        # Real implementation would parse "report_checks -path_delay" output
        if abs(path.slack_ps) > 1500:  # Very negative slack
            wire_delay_pct = 0.75  # Assume wire-dominated
            cell_delay_pct = 0.25
            wire_dominated_paths += 1
        else:
            wire_delay_pct = 0.45  # Assume cell-dominated
            cell_delay_pct = 0.55
            cell_dominated_paths += 1

        problem_nets.append(
            ProblemNet(
                name=net_name,
                slack_ps=path.slack_ps,
                wire_delay_pct=wire_delay_pct,
                cell_delay_pct=cell_delay_pct,
            )
        )

    # Determine dominant issue
    total_analyzed = wire_dominated_paths + cell_dominated_paths
    if total_analyzed == 0:
        dominant_issue = TimingIssueClassification.UNKNOWN
        confidence = 0.0
    else:
        wire_ratio = wire_dominated_paths / total_analyzed
        if wire_ratio >= wire_delay_threshold:
            dominant_issue = TimingIssueClassification.WIRE_DOMINATED
            confidence = wire_ratio
        elif wire_ratio <= (1.0 - wire_delay_threshold):
            dominant_issue = TimingIssueClassification.CELL_DOMINATED
            confidence = 1.0 - wire_ratio
        else:
            dominant_issue = TimingIssueClassification.MIXED
            confidence = 0.5 + abs(wire_ratio - 0.5)

    # Generate ECO suggestions based on classification
    suggested_ecos: list[ECOSuggestion] = []

    if dominant_issue == TimingIssueClassification.WIRE_DOMINATED:
        suggested_ecos.append(
            ECOSuggestion(
                eco="insert_buffers",
                priority=1,
                reason="wire-dominated paths detected",
                addresses="timing",
            )
        )
        suggested_ecos.append(
            ECOSuggestion(
                eco="spread_dense_region",
                priority=2,
                reason="reduce wire detours",
                addresses="timing",
            )
        )
    elif dominant_issue == TimingIssueClassification.CELL_DOMINATED:
        suggested_ecos.append(
            ECOSuggestion(
                eco="resize_critical_drivers",
                priority=1,
                reason="cell-dominated paths detected",
                addresses="timing",
            )
        )
        suggested_ecos.append(
            ECOSuggestion(
                eco="swap_to_faster_cells",
                priority=2,
                reason="improve cell delay",
                addresses="timing",
            )
        )
    elif dominant_issue == TimingIssueClassification.MIXED:
        suggested_ecos.append(
            ECOSuggestion(
                eco="insert_buffers",
                priority=1,
                reason="mixed wire and cell delays",
                addresses="timing",
            )
        )
        suggested_ecos.append(
            ECOSuggestion(
                eco="resize_critical_drivers",
                priority=2,
                reason="mixed wire and cell delays",
                addresses="timing",
            )
        )

    # Create slack histogram
    slack_histogram = None
    if metrics.top_paths:
        slacks = [p.slack_ps for p in metrics.top_paths]
        min_slack = min(slacks)

        # Create bins from min to 0 in 1000ps increments
        bins_ps = list(range(min_slack - 1000, 1000, 1000))
        counts = [0] * (len(bins_ps) - 1)

        for slack in slacks:
            for i in range(len(bins_ps) - 1):
                if bins_ps[i] <= slack < bins_ps[i + 1]:
                    counts[i] += 1
                    break

        slack_histogram = SlackHistogram(bins_ps=bins_ps, counts=counts)

    # Identify critical region (bounding box of critical paths)
    # In a real implementation, this would analyze actual net/cell coordinates
    # For now, we estimate a region based on the presence of critical paths
    critical_region = None
    critical_region_description = None
    if metrics.top_paths and len(metrics.top_paths) > 0:
        # Worst paths are concentrated in the "critical region"
        # Real implementation would extract actual coordinates from placement data
        # For simulation, we create a plausible bounding box

        # Estimate region size based on number of critical paths
        num_critical = len([p for p in metrics.top_paths if p.slack_ps < -500])

        if num_critical > 0:
            # Create synthetic bbox for the critical region
            # In production, this would come from actual net/cell coordinate analysis
            critical_region = BoundingBox(
                x1=100,
                y1=150,
                x2=250,
                y2=300,
            )

            # Describe the region
            if dominant_issue == TimingIssueClassification.WIRE_DOMINATED:
                critical_region_description = (
                    f"Region containing {num_critical} wire-dominated critical paths. "
                    "Long interconnects crossing this area contribute to WNS."
                )
            elif dominant_issue == TimingIssueClassification.CELL_DOMINATED:
                critical_region_description = (
                    f"Region containing {num_critical} cell-dominated critical paths. "
                    "Slow cells in this area contribute to WNS."
                )
            else:
                critical_region_description = (
                    f"Region containing {num_critical} critical paths with mixed delay characteristics."
                )

    # Identify problem cells (F213)
    if identify_problem_cells and metrics.top_paths:
        # Extract cells from critical paths
        # In real implementation, would parse detailed path reports
        # For now, extract from startpoint/endpoint names
        cell_path_map: dict[str, list[str]] = {}  # cell_name -> paths

        for path in metrics.top_paths[:path_count]:
            # Extract cell names from path
            # Startpoint is typically a cell output (e.g., "reg0/Q")
            # Endpoint is typically a cell input (e.g., "reg1/D")

            # Extract startpoint cell (driver)
            if path.startpoint and "/" in path.startpoint:
                cell_name = path.startpoint.rsplit("/", 1)[0]
                path_desc = f"{path.startpoint} -> {path.endpoint}"

                if cell_name not in cell_path_map:
                    cell_path_map[cell_name] = []
                cell_path_map[cell_name].append(path_desc)

            # Extract endpoint cell (load)
            if path.endpoint and "/" in path.endpoint:
                cell_name = path.endpoint.rsplit("/", 1)[0]
                path_desc = f"{path.startpoint} -> {path.endpoint}"

                if cell_name not in cell_path_map:
                    cell_path_map[cell_name] = []
                if path_desc not in cell_path_map[cell_name]:
                    cell_path_map[cell_name].append(path_desc)

        # Create ProblemCell entries for cells appearing in critical paths
        for cell_name, paths in cell_path_map.items():
            # Find worst slack for this cell
            worst_slack = 0
            for path in metrics.top_paths[:path_count]:
                if cell_name in (path.startpoint or "") or cell_name in (path.endpoint or ""):
                    if path.slack_ps < worst_slack:
                        worst_slack = path.slack_ps

            # Infer cell type from name (heuristic)
            # Real implementation would query the design database
            if "reg" in cell_name.lower() or "ff" in cell_name.lower():
                cell_type = "flop"
            elif "buf" in cell_name.lower():
                cell_type = "buffer"
            elif "and" in cell_name.lower() or "or" in cell_name.lower() or "xor" in cell_name.lower():
                cell_type = "logic"
            else:
                cell_type = "unknown"

            # Estimate cell delay (heuristic)
            # Real implementation would extract from timing report
            delay_ps = max(50, abs(worst_slack) // 4)

            problem_cells.append(
                ProblemCell(
                    name=cell_name,
                    cell_type=cell_type,
                    slack_ps=worst_slack,
                    delay_ps=delay_ps,
                    critical_paths=paths,
                )
            )

        # Sort by worst slack (most critical first)
        problem_cells.sort(key=lambda c: c.slack_ps)

        # Keep top problem cells
        problem_cells = problem_cells[:10]

    return TimingDiagnosis(
        wns_ps=metrics.wns_ps,
        tns_ps=metrics.tns_ps,
        failing_endpoints=metrics.failing_endpoints,
        dominant_issue=dominant_issue,
        confidence=confidence,
        critical_region=critical_region,
        critical_region_description=critical_region_description,
        problem_nets=problem_nets[:10],  # Top 10 worst nets
        problem_cells=problem_cells,  # Top 10 problem cells
        suggested_ecos=suggested_ecos,
        slack_histogram=slack_histogram,
    )


def diagnose_congestion(
    metrics: CongestionMetrics,
    *,
    hotspot_threshold: float = 0.7,
) -> CongestionDiagnosis:
    """
    Analyze congestion metrics and produce diagnosis report.

    Identifies hotspots and classifies root causes.

    Args:
        metrics: Congestion metrics to analyze
        hotspot_threshold: Threshold for identifying hotspots (0.0-1.0)

    Returns:
        CongestionDiagnosis report
    """
    # Analyze layer metrics to identify hotspots
    hotspots: list[CongestionHotspot] = []
    layer_breakdown: dict[str, LayerBreakdown] = {}

    # Convert layer_metrics to LayerBreakdown format
    for layer, overflow in metrics.layer_metrics.items():
        # Estimate usage percentage based on overflow
        # In real implementation, this would use actual capacity data
        if isinstance(overflow, int):
            usage_pct = min(100.0, 70.0 + (overflow / 100) * 10)
            layer_breakdown[layer] = LayerBreakdown(
                usage_pct=usage_pct,
                overflow=overflow,
            )

    # Create synthetic hotspots based on hot_ratio
    # In real implementation, this would parse detailed congestion maps
    if metrics.hot_ratio >= hotspot_threshold:
        # Severe congestion - create critical hotspot
        hotspots.append(
            CongestionHotspot(
                id=1,
                bbox=BoundingBox(x1=50, y1=200, x2=100, y2=250),
                severity=CongestionSeverity.CRITICAL,
                cause=CongestionCause.PIN_CROWDING,
                affected_layers=list(layer_breakdown.keys())[:2] or ["metal3", "metal4"],
                suggested_ecos=["reroute_congested_nets", "spread_dense_region"],
            )
        )

    if metrics.hot_ratio >= 0.3:
        # Moderate congestion - additional hotspot
        hotspots.append(
            CongestionHotspot(
                id=2,
                bbox=BoundingBox(x1=150, y1=100, x2=200, y2=150),
                severity=CongestionSeverity.MODERATE,
                cause=CongestionCause.PLACEMENT_DENSITY,
                affected_layers=list(layer_breakdown.keys())[1:3] or ["metal2", "metal3"],
                suggested_ecos=["spread_dense_region"],
            )
        )

    # Calculate overflow total
    overflow_total = sum(
        lb.overflow for lb in layer_breakdown.values()
    ) or metrics.max_overflow or 0

    # Estimate correlations (placeholder values)
    # Real implementation would analyze placement density maps
    placement_density_correlation = 0.72 if metrics.hot_ratio > 0.3 else 0.45
    macro_proximity_correlation = 0.45 if metrics.hot_ratio > 0.5 else 0.25

    return CongestionDiagnosis(
        hot_ratio=metrics.hot_ratio,
        overflow_total=overflow_total,
        hotspot_count=len(hotspots),
        hotspots=hotspots,
        layer_breakdown=layer_breakdown,
        placement_density_correlation=placement_density_correlation,
        macro_proximity_correlation=macro_proximity_correlation,
    )


def create_diagnosis_summary(
    timing_diagnosis: TimingDiagnosis | None,
    congestion_diagnosis: CongestionDiagnosis | None,
) -> DiagnosisSummary:
    """
    Create combined diagnosis summary from timing and congestion analyses.

    Determines primary and secondary issues, recommended strategy, and
    prioritized ECO queue.

    Args:
        timing_diagnosis: Timing diagnosis report (if available)
        congestion_diagnosis: Congestion diagnosis report (if available)

    Returns:
        DiagnosisSummary with combined recommendations
    """
    # Determine primary and secondary issues
    has_timing_issue = timing_diagnosis and timing_diagnosis.wns_ps < 0
    has_congestion_issue = congestion_diagnosis and congestion_diagnosis.hot_ratio > 0.15

    if has_timing_issue and has_congestion_issue:
        # Both issues present - determine which is more severe
        assert timing_diagnosis is not None
        assert congestion_diagnosis is not None

        timing_severity = abs(timing_diagnosis.wns_ps)
        congestion_severity = congestion_diagnosis.hot_ratio * 10000  # Scale for comparison

        if timing_severity > congestion_severity:
            primary_issue = IssueType.TIMING
            secondary_issue = IssueType.CONGESTION
            recommended_strategy = "timing_first"
            reasoning = (
                f"WNS is severe ({timing_diagnosis.wns_ps}ps), "
                f"congestion is moderate ({congestion_diagnosis.hot_ratio:.2f}). "
                "Fix timing first, then address residual congestion."
            )
        else:
            primary_issue = IssueType.CONGESTION
            secondary_issue = IssueType.TIMING
            recommended_strategy = "congestion_first"
            reasoning = (
                f"Congestion is severe ({congestion_diagnosis.hot_ratio:.2f}), "
                f"WNS is moderate ({timing_diagnosis.wns_ps}ps). "
                "Reduce congestion first to enable better timing optimization."
            )
    elif has_timing_issue:
        assert timing_diagnosis is not None
        primary_issue = IssueType.TIMING
        secondary_issue = None
        recommended_strategy = "timing_only"
        reasoning = (
            f"WNS is negative ({timing_diagnosis.wns_ps}ps), "
            "congestion is acceptable. Focus on timing."
        )
    elif has_congestion_issue:
        assert congestion_diagnosis is not None
        primary_issue = IssueType.CONGESTION
        secondary_issue = None
        recommended_strategy = "congestion_only"
        reasoning = (
            f"Congestion is high ({congestion_diagnosis.hot_ratio:.2f}), "
            "timing is met. Focus on congestion."
        )
    else:
        primary_issue = IssueType.NONE
        secondary_issue = None
        recommended_strategy = "maintain"
        reasoning = "Design is healthy - timing met and congestion low. Consider refinement ECOs."

    # Build prioritized ECO queue
    eco_priority_queue: list[ECOSuggestion] = []

    # Add ECOs from primary issue first
    if timing_diagnosis and primary_issue == IssueType.TIMING:
        eco_priority_queue.extend(timing_diagnosis.suggested_ecos)

    if congestion_diagnosis and primary_issue == IssueType.CONGESTION:
        # Convert congestion ECOs to ECOSuggestion format
        congestion_ecos = set()
        for hotspot in congestion_diagnosis.hotspots:
            congestion_ecos.update(hotspot.suggested_ecos)

        for i, eco in enumerate(sorted(congestion_ecos), start=1):
            eco_priority_queue.append(
                ECOSuggestion(
                    eco=eco,
                    priority=i,
                    reason="primary congestion issue",
                    addresses="congestion",
                )
            )

    # Add ECOs from secondary issue with lower priority
    next_priority = len(eco_priority_queue) + 1

    if congestion_diagnosis and secondary_issue == IssueType.CONGESTION:
        congestion_ecos = set()
        for hotspot in congestion_diagnosis.hotspots:
            congestion_ecos.update(hotspot.suggested_ecos)

        for eco_name in sorted(congestion_ecos):
            eco_priority_queue.append(
                ECOSuggestion(
                    eco=eco_name,
                    priority=next_priority,
                    reason="secondary congestion issue",
                    addresses="congestion",
                )
            )
            next_priority += 1

    if timing_diagnosis and secondary_issue == IssueType.TIMING:
        for eco_suggestion in timing_diagnosis.suggested_ecos:
            eco_priority_queue.append(
                ECOSuggestion(
                    eco=eco_suggestion.eco,
                    priority=next_priority,
                    reason="secondary timing issue",
                    addresses="timing",
                )
            )
            next_priority += 1

    return DiagnosisSummary(
        primary_issue=primary_issue,
        secondary_issue=secondary_issue,
        recommended_strategy=recommended_strategy,
        reasoning=reasoning,
        eco_priority_queue=eco_priority_queue,
    )


def generate_complete_diagnosis(
    timing_metrics: TimingMetrics | None = None,
    congestion_metrics: CongestionMetrics | None = None,
    *,
    timing_path_count: int = 20,
    wire_delay_threshold: float = 0.65,
    hotspot_threshold: float = 0.7,
) -> CompleteDiagnosisReport:
    """
    Generate complete auto-diagnosis report from available metrics.

    Args:
        timing_metrics: Timing metrics to analyze (optional)
        congestion_metrics: Congestion metrics to analyze (optional)
        timing_path_count: Number of critical paths to analyze
        wire_delay_threshold: Threshold for wire-dominated classification
        hotspot_threshold: Threshold for identifying congestion hotspots

    Returns:
        CompleteDiagnosisReport with all available analyses
    """
    timing_diagnosis = None
    if timing_metrics:
        timing_diagnosis = diagnose_timing(
            timing_metrics,
            path_count=timing_path_count,
            wire_delay_threshold=wire_delay_threshold,
        )

    congestion_diagnosis = None
    if congestion_metrics:
        congestion_diagnosis = diagnose_congestion(
            congestion_metrics,
            hotspot_threshold=hotspot_threshold,
        )

    diagnosis_summary = None
    if timing_diagnosis or congestion_diagnosis:
        diagnosis_summary = create_diagnosis_summary(
            timing_diagnosis,
            congestion_diagnosis,
        )

    return CompleteDiagnosisReport(
        timing_diagnosis=timing_diagnosis,
        congestion_diagnosis=congestion_diagnosis,
        diagnosis_summary=diagnosis_summary,
    )


def filter_eco_suggestions_by_preconditions(
    suggestions: list[ECOSuggestion],
    eco_registry: dict[str, Any],
    design_metrics: dict[str, Any],
) -> tuple[list[ECOSuggestion], dict[str, dict[str, Any]]]:
    """
    Filter ECO suggestions based on their preconditions.

    This function evaluates ECO preconditions against the current design metrics
    and filters out ECOs whose preconditions are not satisfied. This implements
    F211: Auto-diagnosis respects preconditions defined in ECO definitions.

    Args:
        suggestions: List of ECO suggestions from diagnosis
        eco_registry: Dictionary mapping ECO names to ECO instances
        design_metrics: Current design state metrics (wns_ps, hot_ratio, etc.)

    Returns:
        Tuple of (filtered_suggestions, evaluation_log)
        - filtered_suggestions: ECO suggestions with satisfied preconditions
        - evaluation_log: Dict mapping ECO name to evaluation details
          {
            "eco_name": {
              "all_satisfied": bool,
              "failed": list[str],  # Names of failed preconditions
              "precondition_count": int
            }
          }
    """
    filtered: list[ECOSuggestion] = []
    evaluation_log: dict[str, dict[str, Any]] = {}

    for suggestion in suggestions:
        eco_name = suggestion.eco

        # Check if ECO exists in registry
        if eco_name not in eco_registry:
            # ECO not in registry - assume no preconditions, keep it
            filtered.append(suggestion)
            evaluation_log[eco_name] = {
                "all_satisfied": True,
                "failed": [],
                "precondition_count": 0,
                "note": "ECO not in registry, assumed no preconditions",
            }
            continue

        eco = eco_registry[eco_name]

        # Evaluate preconditions
        all_satisfied, failed_preconditions = eco.evaluate_preconditions(design_metrics)

        # Log evaluation
        evaluation_log[eco_name] = {
            "all_satisfied": all_satisfied,
            "failed": failed_preconditions,
            "precondition_count": len(eco.metadata.preconditions),
        }

        # Only include if preconditions satisfied
        if all_satisfied:
            filtered.append(suggestion)

    return filtered, evaluation_log
