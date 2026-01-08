import json

with open("feature_list.json") as f:
    features = json.load(f)

# Find and update the comparative timing path analysis feature
for feature in features:
    if "comparative timing path analysis" in feature.get("description", "").lower():
        print(f"Found feature: {feature['description']}")
        print(f"Current status: {feature['passes']}")
        feature['passes'] = True
        print(f"Updated status: {feature['passes']}")
        break

# Save updated list
with open("feature_list.json", "w") as f:
    json.dump(features, f, indent=2)

print("\nfeature_list.json updated successfully!")
