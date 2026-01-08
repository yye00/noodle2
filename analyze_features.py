#!/usr/bin/env python3
import json

with open("feature_list.json") as f:
    features = json.load(f)

failing = [f for f in features if not f.get("passes", False)]
print(f"Total features: {len(features)}")
print(f"Passing: {len(features) - len(failing)}")
print(f"Failing: {len(failing)}")
print("\nFirst 20 failing features:\n")

for i, feature in enumerate(failing[:20], 1):
    category = feature.get("category", "unknown")
    description = feature.get("description", "No description")
    print(f"{i}. [{category}] {description}")
