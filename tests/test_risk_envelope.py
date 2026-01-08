"""Tests for ECO risk envelope constraint enforcement."""

import pytest

from src.controller.risk_envelope import (
    ECOImpact,
    EnvelopeCheckResult,
    EnvelopeViolation,
    RiskEnvelope,
    ViolationSeverity,
    ViolationType,
    check_risk_envelope,
    classify_violation_severity,
    should_abort_eco,
)


class TestRiskEnvelope:
    """Tests for RiskEnvelope dataclass."""

    def test_create_risk_envelope_with_all_constraints(self) -> None:
        """Step 1: Define ECO class with risk envelope."""
        envelope = RiskEnvelope(
            max_cells_affected=100,
            max_area_delta_percent=5.0,
            max_wirelength_delta_percent=10.0,
            max_timing_degradation_ps=500,
        )

        assert envelope.max_cells_affected == 100
        assert envelope.max_area_delta_percent == 5.0
        assert envelope.max_wirelength_delta_percent == 10.0
        assert envelope.max_timing_degradation_ps == 500

    def test_create_risk_envelope_with_partial_constraints(self) -> None:
        """Test creating risk envelope with only some constraints."""
        envelope = RiskEnvelope(
            max_cells_affected=50,
            max_area_delta_percent=3.0,
        )

        assert envelope.max_cells_affected == 50
        assert envelope.max_area_delta_percent == 3.0
        assert envelope.max_wirelength_delta_percent is None
        assert envelope.max_timing_degradation_ps is None

    def test_risk_envelope_validates_non_negative(self) -> None:
        """Test that risk envelope validates non-negative constraints."""
        with pytest.raises(ValueError, match="max_cells_affected must be non-negative"):
            RiskEnvelope(max_cells_affected=-1)

        with pytest.raises(
            ValueError, match="max_area_delta_percent must be non-negative"
        ):
            RiskEnvelope(max_area_delta_percent=-5.0)

    def test_risk_envelope_to_dict(self) -> None:
        """Test risk envelope serialization."""
        envelope = RiskEnvelope(
            max_cells_affected=100,
            max_area_delta_percent=5.0,
        )

        envelope_dict = envelope.to_dict()

        assert envelope_dict["max_cells_affected"] == 100
        assert envelope_dict["max_area_delta_percent"] == 5.0
        assert envelope_dict["max_wirelength_delta_percent"] is None


class TestECOImpact:
    """Tests for ECOImpact dataclass."""

    def test_create_eco_impact(self) -> None:
        """Step 3: Measure actual cells affected and area delta."""
        impact = ECOImpact(
            cells_affected=75,
            area_delta_um2=1200.5,
            area_delta_percent=3.2,
            wirelength_delta_um=5000.0,
            wirelength_delta_percent=8.0,
            wns_delta_ps=100.0,  # Improvement
        )

        assert impact.cells_affected == 75
        assert impact.area_delta_percent == 3.2
        assert impact.wns_delta_ps == 100.0

    def test_eco_impact_to_dict(self) -> None:
        """Test ECO impact serialization."""
        impact = ECOImpact(
            cells_affected=50,
            area_delta_percent=2.5,
        )

        impact_dict = impact.to_dict()

        assert impact_dict["cells_affected"] == 50
        assert impact_dict["area_delta_percent"] == 2.5
        assert impact_dict["wns_delta_ps"] == 0.0


class TestViolationSeverityClassification:
    """Tests for violation severity classification."""

    def test_classify_minor_violation(self) -> None:
        """Test classification of minor violation (< 10% over)."""
        # 5% over limit
        severity = classify_violation_severity(limit=100, actual=105)
        assert severity == ViolationSeverity.MINOR

    def test_classify_moderate_violation(self) -> None:
        """Test classification of moderate violation (10-50% over)."""
        # 25% over limit
        severity = classify_violation_severity(limit=100, actual=125)
        assert severity == ViolationSeverity.MODERATE

    def test_classify_major_violation(self) -> None:
        """Test classification of major violation (> 50% over)."""
        # 75% over limit
        severity = classify_violation_severity(limit=100, actual=175)
        assert severity == ViolationSeverity.MAJOR

    def test_classify_violation_at_boundaries(self) -> None:
        """Test classification at severity boundaries."""
        # Exactly 10% over -> moderate
        severity = classify_violation_severity(limit=100, actual=110)
        assert severity == ViolationSeverity.MODERATE

        # Exactly 50% over -> moderate
        severity = classify_violation_severity(limit=100, actual=150)
        assert severity == ViolationSeverity.MODERATE

    def test_classify_violation_with_zero_limit(self) -> None:
        """Test that zero limit results in major violation."""
        severity = classify_violation_severity(limit=0, actual=1)
        assert severity == ViolationSeverity.MAJOR


class TestEnvelopeCheckCellsAffected:
    """Tests for checking cells affected constraint."""

    def test_cells_affected_within_envelope(self) -> None:
        """Step 4: Verify actuals are within risk envelope."""
        envelope = RiskEnvelope(max_cells_affected=100)
        impact = ECOImpact(cells_affected=75)

        result = check_risk_envelope(impact, envelope)

        assert result.passed is True
        assert len(result.violations) == 0

    def test_cells_affected_at_limit(self) -> None:
        """Test cells affected exactly at limit (should pass)."""
        envelope = RiskEnvelope(max_cells_affected=100)
        impact = ECOImpact(cells_affected=100)

        result = check_risk_envelope(impact, envelope)

        assert result.passed is True

    def test_cells_affected_exceeds_envelope(self) -> None:
        """Step 5: Classify as ECO violation if envelope is exceeded."""
        envelope = RiskEnvelope(max_cells_affected=100)
        impact = ECOImpact(cells_affected=150)  # 50% over

        result = check_risk_envelope(impact, envelope)

        assert result.passed is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.violation_type == ViolationType.CELLS_AFFECTED
        assert violation.severity == ViolationSeverity.MODERATE
        assert violation.limit == 100
        assert violation.actual == 150
        assert violation.percent_over == 50.0
        assert "Cells affected" in violation.message


class TestEnvelopeCheckAreaDelta:
    """Tests for checking area delta constraint."""

    def test_area_delta_within_envelope(self) -> None:
        """Test area delta within envelope."""
        envelope = RiskEnvelope(max_area_delta_percent=5.0)
        impact = ECOImpact(area_delta_percent=3.0)

        result = check_risk_envelope(impact, envelope)

        assert result.passed is True

    def test_area_delta_exceeds_envelope(self) -> None:
        """Test area delta exceeding envelope."""
        envelope = RiskEnvelope(max_area_delta_percent=5.0)
        impact = ECOImpact(area_delta_percent=8.0)  # 60% over

        result = check_risk_envelope(impact, envelope)

        assert result.passed is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.violation_type == ViolationType.AREA_DELTA
        assert violation.severity == ViolationSeverity.MAJOR
        assert violation.limit == 5.0
        assert violation.actual == 8.0

    def test_area_delta_checks_absolute_value(self) -> None:
        """Test that area delta uses absolute value (area decrease also checked)."""
        envelope = RiskEnvelope(max_area_delta_percent=5.0)
        impact = ECOImpact(area_delta_percent=-8.0)  # Negative (decrease)

        result = check_risk_envelope(impact, envelope)

        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].actual == 8.0  # Absolute value


class TestEnvelopeCheckWirelengthDelta:
    """Tests for checking wirelength delta constraint."""

    def test_wirelength_delta_within_envelope(self) -> None:
        """Test wirelength delta within envelope."""
        envelope = RiskEnvelope(max_wirelength_delta_percent=10.0)
        impact = ECOImpact(wirelength_delta_percent=7.0)

        result = check_risk_envelope(impact, envelope)

        assert result.passed is True

    def test_wirelength_delta_exceeds_envelope(self) -> None:
        """Test wirelength delta exceeding envelope."""
        envelope = RiskEnvelope(max_wirelength_delta_percent=10.0)
        impact = ECOImpact(wirelength_delta_percent=15.0)

        result = check_risk_envelope(impact, envelope)

        assert result.passed is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.violation_type == ViolationType.WIRELENGTH_DELTA


class TestEnvelopeCheckTimingDegradation:
    """Tests for checking timing degradation constraint."""

    def test_timing_improvement_always_passes(self) -> None:
        """Test that timing improvement (positive WNS delta) passes."""
        envelope = RiskEnvelope(max_timing_degradation_ps=500)
        impact = ECOImpact(wns_delta_ps=200.0)  # Improvement

        result = check_risk_envelope(impact, envelope)

        assert result.passed is True

    def test_timing_degradation_within_envelope(self) -> None:
        """Test timing degradation within envelope."""
        envelope = RiskEnvelope(max_timing_degradation_ps=500)
        impact = ECOImpact(wns_delta_ps=-300.0)  # Degradation (negative)

        result = check_risk_envelope(impact, envelope)

        assert result.passed is True

    def test_timing_degradation_exceeds_envelope(self) -> None:
        """Test timing degradation exceeding envelope."""
        envelope = RiskEnvelope(max_timing_degradation_ps=500)
        impact = ECOImpact(wns_delta_ps=-800.0)  # 60% over (800 vs 500)

        result = check_risk_envelope(impact, envelope)

        assert result.passed is False
        assert len(result.violations) == 1

        violation = result.violations[0]
        assert violation.violation_type == ViolationType.TIMING_DEGRADATION
        assert violation.limit == 500
        assert violation.actual == 800  # Absolute value
        assert violation.severity == ViolationSeverity.MAJOR


class TestMultipleViolations:
    """Tests for handling multiple simultaneous violations."""

    def test_multiple_violations_detected(self) -> None:
        """Test that multiple violations are all detected."""
        envelope = RiskEnvelope(
            max_cells_affected=100,
            max_area_delta_percent=5.0,
            max_timing_degradation_ps=500,
        )

        impact = ECOImpact(
            cells_affected=150,  # Violates
            area_delta_percent=8.0,  # Violates
            wns_delta_ps=-800.0,  # Violates
        )

        result = check_risk_envelope(impact, envelope)

        assert result.passed is False
        assert len(result.violations) == 3

        violation_types = {v.violation_type for v in result.violations}
        assert ViolationType.CELLS_AFFECTED in violation_types
        assert ViolationType.AREA_DELTA in violation_types
        assert ViolationType.TIMING_DEGRADATION in violation_types

    def test_partial_violations(self) -> None:
        """Test that only violated constraints are reported."""
        envelope = RiskEnvelope(
            max_cells_affected=100,
            max_area_delta_percent=5.0,
        )

        impact = ECOImpact(
            cells_affected=75,  # OK
            area_delta_percent=8.0,  # Violates
        )

        result = check_risk_envelope(impact, envelope)

        assert result.passed is False
        assert len(result.violations) == 1
        assert result.violations[0].violation_type == ViolationType.AREA_DELTA


class TestEnvelopeCheckResult:
    """Tests for EnvelopeCheckResult dataclass."""

    def test_check_result_properties(self) -> None:
        """Test EnvelopeCheckResult computed properties."""
        violation1 = EnvelopeViolation(
            violation_type=ViolationType.CELLS_AFFECTED,
            severity=ViolationSeverity.MINOR,
            limit=100,
            actual=105,
            percent_over=5.0,
            message="Test violation",
        )

        violation2 = EnvelopeViolation(
            violation_type=ViolationType.AREA_DELTA,
            severity=ViolationSeverity.MAJOR,
            limit=5.0,
            actual=10.0,
            percent_over=100.0,
            message="Test major violation",
        )

        result = EnvelopeCheckResult(
            passed=False, violations=[violation1, violation2]
        )

        assert result.violation_count == 2
        assert result.has_major_violations is True

    def test_check_result_no_major_violations(self) -> None:
        """Test has_major_violations when no major violations exist."""
        violation = EnvelopeViolation(
            violation_type=ViolationType.CELLS_AFFECTED,
            severity=ViolationSeverity.MINOR,
            limit=100,
            actual=105,
            percent_over=5.0,
            message="Minor violation",
        )

        result = EnvelopeCheckResult(passed=False, violations=[violation])

        assert result.has_major_violations is False

    def test_check_result_to_dict(self) -> None:
        """Test EnvelopeCheckResult serialization."""
        envelope = RiskEnvelope(max_cells_affected=100)
        impact = ECOImpact(cells_affected=150)

        result = check_risk_envelope(impact, envelope)
        result_dict = result.to_dict()

        assert result_dict["passed"] is False
        assert result_dict["violation_count"] == 1
        assert len(result_dict["violations"]) == 1
        assert result_dict["impact"] is not None
        assert result_dict["envelope"] is not None


class TestAbortPolicy:
    """Tests for ECO abort policy based on violations."""

    def test_strict_policy_aborts_on_any_violation(self) -> None:
        """Step 6: Abort ECO based on policy - strict mode."""
        violation = EnvelopeViolation(
            violation_type=ViolationType.CELLS_AFFECTED,
            severity=ViolationSeverity.MINOR,
            limit=100,
            actual=105,
            percent_over=5.0,
            message="Minor violation",
        )

        result = EnvelopeCheckResult(passed=False, violations=[violation])

        # Strict policy: abort on any violation
        assert should_abort_eco(result, policy="strict") is True

    def test_moderate_policy_aborts_on_major_violations(self) -> None:
        """Step 6: Abort ECO based on policy - moderate mode."""
        minor_violation = EnvelopeViolation(
            violation_type=ViolationType.CELLS_AFFECTED,
            severity=ViolationSeverity.MINOR,
            limit=100,
            actual=105,
            percent_over=5.0,
            message="Minor violation",
        )

        major_violation = EnvelopeViolation(
            violation_type=ViolationType.AREA_DELTA,
            severity=ViolationSeverity.MAJOR,
            limit=5.0,
            actual=10.0,
            percent_over=100.0,
            message="Major violation",
        )

        # Minor violation only: don't abort
        result_minor = EnvelopeCheckResult(passed=False, violations=[minor_violation])
        assert should_abort_eco(result_minor, policy="moderate") is False

        # Major violation: abort
        result_major = EnvelopeCheckResult(passed=False, violations=[major_violation])
        assert should_abort_eco(result_major, policy="moderate") is True

    def test_lenient_policy_requires_multiple_major_violations(self) -> None:
        """Step 6: Abort ECO based on policy - lenient mode."""
        major_violation1 = EnvelopeViolation(
            violation_type=ViolationType.CELLS_AFFECTED,
            severity=ViolationSeverity.MAJOR,
            limit=100,
            actual=200,
            percent_over=100.0,
            message="Major violation 1",
        )

        major_violation2 = EnvelopeViolation(
            violation_type=ViolationType.AREA_DELTA,
            severity=ViolationSeverity.MAJOR,
            limit=5.0,
            actual=10.0,
            percent_over=100.0,
            message="Major violation 2",
        )

        # Single major violation: don't abort
        result_single = EnvelopeCheckResult(
            passed=False, violations=[major_violation1]
        )
        assert should_abort_eco(result_single, policy="lenient") is False

        # Multiple major violations: abort
        result_multiple = EnvelopeCheckResult(
            passed=False, violations=[major_violation1, major_violation2]
        )
        assert should_abort_eco(result_multiple, policy="lenient") is True

    def test_no_violations_never_aborts(self) -> None:
        """Test that passing checks never trigger abort."""
        result = EnvelopeCheckResult(passed=True, violations=[])

        assert should_abort_eco(result, policy="strict") is False
        assert should_abort_eco(result, policy="moderate") is False
        assert should_abort_eco(result, policy="lenient") is False

    def test_invalid_policy_raises_error(self) -> None:
        """Test that invalid policy name raises error."""
        result = EnvelopeCheckResult(passed=False, violations=[])

        with pytest.raises(ValueError, match="Unknown policy"):
            should_abort_eco(result, policy="invalid")


class TestEndToEndRiskEnvelope:
    """End-to-end tests for risk envelope workflow."""

    def test_complete_risk_envelope_workflow(self) -> None:
        """Step 2-6: Execute ECO, measure, verify, classify, abort workflow."""
        # Step 1: Define risk envelope
        envelope = RiskEnvelope(
            max_cells_affected=100,
            max_area_delta_percent=5.0,
            max_timing_degradation_ps=500,
        )

        # Step 2: Execute ECO (simulated)
        # Step 3: Measure impact
        impact = ECOImpact(
            cells_affected=150,  # Exceeds limit
            area_delta_percent=3.0,  # OK
            wns_delta_ps=-200.0,  # OK (improvement)
        )

        # Step 4: Verify against envelope
        result = check_risk_envelope(impact, envelope)

        # Step 5: Classify violations
        assert result.passed is False
        assert result.violation_count == 1
        assert result.violations[0].violation_type == ViolationType.CELLS_AFFECTED

        # Step 6: Determine if ECO should be aborted
        should_abort_strict = should_abort_eco(result, policy="strict")
        should_abort_moderate = should_abort_eco(result, policy="moderate")

        assert should_abort_strict is True  # Strict aborts on any violation
        # Moderate depends on severity (50% over = MODERATE)
        assert result.violations[0].severity == ViolationSeverity.MODERATE

    def test_successful_eco_within_envelope(self) -> None:
        """Test successful ECO that stays within all envelope constraints."""
        envelope = RiskEnvelope(
            max_cells_affected=100,
            max_area_delta_percent=5.0,
            max_wirelength_delta_percent=10.0,
            max_timing_degradation_ps=500,
        )

        impact = ECOImpact(
            cells_affected=50,
            area_delta_percent=2.5,
            wirelength_delta_percent=5.0,
            wns_delta_ps=100.0,  # Improvement
        )

        result = check_risk_envelope(impact, envelope)

        assert result.passed is True
        assert result.violation_count == 0
        assert should_abort_eco(result, policy="strict") is False

    def test_mark_eco_as_suspicious(self) -> None:
        """Test marking ECO as suspicious based on violations."""
        envelope = RiskEnvelope(max_cells_affected=100)
        impact = ECOImpact(cells_affected=120)  # 20% over

        result = check_risk_envelope(impact, envelope)

        assert result.passed is False
        assert result.violations[0].severity == ViolationSeverity.MODERATE

        # In moderate policy, this would mark ECO as suspicious but not abort
        # (since violation is moderate, not major)
        should_abort = should_abort_eco(result, policy="moderate")
        # Policy can be used to decide: abort vs mark suspicious
