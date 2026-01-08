"""Tests for policy trace generation and auditability."""

import json
import tempfile
from pathlib import Path

import pytest

from src.policy.policy_trace import (
    PolicyRuleEvaluation,
    PolicyRuleOutcome,
    PolicyRuleType,
    PolicyTrace,
)


class TestPolicyTraceRecording:
    """Test recording of policy rule evaluations."""

    def test_record_survivor_ranking(self):
        """Test recording survivor ranking decisions."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0", "case_0_1", "case_0_2"],
            baseline_metrics={"wns_ps": -1000},
        )

        assert len(trace.evaluations) == 1
        evaluation = trace.evaluations[0]
        assert evaluation.rule_type == PolicyRuleType.SURVIVOR_RANKING
        assert evaluation.outcome == PolicyRuleOutcome.APPLIED
        assert evaluation.inputs["trial_count"] == 10
        assert evaluation.logic["policy_name"] == "wns_delta"
        assert evaluation.result["selected_count"] == 3
        assert evaluation.result["selected_cases"] == [
            "case_0_0",
            "case_0_1",
            "case_0_2",
        ]

    def test_record_survivor_ranking_with_weights(self):
        """Test recording multi-objective ranking with weights."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="multi_objective",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0", "case_0_1", "case_0_2"],
            baseline_metrics={"wns_ps": -1000, "hot_ratio": 0.8},
            weights={"timing": 0.6, "congestion": 0.4},
        )

        assert len(trace.evaluations) == 1
        evaluation = trace.evaluations[0]
        assert evaluation.logic["weights"] == {"timing": 0.6, "congestion": 0.4}
        assert "multi_objective" in evaluation.rationale

    def test_record_eco_selection(self):
        """Test recording ECO selection decisions."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_eco_selection(
            stage_index=0,
            case_name="case_0_0",
            available_ecos=["eco_a", "eco_b", "eco_c"],
            selected_eco="eco_a",
            selection_reason="highest prior",
            eco_priors={"eco_a": "trusted", "eco_b": "mixed", "eco_c": "unknown"},
        )

        assert len(trace.evaluations) == 1
        evaluation = trace.evaluations[0]
        assert evaluation.rule_type == PolicyRuleType.ECO_SELECTION
        assert evaluation.outcome == PolicyRuleOutcome.APPLIED
        assert evaluation.inputs["available_ecos"] == ["eco_a", "eco_b", "eco_c"]
        assert evaluation.result["selected_eco"] == "eco_a"
        assert evaluation.logic["eco_priors"]["eco_a"] == "trusted"

    def test_record_trial_filtering_blacklist(self):
        """Test recording trial filtering with blacklist."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_trial_filtering(
            stage_index=0,
            filter_type="blacklist",
            trials_before=10,
            trials_after=8,
            filter_criteria={"blacklisted_ecos": ["eco_bad"]},
            filtered_items=["trial_1", "trial_5"],
        )

        assert len(trace.evaluations) == 1
        evaluation = trace.evaluations[0]
        assert evaluation.rule_type == PolicyRuleType.TRIAL_FILTERING
        assert evaluation.inputs["trials_before"] == 10
        assert evaluation.result["trials_after"] == 8
        assert evaluation.result["filtered_count"] == 2
        assert evaluation.logic["filter_type"] == "blacklist"

    def test_record_trial_filtering_whitelist(self):
        """Test recording trial filtering with whitelist."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_trial_filtering(
            stage_index=0,
            filter_type="whitelist",
            trials_before=10,
            trials_after=5,
            filter_criteria={"whitelisted_ecos": ["eco_a", "eco_b"]},
            filtered_items=[f"trial_{i}" for i in range(5)],
        )

        assert len(trace.evaluations) == 1
        evaluation = trace.evaluations[0]
        assert evaluation.logic["filter_type"] == "whitelist"
        assert evaluation.result["filtered_count"] == 5

    def test_record_eco_prior_update(self):
        """Test recording ECO prior confidence updates."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_eco_prior_update(
            stage_index=0,
            eco_name="eco_test",
            old_prior="unknown",
            new_prior="trusted",
            update_reason="success_rate_improved",
            evidence={"success_count": 5, "failure_count": 0},
        )

        assert len(trace.evaluations) == 1
        evaluation = trace.evaluations[0]
        assert evaluation.rule_type == PolicyRuleType.ECO_PRIOR_UPDATE
        assert evaluation.inputs["old_prior"] == "unknown"
        assert evaluation.result["new_prior"] == "trusted"
        assert evaluation.logic["update_reason"] == "success_rate_improved"
        assert evaluation.logic["evidence"]["success_count"] == 5

    def test_record_metric_weighting(self):
        """Test recording metric weighting configuration."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_metric_weighting(
            stage_index=0,
            weights={"timing": 0.6, "congestion": 0.4},
            weight_source="stage_config",
        )

        assert len(trace.evaluations) == 1
        evaluation = trace.evaluations[0]
        assert evaluation.rule_type == PolicyRuleType.METRIC_WEIGHTING
        assert evaluation.logic["weights"]["timing"] == 0.6
        assert evaluation.logic["weight_source"] == "stage_config"

    def test_record_budget_allocation(self):
        """Test recording trial budget allocation."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_budget_allocation(
            stage_index=0,
            total_budget=20,
            allocated_trials=18,
            allocation_strategy="eco_class_weighted",
            allocation_details={
                "topology_neutral": 6,
                "placement_local": 8,
                "routing_affecting": 4,
            },
        )

        assert len(trace.evaluations) == 1
        evaluation = trace.evaluations[0]
        assert evaluation.rule_type == PolicyRuleType.BUDGET_ALLOCATION
        assert evaluation.inputs["total_budget"] == 20
        assert evaluation.result["allocated_trials"] == 18
        assert evaluation.logic["allocation_strategy"] == "eco_class_weighted"


class TestPolicyTraceChronologicalOrdering:
    """Test chronological ordering of evaluations."""

    def test_evaluations_have_timestamps(self):
        """Test all evaluations have ISO 8601 timestamps."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0"],
            baseline_metrics={"wns_ps": -1000},
        )

        trace.record_eco_selection(
            stage_index=0,
            case_name="case_0_0",
            available_ecos=["eco_a"],
            selected_eco="eco_a",
            selection_reason="only option",
        )

        for evaluation in trace.evaluations:
            assert evaluation.timestamp
            # Verify ISO 8601 format (contains 'T' and ends with timezone)
            assert "T" in evaluation.timestamp
            assert evaluation.timestamp.endswith("+00:00") or evaluation.timestamp.endswith(
                "Z"
            )

    def test_evaluations_maintain_chronological_order(self):
        """Test evaluations are stored in chronological order."""
        trace = PolicyTrace(study_name="test_study")

        # Record multiple evaluations
        for i in range(5):
            trace.record_eco_prior_update(
                stage_index=i,
                eco_name=f"eco_{i}",
                old_prior="unknown",
                new_prior="trusted",
                update_reason="test",
                evidence={},
            )

        # Verify timestamps are in chronological order
        timestamps = [e.timestamp for e in trace.evaluations]
        assert timestamps == sorted(timestamps)


class TestPolicyTraceSummary:
    """Test policy trace summary statistics."""

    def test_summary_counts_total_evaluations(self):
        """Test summary counts total evaluations."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0"],
            baseline_metrics={"wns_ps": -1000},
        )

        trace.record_eco_selection(
            stage_index=0,
            case_name="case_0_0",
            available_ecos=["eco_a"],
            selected_eco="eco_a",
            selection_reason="test",
        )

        summary = trace.get_summary()
        assert summary["total_evaluations"] == 2

    def test_summary_counts_by_outcome(self):
        """Test summary counts evaluations by outcome."""
        trace = PolicyTrace(study_name="test_study")

        # All APPLIED outcomes
        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0"],
            baseline_metrics={"wns_ps": -1000},
        )

        summary = trace.get_summary()
        assert summary["by_outcome"]["applied"] == 1
        assert summary["by_outcome"]["skipped"] == 0
        assert summary["by_outcome"]["failed"] == 0

    def test_summary_counts_by_rule_type(self):
        """Test summary counts evaluations by rule type."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0"],
            baseline_metrics={"wns_ps": -1000},
        )

        trace.record_survivor_ranking(
            stage_index=1,
            policy_name="wns_delta",
            trial_count=3,
            survivor_count=1,
            selected_cases=["case_1_0"],
            baseline_metrics={"wns_ps": -500},
        )

        trace.record_eco_selection(
            stage_index=0,
            case_name="case_0_0",
            available_ecos=["eco_a"],
            selected_eco="eco_a",
            selection_reason="test",
        )

        summary = trace.get_summary()
        assert summary["by_rule_type"]["survivor_ranking"] == 2
        assert summary["by_rule_type"]["eco_selection"] == 1


class TestPolicyTraceSerialization:
    """Test policy trace serialization and file I/O."""

    def test_to_dict_includes_all_fields(self):
        """Test to_dict includes study name, metadata, summary, and evaluations."""
        trace = PolicyTrace(study_name="test_study", metadata={"key": "value"})

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0"],
            baseline_metrics={"wns_ps": -1000},
        )

        data = trace.to_dict()
        assert data["study_name"] == "test_study"
        assert data["metadata"]["key"] == "value"
        assert "summary" in data
        assert "evaluations" in data
        assert len(data["evaluations"]) == 1

    def test_save_json(self):
        """Test saving policy trace to JSON file."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0"],
            baseline_metrics={"wns_ps": -1000},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "policy_trace.json"
            trace.save_json(output_path)

            assert output_path.exists()

            # Verify JSON is valid
            with open(output_path) as f:
                data = json.load(f)
                assert data["study_name"] == "test_study"
                assert len(data["evaluations"]) == 1

    def test_save_txt(self):
        """Test saving policy trace to text file."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0"],
            baseline_metrics={"wns_ps": -1000},
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "policy_trace.txt"
            trace.save_txt(output_path)

            assert output_path.exists()

            # Verify text content
            content = output_path.read_text()
            assert "POLICY TRACE REPORT" in content
            assert "test_study" in content


class TestPolicyTraceHumanReadable:
    """Test human-readable policy trace formatting."""

    def test_str_has_header(self):
        """Test string representation has header."""
        trace = PolicyTrace(study_name="test_study")
        output = str(trace)

        assert "POLICY TRACE REPORT" in output
        assert "Study: test_study" in output

    def test_str_has_summary_section(self):
        """Test string representation has summary section."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0"],
            baseline_metrics={"wns_ps": -1000},
        )

        output = str(trace)
        assert "Summary:" in output
        assert "Total Evaluations: 1" in output

    def test_str_has_evaluations_by_type(self):
        """Test string representation groups evaluations by type."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0"],
            baseline_metrics={"wns_ps": -1000},
        )

        output = str(trace)
        assert "SURVIVOR_RANKING" in output

    def test_str_has_chronological_log(self):
        """Test string representation has chronological log."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0"],
            baseline_metrics={"wns_ps": -1000},
        )

        output = str(trace)
        assert "CHRONOLOGICAL LOG" in output

    def test_str_shows_outcome_symbols(self):
        """Test string representation shows outcome symbols (✓/-/✗/⚠)."""
        trace = PolicyTrace(study_name="test_study")

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0"],
            baseline_metrics={"wns_ps": -1000},
        )

        output = str(trace)
        # APPLIED evaluations should have ✓
        assert "✓" in output


class TestPolicyTraceIntegration:
    """Test policy trace integration with Study execution."""

    def test_multiple_stages_record_separate_evaluations(self):
        """Test multi-stage Study records evaluations per stage."""
        trace = PolicyTrace(study_name="test_study")

        # Stage 0
        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0", "case_0_1", "case_0_2"],
            baseline_metrics={"wns_ps": -1000},
        )

        # Stage 1
        trace.record_survivor_ranking(
            stage_index=1,
            policy_name="wns_delta",
            trial_count=3,
            survivor_count=1,
            selected_cases=["case_1_0"],
            baseline_metrics={"wns_ps": -500},
        )

        assert len(trace.evaluations) == 2
        assert trace.evaluations[0].inputs["stage_index"] == 0
        assert trace.evaluations[1].inputs["stage_index"] == 1

    def test_complete_study_workflow(self):
        """Test complete Study workflow generates comprehensive trace."""
        trace = PolicyTrace(study_name="test_study")

        # Stage 0: Exploration
        trace.record_metric_weighting(
            stage_index=0,
            weights={"timing": 0.6, "congestion": 0.4},
            weight_source="stage_config",
        )

        trace.record_budget_allocation(
            stage_index=0,
            total_budget=20,
            allocated_trials=20,
            allocation_strategy="uniform",
            allocation_details={},
        )

        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="multi_objective",
            trial_count=20,
            survivor_count=5,
            selected_cases=[f"case_0_{i}" for i in range(5)],
            baseline_metrics={"wns_ps": -1000, "hot_ratio": 0.8},
            weights={"timing": 0.6, "congestion": 0.4},
        )

        # Stage 1: Refinement
        trace.record_eco_prior_update(
            stage_index=1,
            eco_name="eco_buffer",
            old_prior="unknown",
            new_prior="trusted",
            update_reason="high_success_rate",
            evidence={"success_count": 15, "failure_count": 2},
        )

        trace.record_survivor_ranking(
            stage_index=1,
            policy_name="wns_delta",
            trial_count=5,
            survivor_count=1,
            selected_cases=["case_1_0"],
            baseline_metrics={"wns_ps": -500},
        )

        assert len(trace.evaluations) == 5
        summary = trace.get_summary()
        assert summary["total_evaluations"] == 5
        assert summary["by_rule_type"]["survivor_ranking"] == 2
        assert summary["by_rule_type"]["eco_prior_update"] == 1
        assert summary["by_rule_type"]["metric_weighting"] == 1
        assert summary["by_rule_type"]["budget_allocation"] == 1

    def test_trace_enables_post_execution_audit(self):
        """Test policy trace enables post-execution policy audit."""
        trace = PolicyTrace(study_name="test_study")

        # Simulate Study execution
        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0", "case_0_1", "case_0_2"],
            baseline_metrics={"wns_ps": -1000},
        )

        # Audit: Verify policy behavior is traceable
        # 1. Find all survivor ranking decisions
        ranking_decisions = [
            e for e in trace.evaluations if e.rule_type == PolicyRuleType.SURVIVOR_RANKING
        ]
        assert len(ranking_decisions) == 1

        # 2. Verify inputs to ranking decision
        decision = ranking_decisions[0]
        assert decision.inputs["trial_count"] == 10

        # 3. Verify logic used
        assert decision.logic["policy_name"] == "wns_delta"
        assert decision.logic["baseline_metrics"]["wns_ps"] == -1000

        # 4. Verify outcome
        assert decision.outcome == PolicyRuleOutcome.APPLIED
        assert len(decision.result["selected_cases"]) == 3

        # 5. Verify rationale is human-readable
        assert "wns_delta" in decision.rationale
        assert "10 trials" in decision.rationale

    def test_trace_behavior_is_fully_traceable(self):
        """Test all policy behavior is fully traceable through audit trail."""
        trace = PolicyTrace(study_name="test_study")

        # Record various policy decisions
        trace.record_survivor_ranking(
            stage_index=0,
            policy_name="wns_delta",
            trial_count=10,
            survivor_count=3,
            selected_cases=["case_0_0", "case_0_1", "case_0_2"],
            baseline_metrics={"wns_ps": -1000},
        )

        trace.record_eco_selection(
            stage_index=0,
            case_name="case_0_0",
            available_ecos=["eco_a", "eco_b"],
            selected_eco="eco_a",
            selection_reason="highest prior",
            eco_priors={"eco_a": "trusted", "eco_b": "unknown"},
        )

        trace.record_trial_filtering(
            stage_index=0,
            filter_type="blacklist",
            trials_before=10,
            trials_after=9,
            filter_criteria={"blacklisted_ecos": ["eco_bad"]},
            filtered_items=["trial_3"],
        )

        # Verify complete traceability
        # 1. Every decision has timestamp
        for evaluation in trace.evaluations:
            assert evaluation.timestamp

        # 2. Every decision has inputs
        for evaluation in trace.evaluations:
            assert evaluation.inputs

        # 3. Every decision has logic/parameters
        for evaluation in trace.evaluations:
            assert evaluation.logic

        # 4. Every decision has outcome
        for evaluation in trace.evaluations:
            assert evaluation.outcome

        # 5. Every decision has result
        for evaluation in trace.evaluations:
            assert evaluation.result

        # 6. Every decision has rationale
        for evaluation in trace.evaluations:
            assert evaluation.rationale
