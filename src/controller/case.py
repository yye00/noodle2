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
