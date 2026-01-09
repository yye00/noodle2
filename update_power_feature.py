import json

with open("feature_list.json") as f:
    features = json.load(f)

# Find and update the power analysis feature
for i, feature in enumerate(features):
    if "power analysis integration" in feature.get("description", "").lower():
        print(f"Found feature at index {i}: {feature['description']}")
        print(f"Current status: {feature['passes']}")
        feature['passes'] = True
        print(f"Updated status: {feature['passes']}")
        break

# Save updated list
with open("feature_list.json", "w") as f:
    json.dump(features, f, indent=2)

# Count passing features
passing = sum(1 for f in features if f.get("passes", False))
total = len(features)
print(f"\nfeature_list.json updated successfully!")
print(f"New status: {passing}/{total} features passing ({100*passing/total:.1f}%)")
