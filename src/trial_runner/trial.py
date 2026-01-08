"""Trial execution and artifact management for Noodle 2."""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.parsers.timing import parse_openroad_metrics_json, parse_timing_report
from src.trial_runner.docker_runner import DockerRunConfig, DockerTrialRunner


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


@dataclass
class TrialArtifacts:
    """Artifact bundle produced by a trial execution."""

    trial_dir: Path
    timing_report: Path | None = None
    congestion_report: Path | None = None
    metrics_json: Path | None = None
    netlist: Path | None = None
    logs: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert artifacts to dictionary for JSON serialization."""
        return {
            "trial_dir": str(self.trial_dir),
            "timing_report": str(self.timing_report) if self.timing_report else None,
            "congestion_report": str(self.congestion_report) if self.congestion_report else None,
            "metrics_json": str(self.metrics_json) if self.metrics_json else None,
            "netlist": str(self.netlist) if self.netlist else None,
            "logs": str(self.logs) if self.logs else None,
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

    def to_dict(self) -> dict[str, Any]:
        """Convert trial result to dictionary for JSON serialization."""
        return {
            "study_name": self.config.study_name,
            "case_name": self.config.case_name,
            "stage_index": self.config.stage_index,
            "trial_index": self.config.trial_index,
            "success": self.success,
            "return_code": self.return_code,
            "runtime_seconds": self.runtime_seconds,
            "metrics": self.metrics,
            "artifacts": self.artifacts.to_dict(),
            "container_id": self.container_id,
            "metadata": self.config.metadata,
        }


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

    def execute(self) -> TrialResult:
        """
        Execute the trial and return complete results.

        Returns:
            TrialResult with execution details and artifacts

        Raises:
            FileNotFoundError: If script or snapshot not found
            docker.errors.DockerException: On Docker errors
        """
        # Execute trial via Docker
        exec_result = self.docker_runner.execute_trial(
            script_path=self.config.script_path,
            working_dir=self.trial_dir,
            snapshot_dir=self.config.snapshot_dir,
            timeout_seconds=self.config.timeout_seconds,
        )

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
        )

        # Write trial summary
        self._write_trial_summary(result)

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
                content = artifacts.metrics_json.read_text()
                timing_obj = parse_openroad_metrics_json(content)
                metrics["wns_ps"] = timing_obj.wns_ps
                if timing_obj.tns_ps is not None:
                    metrics["tns_ps"] = timing_obj.tns_ps
                if timing_obj.failing_endpoints is not None:
                    metrics["failing_endpoints"] = timing_obj.failing_endpoints
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
