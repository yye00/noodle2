"""Trial execution and artifact management for Noodle 2."""

import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.controller.failure import FailureClassification, FailureClassifier
from src.controller.types import ExecutionMode
from src.parsers.congestion import parse_congestion_report_file
from src.parsers.timing import parse_openroad_metrics_json, parse_timing_report
from src.trial_runner.docker_runner import DockerRunConfig, DockerTrialRunner
from src.trial_runner.provenance import ToolProvenance, create_provenance


@dataclass
class TrialConfig:
    """Configuration for a single trial execution."""

    study_name: str
    case_name: str
    stage_index: int
    trial_index: int
    script_path: str | Path
    snapshot_dir: str | Path | None = None
    timeout_seconds: int = 3600
    metadata: dict[str, Any] = field(default_factory=dict)
    # Ray resource requirements
    num_cpus: float = 1.0
    num_gpus: float = 0.0
    memory_mb: float = 2048.0
    # Execution mode (controls what analysis is performed)
    execution_mode: ExecutionMode = ExecutionMode.STA_ONLY
    # Optional fixed seed for deterministic placement/routing
    openroad_seed: int | None = None
    # Retry configuration for transient failures
    max_retries: int = 3  # Maximum number of retry attempts
    retry_backoff_base: float = 2.0  # Base multiplier for exponential backoff (seconds)
    retry_backoff_max: float = 60.0  # Maximum backoff delay (seconds)


@dataclass
class TrialArtifacts:
    """Artifact bundle produced by a trial execution."""

    trial_dir: Path
    timing_report: Path | None = None
    congestion_report: Path | None = None
    metrics_json: Path | None = None
    netlist: Path | None = None
    logs: Path | None = None
    script: Path | None = None  # TCL script used for execution (for reproducibility)

    def to_dict(self) -> dict[str, Any]:
        """Convert artifacts to dictionary for JSON serialization."""
        return {
            "trial_dir": str(self.trial_dir),
            "timing_report": str(self.timing_report) if self.timing_report else None,
            "congestion_report": str(self.congestion_report) if self.congestion_report else None,
            "metrics_json": str(self.metrics_json) if self.metrics_json else None,
            "netlist": str(self.netlist) if self.netlist else None,
            "logs": str(self.logs) if self.logs else None,
            "script": str(self.script) if self.script else None,
        }


@dataclass
class TrialResult:
    """Complete result of a trial execution."""

    config: TrialConfig
    success: bool
    return_code: int
    runtime_seconds: float
    artifacts: TrialArtifacts
    metrics: dict[str, Any] = field(default_factory=dict)
    stdout: str = ""
    stderr: str = ""
    container_id: str = ""
    failure: FailureClassification | None = None  # Deterministic failure classification
    provenance: ToolProvenance | None = None  # Execution provenance for reproducibility
    # Timestamps for execution time tracking and performance analysis
    start_time: str = ""  # ISO 8601 format timestamp
    end_time: str = ""  # ISO 8601 format timestamp
    # Timeout tracking for runaway execution detection
    timed_out: bool = False  # True if trial exceeded timeout limit
    # Resource utilization metrics
    cpu_time_seconds: float | None = None  # Total CPU time consumed by OpenROAD process
    peak_memory_mb: float | None = None  # Peak memory usage during trial execution
    # Retry tracking for transient failures
    retry_count: int = 0  # Number of retry attempts made
    retry_history: list[dict[str, Any]] = field(default_factory=list)  # Log of all retry attempts

    def calculate_duration_seconds(self) -> float | None:
        """
        Calculate trial duration from timestamps.

        This provides an alternative to runtime_seconds that is based on
        wall-clock time rather than process execution time.

        Returns:
            Duration in seconds, or None if timestamps are missing
        """
        if not self.start_time or not self.end_time:
            return None

        try:
            start = datetime.fromisoformat(self.start_time)
            end = datetime.fromisoformat(self.end_time)
            return (end - start).total_seconds()
        except (ValueError, TypeError):
            return None

    def to_dict(self) -> dict[str, Any]:
        """Convert trial result to dictionary for JSON serialization."""
        result = {
            "study_name": self.config.study_name,
            "case_name": self.config.case_name,
            "stage_index": self.config.stage_index,
            "trial_index": self.config.trial_index,
            "success": self.success,
            "return_code": self.return_code,
            "runtime_seconds": self.runtime_seconds,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "timed_out": self.timed_out,
            "metrics": self.metrics,
            "artifacts": self.artifacts.to_dict(),
            "container_id": self.container_id,
            "metadata": self.config.metadata,
        }

        # Add resource utilization metrics if available
        if self.cpu_time_seconds is not None:
            result["cpu_time_seconds"] = self.cpu_time_seconds
        if self.peak_memory_mb is not None:
            result["peak_memory_mb"] = self.peak_memory_mb

        # Add failure classification if present
        if self.failure:
            result["failure"] = self.failure.to_dict()

        # Add provenance if present
        if self.provenance:
            result["provenance"] = self.provenance.to_dict()

        return result


class Trial:
    """
    Manages execution of a single trial.

    A Trial:
    - Executes a TCL script in an isolated Docker container
    - Produces structured artifacts in a deterministic location
    - Parses outputs and extracts metrics
    - Returns a complete TrialResult

    Artifact directory structure:
        artifacts/{study_name}/{case_name}/stage_{stage_index}/trial_{trial_index}/
            - timing_report.txt
            - congestion_report.txt (optional)
            - metrics.json
            - logs/
            - netlist/
    """

    def __init__(
        self,
        config: TrialConfig,
        artifacts_root: str | Path = "artifacts",
        docker_config: DockerRunConfig | None = None,
    ) -> None:
        """
        Initialize a Trial.

        Args:
            config: Trial configuration
            artifacts_root: Root directory for all artifacts
            docker_config: Docker execution configuration
        """
        self.config = config
        self.artifacts_root = Path(artifacts_root)
        self.docker_runner = DockerTrialRunner(docker_config)

        # Create deterministic artifact path
        self.trial_dir = self._create_trial_directory()

    def _create_trial_directory(self) -> Path:
        """Create deterministic trial artifact directory."""
        trial_dir = (
            self.artifacts_root
            / self.config.study_name
            / self.config.case_name
            / f"stage_{self.config.stage_index}"
            / f"trial_{self.config.trial_index}"
        )
        trial_dir.mkdir(parents=True, exist_ok=True)
        return trial_dir

    def _copy_snapshot_to_trial_dir(self) -> Path | None:
        """
        Copy immutable snapshot to trial directory for isolated execution.

        This ensures:
        - The base snapshot remains unmodified
        - Each trial operates on its own copy
        - Trials are side-effect free with respect to the snapshot

        Returns:
            Path to the copied snapshot directory, or None if no snapshot
        """
        if not self.config.snapshot_dir:
            return None

        snapshot_src = Path(self.config.snapshot_dir)
        if not snapshot_src.exists():
            raise FileNotFoundError(f"Snapshot directory not found: {snapshot_src}")

        # Create snapshot subdirectory in trial dir
        snapshot_dest = self.trial_dir / "snapshot"

        # Copy snapshot files to trial directory
        if snapshot_dest.exists():
            # Clean up any existing snapshot copy
            shutil.rmtree(snapshot_dest)

        shutil.copytree(snapshot_src, snapshot_dest, symlinks=False)

        return snapshot_dest

    def _copy_script_to_trial_dir(self) -> Path:
        """
        Copy the TCL script to the trial artifacts directory for reproducibility.

        This enables manual reproduction of any trial by providing the exact
        script that was executed. The script is saved as 'trial_script.tcl' in
        the trial directory.

        Returns:
            Path to the copied script file

        Raises:
            FileNotFoundError: If script file not found
        """
        script_src = Path(self.config.script_path)
        if not script_src.exists():
            raise FileNotFoundError(f"Script file not found: {script_src}")

        # Save script with standardized name for easy discovery
        script_dest = self.trial_dir / "trial_script.tcl"

        # Copy script content (preserving exact content for reproducibility)
        shutil.copy2(script_src, script_dest)

        return script_dest

    def execute(self) -> TrialResult:
        """
        Execute the trial and return complete results.

        This method:
        1. Copies the immutable snapshot to the trial directory
        2. Executes the trial script via Docker
        3. Discovers and catalogs artifacts
        4. Parses metrics from outputs
        5. Writes a trial summary

        Returns:
            TrialResult with execution details and artifacts

        Raises:
            FileNotFoundError: If script or snapshot not found
            docker.errors.DockerException: On Docker errors
        """
        # Record start time
        start_time = datetime.now(timezone.utc).isoformat()

        # Copy snapshot to trial directory for isolated execution
        snapshot_copy = self._copy_snapshot_to_trial_dir()

        # Copy TCL script to trial artifacts for reproducibility
        self._copy_script_to_trial_dir()

        # Execute trial via Docker, using the copied snapshot
        exec_result = self.docker_runner.execute_trial(
            script_path=self.config.script_path,
            working_dir=self.trial_dir,
            snapshot_dir=snapshot_copy,  # Use the copied snapshot
            timeout_seconds=self.config.timeout_seconds,
        )

        # Record end time
        end_time = datetime.now(timezone.utc).isoformat()

        # Save logs
        logs_dir = self.trial_dir / "logs"
        logs_dir.mkdir(exist_ok=True)

        stdout_file = logs_dir / "stdout.txt"
        stderr_file = logs_dir / "stderr.txt"

        stdout_file.write_text(exec_result.stdout)
        stderr_file.write_text(exec_result.stderr)

        # Discover and catalog artifacts
        artifacts = self._discover_artifacts()

        # Parse metrics
        metrics = self._parse_metrics(artifacts)

        # Classify failure if trial failed
        failure_classification = None
        if not exec_result.success:
            # Classify the failure deterministically
            expected_outputs = ["timing_report.txt", "metrics.json"]  # Basic expectations

            # Extract memory limit from Docker config for OOM diagnostics
            memory_limit_mb = None
            if self.docker_runner.config.memory_limit:
                limit_str = self.docker_runner.config.memory_limit
                # Parse "8g" -> 8192 MB, "4096m" -> 4096 MB
                if limit_str.endswith('g'):
                    memory_limit_mb = float(limit_str[:-1]) * 1024
                elif limit_str.endswith('m'):
                    memory_limit_mb = float(limit_str[:-1])

            failure_classification = FailureClassifier.classify_trial_failure(
                return_code=exec_result.return_code,
                stdout=exec_result.stdout,
                stderr=exec_result.stderr,
                artifacts_dir=self.trial_dir,
                expected_outputs=expected_outputs if exec_result.return_code == 0 else None,
                peak_memory_mb=exec_result.peak_memory_mb,
                memory_limit_mb=memory_limit_mb,
            )

        # Create provenance record for reproducibility
        provenance = create_provenance(
            container_image=self.docker_runner.config.image.rsplit(":", 1)[0],
            container_tag=self.docker_runner.config.image.rsplit(":", 1)[1] if ":" in self.docker_runner.config.image else "latest",
            container_id=exec_result.container_id,
            command=f"openroad {self.config.script_path}",
            working_dir=str(self.trial_dir),
            start_time=start_time,
            end_time=end_time,
            query_version=False,  # Skip version query for performance (best-effort)
            pdk_name=self.config.metadata.get("pdk"),
        )

        # Create trial result
        result = TrialResult(
            config=self.config,
            success=exec_result.success,
            return_code=exec_result.return_code,
            runtime_seconds=exec_result.runtime_seconds,
            artifacts=artifacts,
            metrics=metrics,
            stdout=exec_result.stdout,
            stderr=exec_result.stderr,
            container_id=exec_result.container_id,
            failure=failure_classification,
            provenance=provenance,
            start_time=start_time,
            end_time=end_time,
            timed_out=exec_result.timed_out,
            cpu_time_seconds=exec_result.cpu_time_seconds,
            peak_memory_mb=exec_result.peak_memory_mb,
        )

        # Write trial summary
        self._write_trial_summary(result)

        # Generate artifact index for Ray Dashboard navigation
        self._generate_artifact_index()

        return result

    def _discover_artifacts(self) -> TrialArtifacts:
        """
        Discover artifacts produced by the trial.

        Returns:
            TrialArtifacts with paths to discovered files
        """
        artifacts = TrialArtifacts(trial_dir=self.trial_dir)

        # Common artifact names
        timing_candidates = ["timing_report.txt", "timing.rpt", "sta.rpt"]
        congestion_candidates = ["congestion_report.txt", "congestion.rpt"]
        metrics_candidates = ["metrics.json"]
        netlist_candidates = ["*.v", "*_gl.v", "*.vg"]

        # Find timing report
        for name in timing_candidates:
            path = self.trial_dir / name
            if path.exists():
                artifacts.timing_report = path
                break

        # Find congestion report
        for name in congestion_candidates:
            path = self.trial_dir / name
            if path.exists():
                artifacts.congestion_report = path
                break

        # Find metrics JSON
        for name in metrics_candidates:
            path = self.trial_dir / name
            if path.exists():
                artifacts.metrics_json = path
                break

        # Find netlist (first match)
        for pattern in netlist_candidates:
            netlists = list(self.trial_dir.glob(pattern))
            if netlists:
                artifacts.netlist = netlists[0]
                break

        # Logs directory
        logs_dir = self.trial_dir / "logs"
        if logs_dir.exists():
            artifacts.logs = logs_dir

        # TCL script (for reproducibility)
        script_path = self.trial_dir / "trial_script.tcl"
        if script_path.exists():
            artifacts.script = script_path

        return artifacts

    def _parse_metrics(self, artifacts: TrialArtifacts) -> dict[str, Any]:
        """
        Parse metrics from trial artifacts.

        Args:
            artifacts: Discovered artifacts

        Returns:
            Dictionary of parsed metrics
        """
        metrics: dict[str, Any] = {}

        # Parse timing metrics
        if artifacts.metrics_json and artifacts.metrics_json.exists():
            # Prefer JSON metrics if available
            try:
                import json
                content = artifacts.metrics_json.read_text()

                # Load raw JSON first to get all fields (including hot_ratio)
                raw_metrics = json.loads(content)

                # Parse timing-specific fields using existing parser
                timing_obj = parse_openroad_metrics_json(content)
                metrics["wns_ps"] = timing_obj.wns_ps
                if timing_obj.tns_ps is not None:
                    metrics["tns_ps"] = timing_obj.tns_ps
                if timing_obj.failing_endpoints is not None:
                    metrics["failing_endpoints"] = timing_obj.failing_endpoints

                # Additionally extract hot_ratio if present
                if "hot_ratio" in raw_metrics:
                    metrics["hot_ratio"] = raw_metrics["hot_ratio"]

                # Extract any other custom metrics from JSON
                if "clock_period_ns" in raw_metrics:
                    metrics["clock_period_ns"] = raw_metrics["clock_period_ns"]

            except Exception as e:
                metrics["timing_parse_error"] = str(e)

        elif artifacts.timing_report and artifacts.timing_report.exists():
            # Fall back to text report parsing
            try:
                timing_obj = parse_timing_report(artifacts.timing_report)
                metrics["wns_ps"] = timing_obj.wns_ps
                if timing_obj.tns_ps is not None:
                    metrics["tns_ps"] = timing_obj.tns_ps
                if timing_obj.failing_endpoints is not None:
                    metrics["failing_endpoints"] = timing_obj.failing_endpoints
            except Exception as e:
                metrics["timing_parse_error"] = str(e)

        # Parse congestion metrics (if available)
        if artifacts.congestion_report and artifacts.congestion_report.exists():
            try:
                congestion_obj = parse_congestion_report_file(str(artifacts.congestion_report))
                metrics["bins_total"] = congestion_obj.bins_total
                metrics["bins_hot"] = congestion_obj.bins_hot
                metrics["hot_ratio"] = congestion_obj.hot_ratio
                if congestion_obj.max_overflow is not None:
                    metrics["max_overflow"] = congestion_obj.max_overflow
            except Exception as e:
                metrics["congestion_parse_error"] = str(e)

        return metrics

    def _write_trial_summary(self, result: TrialResult) -> None:
        """
        Write trial summary JSON to artifact directory.

        Args:
            result: Trial result to summarize
        """
        summary_file = self.trial_dir / "trial_summary.json"
        with summary_file.open("w") as f:
            json.dump(result.to_dict(), f, indent=2)

    def get_artifact_index(self) -> dict[str, Any]:
        """
        Generate artifact index for this trial.

        Returns:
            Dictionary describing all trial artifacts
        """
        artifacts = self._discover_artifacts()

        return {
            "trial_id": f"{self.config.study_name}/{self.config.case_name}/stage_{self.config.stage_index}/trial_{self.config.trial_index}",
            "trial_dir": str(self.trial_dir),
            "artifacts": artifacts.to_dict(),
            "metadata": {
                "study_name": self.config.study_name,
                "case_name": self.config.case_name,
                "stage_index": self.config.stage_index,
                "trial_index": self.config.trial_index,
            },
        }

    def _generate_artifact_index(self) -> None:
        """
        Generate and write artifact index JSON file.

        This creates artifact_index.json in the trial directory,
        enabling Ray Dashboard navigation and artifact discovery.
        """
        from src.trial_runner.artifact_index import generate_trial_artifact_index

        index = generate_trial_artifact_index(
            trial_root=self.trial_dir,
            study_name=self.config.study_name,
            case_name=self.config.case_name,
            stage_index=self.config.stage_index,
            trial_index=self.config.trial_index,
        )

        index.write_to_file()
