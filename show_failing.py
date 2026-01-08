import json

with open("feature_list.json") as f:
    features = json.load(f)

failing = [f for f in features if not f.get("passes", False)]
print(f"Total failing: {len(failing)}\n")

for i, feature in enumerate(failing[:50], 1):
    category = feature.get("category", "unknown")
    description = feature.get("description", "No description")
    print(f"{i}. [{category}] {description}")
