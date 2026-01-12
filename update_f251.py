#!/usr/bin/env python3
"""Update F251 to passing status."""

import json
from datetime import datetime, timezone

# Load feature list
with open("feature_list.json", "r") as f:
    features = json.load(f)

# Find and update F251
for feature in features:
    if feature["id"] == "F251":
        feature["passes"] = True
        feature["passed_at"] = datetime.now(timezone.utc).isoformat()
        break

# Save updated feature list
with open("feature_list.json", "w") as f:
    json.dump(features, f, indent=2)

print("✓ F251 marked as passing")
