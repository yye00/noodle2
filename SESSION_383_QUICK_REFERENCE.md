# Session 383 Quick Reference

## What Was Accomplished

✅ **F279 Complete**: Create real ASAP7 design snapshot with ASAP7-specific workarounds
- 24 tests passing
- Real ASAP7 GCD snapshot created at `studies/asap7_base/gcd_placed.odb`
- ASAP7 workarounds applied (low utilization, routing layers, site, pins)
- Overall progress: 232/280 (82.9%)

## Current State

### Progress
- **Total Features**: 280
- **Passing**: 232 (82.9%)
- **Failing**: 48 (17.1%)
- **Needs Reverification**: 0
- **Deprecated**: 0

### Snapshots Available
1. ✅ Nangate45: `studies/nangate45_base/gcd_placed.odb` (680 KB)
2. ✅ ASAP7: `studies/asap7_base/gcd_placed.odb` (826 KB)
3. ⏳ Sky130: Not yet created (F280)

## Next Priority Features

1. **F280 [critical]**: Create real Sky130 design snapshot using sky130hd platform
   - Depends on: F278 ✅
   - Next natural step after F279
   - Completes multi-PDK snapshot infrastructure

2. **F241 [high]**: Compare two studies and generate comparison report
   - Unblocks: F242, F243, F244, F245
   - Study comparison infrastructure

3. **F246 [high]**: Support diverse_top_n survivor selection
   - Unblocks: F247
   - Survivor selection enhancement

## Test Commands

```bash
# Run all tests (excluding Ray-dependent ones)
uv run pytest tests/ -v -k "not asap7_e2e and not sky130_e2e and not nangate45_e2e and not distributed_execution"

# Run F279 tests specifically
uv run pytest tests/test_f279_asap7_snapshot.py -v

# Create ASAP7 snapshot manually
uv run python create_asap7_snapshot.py

# Check feature status
jq '.[] | select(.passes == false and (.deprecated | not)) | .id' feature_list.json | head -10
```

## Files to Review

- `tests/test_f279_asap7_snapshot.py` - ASAP7 snapshot tests
- `create_asap7_snapshot.py` - Script to create ASAP7 snapshot
- `src/infrastructure/orfs_flow.py` - ORFS flow utilities
- `SESSION_383_SUMMARY.md` - Full session report

## Infrastructure Ready

- ✅ Docker container: `openroad/orfs:latest`
- ✅ ORFS repository cloned
- ✅ Nangate45 snapshot ready
- ✅ ASAP7 snapshot ready
- ✅ Real execution infrastructure validated
- ⏳ Sky130 snapshot (next)

## Key Learnings

1. **ASAP7 Workarounds**: Low utilization (0.35) is critical for ASAP7 routing
2. **Liberty Libraries**: ODB snapshots don't include libs - "No liberty libraries found" is expected
3. **Pattern**: F274 (Nangate45) → F279 (ASAP7) → F280 (Sky130) follow same pattern
4. **Test Structure**: 5 verification steps + integration tests work well

## Next Session Recommendation

Start with **F280** (Sky130 snapshot) to complete the multi-PDK infrastructure trio:
- Follow same pattern as F274 and F279
- Use sky130hd platform (not sky130hs)
- Check for Sky130-specific workarounds in app_spec.txt
- Create `studies/sky130_base/` directory
- Write comprehensive tests following F279 pattern
