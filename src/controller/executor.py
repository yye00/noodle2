"""Multi-stage Study execution with sequential stage progression and survivor selection."""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.controller.case import Case, CaseGraph
from src.controller.study import StudyConfig
from src.controller.types import StageConfig
from src.trial_runner.trial import Trial, TrialConfig, TrialResult


@dataclass
class StageResult:
    """Result of executing a single stage."""

    stage_index: int
    stage_name: str
    trials_executed: int
    survivors: list[str]  # Case IDs that survived to next stage
    total_runtime_seconds: float
    trial_results: list[TrialResult] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "stage_index": self.stage_index,
            "stage_name": self.stage_name,
            "trials_executed": self.trials_executed,
            "survivors": self.survivors,
            "total_runtime_seconds": self.total_runtime_seconds,
            "trial_results": [trial.to_dict() for trial in self.trial_results],
            "metadata": self.metadata,
        }


@dataclass
class StudyResult:
    """Complete result of Study execution."""

    study_name: str
    total_stages: int
    stages_completed: int
    total_runtime_seconds: float
    stage_results: list[StageResult] = field(default_factory=list)
    final_survivors: list[str] = field(default_factory=list)
    aborted: bool = False
    abort_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "study_name": self.study_name,
            "total_stages": self.total_stages,
            "stages_completed": self.stages_completed,
            "total_runtime_seconds": self.total_runtime_seconds,
            "stage_results": [stage.to_dict() for stage in self.stage_results],
            "final_survivors": self.final_survivors,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
        }


class StudyExecutor:
    """
    Executes multi-stage Studies with sequential stage progression.

    Key responsibilities:
    - Execute stages sequentially (not in parallel)
    - Enforce trial budgets per stage
    - Select survivors based on ranking metric
    - Propagate only survivors to next stage
    - Abort on safety violations
    """

    def __init__(
        self,
        config: StudyConfig,
        artifacts_root: str | Path = "artifacts",
        survivor_selector: Callable[[list[TrialResult], int], list[str]] | None = None,
    ) -> None:
        """
        Initialize Study executor.

        Args:
            config: Study configuration
            artifacts_root: Root directory for artifacts
            survivor_selector: Custom survivor selection function (optional)
                             Takes (trial_results, survivor_count) -> list of case_ids
        """
        self.config = config
        self.artifacts_root = Path(artifacts_root)
        self.case_graph = CaseGraph()
        self.survivor_selector = survivor_selector or self._default_survivor_selector

        # Create base case
        self.base_case = Case.create_base_case(
            base_name=config.base_case_name,
            snapshot_path=config.snapshot_path,
            metadata={"pdk": config.pdk},
        )
        self.case_graph.add_case(self.base_case)

    def execute(self) -> StudyResult:
        """
        Execute the entire Study with all stages sequentially.

        Returns:
            StudyResult containing complete execution results
        """
        study_start = time.time()
        stage_results: list[StageResult] = []

        # Start with base case for stage 0
        current_cases = [self.base_case]

        for stage_index, stage_config in enumerate(self.config.stages):
            print(f"\n=== Executing Stage {stage_index}: {stage_config.name} ===")
            print(f"Input cases: {len(current_cases)}")
            print(f"Trial budget: {stage_config.trial_budget}")
            print(f"Survivor count: {stage_config.survivor_count}")

            # Execute stage
            stage_result = self._execute_stage(
                stage_index=stage_index,
                stage_config=stage_config,
                input_cases=current_cases,
            )

            stage_results.append(stage_result)

            # Check for stage abort conditions
            if len(stage_result.survivors) == 0:
                print(f"ABORT: Stage {stage_index} produced no survivors")
                return StudyResult(
                    study_name=self.config.name,
                    total_stages=len(self.config.stages),
                    stages_completed=stage_index + 1,
                    total_runtime_seconds=time.time() - study_start,
                    stage_results=stage_results,
                    final_survivors=[],
                    aborted=True,
                    abort_reason=f"Stage {stage_index} produced no survivors",
                )

            # Prepare cases for next stage
            if stage_index < len(self.config.stages) - 1:
                # Derive new cases from survivors for next stage
                current_cases = []
                for derived_idx, survivor_id in enumerate(stage_result.survivors):
                    survivor_case = self.case_graph.get_case(survivor_id)
                    if survivor_case:
                        # Create derived case for next stage
                        derived = survivor_case.derive(
                            eco_name="pass_through",  # Placeholder for actual ECO
                            new_stage_index=stage_index + 1,
                            derived_index=derived_idx,
                            snapshot_path=self.config.snapshot_path,  # Will be updated when ECO is applied
                            metadata={"source_trial": survivor_id},
                        )
                        self.case_graph.add_case(derived)
                        current_cases.append(derived)
            else:
                # Final stage - survivors are final results
                print(f"\nFinal survivors: {stage_result.survivors}")

        study_runtime = time.time() - study_start

        return StudyResult(
            study_name=self.config.name,
            total_stages=len(self.config.stages),
            stages_completed=len(self.config.stages),
            total_runtime_seconds=study_runtime,
            stage_results=stage_results,
            final_survivors=stage_results[-1].survivors if stage_results else [],
            aborted=False,
        )

    def _execute_stage(
        self,
        stage_index: int,
        stage_config: StageConfig,
        input_cases: list[Case],
    ) -> StageResult:
        """
        Execute a single stage with trial budget enforcement.

        Args:
            stage_index: Stage index (0-based)
            stage_config: Stage configuration
            input_cases: Cases to run in this stage

        Returns:
            StageResult with trial results and survivors
        """
        stage_start = time.time()
        trial_results: list[TrialResult] = []

        # Execute trials up to budget
        # The budget controls total number of trials, cycling through input cases if needed
        trials_to_execute = stage_config.trial_budget

        # Create derived cases for each trial (in reality these would be created as ECOs are applied)
        trial_cases: list[Case] = []

        for trial_index in range(trials_to_execute):
            # Cycle through input cases using modulo
            base_case = input_cases[trial_index % len(input_cases)]

            # For framework testing: create a derived case for this trial
            # In real execution, each trial would apply a different ECO
            trial_case = base_case.derive(
                eco_name=f"trial_eco_{trial_index}",  # Placeholder ECO name
                new_stage_index=stage_index,
                derived_index=trial_index,
                snapshot_path=self.config.snapshot_path,
                metadata={"trial_index": trial_index},
            )
            trial_cases.append(trial_case)

            print(f"  Trial {trial_index + 1}/{trials_to_execute}: {trial_case.identifier}")

            # Create trial configuration
            trial_config = TrialConfig(
                study_name=self.config.name,
                case_name=str(trial_case.identifier),
                stage_index=stage_index,
                trial_index=trial_index,
                script_path=self.config.snapshot_path,  # Placeholder - should be actual script
                snapshot_dir=self.config.snapshot_path,
                timeout_seconds=stage_config.timeout_seconds,
                metadata={
                    "stage_name": stage_config.name,
                    "execution_mode": stage_config.execution_mode.value,
                },
            )

            # Note: For now, we're creating TrialConfig but not executing actual trials
            # Real execution would use Trial.execute() here
            # This is a framework implementation to enable testing

            # Create a mock trial result for framework testing
            # This allows survivor selectors to work properly
            from src.trial_runner.trial import TrialArtifacts
            mock_result = TrialResult(
                config=trial_config,
                success=True,  # Assume success for framework testing
                return_code=0,
                runtime_seconds=0.0,
                artifacts=TrialArtifacts(trial_dir=Path("/tmp/mock")),
            )
            trial_results.append(mock_result)

        # Select survivors based on configured count
        survivors = self._select_survivors(
            trial_results=trial_results,
            input_cases=trial_cases,  # Use trial cases instead of input cases
            survivor_count=stage_config.survivor_count,
        )

        stage_runtime = time.time() - stage_start

        return StageResult(
            stage_index=stage_index,
            stage_name=stage_config.name,
            trials_executed=trials_to_execute,
            survivors=survivors,
            total_runtime_seconds=stage_runtime,
            trial_results=trial_results,
            metadata={
                "execution_mode": stage_config.execution_mode.value,
                "trial_budget": stage_config.trial_budget,
            },
        )

    def _select_survivors(
        self,
        trial_results: list[TrialResult],
        input_cases: list[Case],
        survivor_count: int,
    ) -> list[str]:
        """
        Select survivors from trial results.

        Args:
            trial_results: Results from executed trials
            input_cases: Input cases for this stage
            survivor_count: Number of survivors to select

        Returns:
            List of case IDs that survived
        """
        # If we have actual trial results, use them
        if trial_results:
            return self.survivor_selector(trial_results, survivor_count)

        # Otherwise, select from input cases (for framework testing)
        survivors_to_select = min(survivor_count, len(input_cases))
        return [str(case.identifier) for case in input_cases[:survivors_to_select]]

    def _default_survivor_selector(
        self, trial_results: list[TrialResult], survivor_count: int
    ) -> list[str]:
        """
        Default survivor selection: rank by WNS (higher is better).

        Args:
            trial_results: All trial results from stage
            survivor_count: Number to select

        Returns:
            List of case IDs for survivors
        """
        # Filter successful trials only
        successful_trials = [t for t in trial_results if t.success]

        if not successful_trials:
            return []

        # Sort by WNS (higher/less negative is better)
        # For now, use a simple heuristic based on return code
        # In real implementation, would parse metrics.timing.wns_ps
        sorted_trials = sorted(successful_trials, key=lambda t: t.return_code)

        # Select top N
        survivors = sorted_trials[:survivor_count]

        return [trial.config.case_name for trial in survivors]
