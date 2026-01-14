"""Multi-stage Study execution with sequential stage progression and survivor selection."""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from src.controller.case import Case, CaseGraph
from src.controller.eco import (
    BufferInsertionECO,
    CellResizeECO,
    CellSwapECO,
    ECO,
    ECOEffectiveness,
    GateCloningECO,
    NoOpECO,
)
from src.controller.eco_leaderboard import ECOLeaderboardGenerator
from src.controller.graceful_shutdown import GracefulShutdownHandler
from src.controller.prior_repository_sqlite import SQLitePriorRepository
from src.controller.safety import check_study_legality, generate_legality_report
from src.controller.safety_trace import SafetyTrace
from src.controller.stage_abort import evaluate_stage_abort, StageAbortDecision
from src.controller.study import StudyConfig
from src.controller.study_resumption import (
    StudyCheckpoint,
    create_stage_checkpoint,
    find_checkpoint,
    initialize_checkpoint,
    load_checkpoint,
    save_checkpoint,
    should_skip_stage,
    update_checkpoint_after_stage,
    validate_resumption,
)
from src.controller.summary_report import SummaryReportGenerator
from src.controller.telemetry import StageTelemetry, StudyTelemetry, TelemetryEmitter
from src.controller.types import ECOClass, ExecutionMode, StageConfig, StageType
from src.controller.human_approval import (
    ApprovalGateSimulator,
    ApprovalSummary,
    generate_approval_summary,
)
from src.telemetry.event_stream import EventStreamEmitter
from src.trial_runner.trial import Trial, TrialConfig, TrialResult
from src.trial_runner.tcl_generator import generate_trial_script, generate_trial_script_with_eco


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
        """Convert to dictionary for JSON serialization with aggregate statistics."""
        # Compute aggregate statistics
        total_trials = sum(stage.trials_executed for stage in self.stage_results)
        successful_trials = sum(
            sum(1 for trial in stage.trial_results if trial.success)
            for stage in self.stage_results
        )
        failed_trials = total_trials - successful_trials

        # Compute ECO success rate (from cases with parent_id, excluding base case)
        eco_applications = 0
        eco_successes = 0
        for stage in self.stage_results:
            for trial in stage.trial_results:
                # Check if this trial represents an ECO application
                # ECO trials have case names that indicate derivation (non-base cases)
                case_name = trial.config.case_name
                # Base case is typically stage_0_0 or similar, ECO cases have different patterns
                if "_" in case_name:
                    parts = case_name.split("_")
                    # If this is not the first trial (trial 0) of stage 0, it's likely an ECO
                    if not (trial.config.stage_index == 0 and trial.config.trial_index == 0):
                        eco_applications += 1
                        if trial.success:
                            eco_successes += 1

        eco_success_rate = (eco_successes / eco_applications * 100) if eco_applications > 0 else 0.0

        # Find baseline (first trial of first stage) and final metrics
        baseline_metrics = None
        final_metrics = None

        if self.stage_results and self.stage_results[0].trial_results:
            baseline_trial = self.stage_results[0].trial_results[0]
            baseline_metrics = baseline_trial.metrics.copy() if baseline_trial.metrics else {}

        # Final metrics from last successful trial of final stage
        if self.stage_results and self.final_survivors:
            final_stage = self.stage_results[-1]
            # Find the trial for the first final survivor
            final_survivor_id = self.final_survivors[0]
            for trial in reversed(final_stage.trial_results):
                if trial.config.case_name == final_survivor_id and trial.success:
                    final_metrics = trial.metrics.copy() if trial.metrics else {}
                    break

        # Compute improvement deltas
        improvement_deltas = {}
        if baseline_metrics and final_metrics:
            if "wns_ps" in baseline_metrics and "wns_ps" in final_metrics:
                wns_delta = final_metrics["wns_ps"] - baseline_metrics["wns_ps"]
                improvement_deltas["wns_ps"] = wns_delta
                if baseline_metrics["wns_ps"] != 0:
                    improvement_deltas["wns_improvement_percent"] = (wns_delta / abs(baseline_metrics["wns_ps"])) * 100

            if "tns_ps" in baseline_metrics and "tns_ps" in final_metrics:
                tns_delta = final_metrics["tns_ps"] - baseline_metrics["tns_ps"]
                improvement_deltas["tns_ps"] = tns_delta
                if baseline_metrics["tns_ps"] != 0:
                    improvement_deltas["tns_improvement_percent"] = (tns_delta / abs(baseline_metrics["tns_ps"])) * 100

            if "hot_ratio" in baseline_metrics and "hot_ratio" in final_metrics:
                hot_ratio_delta = baseline_metrics["hot_ratio"] - final_metrics["hot_ratio"]  # Reduction is positive
                improvement_deltas["hot_ratio_reduction"] = hot_ratio_delta
                if baseline_metrics["hot_ratio"] != 0:
                    improvement_deltas["hot_ratio_improvement_percent"] = (hot_ratio_delta / baseline_metrics["hot_ratio"]) * 100

        result = {
            "study_name": self.study_name,
            "total_stages": self.total_stages,
            "stages_completed": self.stages_completed,
            "total_runtime_seconds": self.total_runtime_seconds,
            "stage_results": [stage.to_dict() for stage in self.stage_results],
            "final_survivors": self.final_survivors,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            # Aggregate statistics (F069 requirements)
            "aggregate_statistics": {
                "total_trials": total_trials,
                "successful_trials": successful_trials,
                "failed_trials": failed_trials,
                "success_rate_percent": (successful_trials / total_trials * 100) if total_trials > 0 else 0.0,
                "eco_success_rate_percent": eco_success_rate,
                "stages_to_converge": self.stages_completed,
            },
            "baseline_metrics": baseline_metrics,
            "final_metrics": final_metrics,
            "improvement_deltas": improvement_deltas,
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
        enable_graceful_shutdown: bool = True,
        approval_simulator: ApprovalGateSimulator | None = None,
        use_ray: bool = False,
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
            enable_graceful_shutdown: Enable graceful shutdown on SIGTERM/SIGINT (default: True)
            approval_simulator: Approval gate simulator for testing (optional)
            use_ray: Use Ray for parallel trial execution (default: False)
        """
        self.config = config
        self.artifacts_root = Path(artifacts_root)
        self.case_graph = CaseGraph()
        self.survivor_selector = survivor_selector or self._default_survivor_selector
        self.skip_base_case_verification = skip_base_case_verification
        self.approval_simulator = approval_simulator or ApprovalGateSimulator(auto_approve=True)

        # Initialize telemetry emitter
        self.telemetry_emitter = TelemetryEmitter(
            study_name=config.name,
            telemetry_root=telemetry_root,
        )

        # Initialize event stream emitter
        telemetry_root_path = Path(telemetry_root)
        event_stream_path = telemetry_root_path / config.name / "event_stream.ndjson"
        self.event_stream = EventStreamEmitter(stream_path=event_stream_path)

        # Initialize safety trace
        self.safety_trace = SafetyTrace(
            study_name=config.name,
            safety_domain=config.safety_domain,
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

        # Track ECO effectiveness across all trials
        self.eco_effectiveness_map: dict[str, ECOEffectiveness] = {}
        self.eco_class_map: dict[str, str] = {}  # Map ECO name to ECO class

        # Initialize SQLite prior repository for cross-session persistence
        self.prior_repository = SQLitePriorRepository()

        # Initialize graceful shutdown handler
        self.shutdown_handler = GracefulShutdownHandler() if enable_graceful_shutdown else None

        # Initialize Study checkpoint tracking
        self.study_checkpoint: StudyCheckpoint = initialize_checkpoint(config.name)

        # Track completed approval gates for dependency enforcement

        # Track case metrics for before/after ECO comparison (F117)
        self.case_metrics_map: dict[str, dict[str, Any]] = {}
        self.completed_approvals: set[str] = set()

        # Ray parallel execution
        self.use_ray = use_ray
        self.ray_executor = None
        if use_ray:
            from src.trial_runner.ray_executor import RayTrialExecutor
            self.ray_executor = RayTrialExecutor(
                artifacts_root=self.artifacts_root,
            )

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
            # Extract failure details from FailureClassification if available
            if result.failure:
                failure_type = result.failure.failure_type.value
                failure_reason = result.failure.reason
                log_excerpt = result.failure.log_excerpt
            else:
                failure_type = "unknown"
                failure_reason = "Trial failed but no failure classification available"
                log_excerpt = ""

            failure_msg = (
                f"Base case failed structural runnability check:\n"
                f"  Return code: {result.return_code}\n"
                f"  Failure type: {failure_type}\n"
                f"  Reason: {failure_reason}\n"
                f"  Log excerpt:\n{log_excerpt}"
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
            # Metrics are stored in flat structure: metrics["wns_ps"], metrics["tns_ps"], etc.
            if isinstance(result.metrics, dict):
                wns = result.metrics.get("wns_ps")
                tns = result.metrics.get("tns_ps")
                if wns is not None:
                    print(f"  WNS: {wns} ps")
                    # Store baseline WNS for abort threshold checks
                    self.baseline_wns_ps = wns
                if tns is not None:
                    print(f"  TNS: {tns} ps")

                # Store baseline metrics for ECO comparison (F117)
                self.case_metrics_map[self.base_case.case_name] = result.metrics
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
        # Register graceful shutdown handler
        if self.shutdown_handler:
            self.shutdown_handler.register()

        try:
            return self._execute_internal()
        finally:
            # Always unregister shutdown handler
            if self.shutdown_handler:
                self.shutdown_handler.unregister()

    def _execute_internal(self) -> StudyResult:
        """
        Internal execute method with shutdown handler registered.

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

        # Emit study start event
        self.event_stream.emit_study_start(
            study_name=self.config.name,
            safety_domain=self.config.safety_domain.value,
            total_stages=len(self.config.stages),
        )

        # SAFETY GATE 1: Check Study legality (safety domain enforcement)
        print("\n=== Safety Domain Enforcement ===")
        print(f"Safety domain: {self.config.safety_domain.value}")

        # Create report directory (used for all artifacts including safety trace)
        report_dir = self.artifacts_root / self.config.name
        report_dir.mkdir(parents=True, exist_ok=True)

        try:
            # This will raise ValueError if Study is illegal
            legality_result = check_study_legality(self.config)
            print("✓ Study configuration is LEGAL")

            # Emit legality check event
            self.event_stream.emit_legality_check(
                study_name=self.config.name,
                legal=True,
                reason=None,
            )

            # Record legality check in safety trace
            self.safety_trace.record_legality_check(
                is_legal=True,
                violations=[],
                warnings=legality_result.warnings,
            )

            # Generate and save legality report
            legality_report = generate_legality_report(
                self.config,
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            )
            report_path = report_dir / "run_legality_report.txt"
            with open(report_path, "w") as f:
                f.write(str(legality_report))
            print(f"Run Legality Report saved to: {report_path}")

        except ValueError as e:
            # Study is illegal - block execution
            print(f"\n🚫 STUDY BLOCKED: {str(e)}")

            # Emit legality check failure event
            self.event_stream.emit_legality_check(
                study_name=self.config.name,
                legal=False,
                reason=str(e),
            )

            # Emit study blocked event
            self.event_stream.emit_study_blocked(
                study_name=self.config.name,
                reason=f"Study configuration is ILLEGAL: {str(e)}",
            )

            # Record legality check failure in safety trace
            # Extract violations from the error message (simplified approach)
            self.safety_trace.record_legality_check(
                is_legal=False,
                violations=[{"reason": str(e)}],
                warnings=[],
            )

            # Save safety trace before exiting
            trace_path = report_dir / "safety_trace.json"
            self.safety_trace.save_to_file(trace_path)
            trace_txt_path = report_dir / "safety_trace.txt"
            self.safety_trace.save_to_file(trace_txt_path)

            # Export case lineage graph even when blocked
            lineage_dot_path = report_dir / "lineage.dot"
            lineage_dot = self.case_graph.export_to_dot()
            lineage_dot_path.write_text(lineage_dot)

            # Finalize and emit study telemetry for blocked study
            study_telemetry.finalize(
                final_survivors=[],
                aborted=True,
                abort_reason=f"Study configuration is ILLEGAL: {str(e)}",
            )
            self.telemetry_emitter.emit_study_telemetry(study_telemetry)

            study_result = StudyResult(
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

            # Save study result as JSON
            study_summary_json_path = report_dir / "study_summary.json"
            with open(study_summary_json_path, "w") as f:
                import json
                json.dump(study_result.to_dict(), f, indent=2)

            return study_result

        # SAFETY GATE 2: Verify base case before ECO experimentation
        if not self.skip_base_case_verification:
            is_valid, failure_message = self.verify_base_case()

            # Emit base case verification event
            self.event_stream.emit_base_case_verification(
                study_name=self.config.name,
                success=is_valid,
                reason=failure_message if not is_valid else None,
            )

            # Record base case verification in safety trace
            self.safety_trace.record_base_case_verification(is_valid, failure_message)

            if not is_valid:
                print("\n🚫 STUDY BLOCKED: Base case failed structural runnability")
                print("No ECO experimentation will be allowed.")

                # Emit study blocked event
                self.event_stream.emit_study_blocked(
                    study_name=self.config.name,
                    reason=f"Base case failed structural runnability: {failure_message}",
                )

                # Save safety trace before exiting
                trace_path = report_dir / "safety_trace.json"
                self.safety_trace.save_to_file(trace_path)
                trace_txt_path = report_dir / "safety_trace.txt"
                self.safety_trace.save_to_file(trace_txt_path)

                # Export case lineage graph even when base case fails
                lineage_dot_path = report_dir / "lineage.dot"
                lineage_dot = self.case_graph.export_to_dot()
                lineage_dot_path.write_text(lineage_dot)

                # Finalize and emit study telemetry for blocked study
                study_telemetry.finalize(
                    final_survivors=[],
                    aborted=True,
                    abort_reason=f"Base case failed structural runnability: {failure_message}",
                )
                self.telemetry_emitter.emit_study_telemetry(study_telemetry)

                study_result = StudyResult(
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

                # Save study result as JSON
                study_summary_json_path = report_dir / "study_summary.json"
                with open(study_summary_json_path, "w") as f:
                    import json
                    json.dump(study_result.to_dict(), f, indent=2)

                return study_result

        # Start with base case for stage 0
        current_cases = [self.base_case]

        for stage_index, stage_config in enumerate(self.config.stages):
            # Check for graceful shutdown request before starting new stage
            if self.shutdown_handler and self.shutdown_handler.should_shutdown():
                print(f"\n⚠️  Graceful shutdown requested - stopping before stage {stage_index}")
                print(f"   Saving checkpoint with {len(stage_results)} completed stages")

                # Save checkpoint
                self._save_checkpoint(report_dir, stage_results)

                return self._create_shutdown_result(
                    study_start, stage_results, study_telemetry, report_dir
                )

            # Check if this is an approval gate or execution stage
            if stage_config.stage_type == StageType.HUMAN_APPROVAL:
                # Handle approval gate
                current_survivor_ids = [case.case_id for case in current_cases]
                approved, reason = self._execute_approval_gate(
                    stage_index=stage_index,
                    stage_config=stage_config,
                    stage_results=stage_results,
                    current_survivors=current_survivor_ids,
                )

                if not approved:
                    # Study rejected at approval gate
                    print(f"\n🚫 STUDY REJECTED AT APPROVAL GATE: {reason}")

                    # Save safety trace
                    trace_path = report_dir / "safety_trace.json"
                    self.safety_trace.save_to_file(trace_path)
                    trace_txt_path = report_dir / "safety_trace.txt"
                    self.safety_trace.save_to_file(trace_txt_path)

                    # Export case lineage graph
                    lineage_dot_path = report_dir / "lineage.dot"
                    lineage_dot = self.case_graph.export_to_dot()
                    lineage_dot_path.write_text(lineage_dot)

                    # Finalize and emit study telemetry
                    study_telemetry.finalize(
                        final_survivors=[],
                        aborted=True,
                        abort_reason=f"Rejected at approval gate: {reason}",
                    )
                    self.telemetry_emitter.emit_study_telemetry(study_telemetry)
                    self.telemetry_emitter.flush_all_case_telemetry()

                    return StudyResult(
                        study_name=self.config.name,
                        total_stages=len(self.config.stages),
                        stages_completed=stage_index,
                        total_runtime_seconds=time.time() - study_start,
                        stage_results=stage_results,
                        final_survivors=[],
                        aborted=True,
                        abort_reason=f"Rejected at approval gate: {reason}",
                        author=self.config.author,
                        creation_date=self.config.creation_date,
                        description=self.config.description,
                    )

                # Approval granted - record this approval gate as completed
                self.completed_approvals.add(stage_config.name)
                # current_cases passes through unchanged to next stage
                # (Approval gates don't execute trials or select survivors)
            else:
                # Normal execution stage
                print(f"\n=== Executing Stage {stage_index}: {stage_config.name} ===")

                # Check if this stage requires approval dependency
                if stage_config.requires_approval is not None:
                    if stage_config.requires_approval not in self.completed_approvals:
                        # Dependency not satisfied - block execution
                        error_msg = f"Stage '{stage_config.name}' requires approval from '{stage_config.requires_approval}' but it has not been completed"
                        print(f"\n🚫 STAGE BLOCKED: {error_msg}")

                        # Save safety trace
                        trace_path = report_dir / "safety_trace.json"
                        self.safety_trace.save_to_file(trace_path)
                        trace_txt_path = report_dir / "safety_trace.txt"
                        self.safety_trace.save_to_file(trace_txt_path)

                        # Export case lineage graph
                        lineage_dot_path = report_dir / "lineage.dot"
                        lineage_dot = self.case_graph.export_to_dot()
                        lineage_dot_path.write_text(lineage_dot)

                        # Finalize and emit study telemetry
                        study_telemetry.finalize(
                            final_survivors=[],
                            aborted=True,
                            abort_reason=error_msg,
                        )
                        self.telemetry_emitter.emit_study_telemetry(study_telemetry)
                        self.telemetry_emitter.flush_all_case_telemetry()

                        return StudyResult(
                            study_name=self.config.name,
                            total_stages=len(self.config.stages),
                            stages_completed=stage_index,
                            total_runtime_seconds=time.time() - study_start,
                            stage_results=stage_results,
                            final_survivors=[],
                            aborted=True,
                            abort_reason=error_msg,
                            author=self.config.author,
                            creation_date=self.config.creation_date,
                            description=self.config.description,
                        )

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

                # Save checkpoint after stage completes
                stage_checkpoint = create_stage_checkpoint(
                    stage_index=stage_index,
                    stage_name=stage_config.name,
                    survivor_case_ids=stage_result.survivors,
                    trials_completed=stage_result.trials_executed,
                    trials_failed=len([t for t in stage_result.trial_results if not t.success]),
                    metadata=stage_result.metadata,
                )
                self.study_checkpoint = update_checkpoint_after_stage(
                    self.study_checkpoint, stage_checkpoint
                )

                # Save checkpoint to disk
                checkpoint_path = save_checkpoint(self.study_checkpoint, report_dir)
                print(f"   Checkpoint saved: {checkpoint_path}")

            # Record stage abort check in safety trace (only for execution stages)
            if stage_config.stage_type == StageType.EXECUTION and stage_result.abort_decision:
                # Emit abort evaluation event
                self.event_stream.emit_abort_evaluation(
                    study_name=self.config.name,
                    stage_index=stage_index,
                    should_abort=stage_result.abort_decision.should_abort,
                    reason=stage_result.abort_decision.reason.value if stage_result.abort_decision.reason else "unknown",
                )

                self.safety_trace.record_stage_abort_check(
                    stage_index=stage_index,
                    stage_name=stage_config.name,
                    should_abort=stage_result.abort_decision.should_abort,
                    abort_reason=stage_result.abort_decision.reason.value if stage_result.abort_decision.reason else None,
                    details=stage_result.abort_decision.details,
                )

            # Check for stage abort conditions using comprehensive abort logic (only for execution stages)
            if stage_config.stage_type == StageType.EXECUTION and stage_result.abort_decision and stage_result.abort_decision.should_abort:
                abort_reason_str = (
                    f"Stage {stage_index} aborted: {stage_result.abort_decision.reason.value if stage_result.abort_decision.reason else 'unknown'}\n"
                    f"Details: {stage_result.abort_decision.details}"
                )
                print(f"\n🚫 STAGE ABORT: {abort_reason_str}")

                # Emit stage aborted event
                self.event_stream.emit_stage_aborted(
                    study_name=self.config.name,
                    stage_index=stage_index,
                    reason=abort_reason_str,
                )

                # Emit study aborted event
                self.event_stream.emit_study_aborted(
                    study_name=self.config.name,
                    abort_reason=abort_reason_str,
                    stage_index=stage_index,
                )

                # Print violating trials if any
                if stage_result.abort_decision.violating_trials:
                    print(f"Violating trials ({len(stage_result.abort_decision.violating_trials)}):")
                    for trial_id in stage_result.abort_decision.violating_trials[:5]:  # Show first 5
                        print(f"  - {trial_id}")
                    if len(stage_result.abort_decision.violating_trials) > 5:
                        print(f"  ... and {len(stage_result.abort_decision.violating_trials) - 5} more")

                # Save safety trace before exiting
                trace_path = report_dir / "safety_trace.json"
                self.safety_trace.save_to_file(trace_path)
                trace_txt_path = report_dir / "safety_trace.txt"
                self.safety_trace.save_to_file(trace_txt_path)

                # Export case lineage graph even when aborted
                lineage_dot_path = report_dir / "lineage.dot"
                lineage_dot = self.case_graph.export_to_dot()
                lineage_dot_path.write_text(lineage_dot)

                # Finalize and emit study telemetry for aborted study
                study_telemetry.finalize(
                    final_survivors=[],
                    aborted=True,
                    abort_reason=abort_reason_str,
                )
                self.telemetry_emitter.emit_study_telemetry(study_telemetry)
                self.telemetry_emitter.flush_all_case_telemetry()

                study_result = StudyResult(
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

                # Save study result as JSON
                study_summary_json_path = report_dir / "study_summary.json"
                with open(study_summary_json_path, "w") as f:
                    import json
                    json.dump(study_result.to_dict(), f, indent=2)

                return study_result

            # Prepare cases for next stage (only for execution stages)
            if stage_config.stage_type == StageType.EXECUTION:
                if stage_index < len(self.config.stages) - 1:
                    # Derive new cases from survivors for next stage
                    current_cases = []
                    for derived_idx, survivor_id in enumerate(stage_result.survivors):
                        survivor_case = self.case_graph.get_case(survivor_id)
                        if survivor_case:
                            # Find the trial result for this survivor to get modified ODB path
                            modified_odb_path = None
                            for trial_result in stage_result.trial_results:
                                if trial_result.config.case_name == survivor_id and trial_result.success:
                                    modified_odb_path = trial_result.modified_odb_path
                                    break

                            # Use modified ODB as snapshot for next stage, fallback to original
                            next_snapshot_path = modified_odb_path if modified_odb_path else self.config.snapshot_path

                            # Create derived case for next stage
                            derived = survivor_case.derive(
                                eco_name="pass_through",  # Placeholder for actual ECO
                                new_stage_index=stage_index + 1,
                                derived_index=derived_idx,
                                snapshot_path=next_snapshot_path,  # Use modified ODB if available
                                metadata={
                                    "source_trial": survivor_id,
                                    "input_odb_from_stage": stage_index if modified_odb_path else None,
                                    "accumulated_modifications": modified_odb_path is not None,
                                },
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

        # Save safety trace to artifacts
        trace_path = report_dir / "safety_trace.json"
        self.safety_trace.save_to_file(trace_path)
        trace_txt_path = report_dir / "safety_trace.txt"
        self.safety_trace.save_to_file(trace_txt_path)
        print(f"\nSafety Trace saved to:")
        print(f"  JSON: {trace_path}")
        print(f"  TXT: {trace_txt_path}")

        # Export case lineage graph in DOT format
        lineage_dot_path = report_dir / "lineage.dot"
        lineage_dot = self.case_graph.export_to_dot()
        lineage_dot_path.write_text(lineage_dot)
        print(f"\nCase Lineage Graph saved to:")
        print(f"  DOT: {lineage_dot_path}")

        # Generate human-readable summary report
        summary_generator = SummaryReportGenerator()

        # Collect stage telemetries from emitted files
        stage_telemetries: list[StageTelemetry] = []
        for stage_idx in range(len(stage_results)):
            stage_file = self.telemetry_emitter.study_dir / f"stage_{stage_idx}_telemetry.json"
            if stage_file.exists():
                import json
                with stage_file.open("r") as f:
                    stage_data = json.load(f)
                # Reconstruct StageTelemetry from dict
                stage_telem = StageTelemetry(
                    stage_index=stage_data["stage_index"],
                    stage_name=stage_data["stage_name"],
                    trial_budget=stage_data["trial_budget"],
                    survivor_count=stage_data["survivor_count"],
                    trials_executed=stage_data["trials_executed"],
                    successful_trials=stage_data["successful_trials"],
                    failed_trials=stage_data["failed_trials"],
                    survivors=stage_data["survivors"],
                    total_runtime_seconds=stage_data["total_runtime_seconds"],
                    cases_processed=stage_data["cases_processed"],
                    failure_types=stage_data["failure_types"],
                    metadata=stage_data.get("metadata", {}),
                )
                stage_telemetries.append(stage_telem)

        # Collect case telemetries
        case_telemetries = list(self.telemetry_emitter.case_telemetry.values())

        # Write summary report
        summary_path = report_dir / "study_summary.txt"
        summary_generator.write_summary_report(
            summary_path,
            study_telemetry,
            stage_telemetries,
            case_telemetries,
        )
        print(f"\nStudy Summary Report saved to: {summary_path}")

        # Save study result as JSON for programmatic access
        study_result_for_json = StudyResult(
            study_name=self.config.name,
            total_stages=len(self.config.stages),
            stages_completed=len(stage_results),
            total_runtime_seconds=study_runtime,
            stage_results=stage_results,
            final_survivors=final_survivors,
            aborted=False,
            author=self.config.author,
            creation_date=self.config.creation_date,
            description=self.config.description,
        )
        study_summary_json_path = report_dir / "study_summary.json"
        with open(study_summary_json_path, "w") as f:
            import json
            json.dump(study_result_for_json.to_dict(), f, indent=2)

        # Generate ECO effectiveness leaderboard
        if self.eco_effectiveness_map:
            leaderboard_generator = ECOLeaderboardGenerator()
            leaderboard = leaderboard_generator.generate_leaderboard(
                study_name=self.config.name,
                eco_effectiveness_map=self.eco_effectiveness_map,
                eco_class_map=self.eco_class_map,
            )

            json_path, text_path = leaderboard_generator.save_leaderboard(
                leaderboard, report_dir
            )
            print(f"\nECO Effectiveness Leaderboard saved to:")
            print(f"  JSON: {json_path}")
            print(f"  TXT: {text_path}")

        # Emit study complete event
        self.event_stream.emit_study_complete(
            study_name=self.config.name,
            final_survivors=final_survivors,
            runtime_seconds=study_runtime,
        )

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

    def _execute_approval_gate(
        self,
        stage_index: int,
        stage_config: StageConfig,
        stage_results: list[StageResult],
        current_survivors: list[str],
    ) -> tuple[bool, str]:
        """
        Handle human approval gate stage.

        Args:
            stage_index: Stage index (0-based)
            stage_config: Approval gate stage configuration
            stage_results: Results from previous stages
            current_survivors: Current survivor case IDs

        Returns:
            Tuple of (approved: bool, reason: str)
        """
        print(f"\n=== Approval Gate: {stage_config.name} ===")
        print(f"Required approvers: {stage_config.required_approvers}")
        print(f"Timeout: {stage_config.timeout_hours} hours")

        # Generate approval summary
        stage_summaries = [
            {
                "stage_name": result.stage_name,
                "trials_executed": result.trials_executed,
                "survivors": result.survivors,
                "runtime_seconds": result.total_runtime_seconds,
            }
            for result in stage_results
        ]

        # Calculate best metrics from stage results
        best_wns_ps = None
        best_hot_ratio = None
        for stage_result in stage_results:
            for trial_result in stage_result.trial_results:
                if trial_result.success and trial_result.metrics:
                    # metrics is a dict with keys like 'wns_ps', 'hot_ratio', etc.
                    if isinstance(trial_result.metrics, dict):
                        wns = trial_result.metrics.get("wns_ps")
                        if wns is not None and (best_wns_ps is None or wns > best_wns_ps):
                            best_wns_ps = wns
                        hot_ratio = trial_result.metrics.get("hot_ratio")
                        if hot_ratio is not None and (best_hot_ratio is None or hot_ratio < best_hot_ratio):
                            best_hot_ratio = hot_ratio

        # Collect visualization paths if enabled
        visualization_paths: list[str] = []
        pareto_frontier_data: dict[str, Any] | None = None

        if stage_config.show_visualizations:
            # Collect heatmaps and charts from previous stages
            for result in stage_results:
                if hasattr(result, "visualization_paths"):
                    visualization_paths.extend(result.visualization_paths)

            # Generate pareto frontier data if available
            if len(stage_results) > 0:
                last_stage = stage_results[-1]
                pareto_points = []
                for trial_result in last_stage.trial_results:
                    if trial_result.success and trial_result.metrics:
                        if isinstance(trial_result.metrics, dict):
                            case_name = trial_result.config.case_name
                            wns_ps = trial_result.metrics.get("wns_ps")
                            if wns_ps is not None:
                                point = {
                                    "case_name": case_name,
                                    "wns_ps": wns_ps,
                                }
                                hot_ratio = trial_result.metrics.get("hot_ratio")
                                if hot_ratio is not None:
                                    point["hot_ratio"] = hot_ratio
                                pareto_points.append(point)

                if pareto_points:
                    # Simple pareto frontier: select non-dominated points
                    # For now, just include all successful points
                    pareto_frontier_data = {
                        "points": pareto_points,
                        "objective": "wns_ps_hot_ratio",
                    }

        summary = generate_approval_summary(
            study_name=self.config.name,
            stages_completed=len(stage_results),
            total_stages=len(self.config.stages),
            current_stage_name=stage_config.name,
            survivors_count=len(current_survivors),
            stage_summaries=stage_summaries,
            best_wns_ps=best_wns_ps,
            best_hot_ratio=best_hot_ratio,
        )

        # Set visualization display options from stage config
        summary.show_summary = stage_config.show_summary
        summary.show_visualizations = stage_config.show_visualizations
        summary.visualization_paths = visualization_paths
        summary.pareto_frontier_data = pareto_frontier_data

        # Display approval prompt
        print("\n" + summary.format_for_display())

        # Request approval
        self.approval_simulator.request_approval(summary)

        # Simulate approval decision (in real implementation, this would wait for actual approval)
        decision = self.approval_simulator.simulate_approval(summary)

        if decision.approved:
            print(f"\n✓ Approved by {decision.approver}")
            if decision.reason:
                print(f"  Reason: {decision.reason}")
            return True, f"Approved by {decision.approver}"
        else:
            print(f"\n✗ Rejected by {decision.approver}")
            if decision.reason:
                print(f"  Reason: {decision.reason}")
            return False, f"Rejected by {decision.approver}: {decision.reason}"

    def _create_eco_for_trial(self, trial_index: int, stage_index: int) -> ECO | None:
        """
        Create an ECO instance for a given trial.

        This cycles through different ECO types and parameters to explore
        the ECO design space. First trial (trial 0) uses NoOpECO as baseline.

        Args:
            trial_index: Trial index within stage
            stage_index: Stage index

        Returns:
            ECO instance, or None for base case (no ECO)
        """
        # First trial is always no-op (baseline)
        if trial_index == 0:
            return NoOpECO()

        # Cycle through different ECO types for exploration
        # Use division to get parameter variation index (trials with same ECO type get different params)
        param_variant = ((trial_index - 1) // len([1,2,3])) % 3  # Which parameter set to use

        eco_types = [
            ("cell_resize", lambda idx, var: CellResizeECO(
                size_multiplier=1.2 + var * 0.3,  # 1.2, 1.5, 1.8
                max_paths=50 + var * 50  # 50, 100, 150
            )),
            ("buffer_insertion", lambda idx, var: BufferInsertionECO(
                max_capacitance=0.1 + var * 0.05,  # 0.1, 0.15, 0.2
                buffer_cell=["BUF_X2", "BUF_X4", "BUF_X8"][var]
            )),
            ("cell_swap", lambda idx, var: CellSwapECO(
                path_count=30 + var * 20  # 30, 50, 70
            )),
            ("gate_cloning", lambda idx, var: GateCloningECO(
                max_fanout=12 + var * 4  # 12, 16, 20 (lower = more aggressive cloning)
            )),
        ]

        # Select ECO type based on trial index
        eco_type_index = (trial_index - 1) % len(eco_types)
        eco_name, eco_factory = eco_types[eco_type_index]

        # Create ECO with varying parameters
        return eco_factory(trial_index, param_variant)

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

        # Emit stage start event
        self.event_stream.emit_stage_start(
            study_name=self.config.name,
            stage_index=stage_index,
            stage_name=stage_config.name,
            trial_budget=stage_config.trial_budget,
        )

        # Execute trials up to budget
        # The budget controls total number of trials, cycling through input cases if needed
        trials_to_execute = stage_config.trial_budget

        # Create derived cases and trial configs for all trials
        trial_cases: list[Case] = []
        trial_configs: list[TrialConfig] = []

        for trial_index in range(trials_to_execute):
            # Cycle through input cases using modulo
            base_case = input_cases[trial_index % len(input_cases)]

            # Create an ECO instance for this trial
            eco = self._create_eco_for_trial(trial_index, stage_index)
            eco_name = eco.metadata.name if eco else "no_eco"

            # Create derived case for this trial with actual ECO
            # Use base_case.snapshot_path to preserve ODB propagation from previous stage
            trial_case = base_case.derive(
                eco_name=eco_name,
                new_stage_index=stage_index,
                derived_index=trial_index,
                snapshot_path=base_case.snapshot_path,  # Preserve ODB from previous stage
                metadata={
                    "trial_index": trial_index,
                    "eco_type": eco_name,
                    "eco_parameters": eco.metadata.parameters if eco else {},
                },
            )
            # Add trial case to case graph for tracking and survivor selection
            # Skip if already exists (e.g., base case or checkpoint restore)
            if self.case_graph.get_case(trial_case.case_id) is None:
                self.case_graph.add_case(trial_case)
            trial_cases.append(trial_case)

            print(f"  Trial {trial_index + 1}/{trials_to_execute}: {trial_case.identifier} (ECO: {eco_name})")

            # Generate trial script with ECO commands injected
            # Create trial directory to save the custom script
            trial_dir = (
                self.artifacts_root
                / self.config.name
                / str(trial_case.identifier)
                / f"stage_{stage_index}"
                / f"trial_{trial_index}"
            )
            trial_dir.mkdir(parents=True, exist_ok=True)

            # Determine snapshot path from base case (could be modified ODB from previous stage)
            snapshot_path = Path(base_case.snapshot_path)

            # Determine if snapshot_path is a modified ODB file from previous stage
            input_odb_path = None
            input_odb_container_path = None  # Path as seen inside Docker container
            actual_snapshot_dir = self.config.snapshot_path  # Default to base snapshot
            if snapshot_path.suffix == ".odb":
                # This is a modified ODB file from a previous stage
                input_odb_path = str(snapshot_path)  # Host path (for metadata tracking)
                # Snapshot dir should be the parent directory containing the ODB
                actual_snapshot_dir = str(snapshot_path.parent)
                # Convert to container path: the parent dir is mounted as /snapshot
                input_odb_container_path = f"/snapshot/{snapshot_path.name}"
            else:
                # Regular snapshot directory
                actual_snapshot_dir = str(snapshot_path)

            # Generate custom trial script with ECO
            if eco and not isinstance(eco, NoOpECO):
                # Generate ECO TCL commands
                eco_tcl = eco.generate_tcl()

                # Read the snapshot's base STA script to use as foundation
                # This ensures we load the real design properly
                # Note: If we're using a modified ODB, get script from original snapshot
                if snapshot_path.suffix == ".odb":
                    # Modified ODB - use original snapshot for script
                    base_script_path = Path(self.config.snapshot_path) / "run_sta.tcl"
                else:
                    # Regular snapshot directory
                    base_script_path = snapshot_path / "run_sta.tcl"

                if base_script_path.exists():
                    # Use snapshot's script as base (has proper ODB loading)
                    base_script = base_script_path.read_text()
                else:
                    # Fallback: generate mock script (testing scenarios)
                    from src.trial_runner.tcl_generator import generate_trial_script
                    base_script = generate_trial_script(
                        execution_mode=stage_config.execution_mode,
                        design_name=self.config.base_case_name,
                        clock_period_ns=10.0,
                        pdk=self.config.pdk,
                    )

                # Inject ECO commands into base script
                from src.trial_runner.tcl_generator import inject_eco_commands
                script_content = inject_eco_commands(
                    base_script=base_script,
                    eco_tcl=eco_tcl,
                    # Use container path for modified ODB from previous stage
                    input_odb_path=input_odb_container_path,
                    output_odb_path=f"/work/modified_design_{trial_index}.odb",
                )

                # Save custom script to trial directory
                custom_script_path = trial_dir / f"trial_{trial_index}_with_eco.tcl"
                custom_script_path.write_text(script_content)
                script_path = custom_script_path
            else:
                # Use base script for no-op trials
                script_path = snapshot_path / "run_sta.tcl"
                if not script_path.exists():
                    script_path = snapshot_path

            # Create trial configuration
            trial_config = TrialConfig(
                study_name=self.config.name,
                case_name=str(trial_case.identifier),
                stage_index=stage_index,
                trial_index=trial_index,
                script_path=str(script_path),
                snapshot_dir=actual_snapshot_dir,  # Use correct snapshot dir (could be ODB parent)
                timeout_seconds=stage_config.timeout_seconds,
                execution_mode=stage_config.execution_mode,
                metadata={
                    "stage_name": stage_config.name,
                    "execution_mode": stage_config.execution_mode.value,
                    "pdk": self.config.pdk,
                    "eco_type": eco_name,
                    "eco_parameters": eco.metadata.parameters if eco else {},
                    "input_odb_path": input_odb_path,  # Host path for tracking
                    "input_odb_container_path": input_odb_container_path,  # Container path used in TCL
                },
            )
            trial_configs.append(trial_config)

        # Execute trials - parallel with Ray or sequential
        if self.use_ray and self.ray_executor:
            # Parallel execution with Ray
            print(f"  Executing {len(trial_configs)} trials in parallel with Ray...")
            trial_results = self.ray_executor.execute_trials_parallel(trial_configs)

            # Emit events and print ECO application messages for all completed trials
            for trial_case, trial_config, result in zip(trial_cases, trial_configs, trial_results):
                self.event_stream.emit_trial_complete(
                    study_name=self.config.name,
                    case_name=trial_config.case_name,
                    stage_index=stage_index,
                    trial_index=trial_config.trial_index,
                    success=result.success,
                    runtime_seconds=result.runtime_seconds,
                    metrics=result.metrics,
                )

                # Print ECO application message with before/after WNS (F117)
                parent_case_id = trial_case.parent_id
                self._print_eco_application(result, trial_config, parent_case_id)

                # Update case metrics map for future comparisons
                if result.success and result.metrics:
                    self.case_metrics_map[trial_config.case_name] = result.metrics
        else:
            # Sequential execution
            for trial_index, (trial_case, trial_config) in enumerate(zip(trial_cases, trial_configs)):
                # Emit trial start event
                self.event_stream.emit_trial_start(
                    study_name=self.config.name,
                    case_name=str(trial_case.identifier),
                    stage_index=stage_index,
                    trial_index=trial_index,
                )

                # Execute trial using Trial.execute() for real OpenROAD execution
                # Trial will create artifacts at: artifacts_root/study_name/case_name/stage_X/trial_Y/
                trial = Trial(
                    config=trial_config,
                    artifacts_root=self.artifacts_root,
                )

                try:
                    result = trial.execute()
                    trial_results.append(result)
                except Exception as e:
                    # Handle trial execution errors gracefully
                    from src.trial_runner.trial import TrialArtifacts
                    error_result = TrialResult(
                        config=trial_config,
                        success=False,
                        return_code=1,
                        runtime_seconds=0.0,
                        artifacts=TrialArtifacts(trial_dir=trial.trial_dir),
                        stderr=str(e),
                    )
                    trial_results.append(error_result)
                    result = error_result

                # Emit trial complete event
                self.event_stream.emit_trial_complete(
                    study_name=self.config.name,
                    case_name=str(trial_case.identifier),
                    stage_index=stage_index,
                    trial_index=trial_index,
                    success=result.success,
                    runtime_seconds=result.runtime_seconds,
                    metrics=result.metrics,
                )

                # Print ECO application message with before/after WNS (F117)
                parent_case_id = trial_case.parent_id
                self._print_eco_application(result, trial_config, parent_case_id)

                # Update case metrics map for future comparisons
                if result.success and result.metrics:
                    self.case_metrics_map[trial_config.case_name] = result.metrics

        # Track ECO effectiveness for all trials and persist to SQLite
        self._update_and_persist_eco_effectiveness(
            trial_results=trial_results,
            trial_configs=trial_configs,
        )

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

        # Emit stage complete event
        self.event_stream.emit_stage_complete(
            study_name=self.config.name,
            stage_index=stage_index,
            survivors=survivors,
            trials_executed=trials_to_execute,
            runtime_seconds=stage_runtime,
        )

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
        Default survivor selection: rank by WNS (higher is better), with preference for
        trials that produced modified ODBs (to enable cumulative ECO improvements).

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

        def get_sort_key(trial: TrialResult) -> tuple:
            """
            Sort key: (primary: WNS descending, secondary: has_modified_odb)
            Higher WNS is better (less negative). Prefer trials with modified ODB for cumulative improvements.
            """
            wns_ps = None
            if trial.metrics and "wns_ps" in trial.metrics:
                wns_ps = trial.metrics["wns_ps"]
            elif trial.metrics and "timing" in trial.metrics and "wns_ps" in trial.metrics["timing"]:
                wns_ps = trial.metrics["timing"]["wns_ps"]

            # Default to very negative WNS if not found
            wns_ps = wns_ps if wns_ps is not None else -999999

            # Prefer trials with modified ODB (for cumulative ECO improvements)
            has_modified_odb = 1 if trial.modified_odb_path else 0

            # Sort by: WNS (higher is better), then by has_modified_odb (1 > 0)
            return (wns_ps, has_modified_odb)

        # Sort by WNS (higher/less negative is better), with preference for modified ODB
        sorted_trials = sorted(successful_trials, key=get_sort_key, reverse=True)

        # Select top N
        survivors = sorted_trials[:survivor_count]

        return [trial.config.case_name for trial in survivors]

    def _update_and_persist_eco_effectiveness(
        self,
        trial_results: list[TrialResult],
        trial_configs: list[TrialConfig],
    ) -> None:
        """
        Update ECO effectiveness tracking and persist to SQLite database.

        This method:
        1. Updates in-memory eco_effectiveness_map with trial results
        2. Persists each ECO's effectiveness data to SQLite
        3. Prints prior state updates to console for F119

        Args:
            trial_results: Results from executed trials
            trial_configs: Configurations for the executed trials
        """
        if not trial_results or not trial_configs:
            return

        for trial_result, trial_config in zip(trial_results, trial_configs):
            # Extract ECO name from trial metadata
            eco_name = trial_config.metadata.get("eco_type", "unknown")

            # Skip no-op ECOs and unknown ECOs
            if eco_name in ("no_eco", "unknown", ""):
                continue

            # Get or create ECOEffectiveness for this ECO
            if eco_name not in self.eco_effectiveness_map:
                self.eco_effectiveness_map[eco_name] = ECOEffectiveness(eco_name=eco_name)

            eco_effectiveness = self.eco_effectiveness_map[eco_name]

            # Calculate WNS delta if metrics are available
            wns_delta_ps = 0.0
            if trial_result.metrics and "timing" in trial_result.metrics:
                timing = trial_result.metrics["timing"]
                current_wns = timing.get("wns_ps", 0)
                # Compare against baseline WNS if available
                if self.baseline_wns_ps is not None:
                    wns_delta_ps = current_wns - self.baseline_wns_ps
                else:
                    # Use absolute WNS as improvement (negative WNS = violation)
                    wns_delta_ps = current_wns

            # Update ECO effectiveness with trial result
            eco_effectiveness.update(
                success=trial_result.success,
                wns_delta_ps=wns_delta_ps,
            )

            # Persist to SQLite database
            try:
                self.prior_repository.store_prior(eco_effectiveness)
            except Exception as e:
                print(f"Warning: Failed to persist ECO prior '{eco_name}' to database: {e}")

            # Print prior state update for console visibility (F119)
            success_count = eco_effectiveness.successful_applications
            failure_count = eco_effectiveness.failed_applications
            prior_state = eco_effectiveness.prior.value
            print(f"  [PRIOR] {eco_name}: {success_count}S/{failure_count}F -> state={prior_state}")

    def _print_eco_application(
        self,
        trial_result: TrialResult,
        trial_config: TrialConfig,
        parent_case_id: str | None,
    ) -> None:
        """
        Print ECO application console output with before/after metrics (F117).

        Displays:
        - ECO name applied to case
        - WNS before and after
        - Improvement percentage

        Args:
            trial_result: Result from trial execution
            trial_config: Trial configuration
            parent_case_id: Parent case ID to look up previous metrics
        """
        # Extract ECO name
        eco_name = trial_config.metadata.get("eco_type", "unknown")
        case_name = trial_config.case_name

        # Skip if no ECO applied
        if eco_name in ("no_eco", "unknown", ""):
            return

        # Extract current metrics
        current_metrics = trial_result.metrics or {}
        current_wns = current_metrics.get("wns_ps")

        # If no WNS in current metrics, skip
        if current_wns is None:
            return

        # Look up parent case metrics for "before" state
        previous_wns = None
        if parent_case_id and parent_case_id in self.case_metrics_map:
            parent_metrics = self.case_metrics_map[parent_case_id]
            previous_wns = parent_metrics.get("wns_ps")

        # If no parent metrics, use baseline
        if previous_wns is None and self.baseline_wns_ps is not None:
            previous_wns = self.baseline_wns_ps

        # If we have both before and after, print improvement
        if previous_wns is not None:
            # Calculate improvement percentage
            # Improvement is positive when WNS gets closer to 0 (less negative or more positive)
            wns_delta = current_wns - previous_wns

            # For negative WNS values (violations), improvement = reduction in absolute value
            # e.g., -2000ps -> -1000ps is 50% improvement
            if previous_wns != 0:
                improvement_pct = (wns_delta / abs(previous_wns)) * 100
            else:
                improvement_pct = 0.0

            # Format console output
            print(f"  [ECO] Applied {eco_name} to {case_name}")
            print(f"        WNS Before: {previous_wns} ps → After: {current_wns} ps ({improvement_pct:+.1f}% improvement)")
        else:
            # No before metrics, just show current state
            print(f"  [ECO] Applied {eco_name} to {case_name}")
            print(f"        WNS: {current_wns} ps")

    def _print_doom_termination(
        self,
        case_name: str,
        doom_classification: Any,  # DoomClassification from doom_detection module
    ) -> None:
        """
        Print doom termination console output with compute saved (F118).

        Displays:
        - Case terminated message with doom type
        - Compute saved estimate
        - Brief recommendation

        Args:
            case_name: Name of the doomed case
            doom_classification: DoomClassification object with doom details
        """
        # Import here to avoid circular dependency
        from src.controller.doom_detection import DoomClassification

        if not isinstance(doom_classification, DoomClassification):
            return

        # Extract doom information
        doom_type = doom_classification.doom_type.value if doom_classification.doom_type else "unknown"
        compute_saved = doom_classification.compute_saved_trials
        reason = doom_classification.reason

        # Print doom termination message
        print(f"  [DOOM] {case_name} terminated: {doom_type}")
        print(f"         Reason: {reason}")

        if compute_saved > 0:
            print(f"         Compute saved: ~{compute_saved} trials")

        # Print recommendation if available (one-line summary)
        if doom_classification.recommendation:
            # Take first line of recommendation as summary
            rec_first_line = doom_classification.recommendation.split('\n')[0]
            print(f"         Recommendation: {rec_first_line}")

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

    def _save_checkpoint(
        self, report_dir: Path, stage_results: list[StageResult]
    ) -> Path:
        """
        Save Study checkpoint to disk.

        Args:
            report_dir: Directory to save checkpoint
            stage_results: Completed stage results

        Returns:
            Path to saved checkpoint file
        """
        checkpoint_path = save_checkpoint(self.study_checkpoint, report_dir)
        print(f"   Checkpoint saved to: {checkpoint_path}")
        return checkpoint_path

    def _create_shutdown_result(
        self,
        study_start: float,
        stage_results: list[StageResult],
        study_telemetry: StudyTelemetry,
        report_dir: Path,
    ) -> StudyResult:
        """
        Create StudyResult for graceful shutdown.

        Args:
            study_start: Study start time
            stage_results: Completed stage results
            study_telemetry: Study-level telemetry
            report_dir: Report directory for artifacts

        Returns:
            StudyResult indicating graceful shutdown
        """
        shutdown_reason = "Graceful shutdown requested (SIGTERM/SIGINT)"

        # Save safety trace
        trace_path = report_dir / "safety_trace.json"
        self.safety_trace.save_to_file(trace_path)
        trace_txt_path = report_dir / "safety_trace.txt"
        self.safety_trace.save_to_file(trace_txt_path)

        # Export case lineage graph
        lineage_dot_path = report_dir / "lineage.dot"
        lineage_dot = self.case_graph.export_to_dot()
        lineage_dot_path.write_text(lineage_dot)

        # Get final survivors from last completed stage
        final_survivors = stage_results[-1].survivors if stage_results else []

        # Finalize and emit study telemetry
        study_telemetry.finalize(
            final_survivors=final_survivors,
            aborted=True,
            abort_reason=shutdown_reason,
        )
        self.telemetry_emitter.emit_study_telemetry(study_telemetry)
        self.telemetry_emitter.flush_all_case_telemetry()

        # Emit study aborted event
        self.event_stream.emit_study_aborted(
            study_name=self.config.name,
            abort_reason=shutdown_reason,
            stage_index=len(stage_results) - 1 if stage_results else 0,
        )

        print(f"\n✓ Study checkpoint saved - can resume from stage {len(stage_results)}")

        return StudyResult(
            study_name=self.config.name,
            total_stages=len(self.config.stages),
            stages_completed=len(stage_results),
            total_runtime_seconds=time.time() - study_start,
            stage_results=stage_results,
            final_survivors=final_survivors,
            aborted=True,
            abort_reason=shutdown_reason,
            author=self.config.author,
            creation_date=self.config.creation_date,
            description=self.config.description,
        )
