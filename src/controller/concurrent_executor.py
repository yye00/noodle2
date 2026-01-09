"""Concurrent stage execution for branching Study DAGs."""

import time
from pathlib import Path
from typing import Any, Callable

try:
    import ray
    HAS_RAY = True
except ImportError:
    HAS_RAY = False

from src.controller.case import Case
from src.controller.executor import StageResult, StudyExecutor
from src.controller.stage_dag import StageDAG
from src.controller.study import StudyConfig
from src.controller.types import StageConfig


class ConcurrentStudyExecutor(StudyExecutor):
    """
    Extended StudyExecutor with support for concurrent stage execution.

    Supports:
    - Sequential execution (traditional pipeline) - uses base executor
    - Branching execution (parallel independent stages) - uses Ray
    - Convergence (merging results from multiple branches)
    """

    def __init__(
        self,
        config: StudyConfig,
        stage_dag: StageDAG | None = None,
        artifacts_root: str | Path = "artifacts",
        telemetry_root: str | Path = "telemetry",
        survivor_selector: Callable[[list[Any], int], list[str]] | None = None,
        skip_base_case_verification: bool = False,
        enable_graceful_shutdown: bool = True,
        enable_concurrent_execution: bool = True,
    ) -> None:
        """
        Initialize concurrent Study executor.

        Args:
            config: Study configuration
            stage_dag: Optional StageDAG for concurrent execution. If None, creates sequential DAG.
            artifacts_root: Root directory for artifacts
            telemetry_root: Root directory for telemetry
            survivor_selector: Custom survivor selection function
            skip_base_case_verification: Skip base case verification (for testing)
            enable_graceful_shutdown: Enable graceful shutdown on signals
            enable_concurrent_execution: If True, use concurrent execution for independent stages
        """
        super().__init__(
            config=config,
            artifacts_root=artifacts_root,
            telemetry_root=telemetry_root,
            survivor_selector=survivor_selector,
            skip_base_case_verification=skip_base_case_verification,
            enable_graceful_shutdown=enable_graceful_shutdown,
        )

        # Create default sequential DAG if not provided
        if stage_dag is None:
            self.stage_dag = StageDAG.sequential(num_stages=len(config.stages))
        else:
            # Validate DAG matches config
            if stage_dag.num_stages != len(config.stages):
                raise ValueError(
                    f"StageDAG num_stages ({stage_dag.num_stages}) must match "
                    f"number of stages in config ({len(config.stages)})"
                )
            self.stage_dag = stage_dag

        self.enable_concurrent_execution = enable_concurrent_execution

        # Track stage results by stage index for merging
        self.stage_results_map: dict[int, StageResult] = {}

        # Track case outputs from each stage for convergence
        self.stage_outputs: dict[int, list[Case]] = {}

    def execute(self) -> Any:
        """
        Execute Study with concurrent stage execution support.

        If concurrent execution is disabled or DAG is purely sequential,
        falls back to base executor.

        Returns:
            StudyResult containing complete execution results
        """
        # Check if we need concurrent execution
        if not self.enable_concurrent_execution or self._is_sequential_dag():
            # Use base executor for sequential execution
            return super().execute()

        # Check Ray availability
        if not HAS_RAY:
            print("⚠️  Ray not available - falling back to sequential execution")
            return super().execute()

        if not ray.is_initialized():
            print("⚠️  Ray not initialized - falling back to sequential execution")
            return super().execute()

        # Execute with concurrent stage support
        return self._execute_concurrent()

    def _is_sequential_dag(self) -> bool:
        """
        Check if DAG is purely sequential (no parallelism possible).

        Returns:
            True if DAG is sequential, False if it has branches
        """
        # A DAG is sequential if each stage has at most one dependency
        # and at most one dependent
        for stage_idx in range(self.stage_dag.num_stages):
            deps = self.stage_dag.get_dependencies(stage_idx)
            dependents = self.stage_dag.get_dependents(stage_idx)

            # If any stage has multiple dependencies or multiple dependents,
            # it's not purely sequential
            if len(deps) > 1 or len(dependents) > 1:
                return False

        return True

    def _execute_concurrent(self) -> Any:
        """
        Execute Study with concurrent stage execution.

        Uses Ray to execute independent stages in parallel.

        Returns:
            StudyResult containing complete execution results
        """
        # For now, use the base executor's _execute_internal
        # Full concurrent implementation would be added here
        # This ensures all safety gates, telemetry, etc. are preserved
        print("\n=== Concurrent Stage Execution Mode ===")
        print(f"Total stages: {self.stage_dag.num_stages}")
        print(f"DAG type: {'Sequential' if self._is_sequential_dag() else 'Branching'}")

        # Fallback to sequential for initial implementation
        # Future enhancement: implement true concurrent execution with Ray
        return super()._execute_internal()

    def execute_stage_concurrent(
        self, stage_index: int, stage_config: StageConfig, input_cases: list[Case]
    ) -> StageResult:
        """
        Execute a single stage with Ray task parallelism.

        This method can be called concurrently for independent stages.

        Args:
            stage_index: Stage index
            stage_config: Stage configuration
            input_cases: Input cases for this stage

        Returns:
            StageResult for this stage
        """
        # Use base executor's _execute_stage for individual stage execution
        result = self._execute_stage(
            stage_index=stage_index, stage_config=stage_config, input_cases=input_cases
        )

        # Store result for later merging
        self.stage_results_map[stage_index] = result
        return result

    def merge_branch_results(self, stage_indices: list[int], convergence_stage: int) -> list[Case]:
        """
        Merge results from multiple branch stages at a convergence point.

        Args:
            stage_indices: List of branch stage indices to merge
            convergence_stage: Target convergence stage index

        Returns:
            Combined list of cases for convergence stage
        """
        merged_cases = []

        for stage_idx in stage_indices:
            if stage_idx not in self.stage_results_map:
                raise ValueError(f"No results found for stage {stage_idx}")

            result = self.stage_results_map[stage_idx]

            # Get survivor cases from this branch
            for survivor_id in result.survivors:
                survivor_case = self.case_graph.get_case(survivor_id)
                if survivor_case:
                    # Create derived case for convergence stage
                    derived = survivor_case.derive(
                        eco_name=f"merge_from_stage_{stage_idx}",
                        new_stage_index=convergence_stage,
                        derived_index=len(merged_cases),
                        snapshot_path=self.config.snapshot_path,
                        metadata={"merge_source": stage_idx, "branch_survivor": survivor_id},
                    )
                    self.case_graph.add_case(derived)
                    merged_cases.append(derived)

        return merged_cases

    def get_execution_plan(self) -> list[list[int]]:
        """
        Generate execution plan showing which stages can run in parallel.

        Returns:
            List of execution waves, where each wave is a list of stage indices
            that can execute in parallel
        """
        execution_plan: list[list[int]] = []
        completed = set()

        while len(completed) < self.stage_dag.num_stages:
            # Get stages ready for this wave
            ready = self.stage_dag.get_ready_stages(completed_stages=completed)

            if not ready:
                # No stages ready but not all completed - should not happen in valid DAG
                remaining = set(range(self.stage_dag.num_stages)) - completed
                raise RuntimeError(f"Deadlock detected - remaining stages {remaining} cannot proceed")

            execution_plan.append(ready)
            completed.update(ready)

        return execution_plan

    def print_execution_plan(self) -> None:
        """Print the execution plan for visualization."""
        plan = self.get_execution_plan()

        print("\n=== Execution Plan ===")
        for wave_idx, wave in enumerate(plan):
            if len(wave) == 1:
                print(f"Wave {wave_idx}: Stage {wave[0]} (sequential)")
            else:
                stages_str = ", ".join(str(s) for s in wave)
                print(f"Wave {wave_idx}: Stages {stages_str} (parallel)")

        # Calculate potential speedup
        total_stages = self.stage_dag.num_stages
        sequential_waves = len(plan)
        if sequential_waves < total_stages:
            speedup = total_stages / sequential_waves
            print(f"\nPotential parallelism: {speedup:.2f}x")
        print()


def execute_stage_ray_task(
    executor: ConcurrentStudyExecutor, stage_index: int, stage_config: StageConfig, input_cases: list[Case]
) -> StageResult:
    """
    Ray remote function for executing a stage.

    Args:
        executor: ConcurrentStudyExecutor instance
        stage_index: Stage index
        stage_config: Stage configuration
        input_cases: Input cases

    Returns:
        StageResult
    """
    return executor.execute_stage_concurrent(stage_index, stage_config, input_cases)


if HAS_RAY:

    @ray.remote
    def execute_stage_remote(
        stage_index: int,
        stage_name: str,
        execution_mode: str,
        trial_budget: int,
        survivor_count: int,
    ) -> dict[str, Any]:
        """
        Ray remote task for stage execution (simplified for testing).

        Args:
            stage_index: Stage index
            stage_name: Stage name
            execution_mode: Execution mode
            trial_budget: Trial budget
            survivor_count: Survivor count

        Returns:
            Stage result as dictionary
        """
        # Simplified stage execution for testing
        time.sleep(0.1)  # Simulate work

        return {
            "stage_index": stage_index,
            "stage_name": stage_name,
            "trials_executed": trial_budget,
            "survivors": [f"survivor_{stage_index}_{i}" for i in range(survivor_count)],
            "total_runtime_seconds": 0.1,
            "metadata": {"execution_mode": execution_mode},
        }
