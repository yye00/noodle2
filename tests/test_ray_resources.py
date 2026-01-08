"""Tests for Ray cluster resource utilization tracking."""

import json
import tempfile
import time
from pathlib import Path

import pytest
import ray

from src.trial_runner.ray_resources import (
    RayResourceMonitor,
    ResourceSnapshot,
    ResourceUtilizationTimeseries,
)


@pytest.fixture(scope="module", autouse=True)
def ray_cluster():
    """Initialize Ray cluster for all tests in this module."""
    if not ray.is_initialized():
        ray.init(ignore_reinit_error=True)
    yield
    # Keep Ray running for other tests


class TestResourceSnapshot:
    """Test ResourceSnapshot dataclass and its methods."""

    def test_resource_snapshot_creation(self):
        """Test creating a resource snapshot with all fields."""
        snapshot = ResourceSnapshot(
            timestamp=1234567890.5,
            total_cpus=8.0,
            available_cpus=4.0,
            total_memory_bytes=16 * 1024**3,  # 16 GB
            available_memory_bytes=8 * 1024**3,  # 8 GB
            total_gpus=2.0,
            available_gpus=1.0,
            node_count=2,
            metadata={"cluster": "test"},
        )

        assert snapshot.timestamp == 1234567890.5
        assert snapshot.total_cpus == 8.0
        assert snapshot.available_cpus == 4.0
        assert snapshot.total_memory_bytes == 16 * 1024**3
        assert snapshot.available_memory_bytes == 8 * 1024**3
        assert snapshot.total_gpus == 2.0
        assert snapshot.available_gpus == 1.0
        assert snapshot.node_count == 2
        assert snapshot.metadata == {"cluster": "test"}

    def test_cpu_utilization_calculation(self):
        """Test CPU utilization percentage calculation."""
        # 50% utilization (4 out of 8 CPUs used)
        snapshot = ResourceSnapshot(
            timestamp=time.time(),
            total_cpus=8.0,
            available_cpus=4.0,
            total_memory_bytes=1024,
            available_memory_bytes=512,
        )
        assert snapshot.cpu_utilization == 0.5

        # 100% utilization
        snapshot_full = ResourceSnapshot(
            timestamp=time.time(),
            total_cpus=8.0,
            available_cpus=0.0,
            total_memory_bytes=1024,
            available_memory_bytes=0,
        )
        assert snapshot_full.cpu_utilization == 1.0

        # 0% utilization
        snapshot_idle = ResourceSnapshot(
            timestamp=time.time(),
            total_cpus=8.0,
            available_cpus=8.0,
            total_memory_bytes=1024,
            available_memory_bytes=1024,
        )
        assert snapshot_idle.cpu_utilization == 0.0

    def test_memory_utilization_calculation(self):
        """Test memory utilization percentage calculation."""
        # 75% utilization (12 out of 16 GB used)
        snapshot = ResourceSnapshot(
            timestamp=time.time(),
            total_cpus=8.0,
            available_cpus=4.0,
            total_memory_bytes=16 * 1024**3,
            available_memory_bytes=4 * 1024**3,
        )
        assert abs(snapshot.memory_utilization - 0.75) < 0.01

    def test_gpu_utilization_calculation(self):
        """Test GPU utilization percentage calculation."""
        # 50% GPU utilization (1 out of 2 GPUs used)
        snapshot = ResourceSnapshot(
            timestamp=time.time(),
            total_cpus=8.0,
            available_cpus=4.0,
            total_memory_bytes=1024,
            available_memory_bytes=512,
            total_gpus=2.0,
            available_gpus=1.0,
        )
        assert snapshot.gpu_utilization == 0.5

        # No GPUs
        snapshot_no_gpu = ResourceSnapshot(
            timestamp=time.time(),
            total_cpus=8.0,
            available_cpus=4.0,
            total_memory_bytes=1024,
            available_memory_bytes=512,
            total_gpus=0.0,
            available_gpus=0.0,
        )
        assert snapshot_no_gpu.gpu_utilization == 0.0

    def test_snapshot_to_dict(self):
        """Test converting snapshot to dictionary."""
        snapshot = ResourceSnapshot(
            timestamp=1234567890.5,
            total_cpus=8.0,
            available_cpus=4.0,
            total_memory_bytes=1024,
            available_memory_bytes=512,
        )

        snapshot_dict = snapshot.to_dict()

        assert snapshot_dict["timestamp"] == 1234567890.5
        assert snapshot_dict["total_cpus"] == 8.0
        assert snapshot_dict["available_cpus"] == 4.0
        assert snapshot_dict["cpu_utilization"] == 0.5
        assert snapshot_dict["memory_utilization"] == 0.5
        assert "metadata" in snapshot_dict


class TestResourceUtilizationTimeseries:
    """Test ResourceUtilizationTimeseries and aggregation methods."""

    def test_timeseries_creation(self):
        """Test creating empty timeseries."""
        timeseries = ResourceUtilizationTimeseries()
        assert timeseries.snapshots == []
        assert timeseries.duration_seconds == 0.0

    def test_add_snapshot(self):
        """Test adding snapshots to timeseries."""
        timeseries = ResourceUtilizationTimeseries()

        snapshot1 = ResourceSnapshot(
            timestamp=100.0,
            total_cpus=8.0,
            available_cpus=4.0,
            total_memory_bytes=1024,
            available_memory_bytes=512,
        )
        timeseries.add_snapshot(snapshot1)

        assert len(timeseries.snapshots) == 1
        assert timeseries.snapshots[0] == snapshot1

    def test_duration_calculation(self):
        """Test calculating timeseries duration."""
        timeseries = ResourceUtilizationTimeseries()

        # Add snapshots 10 seconds apart
        snapshot1 = ResourceSnapshot(
            timestamp=100.0,
            total_cpus=8.0,
            available_cpus=4.0,
            total_memory_bytes=1024,
            available_memory_bytes=512,
        )
        snapshot2 = ResourceSnapshot(
            timestamp=110.0,
            total_cpus=8.0,
            available_cpus=2.0,
            total_memory_bytes=1024,
            available_memory_bytes=256,
        )

        timeseries.add_snapshot(snapshot1)
        timeseries.add_snapshot(snapshot2)

        assert timeseries.duration_seconds == 10.0

    def test_average_cpu_utilization(self):
        """Test calculating average CPU utilization."""
        timeseries = ResourceUtilizationTimeseries()

        # 50% utilization
        snapshot1 = ResourceSnapshot(
            timestamp=100.0,
            total_cpus=8.0,
            available_cpus=4.0,
            total_memory_bytes=1024,
            available_memory_bytes=512,
        )
        # 75% utilization
        snapshot2 = ResourceSnapshot(
            timestamp=110.0,
            total_cpus=8.0,
            available_cpus=2.0,
            total_memory_bytes=1024,
            available_memory_bytes=256,
        )

        timeseries.add_snapshot(snapshot1)
        timeseries.add_snapshot(snapshot2)

        # Average should be (0.5 + 0.75) / 2 = 0.625
        assert abs(timeseries.avg_cpu_utilization - 0.625) < 0.01

    def test_peak_utilization(self):
        """Test calculating peak CPU and memory utilization."""
        timeseries = ResourceUtilizationTimeseries()

        snapshots = [
            ResourceSnapshot(
                timestamp=100.0 + i,
                total_cpus=8.0,
                available_cpus=8.0 - i,
                total_memory_bytes=1024,
                available_memory_bytes=1024 - (i * 100),
            )
            for i in range(5)
        ]

        for s in snapshots:
            timeseries.add_snapshot(s)

        # Peak CPU utilization should be at snapshot 4 (4/8 = 0.5)
        assert timeseries.peak_cpu_utilization == 0.5

        # Peak memory utilization should be at snapshot 4 (400/1024)
        assert timeseries.peak_memory_utilization == pytest.approx(400 / 1024, rel=0.01)

    def test_identify_bottlenecks_cpu(self):
        """Test identifying CPU bottleneck."""
        timeseries = ResourceUtilizationTimeseries()

        # Add snapshot with 95% CPU utilization
        snapshot = ResourceSnapshot(
            timestamp=100.0,
            total_cpus=8.0,
            available_cpus=0.4,  # 95% used
            total_memory_bytes=1024,
            available_memory_bytes=512,
        )
        timeseries.add_snapshot(snapshot)

        bottlenecks = timeseries.identify_bottlenecks()

        assert bottlenecks["cpu_bottleneck"] is True
        assert bottlenecks["memory_bottleneck"] is False
        assert any("CPU" in rec for rec in bottlenecks["recommendations"])

    def test_identify_bottlenecks_memory(self):
        """Test identifying memory bottleneck."""
        timeseries = ResourceUtilizationTimeseries()

        # Add snapshot with 95% memory utilization
        snapshot = ResourceSnapshot(
            timestamp=100.0,
            total_cpus=8.0,
            available_cpus=4.0,
            total_memory_bytes=1024,
            available_memory_bytes=51,  # 95% used
        )
        timeseries.add_snapshot(snapshot)

        bottlenecks = timeseries.identify_bottlenecks()

        assert bottlenecks["cpu_bottleneck"] is False
        assert bottlenecks["memory_bottleneck"] is True
        assert any("Memory" in rec or "memory" in rec for rec in bottlenecks["recommendations"])

    def test_identify_underutilization(self):
        """Test identifying resource underutilization."""
        timeseries = ResourceUtilizationTimeseries()

        # Add multiple snapshots with low CPU utilization
        for i in range(10):
            snapshot = ResourceSnapshot(
                timestamp=100.0 + i,
                total_cpus=8.0,
                available_cpus=7.5,  # Only 6.25% used
                total_memory_bytes=1024,
                available_memory_bytes=512,
            )
            timeseries.add_snapshot(snapshot)

        bottlenecks = timeseries.identify_bottlenecks()

        # Should suggest increasing parallelism
        assert any("increasing" in rec.lower() for rec in bottlenecks["recommendations"])

    def test_timeseries_to_dict(self):
        """Test converting timeseries to dictionary."""
        timeseries = ResourceUtilizationTimeseries()

        snapshot = ResourceSnapshot(
            timestamp=100.0,
            total_cpus=8.0,
            available_cpus=4.0,
            total_memory_bytes=1024,
            available_memory_bytes=512,
        )
        timeseries.add_snapshot(snapshot)

        timeseries_dict = timeseries.to_dict()

        assert "snapshots" in timeseries_dict
        assert "duration_seconds" in timeseries_dict
        assert "avg_cpu_utilization" in timeseries_dict
        assert "peak_cpu_utilization" in timeseries_dict
        assert "bottlenecks" in timeseries_dict


class TestRayResourceMonitor:
    """Test RayResourceMonitor for tracking cluster resources."""

    def test_monitor_initialization(self):
        """Test creating resource monitor."""
        monitor = RayResourceMonitor(poll_interval_seconds=10.0)

        assert monitor.poll_interval == 10.0
        assert len(monitor.timeseries.snapshots) == 0
        assert monitor._monitoring is False

    def test_capture_snapshot(self):
        """Test capturing a single resource snapshot."""
        monitor = RayResourceMonitor()
        snapshot = monitor.capture_snapshot()

        # Should have captured real cluster resources
        assert snapshot.total_cpus > 0
        assert snapshot.total_memory_bytes > 0
        assert isinstance(snapshot.timestamp, float)
        assert snapshot.timestamp > 0

    def test_start_monitoring(self):
        """Test starting resource monitoring."""
        monitor = RayResourceMonitor()
        monitor.start()

        assert monitor._monitoring is True
        assert monitor._start_time is not None
        assert len(monitor.timeseries.snapshots) == 1

        # Cleanup
        monitor.stop()

    def test_poll_monitoring(self):
        """Test polling resource utilization."""
        monitor = RayResourceMonitor()
        monitor.start()

        initial_count = len(monitor.timeseries.snapshots)

        # Poll a few times
        monitor.poll()
        monitor.poll()

        assert len(monitor.timeseries.snapshots) == initial_count + 2

        # Cleanup
        monitor.stop()

    def test_stop_monitoring(self):
        """Test stopping resource monitoring."""
        monitor = RayResourceMonitor()
        monitor.start()

        initial_count = len(monitor.timeseries.snapshots)

        monitor.stop()

        assert monitor._monitoring is False
        assert monitor._stop_time is not None
        # Should have captured final snapshot
        assert len(monitor.timeseries.snapshots) == initial_count + 1

    def test_monitoring_lifecycle(self):
        """Test complete monitoring lifecycle: start -> poll -> stop."""
        monitor = RayResourceMonitor()

        # Start monitoring
        monitor.start()
        assert len(monitor.timeseries.snapshots) == 1

        # Poll multiple times
        for _ in range(3):
            monitor.poll()
            time.sleep(0.1)  # Small delay between polls

        assert len(monitor.timeseries.snapshots) == 4

        # Stop monitoring
        monitor.stop()
        assert len(monitor.timeseries.snapshots) == 5

        # Should have duration
        assert monitor.timeseries.duration_seconds > 0

    def test_generate_report(self):
        """Test generating resource utilization report."""
        monitor = RayResourceMonitor()
        monitor.start()
        monitor.poll()
        monitor.poll()
        monitor.stop()

        report = monitor.generate_report()

        # Verify report structure
        assert "monitoring_duration_seconds" in report
        assert "poll_count" in report
        assert "cluster_config" in report
        assert "utilization_summary" in report
        assert "bottlenecks" in report
        assert "timeseries" in report

        # Verify cluster config
        cluster_config = report["cluster_config"]
        assert "total_cpus" in cluster_config
        assert "total_memory_gb" in cluster_config
        assert "node_count" in cluster_config

        # Verify utilization summary
        utilization = report["utilization_summary"]
        assert "avg_cpu_utilization" in utilization
        assert "peak_cpu_utilization" in utilization

    def test_save_report(self):
        """Test saving resource utilization report to file."""
        monitor = RayResourceMonitor()
        monitor.start()
        monitor.poll()
        monitor.stop()

        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "resource_report.json"
            monitor.save_report(report_path)

            assert report_path.exists()

            # Verify file is valid JSON
            with open(report_path) as f:
                report = json.load(f)

            assert "monitoring_duration_seconds" in report
            assert "cluster_config" in report

    def test_generate_report_no_data(self):
        """Test generating report with no data captured."""
        monitor = RayResourceMonitor()
        report = monitor.generate_report()

        assert "error" in report
        assert "No resource data captured" in report["error"]

    def test_poll_without_start(self):
        """Test that polling without starting logs warning."""
        monitor = RayResourceMonitor()

        # Should log warning and not crash
        monitor.poll()

        # No snapshots should be added
        assert len(monitor.timeseries.snapshots) == 0


class TestResourceMonitoringIntegration:
    """Integration tests for resource monitoring during Study execution."""

    def test_monitor_during_simulated_study(self):
        """Test monitoring resources during simulated Study execution."""
        monitor = RayResourceMonitor(poll_interval_seconds=0.1)

        # Start monitoring
        monitor.start()

        # Simulate Study execution with simple polling
        # (avoid creating new Ray tasks which can hang in some environments)
        for _ in range(5):
            monitor.poll()
            time.sleep(0.05)

        # Stop monitoring
        monitor.stop()

        # Generate report
        report = monitor.generate_report()

        assert report["poll_count"] >= 6  # start + 5 polls + stop
        assert report["monitoring_duration_seconds"] > 0
        assert report["cluster_config"]["total_cpus"] > 0

    def test_resource_report_structure(self):
        """Test that resource report has all required fields for Study summary."""
        monitor = RayResourceMonitor()
        monitor.start()

        # Do some work
        time.sleep(0.1)
        monitor.poll()
        monitor.poll()

        monitor.stop()

        report = monitor.generate_report()

        # Required for Study summary integration
        required_fields = [
            "monitoring_duration_seconds",
            "cluster_config",
            "utilization_summary",
            "bottlenecks",
        ]

        for field in required_fields:
            assert field in report, f"Missing required field: {field}"

        # Verify bottlenecks structure
        assert "cpu_bottleneck" in report["bottlenecks"]
        assert "memory_bottleneck" in report["bottlenecks"]
        assert "recommendations" in report["bottlenecks"]
