# Session 409 Quick Reference

## Current Status
- **278/280 features passing (99.3%)**
- **2 features remaining**
- **All dependencies satisfied**

## Completed This Session
1. ✅ F265: Warm-start priors inspection CLI (15 tests)
2. ✅ F225: Conditional critical path overlay (12 tests)

## Remaining Features

### F228: Hotspot Bounding Boxes on Heatmap
- **Priority:** Low
- **Depends on:** F226 ✅ (passing)
- **Steps:**
  1. Run congestion diagnosis with bbox coordinates
  2. Generate annotated heatmap
  3. Verify bounding boxes drawn around hotspot regions
  4. Verify bbox coordinates match diagnosis
  5. Verify boxes are visually distinct

### F235: Stage Progression Chart Quality
- **Priority:** Low
- **Depends on:** F234 ✅ (passing)
- **Steps:**
  1. Generate stage progression chart
  2. Verify layout is clear and not cluttered
  3. Verify metrics are easily readable
  4. Verify stage boundaries are visually distinct
  5. Verify chart is publication-quality

## Key Files

### For F228:
- `src/visualization/heatmap_renderer.py` - Main renderer
- `src/analysis/diagnosis.py` - Diagnosis with bboxes
- `tests/test_f226_*.py` - Related test (F226)

### For F235:
- `src/visualization/stage_progression.py` - Chart generator
- `tests/test_f234_*.py` - Related test (F234)

## Commands

```bash
# Run specific feature tests
uv run pytest tests/test_f228_*.py -v
uv run pytest tests/test_f235_*.py -v

# Check status
python3 -c "
import json
with open('feature_list.json') as f:
    features = json.load(f)
passing = sum(1 for f in features if f['passes'])
print(f'{passing}/{len(features)} passing ({passing/len(features)*100:.1f}%)')
"

# Mark feature as passing
python3 << 'EOF'
import json
from datetime import datetime, UTC
with open('feature_list.json') as f:
    features = json.load(f)
for f in features:
    if f['id'] == 'F228':  # or F235
        f['passes'] = True
        f['passed_at'] = datetime.now(UTC).isoformat()
        break
with open('feature_list.json', 'w') as f:
    json.dump(features, f, indent=2)
EOF
```

## Testing Strategy

1. **Read existing implementation** for both F228 and F235
2. **Check related tests** (F226, F234) to understand patterns
3. **Create comprehensive tests** covering all steps
4. **Run tests iteratively** as implementation progresses
5. **Verify no regressions** on related features

## Session Goals

- Complete F228 and F235
- Achieve 100% feature completion (280/280)
- Maintain zero regressions
- Create final project completion report

## Estimated Effort

- F228: 1-1.5 hours (8-12 tests)
- F235: 0.5-1 hour (6-10 tests)
- **Total: 1.5-2.5 hours for 100% completion**
