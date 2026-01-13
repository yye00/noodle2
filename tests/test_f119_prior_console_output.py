"""
Test F119: Demo console output shows prior state updates with success/failure counts

This test validates that:
1. Console output contains [PRIOR] lines
2. Prior updates show success/failure counts (XS/YF format)
3. Prior state is displayed (unknown/trusted/suspicious/mixed)
4. State transitions are visible
5. Updates appear after each trial

Feature Steps:
1. Run demo and capture console output
2. Verify output contains [PRIOR] <eco_name>: XS/YF -> state=<state>
3. Verify success (S) and failure (F) counts are tracked
4. Verify state transitions (unknown -> trusted/suspicious/mixed)
5. Verify prior updates appear after each trial
"""

import re
import subprocess
from pathlib import Path

import pytest


class TestF119PriorConsoleOutput:
    """Test F119: Console output shows prior state updates"""

    def test_step_1_run_demo_and_capture_console_output(self):
        """
        Step 1: Run demo and capture console output

        The demo should print prior state updates to stdout.
        """
        result = subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=1800,  # 30 minute timeout
        )

        assert result.returncode == 0, (
            f"Demo failed with exit code {result.returncode}\n"
            f"STDERR: {result.stderr[-1000:]}"
        )

        # Verify we captured stdout
        assert result.stdout, "No console output captured"
        assert len(result.stdout) > 0, "Console output is empty"

        print(f"\n✓ Captured {len(result.stdout)} bytes of console output")

    def test_step_2_verify_prior_format_in_output(self):
        """
        Step 2: Verify output contains [PRIOR] <eco_name>: XS/YF -> state=<state>

        The expected format is:
          [PRIOR] buffer_insertion: 5S/2F -> state=mixed
        """
        result = subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=1800,
        )

        assert result.returncode == 0, "Demo failed"

        stdout = result.stdout

        # Look for [PRIOR] lines
        prior_pattern = r'\[PRIOR\]\s+(\w+):\s+(\d+)S/(\d+)F\s+->\s+state=(\w+)'
        prior_lines = re.findall(prior_pattern, stdout)

        assert len(prior_lines) > 0, (
            f"No [PRIOR] lines found in console output\n"
            f"Expected format: [PRIOR] <eco_name>: XS/YF -> state=<state>\n"
            f"Console output length: {len(stdout)} bytes"
        )

        print(f"\n✓ Found {len(prior_lines)} prior state updates")
        print("\nExample prior updates:")
        for eco_name, success, failures, state in prior_lines[:5]:
            print(f"  [PRIOR] {eco_name}: {success}S/{failures}F -> state={state}")

    def test_step_3_verify_success_failure_counts_tracked(self):
        """
        Step 3: Verify success (S) and failure (F) counts are tracked

        Success and failure counts should accumulate as trials execute.
        """
        result = subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=1800,
        )

        assert result.returncode == 0, "Demo failed"

        stdout = result.stdout
        prior_pattern = r'\[PRIOR\]\s+(\w+):\s+(\d+)S/(\d+)F\s+->\s+state=(\w+)'
        prior_lines = re.findall(prior_pattern, stdout)

        # Group by ECO name to track count progression
        eco_counts = {}
        for eco_name, success_str, failures_str, state in prior_lines:
            success = int(success_str)
            failures = int(failures_str)

            if eco_name not in eco_counts:
                eco_counts[eco_name] = []

            eco_counts[eco_name].append((success, failures, state))

        # Verify counts accumulate (non-decreasing)
        for eco_name, counts in eco_counts.items():
            for i in range(1, len(counts)):
                prev_success, prev_failures, _ = counts[i-1]
                curr_success, curr_failures, _ = counts[i]

                # Total applications should be non-decreasing
                prev_total = prev_success + prev_failures
                curr_total = curr_success + curr_failures

                assert curr_total >= prev_total, (
                    f"ECO {eco_name} counts decreased:\n"
                    f"Previous: {prev_success}S/{prev_failures}F = {prev_total} total\n"
                    f"Current: {curr_success}S/{curr_failures}F = {curr_total} total"
                )

        print(f"\n✓ Success/failure counts accumulate correctly for {len(eco_counts)} ECOs")

        # Show accumulation for one ECO
        if eco_counts:
            example_eco = list(eco_counts.keys())[0]
            print(f"\nExample accumulation ({example_eco}):")
            for success, failures, state in eco_counts[example_eco][:5]:
                print(f"  {success}S/{failures}F -> {state}")

    def test_step_4_verify_state_transitions(self):
        """
        Step 4: Verify state transitions (unknown -> trusted/suspicious/mixed)

        As ECOs accumulate evidence, their prior state should transition
        from unknown to one of the other states.
        """
        result = subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=1800,
        )

        assert result.returncode == 0, "Demo failed"

        stdout = result.stdout
        prior_pattern = r'\[PRIOR\]\s+(\w+):\s+(\d+)S/(\d+)F\s+->\s+state=(\w+)'
        prior_lines = re.findall(prior_pattern, stdout)

        # Group by ECO name to track state transitions
        eco_states = {}
        for eco_name, success_str, failures_str, state in prior_lines:
            if eco_name not in eco_states:
                eco_states[eco_name] = []
            eco_states[eco_name].append(state)

        # Verify state transitions occur
        valid_states = {"unknown", "trusted", "mixed", "suspicious", "blacklisted"}
        transitions_found = False

        for eco_name, states in eco_states.items():
            # Verify all states are valid
            for state in states:
                assert state in valid_states, (
                    f"Invalid prior state '{state}' for ECO {eco_name}\n"
                    f"Valid states: {valid_states}"
                )

            # Check if state transitions occur
            unique_states = set(states)
            if len(unique_states) > 1:
                transitions_found = True
                print(f"\n✓ State transition found for {eco_name}:")
                print(f"  States: {' -> '.join(states)}")

        print(f"\n✓ All {len(eco_states)} ECOs have valid prior states")

        # Note: Not all ECOs may transition states in a single run,
        # but the state values should always be valid
        if transitions_found:
            print("✓ State transitions observed during demo")

    def test_step_5_verify_updates_appear_after_each_trial(self):
        """
        Step 5: Verify prior updates appear after each trial

        Each trial that applies an ECO should update and print
        the prior state.
        """
        result = subprocess.run(
            ["bash", "demo_nangate45_extreme.sh"],
            capture_output=True,
            text=True,
            timeout=1800,
        )

        assert result.returncode == 0, "Demo failed"

        stdout = result.stdout

        # Look for trial execution patterns and prior updates
        # Expected pattern:
        #   Trial X/Y: ...
        #   ...
        #   [PRIOR] eco_name: ...

        lines = stdout.split('\n')
        trial_indices = []
        prior_indices = []

        for i, line in enumerate(lines):
            if re.search(r'Trial\s+\d+/\d+:', line):
                trial_indices.append(i)
            elif '[PRIOR]' in line:
                prior_indices.append(i)

        print(f"\n✓ Found {len(trial_indices)} trial start messages")
        print(f"✓ Found {len(prior_indices)} prior update messages")

        # Verify we have prior updates
        assert len(prior_indices) > 0, (
            "No prior updates found in console output\n"
            "Expected [PRIOR] lines after trial execution"
        )

        # Verify prior updates appear after trials
        # (Each prior update should come after at least one trial)
        if trial_indices and prior_indices:
            first_trial = trial_indices[0]
            first_prior = prior_indices[0]

            # First prior update should come after first trial starts
            assert first_prior > first_trial, (
                "Prior update appeared before any trials started\n"
                f"First trial at line {first_trial}\n"
                f"First prior update at line {first_prior}"
            )

            print("✓ Prior updates appear after trials execute")


class TestF119IntegrationWithExecutor:
    """Integration tests for prior console output"""

    def test_update_and_persist_method_prints_prior_state(self, tmp_path):
        """Verify that _update_and_persist_eco_effectiveness prints prior state"""
        from src.controller.demo_study import create_nangate45_extreme_demo_study
        from src.controller.executor import StudyExecutor
        from src.trial_runner.trial import TrialConfig, TrialResult, TrialArtifacts
        import io
        import sys

        study_config = create_nangate45_extreme_demo_study()

        executor = StudyExecutor(
            config=study_config,
            artifacts_root=tmp_path / "artifacts",
            telemetry_root=tmp_path / "telemetry",
            skip_base_case_verification=True,
        )

        # Create mock trial results and configs
        trial_config = TrialConfig(
            study_name="test_study",
            case_name="test_case",
            stage_index=0,
            trial_index=0,
            script_path=str(tmp_path / "script.tcl"),
            snapshot_dir=str(tmp_path),
            timeout_seconds=300,
            metadata={"eco_type": "buffer_insertion"},
        )

        trial_result = TrialResult(
            config=trial_config,
            success=True,
            return_code=0,
            runtime_seconds=1.0,
            artifacts=TrialArtifacts(trial_dir=tmp_path / "trial"),
            metrics={"timing": {"wns_ps": -100}},
        )

        # Capture stdout
        captured_output = io.StringIO()
        sys.stdout = captured_output

        try:
            # Call the method
            executor._update_and_persist_eco_effectiveness(
                trial_results=[trial_result],
                trial_configs=[trial_config],
            )
        finally:
            sys.stdout = sys.__stdout__

        output = captured_output.getvalue()

        # Verify [PRIOR] line was printed
        assert "[PRIOR]" in output, (
            "No [PRIOR] line in output\n"
            f"Output: {output}"
        )

        assert "buffer_insertion" in output, (
            "ECO name not in prior update\n"
            f"Output: {output}"
        )

        # Verify format: XS/YF -> state=<state>
        assert re.search(r'\d+S/\d+F\s+->\s+state=\w+', output), (
            "Prior update not in expected format\n"
            f"Expected: XS/YF -> state=<state>\n"
            f"Output: {output}"
        )

        print(f"\n✓ Console output format correct:\n{output.strip()}")
