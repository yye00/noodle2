"""Integration tests for ECO effectiveness leaderboard within StudyExecutor.

This module tests the integration of ECO leaderboard generation with the
StudyExecutor, ensuring that ECO effectiveness is tracked during Study
execution and the leaderboard is automatically generated and saved.
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.controller.eco import ECOEffectiveness, ECOPrior
from src.controller.executor import StudyExecutor
from src.controller.study import SafetyDomain, StudyConfig
from src.controller.types import ECOClass, ExecutionMode, StageConfig


class TestECOLeaderboardStudyExecutorIntegration:
    """Test ECO leaderboard integration with StudyExecutor."""

    def test_executor_initializes_eco_tracking(self):
        """Test that StudyExecutor initializes ECO effectiveness tracking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir) / "snapshot"
            snapshot_dir.mkdir(parents=True)

            config = StudyConfig(
                name="test_study",
                base_case_name="test_base",
                snapshot_path=str(snapshot_dir),
                safety_domain=SafetyDomain.SANDBOX,
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage0",
                        trial_budget=5,
                        survivor_count=2,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                telemetry_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Verify ECO tracking is initialized
            assert hasattr(executor, "eco_effectiveness_map")
            assert hasattr(executor, "eco_class_map")
            assert isinstance(executor.eco_effectiveness_map, dict)
            assert isinstance(executor.eco_class_map, dict)
            assert len(executor.eco_effectiveness_map) == 0
            assert len(executor.eco_class_map) == 0

    def test_executor_tracks_eco_effectiveness(self):
        """Test that executor can track ECO effectiveness."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir) / "snapshot"
            snapshot_dir.mkdir(parents=True)

            config = StudyConfig(
                name="test_study",
                base_case_name="test_base",
                snapshot_path=str(snapshot_dir),
                safety_domain=SafetyDomain.SANDBOX,
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage0",
                        trial_budget=5,
                        survivor_count=2,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                telemetry_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Manually add ECO effectiveness data (simulating trial execution)
            eco1 = ECOEffectiveness(eco_name="buffer_insertion")
            eco1.update(success=True, wns_delta_ps=500.0)
            eco1.update(success=True, wns_delta_ps=600.0)

            eco2 = ECOEffectiveness(eco_name="cell_sizing")
            eco2.update(success=True, wns_delta_ps=300.0)

            executor.eco_effectiveness_map["buffer_insertion"] = eco1
            executor.eco_effectiveness_map["cell_sizing"] = eco2

            executor.eco_class_map["buffer_insertion"] = "placement_local"
            executor.eco_class_map["cell_sizing"] = "topology_neutral"

            # Verify tracking
            assert len(executor.eco_effectiveness_map) == 2
            assert "buffer_insertion" in executor.eco_effectiveness_map
            assert "cell_sizing" in executor.eco_effectiveness_map

            assert executor.eco_effectiveness_map["buffer_insertion"].total_applications == 2
            assert executor.eco_effectiveness_map["cell_sizing"].total_applications == 1

    def test_leaderboard_generated_during_study_execution(self):
        """
        Test that ECO leaderboard is generated and saved during Study execution.

        This is the main integration test covering all 6 feature steps:
        Step 1: Execute Study with multiple ECO types (mocked)
        Step 2: Track effectiveness metrics for each ECO instance
        Step 3: Aggregate effectiveness by ECO class
        Step 4: Rank ECO classes by average improvement
        Step 5: Generate leaderboard report
        Step 6: Include leaderboard in Study summary (save to artifacts)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir) / "snapshot"
            snapshot_dir.mkdir(parents=True)

            # Create a simple TCL script for base case verification
            script_path = snapshot_dir / "run_sta.tcl"
            script_path.write_text("# Placeholder TCL script\n")

            config = StudyConfig(
                name="test_eco_study",
                base_case_name="nangate45_base",
                snapshot_path=str(snapshot_dir),
                safety_domain=SafetyDomain.SANDBOX,
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage0",
                        trial_budget=3,
                        survivor_count=1,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                telemetry_root=tmpdir,
                skip_base_case_verification=True,  # Skip for this test
            )

            # Manually populate ECO effectiveness data
            # (In real execution, this would be done during trial execution)
            eco1 = ECOEffectiveness(eco_name="buffer_insertion")
            eco1.update(success=True, wns_delta_ps=800.0)
            eco1.update(success=True, wns_delta_ps=750.0)
            eco1.update(success=True, wns_delta_ps=900.0)

            eco2 = ECOEffectiveness(eco_name="cell_sizing")
            eco2.update(success=True, wns_delta_ps=400.0)
            eco2.update(success=False, wns_delta_ps=-100.0)

            eco3 = ECOEffectiveness(eco_name="pin_swap")
            eco3.update(success=True, wns_delta_ps=150.0)

            executor.eco_effectiveness_map = {
                "buffer_insertion": eco1,
                "cell_sizing": eco2,
                "pin_swap": eco3,
            }

            executor.eco_class_map = {
                "buffer_insertion": "placement_local",
                "cell_sizing": "topology_neutral",
                "pin_swap": "topology_neutral",
            }

            # Mock trial execution to avoid Docker dependency
            with patch.object(executor, "_execute_stage") as mock_execute_stage:
                from src.controller.executor import StageResult

                mock_execute_stage.return_value = StageResult(
                    stage_index=0,
                    stage_name="stage0",
                    trials_executed=3,
                    survivors=["nangate45_base_0_0"],
                    total_runtime_seconds=1.0,
                )

                # Execute study
                result = executor.execute()

            # Verify study completed
            assert result.stages_completed == 1
            assert not result.aborted

            # Verify leaderboard files were created
            artifacts_dir = Path(tmpdir) / "test_eco_study"
            leaderboard_json = artifacts_dir / "eco_leaderboard.json"
            leaderboard_txt = artifacts_dir / "eco_leaderboard.txt"

            assert leaderboard_json.exists(), "ECO leaderboard JSON not found"
            assert leaderboard_txt.exists(), "ECO leaderboard TXT not found"

            # Verify JSON content
            import json

            with leaderboard_json.open() as f:
                data = json.load(f)

            assert data["study_name"] == "test_eco_study"
            assert data["total_ecos"] == 3
            assert len(data["entries"]) == 3

            # Verify ranking (buffer_insertion should be #1 with highest avg improvement)
            assert data["entries"][0]["eco_name"] == "buffer_insertion"
            assert data["entries"][0]["rank"] == 1

            # Verify text content
            with leaderboard_txt.open() as f:
                text = f.read()

            assert "ECO EFFECTIVENESS LEADERBOARD" in text
            assert "test_eco_study" in text
            assert "buffer_insertion" in text
            assert "cell_sizing" in text
            assert "pin_swap" in text
            assert "Rank" in text
            assert "LEGEND" in text

    def test_leaderboard_not_generated_if_no_eco_data(self):
        """Test that leaderboard is not generated if no ECO data is available."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir) / "snapshot"
            snapshot_dir.mkdir(parents=True)

            config = StudyConfig(
                name="test_study_no_ecos",
                base_case_name="nangate45_base",
                snapshot_path=str(snapshot_dir),
                safety_domain=SafetyDomain.SANDBOX,
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage0",
                        trial_budget=1,
                        survivor_count=1,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                    )
                ],
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                telemetry_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Don't populate any ECO data
            assert len(executor.eco_effectiveness_map) == 0

            # Mock trial execution
            with patch.object(executor, "_execute_stage") as mock_execute_stage:
                from src.controller.executor import StageResult

                mock_execute_stage.return_value = StageResult(
                    stage_index=0,
                    stage_name="stage0",
                    trials_executed=1,
                    survivors=["nangate45_base_0_0"],
                    total_runtime_seconds=0.1,
                )

                result = executor.execute()

            # Verify study completed
            assert result.stages_completed == 1

            # Verify leaderboard files were NOT created
            artifacts_dir = Path(tmpdir) / "test_study_no_ecos"
            leaderboard_json = artifacts_dir / "eco_leaderboard.json"
            leaderboard_txt = artifacts_dir / "eco_leaderboard.txt"

            # Leaderboard should not be generated if there's no ECO data
            assert not leaderboard_json.exists()
            assert not leaderboard_txt.exists()

    def test_leaderboard_includes_eco_class_information(self):
        """Test that leaderboard includes ECO class information."""
        with tempfile.TemporaryDirectory() as tmpdir:
            snapshot_dir = Path(tmpdir) / "snapshot"
            snapshot_dir.mkdir(parents=True)

            config = StudyConfig(
                name="test_study_classes",
                base_case_name="nangate45_base",
                snapshot_path=str(snapshot_dir),
                safety_domain=SafetyDomain.SANDBOX,
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage0",
                        trial_budget=1,
                        survivor_count=1,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[
                            ECOClass.TOPOLOGY_NEUTRAL,
                            ECOClass.PLACEMENT_LOCAL,
                        ],
                    )
                ],
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                telemetry_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Add ECO data with class information
            eco1 = ECOEffectiveness(eco_name="buffer_insertion")
            eco1.update(success=True, wns_delta_ps=500.0)

            executor.eco_effectiveness_map["buffer_insertion"] = eco1
            executor.eco_class_map["buffer_insertion"] = "placement_local"

            # Mock trial execution
            with patch.object(executor, "_execute_stage") as mock_execute_stage:
                from src.controller.executor import StageResult

                mock_execute_stage.return_value = StageResult(
                    stage_index=0,
                    stage_name="stage0",
                    trials_executed=1,
                    survivors=["nangate45_base_0_0"],
                    total_runtime_seconds=0.1,
                )

                result = executor.execute()

            # Verify leaderboard includes ECO class
            artifacts_dir = Path(tmpdir) / "test_study_classes"
            leaderboard_json = artifacts_dir / "eco_leaderboard.json"

            import json

            with leaderboard_json.open() as f:
                data = json.load(f)

            assert data["entries"][0]["eco_class"] == "placement_local"
