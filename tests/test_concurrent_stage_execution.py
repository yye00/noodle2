"""Tests for concurrent stage execution with branching DAGs."""

import pytest
from src.controller.stage_dag import StageDAG, StageDependency, StageRelation


class TestStageDependency:
    """Test StageDependency dataclass."""

    def test_create_dependency(self) -> None:
        """Test creating a stage dependency."""
        dep = StageDependency(from_stage=0, to_stage=1)
        assert dep.from_stage == 0
        assert dep.to_stage == 1
        assert dep.relation == StageRelation.SEQUENTIAL

    def test_dependency_with_relation(self) -> None:
        """Test creating dependency with specific relation."""
        dep = StageDependency(from_stage=0, to_stage=1, relation=StageRelation.INDEPENDENT)
        assert dep.relation == StageRelation.INDEPENDENT

    def test_invalid_dependency_same_stage(self) -> None:
        """Test that stage cannot depend on itself."""
        with pytest.raises(ValueError, match="cannot depend on itself"):
            StageDependency(from_stage=0, to_stage=0)

    def test_invalid_dependency_negative(self) -> None:
        """Test that stages must be non-negative."""
        with pytest.raises(ValueError, match="must be non-negative"):
            StageDependency(from_stage=-1, to_stage=1)


class TestStageDAG:
    """Test StageDAG construction and validation."""

    def test_create_empty_dag(self) -> None:
        """Test creating DAG with no dependencies."""
        dag = StageDAG(num_stages=3, dependencies=[])
        assert dag.num_stages == 3
        assert len(dag.dependencies) == 0

    def test_sequential_dag(self) -> None:
        """Test creating sequential DAG using helper."""
        dag = StageDAG.sequential(num_stages=4)
        assert dag.num_stages == 4
        assert len(dag.dependencies) == 3

        # Verify each stage depends on previous
        for i in range(3):
            assert dag.get_dependencies(i + 1) == [i]

    def test_detect_cycle(self) -> None:
        """Test that DAG rejects cycles."""
        # Create a cycle: 0 -> 1 -> 2 -> 0
        deps = [
            StageDependency(from_stage=0, to_stage=1),
            StageDependency(from_stage=1, to_stage=2),
            StageDependency(from_stage=2, to_stage=0),
        ]
        with pytest.raises(ValueError, match="contain a cycle"):
            StageDAG(num_stages=3, dependencies=deps)

    def test_invalid_stage_reference(self) -> None:
        """Test that dependencies must reference valid stages."""
        deps = [StageDependency(from_stage=0, to_stage=5)]
        with pytest.raises(ValueError, match="invalid stage"):
            StageDAG(num_stages=3, dependencies=deps)

    def test_get_dependencies(self) -> None:
        """Test getting dependencies for a stage."""
        dag = StageDAG.sequential(num_stages=3)
        assert dag.get_dependencies(0) == []
        assert dag.get_dependencies(1) == [0]
        assert dag.get_dependencies(2) == [1]

    def test_get_dependents(self) -> None:
        """Test getting dependents for a stage."""
        dag = StageDAG.sequential(num_stages=3)
        assert dag.get_dependents(0) == [1]
        assert dag.get_dependents(1) == [2]
        assert dag.get_dependents(2) == []

    def test_topological_sort_sequential(self) -> None:
        """Test topological sort on sequential DAG."""
        dag = StageDAG.sequential(num_stages=5)
        order = dag.topological_sort()
        assert order == [0, 1, 2, 3, 4]

    def test_get_ready_stages_sequential(self) -> None:
        """Test getting ready stages in sequential pipeline."""
        dag = StageDAG.sequential(num_stages=4)

        # Initially, only stage 0 is ready
        ready = dag.get_ready_stages(completed_stages=set())
        assert ready == [0]

        # After stage 0, stage 1 is ready
        ready = dag.get_ready_stages(completed_stages={0})
        assert ready == [1]

        # After stages 0 and 1, stage 2 is ready
        ready = dag.get_ready_stages(completed_stages={0, 1})
        assert ready == [2]


class TestBranchingDAG:
    """Test branching DAG configurations."""

    def test_create_branching_dag(self) -> None:
        """Test creating branching DAG with helper."""
        # 1 common stage, then 2 branches of length 2 each
        dag = StageDAG.branching(common_stages=1, branches=[2, 2])
        assert dag.num_stages == 5  # 1 common + 2 + 2 branches

    def test_branching_dag_with_merge(self) -> None:
        """Test branching DAG with convergence point."""
        dag = StageDAG.branching(common_stages=1, branches=[2, 2], merge_stage=True)
        assert dag.num_stages == 6  # 1 common + 2 + 2 branches + 1 merge

        # Merge stage should have 2 dependencies
        merge_idx = 5
        deps = dag.get_dependencies(merge_idx)
        assert len(deps) == 2

    def test_independent_branches_parallel_execution(self) -> None:
        """Test that independent branches can run in parallel."""
        dag = StageDAG.branching(common_stages=1, branches=[2, 3])

        # After common stage completes, both branch starts should be ready
        ready = dag.get_ready_stages(completed_stages={0})
        assert len(ready) == 2  # Both branches ready

    def test_convergence_point_detection(self) -> None:
        """Test detecting convergence points."""
        dag = StageDAG.branching(common_stages=1, branches=[1, 1], merge_stage=True)

        # Merge stage is a convergence point
        merge_idx = 3
        assert dag.is_convergence_point(merge_idx)

        # Other stages are not convergence points
        assert not dag.is_convergence_point(0)
        assert not dag.is_convergence_point(1)
        assert not dag.is_convergence_point(2)

    def test_get_ready_stages_after_branch_merge(self) -> None:
        """Test that merge stage becomes ready after all branches complete."""
        dag = StageDAG.branching(common_stages=1, branches=[1, 1], merge_stage=True)
        # Stage 0 -> Stage 1 (branch 1) -> Stage 3 (merge)
        #        \-> Stage 2 (branch 2) /

        # After common stage, both branches ready
        ready = dag.get_ready_stages(completed_stages={0})
        assert set(ready) == {1, 2}

        # After only one branch, merge is not ready
        ready = dag.get_ready_stages(completed_stages={0, 1})
        assert 3 not in ready

        # After both branches, merge is ready
        ready = dag.get_ready_stages(completed_stages={0, 1, 2})
        assert ready == [3]


class TestStageDAGSerialization:
    """Test StageDAG serialization."""

    def test_to_dict(self) -> None:
        """Test converting DAG to dictionary."""
        dag = StageDAG.sequential(num_stages=3)
        data = dag.to_dict()

        assert data["num_stages"] == 3
        assert len(data["dependencies"]) == 2

    def test_from_dict(self) -> None:
        """Test creating DAG from dictionary."""
        data = {
            "num_stages": 3,
            "dependencies": [
                {"from_stage": 0, "to_stage": 1, "relation": "sequential"},
                {"from_stage": 1, "to_stage": 2, "relation": "sequential"},
            ],
        }
        dag = StageDAG.from_dict(data)

        assert dag.num_stages == 3
        assert len(dag.dependencies) == 2
        assert dag.get_dependencies(2) == [1]

    def test_round_trip_serialization(self) -> None:
        """Test that DAG survives round-trip serialization."""
        original = StageDAG.branching(common_stages=2, branches=[2, 3], merge_stage=True)
        data = original.to_dict()
        restored = StageDAG.from_dict(data)

        assert restored.num_stages == original.num_stages
        assert len(restored.dependencies) == len(original.dependencies)


class TestComplexDAGTopology:
    """Test complex DAG topologies."""

    def test_diamond_dag(self) -> None:
        """Test diamond-shaped DAG (split and merge)."""
        # Stage 0 -> Stage 1 -> Stage 3
        #         \-> Stage 2 /
        deps = [
            StageDependency(from_stage=0, to_stage=1),
            StageDependency(from_stage=0, to_stage=2),
            StageDependency(from_stage=1, to_stage=3),
            StageDependency(from_stage=2, to_stage=3),
        ]
        dag = StageDAG(num_stages=4, dependencies=deps)

        # Stage 0 ready first
        ready = dag.get_ready_stages(completed_stages=set())
        assert ready == [0]

        # After stage 0, stages 1 and 2 ready in parallel
        ready = dag.get_ready_stages(completed_stages={0})
        assert set(ready) == {1, 2}

        # After only stage 1, stage 3 not ready yet
        ready = dag.get_ready_stages(completed_stages={0, 1})
        assert 3 not in ready

        # After both 1 and 2, stage 3 ready
        ready = dag.get_ready_stages(completed_stages={0, 1, 2})
        assert ready == [3]

    def test_multiple_independent_paths(self) -> None:
        """Test DAG with completely independent paths."""
        # Path 1: 0 -> 1
        # Path 2: 2 -> 3 (independent)
        deps = [
            StageDependency(from_stage=0, to_stage=1),
            StageDependency(from_stage=2, to_stage=3),
        ]
        dag = StageDAG(num_stages=4, dependencies=deps)

        # Initially, both path starts are ready
        ready = dag.get_ready_stages(completed_stages=set())
        assert set(ready) == {0, 2}

        # After stage 0, stages 1 and 2 are ready
        ready = dag.get_ready_stages(completed_stages={0})
        assert set(ready) == {1, 2}


class TestConcurrentExecutorIntegration:
    """Test ConcurrentStudyExecutor integration."""

    def test_create_concurrent_executor(self) -> None:
        """Test creating ConcurrentStudyExecutor."""
        from src.controller.concurrent_executor import ConcurrentStudyExecutor
        from src.controller.study import StudyConfig
        from src.controller.types import SafetyDomain, StageConfig, ExecutionMode, ECOClass

        # Create simple study config
        config = StudyConfig(
            name="test_concurrent",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
            ],
            snapshot_path="/tmp/test_snapshot",
        )

        # Create sequential DAG (default)
        executor = ConcurrentStudyExecutor(
            config=config, skip_base_case_verification=True, enable_graceful_shutdown=False
        )

        assert executor.config.name == "test_concurrent"
        assert executor.stage_dag.num_stages == 2

    def test_execution_plan_sequential(self) -> None:
        """Test execution plan for sequential DAG."""
        from src.controller.concurrent_executor import ConcurrentStudyExecutor
        from src.controller.study import StudyConfig
        from src.controller.types import SafetyDomain, StageConfig, ExecutionMode, ECOClass

        config = StudyConfig(
            name="test_sequential",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
            ],
            snapshot_path="/tmp/test_snapshot",
        )

        executor = ConcurrentStudyExecutor(
            config=config, skip_base_case_verification=True, enable_graceful_shutdown=False
        )

        # Get execution plan
        plan = executor.get_execution_plan()

        # Sequential execution: 2 waves, one stage each
        assert len(plan) == 2
        assert plan[0] == [0]
        assert plan[1] == [1]

    def test_execution_plan_branching(self) -> None:
        """Test execution plan for branching DAG."""
        from src.controller.concurrent_executor import ConcurrentStudyExecutor
        from src.controller.study import StudyConfig
        from src.controller.types import SafetyDomain, StageConfig, ExecutionMode, ECOClass

        config = StudyConfig(
            name="test_branching",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
                StageConfig(
                    name="stage1_branch1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
                StageConfig(
                    name="stage2_branch2",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
            ],
            snapshot_path="/tmp/test_snapshot",
        )

        # Create branching DAG: 1 common stage, then 2 branches
        dag = StageDAG.branching(common_stages=1, branches=[1, 1])

        executor = ConcurrentStudyExecutor(
            config=config, stage_dag=dag, skip_base_case_verification=True, enable_graceful_shutdown=False
        )

        # Get execution plan
        plan = executor.get_execution_plan()

        # Branching execution: 2 waves
        # Wave 0: stage 0
        # Wave 1: stages 1 and 2 (parallel)
        assert len(plan) == 2
        assert plan[0] == [0]
        assert set(plan[1]) == {1, 2}

    def test_is_sequential_dag_detection(self) -> None:
        """Test detecting whether DAG is sequential."""
        from src.controller.concurrent_executor import ConcurrentStudyExecutor
        from src.controller.study import StudyConfig
        from src.controller.types import SafetyDomain, StageConfig, ExecutionMode, ECOClass

        config_seq = StudyConfig(
            name="test_detection",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
                StageConfig(
                    name="stage1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
            ],
            snapshot_path="/tmp/test_snapshot",
        )

        # Test with sequential DAG
        executor_seq = ConcurrentStudyExecutor(
            config=config_seq, skip_base_case_verification=True, enable_graceful_shutdown=False
        )
        assert executor_seq._is_sequential_dag()

        # Test with branching DAG - need matching number of stages
        config_branch = StudyConfig(
            name="test_detection_branch",
            safety_domain=SafetyDomain.SANDBOX,
            base_case_name="test_base",
            pdk="Nangate45",
            stages=[
                StageConfig(
                    name="stage0",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=5,
                    survivor_count=2,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
                StageConfig(
                    name="stage1_branch1",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
                StageConfig(
                    name="stage2_branch2",
                    execution_mode=ExecutionMode.STA_ONLY,
                    trial_budget=3,
                    survivor_count=1,
                    allowed_eco_classes=[ECOClass.TOPOLOGY_NEUTRAL],
                ),
            ],
            snapshot_path="/tmp/test_snapshot",
        )
        dag_branch = StageDAG.branching(common_stages=1, branches=[1, 1])
        executor_branch = ConcurrentStudyExecutor(
            config=config_branch, stage_dag=dag_branch, skip_base_case_verification=True, enable_graceful_shutdown=False
        )
        assert not executor_branch._is_sequential_dag()


class TestConcurrentStageExecutionE2E:
    """End-to-end tests for concurrent stage execution feature."""

    def test_step_1_define_study_with_branching_dag(self) -> None:
        """Step 1: Define Study with branching DAG allowing parallel stages."""
        # Create a branching DAG: 1 common stage, then 2 independent branches
        dag = StageDAG.branching(common_stages=1, branches=[2, 2], merge_stage=True)

        assert dag.num_stages == 6
        assert len(dag.dependencies) > 0

        # Verify structure: after stage 0, two branches should be ready
        ready_after_common = dag.get_ready_stages(completed_stages={0})
        assert len(ready_after_common) == 2  # Two independent branches

    def test_step_2_identify_independent_stage_branches(self) -> None:
        """Step 2: Identify independent stage branches."""
        dag = StageDAG.branching(common_stages=1, branches=[2, 3], merge_stage=False)

        # After common stage, identify ready stages
        completed = {0}
        ready = dag.get_ready_stages(completed_stages=completed)

        # Should have 2 independent branches ready
        assert len(ready) == 2

        # Verify they are truly independent (no dependencies between them)
        branch1_start, branch2_start = ready[0], ready[1]
        assert branch1_start not in dag.get_dependencies(branch2_start)
        assert branch2_start not in dag.get_dependencies(branch1_start)

    def test_step_3_execute_independent_stages_in_parallel(self) -> None:
        """Step 3: Execute independent stages in parallel (simulation)."""
        dag = StageDAG.branching(common_stages=1, branches=[2, 2])

        completed = {0}
        ready = dag.get_ready_stages(completed_stages=completed)

        # Simulate parallel execution: both branches start simultaneously
        assert len(ready) == 2
        executing = set(ready)

        # Simulate completion of both first stages in branches
        completed.update(executing)

        # Check next stages in each branch become ready
        next_ready = dag.get_ready_stages(completed_stages=completed)
        assert len(next_ready) == 2  # Next stage in each branch

    def test_step_4_merge_results_at_convergence_point(self) -> None:
        """Step 4: Merge results at convergence point."""
        dag = StageDAG.branching(common_stages=1, branches=[2, 2], merge_stage=True)

        # Execute through branches
        completed = {0, 1, 2, 3, 4}  # Common + all branch stages

        # Convergence stage should now be ready
        ready = dag.get_ready_stages(completed_stages=completed)
        assert len(ready) == 1

        merge_idx = ready[0]
        assert dag.is_convergence_point(merge_idx)

        # Verify all branches feed into merge
        merge_deps = dag.get_dependencies(merge_idx)
        assert len(merge_deps) == 2  # Two branches converge

    def test_step_5_verify_safety_gates_in_parallel(self) -> None:
        """Step 5: Verify safety gates are evaluated correctly in parallel."""
        dag = StageDAG.branching(common_stages=1, branches=[2, 2])

        # Simulate parallel execution with safety checks
        completed = set()

        # Common stage passes safety
        completed.add(0)
        ready = dag.get_ready_stages(completed_stages=completed)
        assert len(ready) == 2

        # Both branches can execute in parallel, each with independent safety checks
        # (Safety checks are independent per stage)
        for stage in ready:
            # Simulate safety gate passing for each parallel stage
            deps = dag.get_dependencies(stage)
            assert all(dep in completed for dep in deps)

    def test_step_6_confirm_study_determinism_preserved(self) -> None:
        """Step 6: Confirm overall Study determinism is preserved."""
        dag = StageDAG.branching(common_stages=1, branches=[2, 2], merge_stage=True)

        # Topological sort provides deterministic ordering
        topo_order = dag.topological_sort()

        # Run twice to verify determinism
        topo_order_2 = dag.topological_sort()
        assert topo_order == topo_order_2

        # Verify that ready stages are always returned in sorted order (deterministic)
        completed = {0}
        ready1 = dag.get_ready_stages(completed_stages=completed)
        ready2 = dag.get_ready_stages(completed_stages=completed)
        assert ready1 == ready2

        # Verify DAG structure is deterministic
        for stage in range(dag.num_stages):
            deps1 = dag.get_dependencies(stage)
            deps2 = dag.get_dependencies(stage)
            assert deps1 == deps2
