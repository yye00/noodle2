#!/bin/bash
# Quick script to check demo results and calculate if F115/F116 pass

SUMMARY_FILE="demo_output/nangate45_extreme_demo/summary.json"

if [ ! -f "$SUMMARY_FILE" ]; then
    echo "Error: $SUMMARY_FILE not found"
    echo "Demo may still be running or failed"
    exit 1
fi

echo "=== Nangate45 Extreme Demo Results ==="
echo ""

# Extract values using jq
INITIAL_WNS=$(jq -r '.initial_state.wns_ps' "$SUMMARY_FILE")
FINAL_WNS=$(jq -r '.final_state.wns_ps' "$SUMMARY_FILE")
WNS_IMPROVEMENT=$(jq -r '.improvements.wns_improvement_percent' "$SUMMARY_FILE")

INITIAL_HOT=$(jq -r '.initial_state.hot_ratio' "$SUMMARY_FILE")
FINAL_HOT=$(jq -r '.final_state.hot_ratio' "$SUMMARY_FILE")
HOT_REDUCTION=$(jq -r '.improvements.hot_ratio_improvement_percent' "$SUMMARY_FILE")

echo "WNS Results:"
echo "  Initial: ${INITIAL_WNS}ps"
echo "  Final:   ${FINAL_WNS}ps"
echo "  Improvement: ${WNS_IMPROVEMENT}%"
echo ""

echo "Hot Ratio Results:"
echo "  Initial: ${INITIAL_HOT}"
echo "  Final:   ${FINAL_HOT}"
echo "  Reduction: ${HOT_REDUCTION}%"
echo ""

# Check F115 (>50% WNS improvement)
echo "F115 Status (WNS >50% improvement):"
if (( $(echo "$WNS_IMPROVEMENT > 50" | bc -l) )); then
    echo "  ✓ PASSING (${WNS_IMPROVEMENT}% > 50%)"
    F115_PASS=1
else
    echo "  ✗ FAILING (${WNS_IMPROVEMENT}% <= 50%)"
    F115_PASS=0
fi
echo ""

# Check F116 (>60% hot_ratio reduction)
echo "F116 Status (hot_ratio >60% reduction):"
if (( $(echo "$HOT_REDUCTION > 60" | bc -l) )); then
    echo "  ✓ PASSING (${HOT_REDUCTION}% > 60%)"
    F116_PASS=1
else
    echo "  ✗ FAILING (${HOT_REDUCTION}% <= 60%)"
    F116_PASS=0
fi
echo ""

# Overall result
if [ $F115_PASS -eq 1 ] && [ $F116_PASS -eq 1 ]; then
    echo "=== OVERALL: BOTH TESTS PASS ==="
    echo "Session 73 ECO optimization was successful!"
    echo "Next step: Update feature_list.json to mark F115 and F116 as passing"
    exit 0
elif [ $F115_PASS -eq 1 ] || [ $F116_PASS -eq 1 ]; then
    echo "=== OVERALL: PARTIAL SUCCESS ==="
    echo "One test passing, one failing. Improvement shown but not sufficient."
    echo "Next step: Consider additional optimizations (timing-driven placement)"
    exit 1
else
    echo "=== OVERALL: BOTH TESTS FAIL ==="
    echo "Session 73 ECO optimization did not achieve targets."
    echo "Next steps:"
    echo "  1. Analyze what happened vs baseline (9.25% / 0.53%)"
    echo "  2. Consider timing-driven placement ECO"
    echo "  3. Review TIMING_DRIVEN_PLACEMENT_PLAN.md"
    exit 2
fi
