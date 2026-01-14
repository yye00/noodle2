# Timing-Driven Placement ECO Implementation Plan

## Overview

If Session 73's "skip repair_design" approach doesn't achieve >50% WNS improvement, the next strategy from the research list is to implement timing-driven global placement.

## Current State

Session 73 implemented:
- Skip `repair_design` in ECOs
- Use only `repair_timing` with multiple aggressive passes (4 passes per ECO)
- Margins: 0.3-0.4 → 0.15-0.2 → 0.05-0.1 → 0.0

This addresses DRV-driven buffer insertion but doesn't fundamentally change placement.

## New Approach: Timing-Driven Placement ECO

### Research Findings

From ORFS `global_place.tcl` (lines 29-34):
```tcl
if { $::env(GPL_TIMING_DRIVEN) } {
  lappend global_placement_args {-timing_driven}
  if { [info exists ::env(GPL_KEEP_OVERFLOW)] } {
    lappend global_placement_args -keep_resize_below_overflow $::env(GPL_KEEP_OVERFLOW)
  }
}
```

Key commands:
1. `remove_buffers` - Remove existing buffers before re-placement
2. `global_placement -timing_driven -density X` - Timing-aware placement
3. `detailed_placement` - Legalize the placement

### Proposed Implementation

Create a new `TimingDrivenPlacementECO` class:

```python
class TimingDrivenPlacementECO(ECO):
    """ECO that re-runs placement with timing awareness.

    This ECO removes existing buffers and re-runs global placement
    with the -timing_driven flag, allowing OpenROAD to optimize
    placement for timing rather than just wirelength.
    """

    def __init__(
        self,
        target_density: float = 0.70,
        keep_overflow: float = 0.1,
    ) -> None:
        metadata = ECOMetadata(
            name="timing_driven_placement",
            eco_class=ECOClass.PLACEMENT_AFFECTING,
            description="Re-run placement with timing awareness to reduce critical path delay",
            parameters={
                "target_density": target_density,
                "keep_overflow": keep_overflow,
            },
            version="1.0",
            tags=["timing_optimization", "placement", "timing_driven"],
        )
        super().__init__(metadata)

    def generate_tcl(self, **kwargs: Any) -> str:
        density = self.metadata.parameters["target_density"]
        keep_overflow = self.metadata.parameters["keep_overflow"]

        tcl_script = f"""# Timing-Driven Placement ECO
# Re-optimize placement with timing awareness

# Set wire RC for accurate parasitic estimation
set_wire_rc -signal -layer metal3
set_wire_rc -clock -layer metal5

# Remove existing buffers to allow fresh placement
remove_buffers

# Run timing-driven global placement
# This optimizes for timing instead of just wirelength
global_placement -timing_driven -density {density} \\
    -keep_resize_below_overflow {keep_overflow}

# Legalize placement
detailed_placement

# Re-estimate parasitics with new placement
estimate_parasitics -placement

# Multiple passes of repair_timing to fix remaining violations
repair_timing -setup -setup_margin 0.3
estimate_parasitics -placement

repair_timing -setup -setup_margin 0.15
estimate_parasitics -placement

repair_timing -setup -setup_margin 0.0

puts "Timing-driven placement ECO complete"
"""
        return tcl_script
```

### Integration Points

1. **Add to ECO Templates**: Add to `EcoTemplate` enum if it exists
2. **Add to Demo Study**: Include in one of the stages (probably stage 1 or 2)
3. **Testing**: Create test file `test_timing_driven_placement_eco.py`

### Expected Impact

**Why This Might Help**:
- Default placement optimizes for wirelength
- Timing-driven placement considers path delays during placement
- Can reduce critical path delay by better cell positioning
- Removes buffers first to allow clean re-optimization

**Risk**:
- More aggressive change than local ECOs
- Could increase congestion if density is too high
- Takes longer to execute (full re-placement)

### Alternative: Hybrid Approach

Instead of full re-placement, could add timing-driven placement as a "heavy" ECO used only in later stages after local ECOs have been tried.

**Phased Approach**:
1. Stage 0-1: Try local ECOs (current implementation)
2. Stage 2: If improvement < 30%, trigger timing-driven re-placement
3. Stage 3: Follow up with local ECOs on improved placement

## Testing Plan

1. **Unit Test**: Verify TCL generation works
2. **Integration Test**: Add to demo study, verify execution
3. **Performance Test**: Measure WNS improvement vs baseline
4. **Comparison**: Compare with Session 73 results

## Decision Criteria

Implement timing-driven placement if:
- Session 73 approach shows < 30% improvement
- We have evidence that placement is the bottleneck (not just cell sizing)
- Ready to invest additional execution time (~10-15 minutes per trial)

## Status

- [ ] Session 73 demo results analyzed
- [ ] Decision made to implement timing-driven placement
- [ ] TimingDrivenPlacementECO class implemented
- [ ] Unit tests written
- [ ] Integration test passed
- [ ] Demo re-run with new ECO
- [ ] F115/F116 performance targets achieved

---

*Document created: Session 74*
*Author: Claude (Autonomous Development Agent)*
*Next review: After Session 73 demo completes*
