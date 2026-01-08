"""
Tests for resource utilization tracking (CPU time, peak memory).

This module validates Feature: Track resource utilization per trial (CPU time, peak memory)

Test Coverage:
- Resource metrics captured from Docker stats
- CPU time extraction and conversion (nanoseconds -> seconds)
- Peak memory extraction and conversion (bytes -> MB)
- Resource metrics propagated to TrialResult
- Resource metrics included in telemetry
- Best-effort behavior (no failure if stats unavailable)
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.trial_runner.docker_runner import (
    DockerRunConfig,
    DockerTrialRunner,
    TrialExecutionResult,
)
from src.trial_runner.trial import Trial, TrialConfig


class TestDockerResourceStatsExtraction:
    """Test resource stats extraction from Docker containers."""

    def test_extract_cpu_time_from_container_stats(self):
        """CPU time is extracted from container stats and converted to seconds."""
        runner = DockerTrialRunner()

        # Mock container with stats
        mock_container = Mock()
        mock_container.stats.return_value = {
            "cpu_stats": {
                "cpu_usage": {
                    "total_usage": 5_000_000_000,  # 5 billion nanoseconds = 5 seconds
                }
            },
            "memory_stats": {},
        }

        cpu_time, _ = runner._get_container_resource_stats(mock_container)

        assert cpu_time is not None
        assert cpu_time == 5.0  # 5 seconds

    def test_extract_peak_memory_from_container_stats(self):
        """Peak memory is extracted from container stats and converted to MB."""
        runner = DockerTrialRunner()

        # Mock container with stats
        mock_container = Mock()
        mock_container.stats.return_value = {
            "cpu_stats": {},
            "memory_stats": {
                "max_usage": 512 * 1024 * 1024,  # 512 MB in bytes
            },
        }

        _, peak_memory = runner._get_container_resource_stats(mock_container)

        assert peak_memory is not None
        assert peak_memory == 512.0  # 512 MB

    def test_extract_both_cpu_and_memory(self):
        """Both CPU time and peak memory are extracted together."""
        runner = DockerTrialRunner()

        # Mock container with full stats
        mock_container = Mock()
        mock_container.stats.return_value = {
            "cpu_stats": {
                "cpu_usage": {
                    "total_usage": 10_000_000_000,  # 10 seconds
                }
            },
            "memory_stats": {
                "max_usage": 1024 * 1024 * 1024,  # 1024 MB (1 GB)
            },
        }

        cpu_time, peak_memory = runner._get_container_resource_stats(mock_container)

        assert cpu_time == 10.0
        assert peak_memory == 1024.0

    def test_fallback_to_current_memory_if_max_unavailable(self):
        """Falls back to current memory usage if max_usage is not available."""
        runner = DockerTrialRunner()

        # Mock container with only current usage
        mock_container = Mock()
        mock_container.stats.return_value = {
            "cpu_stats": {},
            "memory_stats": {
                "usage": 256 * 1024 * 1024,  # 256 MB in bytes
                # No max_usage field
            },
        }

        _, peak_memory = runner._get_container_resource_stats(mock_container)

        assert peak_memory is not None
        assert peak_memory == 256.0

    def test_returns_none_if_stats_unavailable(self):
        """Returns None if container stats are unavailable or malformed."""
        runner = DockerTrialRunner()

        # Mock container that raises exception
        mock_container = Mock()
        mock_container.stats.side_effect = Exception("Stats not available")

        cpu_time, peak_memory = runner._get_container_resource_stats(mock_container)

        # Best-effort: return None instead of failing
        assert cpu_time is None
        assert peak_memory is None

    def test_handles_missing_cpu_usage_field(self):
        """Handles missing CPU usage field gracefully."""
        runner = DockerTrialRunner()

        mock_container = Mock()
        mock_container.stats.return_value = {
            "cpu_stats": {},  # No cpu_usage field
            "memory_stats": {
                "max_usage": 128 * 1024 * 1024,
            },
        }

        cpu_time, peak_memory = runner._get_container_resource_stats(mock_container)

        assert cpu_time is None  # CPU not available
        assert peak_memory == 128.0  # Memory still extracted

    def test_handles_missing_memory_stats_field(self):
        """Handles missing memory stats field gracefully."""
        runner = DockerTrialRunner()

        mock_container = Mock()
        mock_container.stats.return_value = {
            "cpu_stats": {
                "cpu_usage": {
                    "total_usage": 3_000_000_000,
                }
            },
            "memory_stats": {},  # No usage fields
        }

        cpu_time, peak_memory = runner._get_container_resource_stats(mock_container)

        assert cpu_time == 3.0  # CPU extracted
        assert peak_memory is None  # Memory not available


class TestTrialExecutionResultResourceMetrics:
    """Test resource metrics in TrialExecutionResult."""

    def test_trial_execution_result_includes_cpu_time(self):
        """TrialExecutionResult includes cpu_time_seconds field."""
        result = TrialExecutionResult(
            return_code=0,
            stdout="output",
            stderr="",
            runtime_seconds=15.5,
            success=True,
            cpu_time_seconds=12.3,
        )

        assert result.cpu_time_seconds == 12.3

    def test_trial_execution_result_includes_peak_memory(self):
        """TrialExecutionResult includes peak_memory_mb field."""
        result = TrialExecutionResult(
            return_code=0,
            stdout="output",
            stderr="",
            runtime_seconds=15.5,
            success=True,
            peak_memory_mb=768.0,
        )

        assert result.peak_memory_mb == 768.0

    def test_trial_execution_result_allows_none_resource_metrics(self):
        """Resource metrics can be None if unavailable."""
        result = TrialExecutionResult(
            return_code=0,
            stdout="output",
            stderr="",
            runtime_seconds=15.5,
            success=True,
            cpu_time_seconds=None,
            peak_memory_mb=None,
        )

        assert result.cpu_time_seconds is None
        assert result.peak_memory_mb is None


class TestTrialResultResourceMetrics:
    """Test resource metrics in TrialResult."""

    def test_trial_result_includes_resource_metrics(self):
        """TrialResult includes cpu_time_seconds and peak_memory_mb fields."""
        from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult

        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="test.tcl",
        )

        artifacts = TrialArtifacts(trial_dir=Path("/tmp/trial"))

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=20.0,
            artifacts=artifacts,
            cpu_time_seconds=18.5,
            peak_memory_mb=1024.0,
        )

        assert result.cpu_time_seconds == 18.5
        assert result.peak_memory_mb == 1024.0

    def test_trial_result_to_dict_includes_resource_metrics(self):
        """TrialResult.to_dict() includes resource metrics."""
        from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult

        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="test.tcl",
        )

        artifacts = TrialArtifacts(trial_dir=Path("/tmp/trial"))

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=20.0,
            artifacts=artifacts,
            cpu_time_seconds=25.0,
            peak_memory_mb=2048.0,
        )

        result_dict = result.to_dict()

        assert "cpu_time_seconds" in result_dict
        assert result_dict["cpu_time_seconds"] == 25.0
        assert "peak_memory_mb" in result_dict
        assert result_dict["peak_memory_mb"] == 2048.0

    def test_trial_result_to_dict_omits_none_resource_metrics(self):
        """TrialResult.to_dict() omits resource metrics if they are None."""
        from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult

        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="test.tcl",
        )

        artifacts = TrialArtifacts(trial_dir=Path("/tmp/trial"))

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=20.0,
            artifacts=artifacts,
            cpu_time_seconds=None,
            peak_memory_mb=None,
        )

        result_dict = result.to_dict()

        # None values should not be included in the dict
        assert "cpu_time_seconds" not in result_dict
        assert "peak_memory_mb" not in result_dict


class TestResourceMetricsInTelemetry:
    """Test resource metrics appear in trial telemetry."""

    def test_trial_summary_includes_resource_metrics(self, tmp_path):
        """Trial summary JSON includes resource metrics."""
        from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult

        trial_dir = tmp_path / "trial"
        trial_dir.mkdir()

        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path="test.tcl",
        )

        artifacts = TrialArtifacts(trial_dir=trial_dir)

        result = TrialResult(
            config=config,
            success=True,
            return_code=0,
            runtime_seconds=30.0,
            artifacts=artifacts,
            cpu_time_seconds=28.0,
            peak_memory_mb=512.0,
        )

        # Write trial summary
        summary_file = trial_dir / "trial_summary.json"
        with summary_file.open("w") as f:
            json.dump(result.to_dict(), f, indent=2)

        # Read back and verify
        with summary_file.open() as f:
            summary = json.load(f)

        assert summary["cpu_time_seconds"] == 28.0
        assert summary["peak_memory_mb"] == 512.0


class TestResourceMetricsIntegration:
    """Integration tests for resource metrics through the full trial execution flow."""

    @patch("src.trial_runner.docker_runner.docker.from_env")
    def test_resource_metrics_propagated_through_trial_execution(
        self, mock_docker_env, tmp_path
    ):
        """Resource metrics are propagated from Docker stats to TrialResult."""
        # Create test script
        script_file = tmp_path / "test.tcl"
        script_file.write_text("puts {test}")

        # Mock Docker client and container
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client

        # Mock image already available
        mock_client.images.get.return_value = Mock()

        # Mock container execution
        mock_container = Mock()
        mock_container.id = "abc123def456"
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.side_effect = [
            b"stdout output",  # stdout
            b"stderr output",  # stderr
        ]

        # Mock container stats with resource metrics
        mock_container.stats.return_value = {
            "cpu_stats": {
                "cpu_usage": {
                    "total_usage": 15_000_000_000,  # 15 seconds
                }
            },
            "memory_stats": {
                "max_usage": 768 * 1024 * 1024,  # 768 MB
            },
        }

        mock_client.containers.run.return_value = mock_container

        # Create trial config
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=script_file,
        )

        # Execute trial
        trial = Trial(config=config, artifacts_root=tmp_path)
        result = trial.execute()

        # Verify resource metrics are captured
        assert result.cpu_time_seconds is not None
        assert result.cpu_time_seconds == 15.0
        assert result.peak_memory_mb is not None
        assert result.peak_memory_mb == 768.0

    @patch("src.trial_runner.docker_runner.docker.from_env")
    def test_trial_succeeds_even_if_resource_stats_unavailable(
        self, mock_docker_env, tmp_path
    ):
        """Trial execution succeeds even if resource stats are unavailable."""
        # Create test script
        script_file = tmp_path / "test.tcl"
        script_file.write_text("puts {test}")

        # Mock Docker client and container
        mock_client = MagicMock()
        mock_docker_env.return_value = mock_client

        # Mock image already available
        mock_client.images.get.return_value = Mock()

        # Mock container execution
        mock_container = Mock()
        mock_container.id = "abc123def456"
        mock_container.wait.return_value = {"StatusCode": 0}
        mock_container.logs.side_effect = [
            b"stdout output",
            b"stderr output",
        ]

        # Mock stats() raises exception (stats not available)
        mock_container.stats.side_effect = Exception("Stats API unavailable")

        mock_client.containers.run.return_value = mock_container

        # Create trial config
        config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=script_file,
        )

        # Execute trial - should succeed despite stats unavailable
        trial = Trial(config=config, artifacts_root=tmp_path)
        result = trial.execute()

        # Trial should succeed
        assert result.success is True
        assert result.return_code == 0

        # Resource metrics should be None (best-effort)
        assert result.cpu_time_seconds is None
        assert result.peak_memory_mb is None


class TestResourceBudgetPlanning:
    """Test resource metrics can be used for resource budget planning."""

    def test_aggregate_resource_metrics_across_trials(self):
        """Resource metrics can be aggregated across trials for budget planning."""
        from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult

        # Simulate multiple trial results
        trial_results = []

        for i in range(5):
            config = TrialConfig(
                study_name="test_study",
                case_name="test_case",
                stage_index=0,
                trial_index=i,
                script_path="test.tcl",
            )

            result = TrialResult(
                config=config,
                success=True,
                return_code=0,
                runtime_seconds=20.0 + i,
                artifacts=TrialArtifacts(trial_dir=Path(f"/tmp/trial_{i}")),
                cpu_time_seconds=18.0 + i * 2,
                peak_memory_mb=512.0 + i * 100,
            )

            trial_results.append(result)

        # Calculate aggregate metrics
        total_cpu_time = sum(r.cpu_time_seconds for r in trial_results if r.cpu_time_seconds)
        max_memory = max(r.peak_memory_mb for r in trial_results if r.peak_memory_mb)
        avg_cpu_time = total_cpu_time / len(trial_results)

        assert total_cpu_time == 18.0 + 20.0 + 22.0 + 24.0 + 26.0  # 110.0
        assert max_memory == 512.0 + 4 * 100  # 912.0
        assert avg_cpu_time == 22.0

    def test_identify_resource_intensive_trials(self):
        """Resource metrics help identify resource-intensive trials."""
        from src.trial_runner.trial import TrialArtifacts, TrialConfig, TrialResult

        trials = []

        for i, (cpu, mem) in enumerate(
            [(10.0, 256.0), (50.0, 1024.0), (15.0, 512.0), (100.0, 2048.0)]
        ):
            config = TrialConfig(
                study_name="test_study",
                case_name="test_case",
                stage_index=0,
                trial_index=i,
                script_path="test.tcl",
            )

            result = TrialResult(
                config=config,
                success=True,
                return_code=0,
                runtime_seconds=20.0,
                artifacts=TrialArtifacts(trial_dir=Path(f"/tmp/trial_{i}")),
                cpu_time_seconds=cpu,
                peak_memory_mb=mem,
            )

            trials.append(result)

        # Find most CPU-intensive trial
        most_cpu_intensive = max(trials, key=lambda t: t.cpu_time_seconds or 0)
        assert most_cpu_intensive.config.trial_index == 3
        assert most_cpu_intensive.cpu_time_seconds == 100.0

        # Find most memory-intensive trial
        most_memory_intensive = max(trials, key=lambda t: t.peak_memory_mb or 0)
        assert most_memory_intensive.config.trial_index == 3
        assert most_memory_intensive.peak_memory_mb == 2048.0
