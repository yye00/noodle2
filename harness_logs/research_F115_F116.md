# Research Findings: F115/F116 Extreme Timing Optimization

## Research Date: 2026-01-14
## Source: Perplexity Deep Research

## Executive Summary

For designs with extreme timing violations (5.3x over budget), standard OpenROAD ECO commands (`repair_design`, `repair_timing`) are insufficient and often make timing WORSE. Achieving >50% WNS improvement requires a multi-strategy approach combining advanced placement, iterative ECO flows, and potentially architectural changes.

## Key Findings

### 1. Why Standard ECOs Fail

**The Buffer Paradox:**
- `repair_design` fixes DRV by inserting buffers
- Buffer insertion adds delay to paths
- `repair_timing` tries to recover but can't overcome added delay
- Net result: timing degrades

**Evidence from demos:**
```
Initial WNS:     -1848ps → After ECOs: -2473ps (34% WORSE)
Initial hot_ratio: 0.526 → After ECOs: 1.000   (90% WORSE)
```

### 2. Strategies That CAN Work

#### Strategy A: Timing-Driven Placement Re-optimization
- **Improvement potential:** 40-50% TNS reduction
- **OpenROAD command:** `global_placement -timing_driven -overflow 0.1`
- **How it works:** Uses STA feedback to keep timing-critical cells closer together

#### Strategy B: MLBuf-RePlAce (Buffer-Aware Placement)
- **Improvement potential:** 56% TNS improvement (documented in research)
- **Key insight:** Reserve buffer space DURING placement, not after
- **Reference:** UCSD VLSI CAD paper

#### Strategy C: Iterative ECO Flow
- **Key difference:** Multiple passes, not single-pass
- **Algorithm:**
  ```
  while violations exist and iteration < max:
      1. Analyze post-route timing (with actual parasitics)
      2. Insert buffers on WORST paths only
      3. Incremental placement + routing
      4. Re-analyze timing
      5. Check if improvement plateaued
  ```
- **Evidence:** LiteX core fixed 131 hold violations over 10 ECO iterations

#### Strategy D: Skip repair_design
- Only use `repair_timing`
- Avoids buffer insertion that adds delay
- Already attempted by harness - showed modest improvement

#### Strategy E: Pipelining (Architectural Change)
- Insert register stages on critical paths
- Trades latency for timing closure
- Required when logic depth exceeds timing budget

### 3. Realistic Expectations

For a design 5.3x over timing budget (-1848ps on 350ps clock):

| Strategy Combination | Expected Improvement |
|---------------------|---------------------|
| Single ECO pass | -30% to +10% (often worse) |
| Timing-driven re-placement | 40-50% TNS |
| Iterative ECO (10+ passes) | 20-40% additional |
| Combined strategies | 50-70% possible |
| With pipelining | Can achieve closure |

### 4. Recommended Approach for F115/F116

**Phase 1: Diagnosis**
- Verify which corners have violations
- Check if violations are clock-skew driven

**Phase 2: Placement Re-optimization**
```tcl
# In OpenROAD
global_placement -timing_driven -overflow 0.1
detailed_placement
```

**Phase 3: Iterative ECO (Not Single-Pass)**
```tcl
# Repeat until convergence or max iterations
for {set i 0} {$i < 10} {incr i} {
    repair_timing -setup -hold
    # Check improvement
    report_worst_slack -max
    # If <2% improvement, stop
}
```

**Phase 4: If Still Failing**
- Create less extreme snapshot (2-3x over budget instead of 5.3x)
- Or document as requiring architectural changes (pipelining)

### 5. Alternative: Less Extreme Snapshot

The current snapshot uses 0.5ns clock (4.4x faster than 2.2ns default). This creates artificially extreme violations.

**Option:** Create snapshot with 1.0-1.5ns clock instead:
- Still "extreme" (2-3x over budget)
- More realistically fixable with local ECOs
- Demonstrates ECO effectiveness without requiring architectural changes

## Citations

1. OpenROAD YouTube tutorials on timing closure
2. OpenLane2 documentation on timing closure
3. UCSD MLBuf-RePlAce paper (56% TNS improvement)
4. OpenROAD GitHub issues #1371, #860, #4908
5. NVIDIA research on RL-based parameter tuning (79% TNS improvement)
6. AMD/Xilinx timing closure guides

## Action Items for Harness

1. [x] Use Perplexity to research any additional strategies (DONE - this document)
2. [x] Try timing-driven re-placement before ECOs (DONE - TimingDrivenPlacementECO)
3. [x] Implement iterative ECO flow (min 5 passes) (DONE - IterativeTimingDrivenECO)
4. [ ] Run demo with IterativeTimingDrivenECO and measure results
5. [ ] If still failing, create less extreme snapshot OR document as architectural limitation

## Implementation Status (Session 79)

### Newly Implemented: IterativeTimingDrivenECO

Created ultra-aggressive iterative ECO based on research findings:

**Features:**
- Combines timing-driven placement re-optimization
- Iterative repair_timing with up to 10 passes
- Convergence checking (stops if improvement < 2%)
- Adaptive margin scheduling (starts at 30%, ends at 0%)
- Registered in ECO_REGISTRY as "iterative_timing_driven"

**Implementation:**
- Location: `src/controller/eco.py` (IterativeTimingDrivenECO class)
- Tests: `tests/test_iterative_timing_driven_eco.py` (8 tests, all passing)
- Classification: ECOClass.GLOBAL_DISRUPTIVE

**Expected Improvement:**
Based on research, iterative ECO flows can provide 20-40% additional improvement beyond single-pass timing-driven placement. Current best: 10.1%, so with iterative approach, could potentially reach 30-50% improvement.

**Next Step:**
Run demo with this new ECO to measure actual improvement vs target of 50%.
