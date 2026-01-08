"""Case management and lineage tracking for Noodle 2."""

from dataclasses import dataclass, field
from typing import Optional

from .types import CaseIdentifier


@dataclass
class Case:
    """
    Represents a concrete design state within a Study.

    Cases form a directed acyclic graph (DAG):
    - Base Case: original snapshot (no parent)
    - Derived Cases: created by applying ECOs (has parent)

    Attributes:
        identifier: Deterministic case name
        parent_id: Parent case (None for base case)
        eco_applied: ECO name that produced this case (None for base case)
        stage_index: Current stage index
        snapshot_path: Path to design snapshot for this case
        metadata: Additional case-specific data
    """

    identifier: CaseIdentifier
    parent_id: Optional[str] = None
    eco_applied: Optional[str] = None
    stage_index: int = 0
    snapshot_path: str = ""
    metadata: dict = field(default_factory=dict)

    @property
    def case_id(self) -> str:
        """Get string representation of case identifier."""
        return str(self.identifier)

    @property
    def case_name(self) -> str:
        """Get base case name without stage/derived indices."""
        return self.identifier.case_name

    @property
    def is_base_case(self) -> bool:
        """Check if this is the base case (no parent)."""
        return self.parent_id is None

    @classmethod
    def create_base_case(
        cls,
        base_name: str,
        snapshot_path: str,
        metadata: Optional[dict] = None,
    ) -> "Case":
        """
        Create the base case for a Study.

        Base case uses stage_index=0, derived_index=0 by convention,
        but has no parent and no ECO applied.

        Args:
            base_name: Base case name (e.g., "nangate45_base")
            snapshot_path: Path to base snapshot
            metadata: Optional metadata

        Returns:
            Base Case instance
        """
        identifier = CaseIdentifier(
            case_name=base_name,
            stage_index=0,
            derived_index=0,
        )
        return cls(
            identifier=identifier,
            parent_id=None,
            eco_applied=None,
            stage_index=0,
            snapshot_path=snapshot_path,
            metadata=metadata or {},
        )

    def derive(
        self,
        eco_name: str,
        new_stage_index: int,
        derived_index: int,
        snapshot_path: str,
        metadata: Optional[dict] = None,
    ) -> "Case":
        """
        Create a derived case from this case.

        Args:
            eco_name: Name of ECO being applied
            new_stage_index: Stage index for derived case
            derived_index: Derived case index within stage
            snapshot_path: Path to derived snapshot
            metadata: Optional metadata

        Returns:
            New derived Case
        """
        new_identifier = CaseIdentifier(
            case_name=self.identifier.case_name,
            stage_index=new_stage_index,
            derived_index=derived_index,
        )
        return Case(
            identifier=new_identifier,
            parent_id=self.case_id,
            eco_applied=eco_name,
            stage_index=new_stage_index,
            snapshot_path=snapshot_path,
            metadata=metadata or {},
        )


@dataclass
class CaseLineage:
    """
    Tracks the complete lineage of a case back to the base case.

    This enables traceability and auditability across complex
    branching experiments.
    """

    case_id: str
    ancestors: list[str] = field(default_factory=list)
    ecos_applied: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        """Generate human-readable lineage."""
        if not self.ancestors:
            return f"{self.case_id} (base case)"

        lineage_parts = []
        for ancestor, eco in zip(self.ancestors, self.ecos_applied):
            lineage_parts.append(f"{ancestor} --[{eco}]-->")
        lineage_parts.append(self.case_id)

        return " ".join(lineage_parts)


class CaseGraph:
    """
    Manages the DAG of cases within a Study.

    Provides methods to:
    - Track all cases
    - Query lineage
    - Find cases by stage
    - Validate case references
    """

    def __init__(self) -> None:
        """Initialize empty case graph."""
        self.cases: dict[str, Case] = {}

    def add_case(self, case: Case) -> None:
        """
        Add a case to the graph.

        Args:
            case: Case to add

        Raises:
            ValueError: If case ID already exists
            ValueError: If parent case doesn't exist
        """
        case_id = case.case_id

        if case_id in self.cases:
            raise ValueError(f"Case {case_id} already exists in graph")

        # Validate parent exists (except for base case)
        if case.parent_id is not None and case.parent_id not in self.cases:
            raise ValueError(
                f"Parent case {case.parent_id} not found for case {case_id}"
            )

        self.cases[case_id] = case

    def get_case(self, case_id: str) -> Optional[Case]:
        """Get case by ID."""
        return self.cases.get(case_id)

    def get_lineage(self, case_id: str) -> CaseLineage:
        """
        Get complete lineage for a case.

        Args:
            case_id: Case to trace

        Returns:
            CaseLineage with ancestors and ECOs

        Raises:
            ValueError: If case not found
        """
        case = self.cases.get(case_id)
        if case is None:
            raise ValueError(f"Case {case_id} not found in graph")

        ancestors = []
        ecos = []

        current = case
        while current.parent_id is not None:
            parent = self.cases.get(current.parent_id)
            if parent is None:
                raise ValueError(
                    f"Parent {current.parent_id} not found (broken lineage)"
                )

            ancestors.insert(0, parent.case_id)
            ecos.insert(0, current.eco_applied or "unknown")
            current = parent

        return CaseLineage(
            case_id=case_id,
            ancestors=ancestors,
            ecos_applied=ecos,
        )

    def get_cases_by_stage(self, stage_index: int) -> list[Case]:
        """Get all cases at a specific stage."""
        return [
            case for case in self.cases.values()
            if case.stage_index == stage_index
        ]

    def get_base_case(self) -> Optional[Case]:
        """Get the base case (no parent)."""
        for case in self.cases.values():
            if case.is_base_case:
                return case
        return None

    def count_cases(self) -> int:
        """Get total number of cases in graph."""
        return len(self.cases)

    def count_cases_by_stage(self, stage_index: int) -> int:
        """Count cases at a specific stage."""
        return len(self.get_cases_by_stage(stage_index))

    def export_dag(self) -> dict:
        """
        Export the case DAG in machine-readable format.

        Returns a dictionary with:
        - nodes: List of all cases with their metadata
        - edges: List of parent-child relationships
        - statistics: DAG statistics (depth, branching factor, etc.)

        Returns:
            Dictionary representation of the DAG
        """
        nodes = []
        edges = []

        for case in self.cases.values():
            # Add node
            nodes.append({
                "case_id": case.case_id,
                "case_name": case.case_name,
                "stage_index": case.stage_index,
                "derived_index": case.identifier.derived_index,
                "is_base_case": case.is_base_case,
                "eco_applied": case.eco_applied,
                "snapshot_path": case.snapshot_path,
                "metadata": case.metadata,
            })

            # Add edge if there's a parent
            if case.parent_id is not None:
                edges.append({
                    "source": case.parent_id,
                    "target": case.case_id,
                    "eco": case.eco_applied,
                })

        # Calculate statistics
        stats = {
            "total_cases": len(nodes),
            "total_edges": len(edges),
            "max_stage": max((case.stage_index for case in self.cases.values()), default=0),
            "cases_per_stage": {
                i: self.count_cases_by_stage(i)
                for i in range(max((case.stage_index for case in self.cases.values()), default=0) + 1)
            },
        }

        return {
            "nodes": nodes,
            "edges": edges,
            "statistics": stats,
        }

    def verify_dag_integrity(self) -> tuple[bool, list[str]]:
        """
        Verify that the case graph is a valid DAG (no cycles).

        Uses depth-first search to detect cycles.

        Returns:
            Tuple of (is_valid, errors)
            - is_valid: True if DAG is valid (no cycles, all parents exist)
            - errors: List of error messages if invalid
        """
        errors = []

        # Check 1: All parents exist
        for case in self.cases.values():
            if case.parent_id is not None and case.parent_id not in self.cases:
                errors.append(
                    f"Case {case.case_id} references non-existent parent {case.parent_id}"
                )

        # Check 2: Detect cycles using DFS
        visited = set()
        rec_stack = set()

        def has_cycle(case_id: str) -> bool:
            """DFS to detect cycles."""
            visited.add(case_id)
            rec_stack.add(case_id)

            case = self.cases.get(case_id)
            if case and case.parent_id:
                if case.parent_id not in visited:
                    if has_cycle(case.parent_id):
                        return True
                elif case.parent_id in rec_stack:
                    errors.append(
                        f"Cycle detected involving case {case_id} and parent {case.parent_id}"
                    )
                    return True

            rec_stack.remove(case_id)
            return False

        for case_id in self.cases:
            if case_id not in visited:
                if has_cycle(case_id):
                    break

        return (len(errors) == 0, errors)

    def get_dag_depth(self) -> int:
        """
        Calculate the maximum depth of the DAG.

        Depth is the longest path from base case to any leaf case.

        Returns:
            Maximum DAG depth
        """
        def calculate_depth(case_id: str, memo: dict[str, int]) -> int:
            """Calculate depth for a case with memoization."""
            if case_id in memo:
                return memo[case_id]

            case = self.cases[case_id]
            if case.is_base_case:
                depth = 0
            else:
                parent_depth = calculate_depth(case.parent_id, memo)
                depth = parent_depth + 1

            memo[case_id] = depth
            return depth

        if not self.cases:
            return 0

        memo: dict[str, int] = {}
        return max(calculate_depth(case_id, memo) for case_id in self.cases)

    def get_leaf_cases(self) -> list[Case]:
        """
        Get all leaf cases (cases with no children).

        Returns:
            List of leaf cases
        """
        # Find all cases that are parents
        parent_ids = {case.parent_id for case in self.cases.values() if case.parent_id}

        # Leaf cases are those not in the parent set
        return [
            case for case in self.cases.values()
            if case.case_id not in parent_ids
        ]

    def export_to_dot(self) -> str:
        """
        Export the case lineage graph in Graphviz DOT format.

        Generates a directed graph with:
        - Nodes representing cases (with stage and ECO info)
        - Edges representing parent-child relationships (labeled with ECO names)
        - Visual styling based on case properties (base case highlighted)

        Returns:
            String containing DOT format graph specification
        """
        lines = []
        lines.append("digraph CaseLineage {")
        lines.append("  rankdir=TB;  // Top to bottom layout")
        lines.append("  node [shape=box, style=rounded];")
        lines.append("")

        # Add nodes
        for case in self.cases.values():
            case_id = case.case_id.replace("-", "_").replace(".", "_")

            # Build node label with case info
            label_parts = [case.case_id]
            if case.is_base_case:
                label_parts.append("(BASE)")
            else:
                label_parts.append(f"Stage {case.stage_index}")

            label = "\\n".join(label_parts)

            # Style base case differently
            if case.is_base_case:
                style = 'node [shape=box, style="rounded,filled", fillcolor=lightblue];'
                lines.append(f"  {style}")
                lines.append(f'  {case_id} [label="{label}"];')
            else:
                lines.append(f'  {case_id} [label="{label}"];')

        lines.append("")

        # Add edges
        for case in self.cases.values():
            if case.parent_id is not None:
                source_id = case.parent_id.replace("-", "_").replace(".", "_")
                target_id = case.case_id.replace("-", "_").replace(".", "_")
                eco_label = case.eco_applied or "unknown"
                lines.append(f'  {source_id} -> {target_id} [label="{eco_label}"];')

        lines.append("}")
        return "\n".join(lines)
