#!/usr/bin/env python3
"""Update F250 feature to mark as passing."""

import json
from datetime import datetime

with open("feature_list.json", "r") as f:
    features = json.load(f)

for feature in features:
    if feature["id"] == "F250":
        feature["passes"] = True
        feature["passed_at"] = datetime.now().isoformat() + "Z"
        break

with open("feature_list.json", "w") as f:
    json.dump(features, f, indent=2)

print("✓ F250 marked as passing")
