#!/usr/bin/env python3
"""Check if F115/F116 targets are met from demo results."""

import json
from pathlib import Path

def check_results():
    """Check demo results and determine if F115/F116 pass."""

    summary_path = Path("demo_output/nangate45_extreme_demo/summary.json")

    if not summary_path.exists():
        print("❌ summary.json not found - demo may not have completed")
        return False, False

    with open(summary_path) as f:
        summary = json.load(f)

    # Extract metrics
    initial_wns = summary["initial_state"]["wns_ps"]
    final_wns = summary["final_state"]["wns_ps"]
    initial_hot_ratio = summary["initial_state"]["hot_ratio"]
    final_hot_ratio = summary["final_state"]["hot_ratio"]

    # Calculate improvements
    wns_improvement_pct = summary["improvements"]["wns_improvement_percent"]
    hot_ratio_reduction_pct = summary["improvements"]["hot_ratio_improvement_percent"]

    # Check targets
    f115_target = 50.0  # >50% WNS improvement
    f116_target = 60.0  # >60% hot_ratio reduction

    f115_passes = wns_improvement_pct > f115_target
    f116_passes = hot_ratio_reduction_pct > f116_target

    # Print results
    print("="*60)
    print("F115/F116 Results Analysis")
    print("="*60)
    print()
    print("Initial State:")
    print(f"  WNS:       {initial_wns:6d} ps")
    print(f"  hot_ratio: {initial_hot_ratio:6.4f}")
    print()
    print("Final State:")
    print(f"  WNS:       {final_wns:6d} ps")
    print(f"  hot_ratio: {final_hot_ratio:6.4f}")
    print()
    print("Improvements:")
    print(f"  WNS improvement:      {wns_improvement_pct:6.2f}% (target: >{f115_target}%)")
    print(f"  hot_ratio reduction:  {hot_ratio_reduction_pct:6.2f}% (target: >{f116_target}%)")
    print()
    print("F115 (WNS >50% improvement):")
    print(f"  {'✓ PASS' if f115_passes else '✗ FAIL'} - {wns_improvement_pct:.2f}% improvement")
    print()
    print("F116 (hot_ratio >60% reduction):")
    print(f"  {'✓ PASS' if f116_passes else '✗ FAIL'} - {hot_ratio_reduction_pct:.2f}% reduction")
    print()
    print("="*60)
    print(f"Overall: {'✓ BOTH PASS - 120/120 features!' if (f115_passes and f116_passes) else '✗ Targets not met'}")
    print("="*60)

    return f115_passes, f116_passes

if __name__ == "__main__":
    check_results()
