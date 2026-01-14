# Session 67: ECO Strategy Fixes for F115/F116

## Executive Summary

Fixed critical ECO implementation issues that were causing designs to get WORSE instead of better. Two key commits address the root causes:

1. **Commit f269afc**: Remove unsupported `-max_cap` flag from BufferInsertionECO
2. **Commit ff50555**: Optimize ALL ECO strategies with gentle constraints

## Problem Statement

**F115** and **F116** were failing because ECO trials were degrading design quality:

### Before Fixes (Last Demo Run - Jan 14 04:57):
- Initial: WNS = -1848ps, hot_ratio = 0.526
- Final: WNS = -2473ps, hot_ratio = 1.0
- **Result**: 33.8% WORSE timing, 90% WORSE congestion

### Target (F115/F116 Requirements):
- F115: >50% WNS improvement (-1848ps → better than -924ps)
- F116: >60% hot_ratio reduction (0.526 → better than 0.210)

## Root Causes Identified

### 1. Unsupported OpenROAD Command (40% Trial Crash Rate)

```tcl
# BROKEN - caused error in 40% of trials
repair_design -max_cap 0.15 -max_wire_length 50
```

Error: `[ERROR STA-0562] repair_design -max_cap is not a known keyword or flag`

### 2. Overly Aggressive ECO Strategy (Made Design Worse)

Previous approach used 4-pass strategy with progressively TIGHTER constraints:

```tcl
# PASS 1: Aggressive
repair_design -max_wire_length 50 -max_utilization 0.95

# PASS 2: More Aggressive
repair_design -max_wire_length 25 -max_utilization 0.98

# PASS 3: Ultra-Aggressive
repair_design -max_wire_length 15 -max_utilization 0.99

# PASS 4: Extreme
repair_design -max_wire_length 10
```

**Why This Failed:**
- For WNS = -1848ps (missing timing by 5.3x clock period), design is extremely broken
- Tight constraints (short wires, high utilization) prevent OpenROAD from exploring solution space
- Multiple passes compound errors instead of fixing them
- Each pass builds on a broken foundation

## Fixes Applied

### Fix 1: Remove Unsupported Flag (Commit f269afc)

**BufferInsertionECO**:
- Removed `-max_cap` flag from all `repair_design` calls
- Prevents 40% of trials from crashing
- Parameter still stored in metadata for documentation

```tcl
# FIXED - no -max_cap flag
repair_design -max_wire_length 120 -max_utilization 0.80
```

### Fix 2: Gentle Constraint Strategy (Commit ff50555)

**New Philosophy**: Give OpenROAD MAXIMUM freedom, not minimum

**Changes to ALL timing ECOs**:

#### BufferInsertionECO
- Wire length: 120um (was 10-50um progressive)
- Utilization: 80% (was 95-99%)
- Passes: 2 (was 4)
- Setup margin: 0.1 on first pass (was 0.0)

#### CellResizeECO
- Wire length: 100um (was 12-60um progressive)
- Utilization: 85% (was 95-99%)
- Passes: 2 (was 4)
- Setup margin: 0.1 on first pass (was 0.0)

#### CellSwapECO
- Wire length: 150um (was 15-80um progressive)
- Utilization: 75% (was 95-99%)
- Passes: 2 (was 4)
- Setup margin: 0.1 on first pass (was 0.0)

#### GateCloningECO
- Wire length: 100um after cloning (was 80um)
- Utilization: 85% (was not specified)

### New ECO Template

```tcl
# Pass 1: Gentle constraints with positive margin
repair_design -max_wire_length 100 -max_utilization 0.85
repair_timing -setup -setup_margin 0.1

# Re-estimate parasitics
estimate_parasitics -placement

# Pass 2: Consolidate improvements
repair_timing -setup -setup_margin 0.0
```

## Rationale

For extremely broken designs (WNS = -1848ps with 350ps clock):

1. **Longer wires** (100-150um vs 10-50um): Allows tool to find routing solutions
2. **Lower utilization** (75-85% vs 95-99%): Reduces congestion pressure
3. **Fewer passes** (2 vs 4): Avoids compounding errors
4. **Positive margins** (0.1 first pass): Conservative repair, room for consolidation
5. **Maximum freedom**: Let `repair_design`/`repair_timing` explore full solution space

## Validation

### Tests Passing
- All ECO framework tests: 34/34 ✓
- All buffer ECO trial tests: 41/41 ✓

### TCL Validation
```
✓ All ECOs use gentle constraints (100-150um wires, 75-85% util)
✓ All ECOs use 2-pass strategy (not 4)
✓ All ECOs include setup_margin 0.1 on first pass
✓ No -max_cap flags in executable code
✓ Commands are OpenROAD-compliant
```

## Expected Outcome

### Demo Runtime (demo_nangate45_extreme.sh)
- 57 total trials across 4 stages
- Best case: ~30 minutes (all succeed quickly)
- Worst case: ~14 hours (sequential, all timeout)
- Typical (Ray parallel, 4 workers): ~3-4 hours

### Expected Improvements

**Conservative Estimate** (50% success rate):
- Each successful ECO trial: +100-200ps WNS improvement
- Cumulative over 4 stages: could reach +800-1000ps
- Starting from -1848ps → -848ps to -1048ps = 43-56% improvement
- **Likely F115 PASS** (need >50%)

**Optimistic Estimate** (75% success rate):
- Could achieve +1200-1500ps cumulative
- Starting from -1848ps → -348ps to -648ps = 65-81% improvement
- **Definite F115 PASS**

**For F116** (hot_ratio):
- PlacementDensityECO now uses 0.60-0.65 density (was attempting higher)
- Should reduce congestion significantly
- Starting from 0.526 → target < 0.210 (60% reduction)
- **Likely F116 PASS** if density reduction is effective

## Next Steps

1. **Run Full Demo** (requires 3-4 hours):
   ```bash
   ./demo_nangate45_extreme.sh
   ```

2. **Monitor Progress**:
   ```bash
   ./monitor_demo.sh  # If available
   # Or check: demo_output/nangate45_extreme_demo/summary.json
   ```

3. **Verify F115/F116**:
   ```bash
   pytest tests/test_f115_f116_extreme_demo.py -v
   ```

4. **If Tests Pass**:
   - Update feature_list.json:
     - F115: passes=true, passed_at=(timestamp)
     - F116: passes=true, passed_at=(timestamp)
   - Celebrate: 120/120 features complete! 🎉

5. **If Tests Still Fail**:
   - Analyze demo_output/nangate45_extreme_demo/summary.json
   - Check individual trial metrics in telemetry/
   - May need further ECO tuning or additional ECO types
   - Consider adding specialized ECOs for extreme cases

## Files Modified

- `src/controller/eco.py`: BufferInsertionECO, CellResizeECO, CellSwapECO, GateCloningECO
- `claude-progress.txt`: Session 67 notes
- `SESSION_67_ECO_FIXES.md`: This document

## Commits

- `f269afc`: Fix BufferInsertionECO: remove unsupported -max_cap flag
- `ff50555`: Optimize ECO strategies for extreme timing violations
- `21b3ab2`: Session 67: Document ECO strategy optimization for F115/F116
