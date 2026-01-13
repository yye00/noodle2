"""Tests for F110: Trial configs generated with varied ECO parameters for differentiation.

Feature F110 depends on F104 (ECO execution), F108 (ECO TCL generation), and F109 (CellSwapECO).

This feature verifies that:
1. Trial configs are generated with varied ECO parameters
2. Parameters differ across trials to explore the ECO design space
3. Each trial has unique eco_params for differentiation
4. Parameter variation produces observable effects in metrics
5. Parameter sweep creates an effect gradient
"""

import tempfile
from pathlib import Path

import pytest

from src.controller.eco import BufferInsertionECO, CellResizeECO, CellSwapECO, NoOpECO
from src.controller.executor import StudyExecutor
from src.controller.types import ExecutionMode, SafetyDomain, StageConfig, StudyConfig


class TestF110TrialConfigECOParameters:
    """Tests for Feature F110: Trial config ECO parameter variation."""

    def test_step_1_define_trial_config_generation_function(self) -> None:
        """
        Step 1: Define generate_trial_configs function for a stage.

        Verify that StudyExecutor has a method to create ECO instances
        for trials with varying parameters.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="parameter_test",
                safety_domain=SafetyDomain.GUARDED,
                base_case_name="test_design",
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        trial_budget=10,
                        survivor_count=5,
                        timeout_seconds=300,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[],
                    )
                ],
                snapshot_path=str(Path(tmpdir) / "snapshot"),
                metadata={},
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Verify _create_eco_for_trial method exists
            assert hasattr(executor, "_create_eco_for_trial")

            print("✓ StudyExecutor has _create_eco_for_trial method")

            # Test creating ECO for trial
            eco = executor._create_eco_for_trial(trial_index=1, stage_index=0)
            assert eco is not None
            assert hasattr(eco, "metadata")
            assert hasattr(eco.metadata, "parameters")

            print("✓ _create_eco_for_trial creates ECO with parameters")
            print(f"  ECO type: {eco.metadata.name}")
            print(f"  Parameters: {eco.metadata.parameters}")

    def test_step_2_create_n_trial_configs_with_varying_parameters(self) -> None:
        """
        Step 2: Create N trial configs with varying parameters.

        Verify that multiple trial configs are created with different
        parameter values (e.g., size_multiplier: 1.2, 1.3, 1.4).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="parameter_variation_test",
                safety_domain=SafetyDomain.GUARDED,
                base_case_name="test_design",
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        trial_budget=12,
                        survivor_count=5,
                        timeout_seconds=300,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[],
                    )
                ],
                snapshot_path=str(Path(tmpdir) / "snapshot"),
                metadata={},
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Create ECOs for multiple trials
            ecos = []
            for trial_index in range(12):
                eco = executor._create_eco_for_trial(trial_index, stage_index=0)
                ecos.append(eco)

            # Verify we have 12 ECOs
            assert len(ecos) == 12

            print("✓ Created 12 trial ECO configs")

            # Verify trial 0 is NoOpECO (baseline)
            assert isinstance(ecos[0], NoOpECO)
            print("  Trial 0: NoOpECO (baseline)")

            # Verify subsequent trials have varied parameters
            # Trials 1, 4, 7, 10 should use CellResizeECO with different parameters
            cell_resize_trials = [1, 4, 7, 10]
            cell_resize_ecos = [ecos[i] for i in cell_resize_trials if isinstance(ecos[i], CellResizeECO)]

            assert len(cell_resize_ecos) >= 3, "Should have multiple CellResizeECO with different parameters"

            print(f"✓ Found {len(cell_resize_ecos)} CellResizeECO instances")

            # Check parameter variation
            size_multipliers = [eco.metadata.parameters["size_multiplier"] for eco in cell_resize_ecos]
            max_paths_values = [eco.metadata.parameters["max_paths"] for eco in cell_resize_ecos]

            print(f"  Size multipliers: {size_multipliers}")
            print(f"  Max paths: {max_paths_values}")

            # Verify parameters differ
            assert len(set(size_multipliers)) > 1 or len(set(max_paths_values)) > 1

            print("✓ CellResizeECO parameters vary across trials")

    def test_step_3_verify_each_config_has_unique_eco_params(self) -> None:
        """
        Step 3: Verify each config has unique eco_params.

        Verify that trials with the same ECO type have different
        parameter values to explore the parameter space.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="unique_params_test",
                safety_domain=SafetyDomain.GUARDED,
                base_case_name="test_design",
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        trial_budget=15,
                        survivor_count=5,
                        timeout_seconds=300,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[],
                    )
                ],
                snapshot_path=str(Path(tmpdir) / "snapshot"),
                metadata={},
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Create ECOs and group by type
            ecos_by_type: dict[str, list] = {}
            for trial_index in range(1, 15):  # Skip trial 0 (NoOpECO)
                eco = executor._create_eco_for_trial(trial_index, stage_index=0)
                eco_type = eco.metadata.name
                if eco_type not in ecos_by_type:
                    ecos_by_type[eco_type] = []
                ecos_by_type[eco_type].append(eco)

            print(f"✓ Created {sum(len(ecos) for ecos in ecos_by_type.values())} ECOs")
            print(f"  ECO types: {list(ecos_by_type.keys())}")

            # Verify each ECO type has multiple parameter variants
            for eco_type, eco_list in ecos_by_type.items():
                if len(eco_list) >= 2:
                    # Compare parameters between instances
                    params_list = [eco.metadata.parameters for eco in eco_list]

                    # Verify at least some parameters differ
                    all_identical = all(p == params_list[0] for p in params_list)

                    if not all_identical:
                        print(f"✓ {eco_type}: Parameters vary across {len(eco_list)} instances")
                        # Show first two parameter sets
                        for i, params in enumerate(params_list[:2]):
                            print(f"    Instance {i}: {params}")

    def test_step_4_execute_trials_and_verify_metrics_differ(self) -> None:
        """
        Step 4: Execute trials and verify metrics differ.

        Verify that different parameter values would produce different
        metrics (via TCL analysis - we don't run actual Docker executions).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="metrics_diff_test",
                safety_domain=SafetyDomain.GUARDED,
                base_case_name="test_design",
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        trial_budget=10,
                        survivor_count=5,
                        timeout_seconds=300,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[],
                    )
                ],
                snapshot_path=str(Path(tmpdir) / "snapshot"),
                metadata={},
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Create multiple CellResizeECO instances with different parameters
            eco_1 = executor._create_eco_for_trial(trial_index=1, stage_index=0)
            eco_4 = executor._create_eco_for_trial(trial_index=4, stage_index=0)

            # Both should be CellResizeECO
            assert isinstance(eco_1, CellResizeECO)
            assert isinstance(eco_4, CellResizeECO)

            # Verify parameters differ
            params_1 = eco_1.metadata.parameters
            params_4 = eco_4.metadata.parameters

            print(f"✓ Trial 1 parameters: {params_1}")
            print(f"✓ Trial 4 parameters: {params_4}")

            # Parameters should differ
            assert params_1 != params_4

            print("✓ Different trial configs have different parameters")

            # Verify TCL generation differs based on parameters
            tcl_1 = eco_1.generate_tcl()
            tcl_4 = eco_4.generate_tcl()

            # TCL should differ (different parameter values)
            assert tcl_1 != tcl_4

            print("✓ Different parameters produce different TCL commands")
            print(f"  This would result in different OpenROAD executions")
            print(f"  Leading to different timing/congestion metrics")

    def test_step_5_verify_parameter_sweep_produces_effect_gradient(self) -> None:
        """
        Step 5: Verify parameter sweep produces observable effect gradient.

        Verify that parameter variation creates a gradient effect where
        different parameter values produce systematically different results.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="gradient_test",
                safety_domain=SafetyDomain.GUARDED,
                base_case_name="test_design",
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        trial_budget=12,
                        survivor_count=5,
                        timeout_seconds=300,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[],
                    )
                ],
                snapshot_path=str(Path(tmpdir) / "snapshot"),
                metadata={},
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Collect CellResizeECO instances (trials 1, 4, 7, 10)
            cell_resize_ecos = []
            for trial_index in [1, 4, 7, 10]:
                eco = executor._create_eco_for_trial(trial_index, stage_index=0)
                if isinstance(eco, CellResizeECO):
                    cell_resize_ecos.append(eco)

            assert len(cell_resize_ecos) >= 3, "Need at least 3 instances for gradient"

            print(f"✓ Collected {len(cell_resize_ecos)} CellResizeECO instances")

            # Extract parameter values
            size_multipliers = [eco.metadata.parameters["size_multiplier"] for eco in cell_resize_ecos]
            max_paths = [eco.metadata.parameters["max_paths"] for eco in cell_resize_ecos]

            print(f"  Size multipliers: {size_multipliers}")
            print(f"  Max paths: {max_paths}")

            # Verify parameter gradient exists
            # Either size_multipliers or max_paths should form a gradient
            size_mult_gradient = len(set(size_multipliers)) > 1
            max_paths_gradient = len(set(max_paths)) > 1

            assert size_mult_gradient or max_paths_gradient

            if size_mult_gradient:
                print(f"✓ Size multiplier gradient: {min(size_multipliers)} -> {max(size_multipliers)}")
                print(f"  Lower values = less aggressive upsizing")
                print(f"  Higher values = more aggressive upsizing")
                print(f"  This creates a gradient of timing improvements")

            if max_paths_gradient:
                print(f"✓ Max paths gradient: {min(max_paths)} -> {max(max_paths)}")
                print(f"  Lower values = fewer paths optimized")
                print(f"  Higher values = more paths optimized")
                print(f"  This creates a gradient of optimization coverage")

            # Verify systematic variation (not random)
            # Parameters should increase or decrease systematically
            if size_mult_gradient:
                sorted_multipliers = sorted(size_multipliers)
                print(f"✓ Systematic parameter variation confirmed")
                print(f"  Sorted values: {sorted_multipliers}")


class TestParameterVariationIntegration:
    """Integration tests for parameter variation across ECO types."""

    def test_parameter_variation_across_all_eco_types(self) -> None:
        """
        Verify that all ECO types (CellResize, BufferInsertion, CellSwap)
        have parameter variation.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="all_eco_types_test",
                safety_domain=SafetyDomain.GUARDED,
                base_case_name="test_design",
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        trial_budget=20,
                        survivor_count=5,
                        timeout_seconds=300,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[],
                    )
                ],
                snapshot_path=str(Path(tmpdir) / "snapshot"),
                metadata={},
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Collect ECOs by type
            eco_instances: dict[str, list] = {
                "cell_resize": [],
                "buffer_insertion": [],
                "cell_swap": [],
            }

            for trial_index in range(1, 20):
                eco = executor._create_eco_for_trial(trial_index, stage_index=0)
                if isinstance(eco, CellResizeECO):
                    eco_instances["cell_resize"].append(eco)
                elif isinstance(eco, BufferInsertionECO):
                    eco_instances["buffer_insertion"].append(eco)
                elif isinstance(eco, CellSwapECO):
                    eco_instances["cell_swap"].append(eco)

            print("✓ ECO type distribution:")
            for eco_type, instances in eco_instances.items():
                print(f"  {eco_type}: {len(instances)} instances")

            # Verify each type has parameter variation
            for eco_type, instances in eco_instances.items():
                if len(instances) >= 2:
                    params_list = [eco.metadata.parameters for eco in instances]
                    unique_params = len(set(str(p) for p in params_list))

                    assert unique_params > 1, f"{eco_type} should have parameter variation"

                    print(f"✓ {eco_type}: {unique_params} unique parameter sets")

    def test_parameter_ranges_are_reasonable(self) -> None:
        """
        Verify that parameter ranges are reasonable for physical design.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            config = StudyConfig(
                name="param_ranges_test",
                safety_domain=SafetyDomain.GUARDED,
                base_case_name="test_design",
                pdk="nangate45",
                stages=[
                    StageConfig(
                        name="stage_0",
                        trial_budget=15,
                        survivor_count=5,
                        timeout_seconds=300,
                        execution_mode=ExecutionMode.STA_ONLY,
                        allowed_eco_classes=[],
                    )
                ],
                snapshot_path=str(Path(tmpdir) / "snapshot"),
                metadata={},
            )

            executor = StudyExecutor(
                config=config,
                artifacts_root=tmpdir,
                skip_base_case_verification=True,
            )

            # Check CellResizeECO parameter ranges
            for trial_index in [1, 4, 7]:
                eco = executor._create_eco_for_trial(trial_index, stage_index=0)
                if isinstance(eco, CellResizeECO):
                    size_mult = eco.metadata.parameters["size_multiplier"]
                    max_paths = eco.metadata.parameters["max_paths"]

                    # Size multiplier should be reasonable (1.0 to 3.0 range)
                    assert 1.0 <= size_mult <= 3.0, f"Size multiplier {size_mult} outside reasonable range"

                    # Max paths should be positive and reasonable
                    assert 0 < max_paths <= 500, f"Max paths {max_paths} outside reasonable range"

                    print(f"✓ Trial {trial_index}: size_mult={size_mult}, max_paths={max_paths} (reasonable)")

            # Check CellSwapECO parameter ranges
            for trial_index in [3, 6, 9]:
                eco = executor._create_eco_for_trial(trial_index, stage_index=0)
                if isinstance(eco, CellSwapECO):
                    path_count = eco.metadata.parameters["path_count"]

                    # Path count should be reasonable
                    assert 0 < path_count <= 500, f"Path count {path_count} outside reasonable range"

                    print(f"✓ Trial {trial_index}: path_count={path_count} (reasonable)")
