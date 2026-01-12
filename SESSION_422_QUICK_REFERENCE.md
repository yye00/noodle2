# Session 422 Quick Reference

## What Was Fixed

**Test failure:** `test_study_config.py::test_stage_config_validation`
**Issue:** Expected `TrialBudgetError`, got `ValueError`

## The Fix

Moved validation from `StageConfig.__post_init__()` to `StudyConfig.validate()`:

```python
# Before (in StageConfig.__post_init__)
if self.trial_budget <= 0:
    raise ValueError("trial_budget must be positive")  # ❌ Generic

# After (in StudyConfig.validate)
if stage.trial_budget <= 0:
    raise TrialBudgetError(idx)  # ✅ Custom exception with stage index
```

## Result

- ✅ 6/6 study config tests pass
- ✅ 263/264 stage/study tests pass
- ✅ Proper error codes (N2-E-004, N2-E-005, N2-E-006)
- ✅ Better error messages with stage indices

## Commits

- `07f296c` - Fix validation
- `9d1ee16` - Update progress tracker
