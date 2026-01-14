# Session 66 Summary - Root Cause Analysis of F115/F116 Failures

**Date:** 2026-01-14  
**Status:** Investigation Complete  
**Features Affected:** F115, F116  
**Overall Progress:** 118/120 features passing (98.3%)

## Executive Summary

Conducted deep investigation into why F115 (>50% WNS improvement) and F116 (>60% hot_ratio reduction) continue to fail despite the Session 65 metrics bug fix.

**Key Finding:** The ECO implementation is fundamentally broken - it makes designs WORSE instead of better.

## Critical Discovery

### The Session 65 Bug Was NOT the Root Cause

Session 65 fixed hardcoded `design="gcd"` and `clock_period_ns=0.001` in metrics.json. However, this bug only affected **metadata fields**, not the actual timing measurements.

The actual WNS/TNS/hot_ratio values come from Tcl STA commands:
```tcl
set wns [sta::worst_slack -max]
set tns [sta::total_negative_slack -max]
```

These values were ALWAYS correct, even with wrong metadata. Therefore, the demo results showing **negative improvement were ACCURATE**.

## Evidence from Telemetry Analysis

### Demo Run (Jan 14 04:57)

**Initial State (ibex snapshot):**
- WNS: -1848 ps
- hot_ratio: 0.526

**Final State (after 4 stages, 57 trials):**
- WNS: -2473 ps (33.8% WORSE)
- hot_ratio: 1.0 (90% WORSE)

### Trial-Level Analysis

Example trial (nangate45_extreme_ibex_0_3):
- Started with: WNS=-1848ps, hot_ratio=0.526
- After ECO: WNS=-2553ps, hot_ratio=1.0
- **Result: 705ps timing degradation, congestion maxed out**
- Trial succeeded (return_code=0) but made design objectively worse

### Error Analysis

8 out of 20 trials (40%) in stage 0 failed with:
```
[ERROR STA-0562] repair_design -max_cap is not a known keyword or flag
```

The `BufferInsertionECO` uses `repair_design -max_cap` which is not supported in the current OpenROAD version.

## Root Cause Analysis

### Problem 1: Unsupported OpenROAD Commands
- `BufferInsertionECO` uses `repair_design -max_cap {value}` 
- This flag is not recognized by the OpenROAD version in use
- 40% of trials crash immediately

### Problem 2: Harmful ECO Side Effects
- Even "successful" ECO trials degrade metrics
- `repair_timing` and `repair_design` are making timing WORSE
- Possible causes:
  - Missing wire RC setup
  - Incorrect parasitic estimation
  - Too aggressive optimization
  - Missing timing constraints context

### Problem 3: No ECO Validation
- ECOs are applied blindly without pre/post comparison
- No rollback mechanism if ECO degrades metrics
- Multi-stage process compounds the damage

## Why F115/F116 Cannot Pass

**F115 Target:** >50% WNS improvement from -1848ps
- Need to achieve: -924ps or better
- Current result: -2473ps
- **Gap: 2174ps improvement needed**

**F116 Target:** >60% hot_ratio reduction from 0.526  
- Need to achieve: 0.210 or better
- Current result: 1.0
- **Gap: 0.790 reduction needed**

## Implications

**The metrics bug fix did NOT solve the problem.** The actual issue is algorithmic - the ECO commands are fundamentally broken and make designs worse instead of better.

## Recommendations for Next Session

**DO NOT** run more demos until ECO implementation is fixed. Running demos will waste 2+ hours and continue to fail.

### Priority Actions

1. **Immediate:** Test OpenROAD commands in isolation
   - Verify which `repair_design` flags are supported
   - Test if `repair_timing` improves or degrades timing
   - Create minimal test cases with known good results

2. **Short-term:** Fix BufferInsertionECO
   - Remove unsupported `-max_cap` flag
   - Use supported syntax for current OpenROAD version
   - Add pre/post ECO validation

3. **Medium-term:** Add ECO effectiveness validation
   - Compare metrics before and after each ECO
   - Only keep ECO if it improves metrics
   - Implement rollback mechanism

4. **Long-term:** Redesign ECO strategy
   - Current 4-pass aggressive buffering is counterproductive
   - Consider gentler, targeted ECOs
   - Add diagnosis-driven ECO selection
   - Implement learning from ECO success/failure

## Session Artifacts

- **Commit:** Session 66 findings documented and committed
- **Analysis:** Full telemetry analysis of 57 trials across 4 stages
- **Evidence:** Trial-level data showing systematic degradation
- **Progress Notes:** Updated with detailed root cause analysis

## Status

- F115: **FAILING** - ECO makes design worse (need fix)
- F116: **FAILING** - ECO makes design worse (need fix)
- Framework: **118/120 passing (98.3%)**
- Critical Path: **Fix ECO implementation**

---

**Session 66 completed:** 2026-01-14  
**Next session focus:** Fix ECO command compatibility and effectiveness
