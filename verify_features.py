#!/usr/bin/env python3
"""Verify feature_list.json meets requirements."""

import json

with open('feature_list.json', 'r') as f:
    features = json.load(f)

total = len(features)
functional = len([f for f in features if f['category'] == 'functional'])
style = len([f for f in features if f['category'] == 'style'])
long_tests = len([f for f in features if len(f['steps']) >= 10])
passing = len([f for f in features if f['passes'] == True])

print(f"Feature List Verification")
print(f"=" * 50)
print(f"Total features: {total}")
print(f"  Functional: {functional}")
print(f"  Style: {style}")
print(f"  With 10+ steps: {long_tests}")
print(f"  Currently passing: {passing}")
print(f"")
print(f"Requirements:")
print(f"  ✓ Minimum 200 features: {'PASS' if total >= 200 else 'FAIL'}")
print(f"  ✓ At least 25 with 10+ steps: {'PASS' if long_tests >= 25 else 'FAIL'}")
print(f"  ✓ All start with passes=false: {'PASS' if passing == 0 else 'FAIL'}")
print(f"")
print(f"Status: {'ALL REQUIREMENTS MET' if total >= 200 and long_tests >= 25 and passing == 0 else 'INCOMPLETE'}")
