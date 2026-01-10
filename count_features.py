#!/usr/bin/env python3
import json

with open("feature_list.json") as f:
    data = json.load(f)

total = len(data)
passing = sum(1 for f in data if f.get("passes", False))
failing = sum(1 for f in data if not f.get("passes", False))
needs_reverification = sum(1 for f in data if f.get("needs_reverification", False))

print(f"Total features: {total}")
print(f"Passing: {passing}")
print(f"Failing: {failing}")
print(f"Needs reverification: {needs_reverification}")
