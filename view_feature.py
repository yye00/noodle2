import json
import sys

fid = sys.argv[1] if len(sys.argv) > 1 else "F278"

with open('feature_list.json', 'r') as f:
    features = json.load(f)

feature = next((f for f in features if f['id'] == fid), None)
if feature:
    print(f"Feature: {feature['id']}")
    print(f"Priority: {feature.get('priority', 'medium')}")
    print(f"Status: {'✓ PASSING' if feature['passes'] else '✗ FAILING'}")
    print(f"Category: {feature.get('category', 'N/A')}")
    print(f"Dependencies: {', '.join(feature.get('depends_on', [])) or 'None'}")
    print(f"\nDescription:")
    print(f"  {feature['description']}")
    print(f"\nVerification Steps:")
    for i, step in enumerate(feature['steps'], 1):
        print(f"  {i}. {step}")
else:
    print(f"Feature {fid} not found")
