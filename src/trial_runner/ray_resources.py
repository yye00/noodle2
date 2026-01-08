"""Ray cluster resource utilization tracking and reporting for Noodle 2."""

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ray

logger = logging.getLogger(__name__)


@dataclass
class ResourceSnapshot:
    """
    Snapshot of Ray cluster resource utilization at a specific point in time.

    Attributes:
        timestamp: Unix timestamp when snapshot was taken
        total_cpus: Total CPU cores in cluster
        available_cpus: Available CPU cores
        total_memory_bytes: Total memory in bytes
        available_memory_bytes: Available memory in bytes
        total_gpus: Total GPU count
        available_gpus: Available GPUs
        node_count: Number of nodes in cluster
        metadata: Additional metadata
    """

    timestamp: float
    total_cpus: float
    available_cpus: float
    total_memory_bytes: float
    available_memory_bytes: float
    total_gpus: float = 0.0
    available_gpus: float = 0.0
    node_count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def cpu_utilization(self) -> float:
        """Calculate CPU utilization percentage (0.0 to 1.0)."""
        if self.total_cpus == 0:
            return 0.0
        return 1.0 - (self.available_cpus / self.total_cpus)

    @property
    def memory_utilization(self) -> float:
        """Calculate memory utilization percentage (0.0 to 1.0)."""
        if self.total_memory_bytes == 0:
            return 0.0
        return 1.0 - (self.available_memory_bytes / self.total_memory_bytes)

    @property
    def gpu_utilization(self) -> float:
        """Calculate GPU utilization percentage (0.0 to 1.0)."""
        if self.total_gpus == 0:
            return 0.0
        return 1.0 - (self.available_gpus / self.total_gpus)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "total_cpus": self.total_cpus,
            "available_cpus": self.available_cpus,
            "total_memory_bytes": self.total_memory_bytes,
            "available_memory_bytes": self.available_memory_bytes,
            "total_gpus": self.total_gpus,
            "available_gpus": self.available_gpus,
            "node_count": self.node_count,
            "cpu_utilization": self.cpu_utilization,
            "memory_utilization": self.memory_utilization,
            "gpu_utilization": self.gpu_utilization,
            "metadata": self.metadata,
        }


@dataclass
class ResourceUtilizationTimeseries:
    """
    Time-series collection of resource utilization snapshots.

    This tracks resource usage over the duration of Study execution.
    """

    snapshots: list[ResourceSnapshot] = field(default_factory=list)

    def add_snapshot(self, snapshot: ResourceSnapshot) -> None:
        """Add a resource snapshot to the timeseries."""
        self.snapshots.append(snapshot)

    @property
    def duration_seconds(self) -> float:
        """Calculate total duration covered by timeseries."""
        if len(self.snapshots) < 2:
            return 0.0
        return self.snapshots[-1].timestamp - self.snapshots[0].timestamp

    @property
    def avg_cpu_utilization(self) -> float:
        """Calculate average CPU utilization across all snapshots."""
        if not self.snapshots:
            return 0.0
        return sum(s.cpu_utilization for s in self.snapshots) / len(self.snapshots)

    @property
    def avg_memory_utilization(self) -> float:
        """Calculate average memory utilization across all snapshots."""
        if not self.snapshots:
            return 0.0
        return sum(s.memory_utilization for s in self.snapshots) / len(self.snapshots)

    @property
    def peak_cpu_utilization(self) -> float:
        """Calculate peak CPU utilization."""
        if not self.snapshots:
            return 0.0
        return max(s.cpu_utilization for s in self.snapshots)

    @property
    def peak_memory_utilization(self) -> float:
        """Calculate peak memory utilization."""
        if not self.snapshots:
            return 0.0
        return max(s.memory_utilization for s in self.snapshots)

    def identify_bottlenecks(self, cpu_threshold: float = 0.9, memory_threshold: float = 0.9) -> dict[str, Any]:
        """
        Identify resource bottlenecks based on utilization thresholds.

        Args:
            cpu_threshold: CPU utilization threshold for bottleneck (default 0.9 = 90%)
            memory_threshold: Memory utilization threshold for bottleneck (default 0.9 = 90%)

        Returns:
            Dictionary describing bottlenecks with severity and recommendations
        """
        bottlenecks = {
            "cpu_bottleneck": False,
            "memory_bottleneck": False,
            "cpu_peak": self.peak_cpu_utilization,
            "memory_peak": self.peak_memory_utilization,
            "recommendations": [],
        }

        # Check for CPU bottleneck
        if self.peak_cpu_utilization >= cpu_threshold:
            bottlenecks["cpu_bottleneck"] = True
            bottlenecks["recommendations"].append(
                f"CPU utilization peaked at {self.peak_cpu_utilization*100:.1f}%. "
                "Consider adding more CPU resources or reducing parallelism."
            )

        # Check for memory bottleneck
        if self.peak_memory_utilization >= memory_threshold:
            bottlenecks["memory_bottleneck"] = True
            bottlenecks["recommendations"].append(
                f"Memory utilization peaked at {self.peak_memory_utilization*100:.1f}%. "
                "Consider adding more memory or reducing trial parallelism."
            )

        # Check for underutilization
        if self.avg_cpu_utilization < 0.3 and len(self.snapshots) > 5:
            bottlenecks["recommendations"].append(
                f"CPU utilization averaged only {self.avg_cpu_utilization*100:.1f}%. "
                "Consider increasing trial parallelism to improve resource utilization."
            )

        return bottlenecks

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "snapshots": [s.to_dict() for s in self.snapshots],
            "duration_seconds": self.duration_seconds,
            "avg_cpu_utilization": self.avg_cpu_utilization,
            "avg_memory_utilization": self.avg_memory_utilization,
            "peak_cpu_utilization": self.peak_cpu_utilization,
            "peak_memory_utilization": self.peak_memory_utilization,
            "bottlenecks": self.identify_bottlenecks(),
        }


class RayResourceMonitor:
    """
    Monitors Ray cluster resource utilization during Study execution.

    Key responsibilities:
    - Query Ray cluster status at Study start
    - Poll cluster resource usage during execution
    - Track CPU, memory, node utilization over time
    - Emit resource utilization timeseries to telemetry
    - Generate resource utilization report
    - Identify resource bottlenecks

    Usage:
        monitor = RayResourceMonitor()
        monitor.start()

        # ... execute study ...

        monitor.stop()
        report = monitor.generate_report()
    """

    def __init__(self, poll_interval_seconds: float = 5.0) -> None:
        """
        Initialize resource monitor.

        Args:
            poll_interval_seconds: How often to poll cluster resources (default 5.0)
        """
        self.poll_interval = poll_interval_seconds
        self.timeseries = ResourceUtilizationTimeseries()
        self._monitoring = False
        self._start_time: float | None = None
        self._stop_time: float | None = None

        # Verify Ray is initialized
        if not ray.is_initialized():
            logger.warning("Ray is not initialized. Resource monitoring will be limited.")

    def capture_snapshot(self) -> ResourceSnapshot:
        """
        Capture a single snapshot of current cluster resources.

        Returns:
            ResourceSnapshot with current resource utilization
        """
        if not ray.is_initialized():
            # Return empty snapshot if Ray not initialized
            return ResourceSnapshot(
                timestamp=time.time(),
                total_cpus=0.0,
                available_cpus=0.0,
                total_memory_bytes=0.0,
                available_memory_bytes=0.0,
            )

        # Query Ray cluster resources
        available = ray.available_resources()
        total = ray.cluster_resources()

        # Count nodes (if available in Ray API)
        try:
            nodes = ray.nodes()
            node_count = len([n for n in nodes if n.get("Alive", False)])
        except Exception:
            node_count = 1  # Default to single node

        snapshot = ResourceSnapshot(
            timestamp=time.time(),
            total_cpus=total.get("CPU", 0.0),
            available_cpus=available.get("CPU", 0.0),
            total_memory_bytes=total.get("memory", 0.0),
            available_memory_bytes=available.get("memory", 0.0),
            total_gpus=total.get("GPU", 0.0),
            available_gpus=available.get("GPU", 0.0),
            node_count=node_count,
        )

        return snapshot

    def start(self) -> None:
        """
        Start resource monitoring.

        Captures initial snapshot and marks monitoring as active.
        Call this at the beginning of Study execution.
        """
        self._monitoring = True
        self._start_time = time.time()

        # Capture initial snapshot
        snapshot = self.capture_snapshot()
        self.timeseries.add_snapshot(snapshot)

        logger.info(
            f"Resource monitoring started: "
            f"{snapshot.total_cpus} CPUs, "
            f"{snapshot.total_memory_bytes / (1024**3):.1f} GB memory, "
            f"{snapshot.node_count} nodes"
        )

    def poll(self) -> None:
        """
        Poll current resource utilization and add to timeseries.

        Call this periodically during Study execution.
        """
        if not self._monitoring:
            logger.warning("Cannot poll: monitoring not started")
            return

        snapshot = self.capture_snapshot()
        self.timeseries.add_snapshot(snapshot)

        logger.debug(
            f"Resource poll: CPU {snapshot.cpu_utilization*100:.1f}%, "
            f"Memory {snapshot.memory_utilization*100:.1f}%"
        )

    def stop(self) -> None:
        """
        Stop resource monitoring.

        Captures final snapshot and marks monitoring as complete.
        Call this at the end of Study execution.
        """
        if not self._monitoring:
            logger.warning("Cannot stop: monitoring not started")
            return

        # Capture final snapshot
        snapshot = self.capture_snapshot()
        self.timeseries.add_snapshot(snapshot)

        self._monitoring = False
        self._stop_time = time.time()

        logger.info(
            f"Resource monitoring stopped after {self.timeseries.duration_seconds:.1f}s: "
            f"Avg CPU {self.timeseries.avg_cpu_utilization*100:.1f}%, "
            f"Avg Memory {self.timeseries.avg_memory_utilization*100:.1f}%"
        )

    def generate_report(self) -> dict[str, Any]:
        """
        Generate comprehensive resource utilization report.

        Returns:
            Dictionary with resource utilization summary and recommendations
        """
        if not self.timeseries.snapshots:
            return {
                "error": "No resource data captured",
                "monitoring_active": self._monitoring,
            }

        first = self.timeseries.snapshots[0]
        last = self.timeseries.snapshots[-1]

        report = {
            "monitoring_duration_seconds": self.timeseries.duration_seconds,
            "poll_count": len(self.timeseries.snapshots),
            "cluster_config": {
                "total_cpus": first.total_cpus,
                "total_memory_gb": first.total_memory_bytes / (1024**3),
                "total_gpus": first.total_gpus,
                "node_count": first.node_count,
            },
            "utilization_summary": {
                "avg_cpu_utilization": self.timeseries.avg_cpu_utilization,
                "avg_memory_utilization": self.timeseries.avg_memory_utilization,
                "peak_cpu_utilization": self.timeseries.peak_cpu_utilization,
                "peak_memory_utilization": self.timeseries.peak_memory_utilization,
            },
            "bottlenecks": self.timeseries.identify_bottlenecks(),
            "timeseries": self.timeseries.to_dict(),
        }

        return report

    def save_report(self, output_path: str | Path) -> None:
        """
        Save resource utilization report to JSON file.

        Args:
            output_path: Path to save report
        """
        import json

        report = self.generate_report()

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        logger.info(f"Resource utilization report saved to {output_file}")
