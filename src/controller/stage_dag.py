"""Stage DAG and dependency management for concurrent execution."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StageRelation(str, Enum):
    """Type of relationship between stages."""

    SEQUENTIAL = "sequential"  # Stage B depends on A completing
    INDEPENDENT = "independent"  # Stages can run in parallel
    CONVERGENCE = "convergence"  # Multiple stages feed into one


@dataclass
class StageDependency:
    """Defines a dependency relationship between stages."""

    from_stage: int  # Stage index that must complete first
    to_stage: int  # Stage index that depends on from_stage
    relation: StageRelation = StageRelation.SEQUENTIAL

    def __post_init__(self) -> None:
        """Validate dependency relationship."""
        if self.from_stage < 0:
            raise ValueError("from_stage must be non-negative")
        if self.to_stage < 0:
            raise ValueError("to_stage must be non-negative")
        if self.from_stage == self.to_stage:
            raise ValueError("Stage cannot depend on itself")


@dataclass
class StageDAG:
    """
    Directed Acyclic Graph representing stage dependencies.

    Supports:
    - Sequential execution (traditional pipeline)
    - Branching execution (multiple independent paths)
    - Convergence (multiple paths merge into one stage)
    """

    num_stages: int
    dependencies: list[StageDependency] = field(default_factory=list)
    _adjacency_list: dict[int, list[int]] = field(default_factory=dict, init=False, repr=False)
    _reverse_adjacency: dict[int, list[int]] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        """Build adjacency lists from dependencies."""
        if self.num_stages <= 0:
            raise ValueError("num_stages must be positive")

        # Build adjacency lists
        self._adjacency_list = {i: [] for i in range(self.num_stages)}
        self._reverse_adjacency = {i: [] for i in range(self.num_stages)}

        for dep in self.dependencies:
            if dep.from_stage >= self.num_stages or dep.to_stage >= self.num_stages:
                raise ValueError(f"Dependency references invalid stage: {dep.from_stage} -> {dep.to_stage}")
            self._adjacency_list[dep.from_stage].append(dep.to_stage)
            self._reverse_adjacency[dep.to_stage].append(dep.from_stage)

        # Verify DAG property (no cycles)
        if self._has_cycle():
            raise ValueError("Stage dependencies contain a cycle - must be a DAG")

    def _has_cycle(self) -> bool:
        """Check if the graph contains a cycle using DFS."""
        visited = set()
        rec_stack = set()

        def dfs(node: int) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in self._adjacency_list[node]:
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in range(self.num_stages):
            if node not in visited:
                if dfs(node):
                    return True

        return False

    def get_dependencies(self, stage_index: int) -> list[int]:
        """
        Get list of stages that must complete before the given stage can start.

        Args:
            stage_index: Stage to query

        Returns:
            List of stage indices that this stage depends on
        """
        if stage_index < 0 or stage_index >= self.num_stages:
            raise ValueError(f"Invalid stage_index: {stage_index}")
        return self._reverse_adjacency[stage_index].copy()

    def get_dependents(self, stage_index: int) -> list[int]:
        """
        Get list of stages that depend on the given stage.

        Args:
            stage_index: Stage to query

        Returns:
            List of stage indices that depend on this stage
        """
        if stage_index < 0 or stage_index >= self.num_stages:
            raise ValueError(f"Invalid stage_index: {stage_index}")
        return self._adjacency_list[stage_index].copy()

    def get_ready_stages(self, completed_stages: set[int]) -> list[int]:
        """
        Get list of stages that are ready to execute.

        A stage is ready if all its dependencies have completed.

        Args:
            completed_stages: Set of stage indices that have completed

        Returns:
            List of stage indices ready to execute
        """
        ready = []
        for stage_idx in range(self.num_stages):
            if stage_idx in completed_stages:
                continue

            deps = self.get_dependencies(stage_idx)
            if all(dep in completed_stages for dep in deps):
                ready.append(stage_idx)

        return ready

    def get_independent_branches(self, start_stages: list[int]) -> list[list[int]]:
        """
        Identify independent execution branches from given starting stages.

        Args:
            start_stages: List of stages to start from (usually stages with no dependencies)

        Returns:
            List of branches, where each branch is a list of stage indices
        """
        branches: list[list[int]] = []

        for start in start_stages:
            branch = self._trace_branch(start, set())
            if branch:
                branches.append(branch)

        return branches

    def _trace_branch(self, stage_idx: int, visited: set[int]) -> list[int]:
        """
        Trace a single branch from a starting stage.

        Args:
            stage_idx: Starting stage
            visited: Set of already visited stages

        Returns:
            List of stages in this branch
        """
        if stage_idx in visited:
            return []

        branch = [stage_idx]
        visited.add(stage_idx)

        dependents = self.get_dependents(stage_idx)

        # If single dependent, continue the branch
        if len(dependents) == 1:
            branch.extend(self._trace_branch(dependents[0], visited))
        # If multiple dependents, this is a branching point - stop here
        # If no dependents, this is a terminal stage

        return branch

    def topological_sort(self) -> list[int]:
        """
        Return a topological ordering of stages.

        Returns:
            List of stage indices in topological order

        Raises:
            ValueError: If graph has a cycle (should not happen if __post_init__ passed)
        """
        in_degree = [len(self.get_dependencies(i)) for i in range(self.num_stages)]
        queue = [i for i in range(self.num_stages) if in_degree[i] == 0]
        result = []

        while queue:
            # Sort for determinism
            queue.sort()
            node = queue.pop(0)
            result.append(node)

            for dependent in self.get_dependents(node):
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)

        if len(result) != self.num_stages:
            raise ValueError("Graph has a cycle")

        return result

    def is_convergence_point(self, stage_index: int) -> bool:
        """
        Check if a stage is a convergence point (multiple inputs).

        Args:
            stage_index: Stage to check

        Returns:
            True if stage has multiple dependencies
        """
        deps = self.get_dependencies(stage_index)
        return len(deps) > 1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "num_stages": self.num_stages,
            "dependencies": [
                {
                    "from_stage": dep.from_stage,
                    "to_stage": dep.to_stage,
                    "relation": dep.relation.value,
                }
                for dep in self.dependencies
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StageDAG":
        """Create StageDAG from dictionary."""
        dependencies = [
            StageDependency(
                from_stage=dep["from_stage"],
                to_stage=dep["to_stage"],
                relation=StageRelation(dep["relation"]),
            )
            for dep in data["dependencies"]
        ]
        return cls(num_stages=data["num_stages"], dependencies=dependencies)

    @classmethod
    def sequential(cls, num_stages: int) -> "StageDAG":
        """
        Create a sequential DAG (traditional pipeline).

        Args:
            num_stages: Number of stages

        Returns:
            StageDAG with sequential dependencies
        """
        if num_stages <= 0:
            raise ValueError("num_stages must be positive")

        dependencies = [
            StageDependency(from_stage=i, to_stage=i + 1, relation=StageRelation.SEQUENTIAL)
            for i in range(num_stages - 1)
        ]
        return cls(num_stages=num_stages, dependencies=dependencies)

    @classmethod
    def branching(cls, common_stages: int, branches: list[int], merge_stage: bool = False) -> "StageDAG":
        """
        Create a branching DAG with common prefix, parallel branches, and optional merge.

        Args:
            common_stages: Number of initial sequential stages
            branches: List of branch lengths (number of stages per branch)
            merge_stage: If True, add a final convergence stage

        Returns:
            StageDAG with branching structure

        Example:
            branching(common_stages=2, branches=[2, 3], merge_stage=True)
            Creates:
              0 -> 1 -> 2 -> 3 -----> 5 (merge)
                     \\-> 4 -> 6 -> 7 /
        """
        if common_stages < 0:
            raise ValueError("common_stages must be non-negative")
        if not branches:
            raise ValueError("Must have at least one branch")
        if any(b <= 0 for b in branches):
            raise ValueError("All branch lengths must be positive")

        dependencies = []
        stage_idx = 0

        # Common stages (sequential)
        for i in range(common_stages - 1):
            dependencies.append(StageDependency(from_stage=i, to_stage=i + 1))
        stage_idx = common_stages

        # Create branches
        branch_starts = []
        branch_ends = []

        for branch_length in branches:
            branch_start = stage_idx

            # First stage of branch depends on last common stage (or is independent if no common stages)
            if common_stages > 0:
                dependencies.append(
                    StageDependency(
                        from_stage=common_stages - 1, to_stage=branch_start, relation=StageRelation.INDEPENDENT
                    )
                )

            branch_starts.append(branch_start)

            # Sequential stages within branch
            for i in range(branch_length - 1):
                dependencies.append(StageDependency(from_stage=stage_idx, to_stage=stage_idx + 1))
                stage_idx += 1

            branch_ends.append(stage_idx)
            stage_idx += 1

        # Optional merge stage
        if merge_stage:
            merge_idx = stage_idx
            for branch_end in branch_ends:
                dependencies.append(
                    StageDependency(from_stage=branch_end, to_stage=merge_idx, relation=StageRelation.CONVERGENCE)
                )
            stage_idx += 1

        return cls(num_stages=stage_idx, dependencies=dependencies)
