#!/usr/bin/env python3
"""Update F241 status to passing."""

import json
from datetime import datetime, timezone

# Read feature list
with open("feature_list.json", "r") as f:
    features = json.load(f)

# Find and update F241
for feature in features:
    if feature["id"] == "F241":
        feature["passes"] = True
        feature["passed_at"] = datetime.now(timezone.utc).isoformat()
        print(f"Updated {feature['id']}: {feature['description']}")
        print(f"  passes: {feature['passes']}")
        print(f"  passed_at: {feature['passed_at']}")
        break

# Write back
with open("feature_list.json", "w") as f:
    json.dump(features, f, indent=2)

print("\nFeature list updated!")
