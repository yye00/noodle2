import json
from datetime import datetime, timezone

with open('feature_list.json', 'r') as f:
    features = json.load(f)

# Find F278
for feature in features:
    if feature['id'] == 'F278':
        feature['passes'] = True
        feature['passed_at'] = datetime.now(timezone.utc).isoformat()
        print(f"✓ Updated {feature['id']}: {feature['description']}")
        break

# Save updated feature list
with open('feature_list.json', 'w') as f:
    json.dump(features, f, indent=2)

print("\n✓ feature_list.json updated successfully")
