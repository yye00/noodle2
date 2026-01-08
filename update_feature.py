import json

with open("feature_list.json") as f:
    features = json.load(f)

# Find and update the README feature
for feature in features:
    if "README provides clear setup instructions" in feature.get("description", ""):
        print(f"Found feature: {feature['description']}")
        print(f"Current status: {feature['passes']}")
        feature['passes'] = True
        print(f"Updated status: {feature['passes']}")
        break

# Save updated list
with open("feature_list.json", "w") as f:
    json.dump(features, f, indent=2)

print("\nfeature_list.json updated successfully!")
