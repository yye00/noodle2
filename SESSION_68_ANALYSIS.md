
## Session 68 - Critical Finding: ECO Strategies Still Not Working

### Demo Run Status (25 minutes elapsed)
- **Trials completed**: 60+
- **Best WNS**: -1848ps (0% improvement)
- **Best hot_ratio**: 0.526 (0% improvement)
- **Conclusion**: ECOs are NOT improving the design

### Root Cause Analysis

Examined trial 7 stdout logs:
1. **Initial baseline**: WNS = -1848ps (from snapshot)
2. **After `repair_design`**: WNS = -2288ps (440ps WORSE!)
3. **After `repair_timing` pass 1**: WNS = -1952ps (recovered 336ps)
4. **After `repair_timing` pass 2**: WNS = -1927ps (recovered 25ps more)
5. **Final**: WNS = -1926ps (78ps worse than initial!)

### Problem Identified

The Session 67 "gentle constraints" strategy is:
- **repair_design** with `-max_wire_length 120 -max_utilization 0.80`
- **repair_timing** with `-setup_margin 0.1` then `-setup_margin 0.0`

**The issue**: `repair_design` makes timing WORSE (adds delay), then `repair_timing` 
tries to fix it but can't fully recover. Net result: slight degradation or no change.

### Why This Happens

For an EXTREME design (WNS -1848ps, missing timing by 5.3x):
- `repair_design` focuses on DRV violations (slew, cap, fanout)
- Fixing DRV often adds buffers/increases delay
- `repair_timing` then tries to fix timing, but is constrained by the new topology
- In extreme cases, you can't have both good DRV and good timing

### The Fundamental Problem

**Noodle 2's ECO approach may be fundamentally flawed for extreme violations:**
1. We're trying to fix a design that's 5.3x over budget with local ECOs
2. Local ECOs (buffer insertion, cell resize) can't fix systematic problems
3. The design needs GLOBAL changes (floorplanning, synthesis constraints, etc.)

### What Session 67 Fixed vs. What's Still Broken

**Session 67 fixed**:
- ✅ Removed unsupported `-max_cap` flag (prevented crashes)
- ✅ Used gentle constraints (prevents crashes from over-aggressive repair)

**What's still broken**:
- ❌ ECOs don't improve timing (stay same or get worse)
- ❌ The ECO strategy itself doesn't work for extreme violations
- ❌ F115/F116 will FAIL unless we find a different approach

### Recommendations

**Option 1: Accept that F115/F116 are not achievable with current approach**
- Mark F115/F116 as failing
- Document that extreme violations require global fixes, not local ECOs
- Focus on demonstrating the framework works for moderate violations

**Option 2: Change the test to use a less extreme design**
- Use a design with WNS ~ -200ps instead of -1848ps
- This would test if ECOs can achieve 50% improvement on realistic violations
- More representative of actual use cases

**Option 3: Implement a different ECO strategy**
- Try running `repair_timing` ONLY (skip `repair_design`)
- Use negative setup_margin to be more aggressive
- Accept DRV violations to prioritize timing

**Option 4: Change the initial design to be fixable**
- Instead of using the "extreme" ibex snapshot
- Create a "moderate" ibex snapshot with ~300ps violations
- Demonstrate that ECOs can fix moderate problems

### Immediate Decision Needed

The demo is running and will take ~2 hours. Options:
1. **Kill it now** - we know the outcome (0% improvement)
2. **Let it finish** - maybe later stages/ECOs do better (unlikely)
3. **Let it run in background** - continue with other work

I recommend: **Kill the demo, document findings, propose next steps**

### Time Investment Analysis

- Session 67: ~2 hours (ECO strategy optimization)
- Session 68: 25 minutes so far
- If we wait 2 more hours: Total 4+ hours for approach that doesn't work
- Better to pivot now than invest more time

