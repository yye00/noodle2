"""CI/CD integration for regression safety checks.

Enables Noodle 2 to be used in CI pipelines for regression detection
with deterministic pass/fail criteria and clear exit codes.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.controller.executor import StudyExecutor, StudyResult
from src.controller.study import StudyConfig
from src.controller.types import SafetyDomain


@dataclass
class RegressionBaseline:
    """
    Known-good baseline for regression testing.

    Captures expected metrics that must not regress in CI.
    """

    case_name: str
    expected_wns_ps: int  # Worst Negative Slack in picoseconds
    tolerance_ps: int = 100  # Allowed variance due to tool non-determinism
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_regression(self, actual_wns_ps: int) -> tuple[bool, str]:
        """
        Check if actual WNS represents a regression from baseline.

        Args:
            actual_wns_ps: Actual WNS measured in trial

        Returns:
            Tuple of (is_regression: bool, reason: str)
        """
        # WNS regression: more negative is worse
        # Allow some tolerance for tool non-determinism
        if actual_wns_ps < (self.expected_wns_ps - self.tolerance_ps):
            delta = actual_wns_ps - self.expected_wns_ps
            return True, (
                f"WNS regression detected: expected {self.expected_wns_ps}ps, "
                f"got {actual_wns_ps}ps (delta: {delta}ps, "
                f"tolerance: {self.tolerance_ps}ps)"
            )

        return False, ""


@dataclass
class CIConfig:
    """
    Configuration for CI regression testing.

    Defines regression baselines and fail-fast behavior.
    """

    study_config: StudyConfig
    baselines: list[RegressionBaseline] = field(default_factory=list)
    fail_on_study_abort: bool = True  # Fail CI if Study aborts
    fail_on_regression: bool = True  # Fail CI if any baseline regresses
    fail_on_safety_violation: bool = True  # Fail CI if safety violations occur
    artifacts_root: str | Path = "artifacts"
    telemetry_root: str | Path = "telemetry"

    def validate(self) -> tuple[bool, list[str]]:
        """
        Validate CI configuration.

        Returns:
            Tuple of (is_valid: bool, issues: list[str])
        """
        issues = []

        # CI Studies must use 'locked' safety domain
        if self.study_config.safety_domain != SafetyDomain.LOCKED:
            issues.append(
                f"CI Studies must use 'locked' safety domain, "
                f"got '{self.study_config.safety_domain.value}'"
            )

        # Must have at least one baseline for regression testing
        if self.fail_on_regression and not self.baselines:
            issues.append(
                "CI config has fail_on_regression=True but no baselines defined"
            )

        return len(issues) == 0, issues


@dataclass
class CIResult:
    """
    Result of CI regression test execution.

    Contains pass/fail verdict and detailed diagnostics.
    """

    study_result: StudyResult
    regressions_detected: list[tuple[str, str]] = field(
        default_factory=list
    )  # (case_name, reason)
    safety_violations: list[str] = field(default_factory=list)
    passed: bool = False
    failure_reason: str | None = None
    exit_code: int = 0  # 0 = success, non-zero = failure

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "study_name": self.study_result.study_name,
            "passed": self.passed,
            "failure_reason": self.failure_reason,
            "exit_code": self.exit_code,
            "regressions_detected": [
                {"case_name": case, "reason": reason}
                for case, reason in self.regressions_detected
            ],
            "safety_violations": self.safety_violations,
            "study_result": self.study_result.to_dict(),
        }


class CIRunner:
    """
    Executes Studies in CI mode with regression detection and exit codes.

    Ensures deterministic pass/fail behavior for CI/CD pipelines.
    """

    def __init__(self, config: CIConfig):
        """
        Initialize CI runner.

        Args:
            config: CI configuration

        Raises:
            ValueError: If CI configuration is invalid
        """
        is_valid, issues = config.validate()
        if not is_valid:
            raise ValueError(
                f"Invalid CI configuration:\n" + "\n".join(f"  - {issue}" for issue in issues)
            )

        self.config = config

        # Create Study executor
        self.executor = StudyExecutor(
            config=config.study_config,
            artifacts_root=config.artifacts_root,
            telemetry_root=config.telemetry_root,
        )

        # Map baselines by case name for quick lookup
        self.baseline_map = {bl.case_name: bl for bl in config.baselines}

    def run(self) -> CIResult:
        """
        Execute Study in CI mode with regression detection.

        Returns:
            CIResult with pass/fail verdict and exit code
        """
        print("\n" + "=" * 70)
        print("CI REGRESSION TEST")
        print("=" * 70)
        print(f"Study: {self.config.study_config.name}")
        print(f"Safety Domain: {self.config.study_config.safety_domain.value}")
        print(f"Baselines: {len(self.config.baselines)}")
        print("=" * 70 + "\n")

        # Execute Study
        study_result = self.executor.execute()

        # Initialize CI result
        ci_result = CIResult(study_result=study_result)

        # Check for Study abortion
        if study_result.aborted:
            if self.config.fail_on_study_abort:
                ci_result.passed = False
                ci_result.failure_reason = (
                    f"Study aborted: {study_result.abort_reason}"
                )
                ci_result.exit_code = 1
                return ci_result

        # Check for regressions against baselines
        regressions = self._detect_regressions(study_result)
        if regressions:
            ci_result.regressions_detected = regressions
            if self.config.fail_on_regression:
                ci_result.passed = False
                ci_result.failure_reason = (
                    f"{len(regressions)} regression(s) detected"
                )
                ci_result.exit_code = 2
                return ci_result

        # If we got here, all checks passed
        ci_result.passed = True
        ci_result.exit_code = 0

        return ci_result

    def _detect_regressions(
        self, study_result: StudyResult
    ) -> list[tuple[str, str]]:
        """
        Detect regressions by comparing trial results against baselines.

        Args:
            study_result: Completed Study result

        Returns:
            List of (case_name, reason) tuples for detected regressions
        """
        regressions = []

        # Collect all trial results across all stages
        for stage_result in study_result.stage_results:
            for trial_result in stage_result.trial_results:
                # TrialResult has case_name in config
                case_name = trial_result.config.case_name

                # Check if we have a baseline for this case
                baseline = self.baseline_map.get(case_name)
                if not baseline:
                    continue

                # Extract WNS from trial metrics
                wns_ps = trial_result.metrics.get("wns_ps")
                if wns_ps is None:
                    # Can't check regression without WNS metric
                    continue

                # Check for regression
                is_regression, reason = baseline.is_regression(wns_ps)
                if is_regression:
                    regressions.append((case_name, reason))

        return regressions

    def run_and_exit(self) -> None:
        """
        Execute Study in CI mode and exit with appropriate code.

        This is the main entry point for CI pipeline integration.
        Calls sys.exit() with the CI result exit code.
        """
        result = self.run()

        # Print CI summary
        print("\n" + "=" * 70)
        print("CI RESULT")
        print("=" * 70)
        if result.passed:
            print("✓ PASSED - No regressions detected")
        else:
            print(f"✗ FAILED - {result.failure_reason}")
            if result.regressions_detected:
                print("\nRegressions:")
                for case_name, reason in result.regressions_detected:
                    print(f"  - {case_name}: {reason}")
        print(f"\nExit code: {result.exit_code}")
        print("=" * 70 + "\n")

        sys.exit(result.exit_code)


def create_ci_config(
    study_config: StudyConfig,
    baselines: list[RegressionBaseline] | None = None,
    **kwargs: Any,
) -> CIConfig:
    """
    Create CI configuration with validation.

    Args:
        study_config: Study configuration for CI run
        baselines: Regression baselines (optional)
        **kwargs: Additional CIConfig parameters

    Returns:
        Validated CIConfig

    Raises:
        ValueError: If configuration is invalid
    """
    config = CIConfig(
        study_config=study_config,
        baselines=baselines or [],
        **kwargs,
    )

    # Validate immediately
    is_valid, issues = config.validate()
    if not is_valid:
        raise ValueError(
            f"Invalid CI configuration:\n" + "\n".join(f"  - {issue}" for issue in issues)
        )

    return config
