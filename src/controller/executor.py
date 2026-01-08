"""Multi-stage Study execution with sequential stage progression and survivor selection."""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.controller.case import Case, CaseGraph
from src.controller.safety import check_study_legality, generate_legality_report
from src.controller.stage_abort import evaluate_stage_abort, StageAbortDecision
from src.controller.study import StudyConfig
from src.controller.telemetry import StageTelemetry, StudyTelemetry, TelemetryEmitter
from src.controller.types import ECOClass, ExecutionMode, StageConfig
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
    abort_decision: StageAbortDecision | None = None

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
            "abort_decision": self.abort_decision.to_dict() if self.abort_decision else None,
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
    # Study metadata for documentation and cataloging
    author: str | None = None
    creation_date: str | None = None
    description: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "study_name": self.study_name,
            "total_stages": self.total_stages,
            "stages_completed": self.stages_completed,
            "total_runtime_seconds": self.total_runtime_seconds,
            "stage_results": [stage.to_dict() for stage in self.stage_results],
            "final_survivors": self.final_survivors,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
        }

        # Include metadata if present
        if self.author is not None:
            result["author"] = self.author
        if self.creation_date is not None:
            result["creation_date"] = self.creation_date
        if self.description is not None:
            result["description"] = self.description

        return result


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
        telemetry_root: str | Path = "telemetry",
        survivor_selector: Callable[[list[TrialResult], int], list[str]] | None = None,
        skip_base_case_verification: bool = False,
    ) -> None:
        """
        Initialize Study executor.

        Args:
            config: Study configuration
            artifacts_root: Root directory for artifacts
            telemetry_root: Root directory for telemetry
            survivor_selector: Custom survivor selection function (optional)
                             Takes (trial_results, survivor_count) -> list of case_ids
            skip_base_case_verification: Skip base case verification (for testing only)
        """
        self.config = config
        self.artifacts_root = Path(artifacts_root)
        self.case_graph = CaseGraph()
        self.survivor_selector = survivor_selector or self._default_survivor_selector
        self.skip_base_case_verification = skip_base_case_verification

        # Initialize telemetry emitter
        self.telemetry_emitter = TelemetryEmitter(
            study_name=config.name,
            telemetry_root=telemetry_root,
        )

        # Create base case
        self.base_case = Case.create_base_case(
            base_name=config.base_case_name,
            snapshot_path=config.snapshot_path,
            metadata={"pdk": config.pdk},
        )
        self.case_graph.add_case(self.base_case)

        # Store baseline WNS for abort threshold checks
        self.baseline_wns_ps: int | None = None

    def verify_base_case(self) -> tuple[bool, str]:
        """
        Verify base case structural runnability before ECO experimentation.

        Executes the base case with no-op ECO to ensure:
        - Tool return code rc == 0
        - Required reports are produced
        - Parseable metrics can be extracted

        Returns:
            Tuple of (is_valid, failure_message)
            - is_valid: True if base case is structurally runnable
            - failure_message: Empty if valid, error description if invalid
        """
        print("\n=== Verifying Base Case Structural Runnability ===")
        print(f"Base case: {self.base_case.case_name}")
        print(f"Snapshot: {self.base_case.snapshot_path}")

        # For base case verification, we need to use the STA script from the snapshot
        # Assume run_sta.tcl exists in the snapshot directory
        script_path = Path(self.base_case.snapshot_path) / "run_sta.tcl"

        # Create a trial for base case verification
        # Use the execution mode from stage 0 (or default to STA_ONLY for verification)
        execution_mode = self.config.stages[0].execution_mode if self.config.stages else ExecutionMode.STA_ONLY

        trial_config = TrialConfig(
            study_name=self.config.name,
            case_name=self.base_case.case_name,
            stage_index=0,
            trial_index=0,
            script_path=str(script_path),
            snapshot_dir=str(self.base_case.snapshot_path),
            execution_mode=execution_mode,
            metadata={"verification": True, "pdk": self.config.pdk},
        )

        # Execute verification trial
        trial = Trial(trial_config, artifacts_root=str(self.artifacts_root))

        try:
            result = trial.execute()
        except Exception as e:
            # Any exception during base case execution is a structural failure
            failure_msg = (
                f"Base case failed structural runnability check:\n"
                f"  Exception: {type(e).__name__}\n"
                f"  Message: {str(e)}"
            )
            print(f"\nBASE CASE FAILURE:\n{failure_msg}")
            return False, failure_msg

        # Check for structural failures
        if not result.success:
            failure_msg = (
                f"Base case failed structural runnability check:\n"
                f"  Return code: {result.return_code}\n"
                f"  Failure type: {result.failure_type}\n"
                f"  Reason: {result.failure_reason}\n"
                f"  Log excerpt:\n{result.log_excerpt}"
            )
            print(f"\nBASE CASE FAILURE:\n{failure_msg}")
            return False, failure_msg

        # Check that required reports were produced
        if result.metrics is None:
            failure_msg = (
                f"Base case did not produce required metrics.\n"
                f"  Return code: {result.return_code}\n"
                f"  Artifact path: {result.artifact_path}"
            )
            print(f"\nBASE CASE FAILURE:\n{failure_msg}")
            return False, failure_msg

        # Base case is valid
        print(f"✓ Base case verification PASSED")
        if result.metrics:
            # Metrics could be a dict or an object
            if isinstance(result.metrics, dict):
                if "timing" in result.metrics:
                    timing = result.metrics["timing"]
                    if isinstance(timing, dict):
                        wns = timing.get("wns_ps")
                        tns = timing.get("tns_ps")
                    else:
                        wns = timing.wns_ps
                        tns = timing.tns_ps if hasattr(timing, "tns_ps") else None
                    if wns is not None:
                        print(f"  WNS: {wns} ps")
                        # Store baseline WNS for abort threshold checks
                        self.baseline_wns_ps = wns
                    if tns is not None:
                        print(f"  TNS: {tns} ps")
            else:
                # Object with attributes
                wns = result.metrics.timing.wns_ps
                print(f"  WNS: {wns} ps")
                # Store baseline WNS for abort threshold checks
                self.baseline_wns_ps = wns
                if result.metrics.timing.tns_ps is not None:
                    print(f"  TNS: {result.metrics.timing.tns_ps} ps")
        print(f"  Return code: {result.return_code}")

        return True, ""

    def is_eco_class_allowed(self, eco_class: ECOClass, stage_index: int) -> bool:
        """
        Check if an ECO class is allowed in the current safety domain and stage.

        Args:
            eco_class: ECO class to validate
            stage_index: Stage index (0-based)

        Returns:
            True if ECO class is allowed, False otherwise
        """
        from src.controller.safety import SAFETY_POLICY

        # Get allowed ECO classes for this safety domain
        allowed_classes = SAFETY_POLICY.get(self.config.safety_domain, [])

        # Check if ECO class is allowed globally
        if eco_class not in allowed_classes:
            return False

        # Check if ECO class is allowed in this specific stage
        if stage_index < len(self.config.stages):
            stage_config = self.config.stages[stage_index]
            if eco_class not in stage_config.allowed_eco_classes:
                return False

        return True

    def execute(self) -> StudyResult:
        """
        Execute the entire Study with all stages sequentially.

        SAFETY GATES:
        1. Safety domain enforcement (ECO class legality)
        2. Base case verification (structural runnability)

        Returns:
            StudyResult containing complete execution results
        """
        study_start = time.time()
        stage_results: list[StageResult] = []

        # Initialize Study-level telemetry
        study_telemetry = StudyTelemetry(
            study_name=self.config.name,
            safety_domain=self.config.safety_domain.value,
            total_stages=len(self.config.stages),
        )

        # SAFETY GATE 1: Check Study legality (safety domain enforcement)
        print("\n=== Safety Domain Enforcement ===")
        print(f"Safety domain: {self.config.safety_domain.value}")

        try:
            # This will raise ValueError if Study is illegal
            legality_result = check_study_legality(self.config)
            print("✓ Study configuration is LEGAL")

            # Generate and save legality report
            legality_report = generate_legality_report(
                self.config,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )

            # Save legality report to artifacts
            report_dir = self.artifacts_root / self.config.name
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / "run_legality_report.txt"
            with open(report_path, "w") as f:
                f.write(str(legality_report))
            print(f"Run Legality Report saved to: {report_path}")

        except ValueError as e:
            # Study is illegal - block execution
            print(f"\n🚫 STUDY BLOCKED: {str(e)}")

            # Finalize and emit study telemetry for blocked study
            study_telemetry.finalize(
                final_survivors=[],
                aborted=True,
                abort_reason=f"Study configuration is ILLEGAL: {str(e)}",
            )
            self.telemetry_emitter.emit_study_telemetry(study_telemetry)

            return StudyResult(
                study_name=self.config.name,
                total_stages=len(self.config.stages),
                stages_completed=0,
                total_runtime_seconds=time.time() - study_start,
                stage_results=[],
                final_survivors=[],
                aborted=True,
                abort_reason=f"Study configuration is ILLEGAL: {str(e)}",
                author=self.config.author,
                creation_date=self.config.creation_date,
                description=self.config.description,
            )

        # SAFETY GATE 2: Verify base case before ECO experimentation
        if not self.skip_base_case_verification:
            is_valid, failure_message = self.verify_base_case()
            if not is_valid:
                print("\n🚫 STUDY BLOCKED: Base case failed structural runnability")
                print("No ECO experimentation will be allowed.")

                # Finalize and emit study telemetry for blocked study
                study_telemetry.finalize(
                    final_survivors=[],
                    aborted=True,
                    abort_reason=f"Base case failed structural runnability: {failure_message}",
                )
                self.telemetry_emitter.emit_study_telemetry(study_telemetry)

                return StudyResult(
                    study_name=self.config.name,
                    total_stages=len(self.config.stages),
                    stages_completed=0,
                    total_runtime_seconds=time.time() - study_start,
                    stage_results=[],
                    final_survivors=[],
                    aborted=True,
                    abort_reason=f"Base case failed structural runnability: {failure_message}",
                    author=self.config.author,
                    creation_date=self.config.creation_date,
                    description=self.config.description,
                )

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

            # Emit stage telemetry
            self._emit_stage_telemetry(stage_result, stage_config, study_telemetry)

            # Check for stage abort conditions using comprehensive abort logic
            if stage_result.abort_decision and stage_result.abort_decision.should_abort:
                abort_reason_str = (
                    f"Stage {stage_index} aborted: {stage_result.abort_decision.reason.value if stage_result.abort_decision.reason else 'unknown'}\n"
                    f"Details: {stage_result.abort_decision.details}"
                )
                print(f"\n🚫 STAGE ABORT: {abort_reason_str}")

                # Print violating trials if any
                if stage_result.abort_decision.violating_trials:
                    print(f"Violating trials ({len(stage_result.abort_decision.violating_trials)}):")
                    for trial_id in stage_result.abort_decision.violating_trials[:5]:  # Show first 5
                        print(f"  - {trial_id}")
                    if len(stage_result.abort_decision.violating_trials) > 5:
                        print(f"  ... and {len(stage_result.abort_decision.violating_trials) - 5} more")

                # Finalize and emit study telemetry for aborted study
                study_telemetry.finalize(
                    final_survivors=[],
                    aborted=True,
                    abort_reason=abort_reason_str,
                )
                self.telemetry_emitter.emit_study_telemetry(study_telemetry)
                self.telemetry_emitter.flush_all_case_telemetry()

                return StudyResult(
                    study_name=self.config.name,
                    total_stages=len(self.config.stages),
                    stages_completed=stage_index + 1,
                    total_runtime_seconds=time.time() - study_start,
                    stage_results=stage_results,
                    final_survivors=[],
                    aborted=True,
                    abort_reason=abort_reason_str,
                    author=self.config.author,
                    creation_date=self.config.creation_date,
                    description=self.config.description,
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

        # Finalize and emit study telemetry
        final_survivors = stage_results[-1].survivors if stage_results else []
        study_telemetry.finalize(final_survivors=final_survivors, aborted=False)
        self.telemetry_emitter.emit_study_telemetry(study_telemetry)
        self.telemetry_emitter.flush_all_case_telemetry()

        return StudyResult(
            study_name=self.config.name,
            total_stages=len(self.config.stages),
            stages_completed=len(self.config.stages),
            total_runtime_seconds=study_runtime,
            stage_results=stage_results,
            final_survivors=final_survivors,
            aborted=False,
            author=self.config.author,
            creation_date=self.config.creation_date,
            description=self.config.description,
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
                execution_mode=stage_config.execution_mode,
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

        # Evaluate stage abort conditions
        abort_decision = evaluate_stage_abort(
            stage_config=stage_config,
            trial_results=trial_results,
            survivors=survivors,
            baseline_wns_ps=self.baseline_wns_ps,
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
            abort_decision=abort_decision,
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

    def _emit_stage_telemetry(
        self,
        stage_result: StageResult,
        stage_config: StageConfig,
        study_telemetry: StudyTelemetry,
    ) -> None:
        """
        Emit telemetry for a completed stage.

        Args:
            stage_result: Results from stage execution
            stage_config: Stage configuration
            study_telemetry: Study-level telemetry to update
        """
        # Create stage-level telemetry
        stage_telemetry = StageTelemetry(
            stage_index=stage_result.stage_index,
            stage_name=stage_result.stage_name,
            trial_budget=stage_config.trial_budget,
            survivor_count=stage_config.survivor_count,
            survivors=stage_result.survivors,
            total_runtime_seconds=stage_result.total_runtime_seconds,
        )

        # Aggregate trial results into stage telemetry
        for trial in stage_result.trial_results:
            stage_telemetry.add_trial_result(trial)

            # Update case-level telemetry
            case_telemetry = self.telemetry_emitter.get_or_create_case_telemetry(
                case_id=trial.config.case_name,
                base_case=self.config.base_case_name,
                stage_index=trial.config.stage_index,
                derived_index=trial.config.trial_index,  # Simplified for now
            )
            case_telemetry.add_trial(trial)

        # Emit stage telemetry to disk
        self.telemetry_emitter.emit_stage_telemetry(stage_telemetry)

        # Update study-level telemetry
        study_telemetry.add_stage_telemetry(stage_telemetry)
