import json

with open('feature_list.json', 'r') as f:
    features = json.load(f)

passing = [f for f in features if f['passes']]
failing = [f for f in features if not f['passes'] and not f.get('deprecated', False)]
needs_rev = [f for f in features if f.get('needs_reverification', False)]
deprecated = [f for f in features if f.get('deprecated', False)]

print("=== FEATURE SUMMARY ===")
print(f"Total: {len(features)}")
print(f"Passing: {len(passing)}")
print(f"Failing: {len(failing)}")
print(f"Needs reverification: {len(needs_rev)}")
print(f"Deprecated: {len(deprecated)}")
print()

# Get passing IDs
passing_ids = {f['id'] for f in passing}

# Find next features (dependencies satisfied)
priority_map = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
ready = []
for f in failing:
    deps = f.get('depends_on', [])
    if all(dep in passing_ids for dep in deps):
        ready.append(f)

ready.sort(key=lambda x: priority_map.get(x.get('priority', 'medium'), 2))

print("=== NEXT FEATURES TO WORK ON (dependencies satisfied) ===")
for f in ready[:10]:
    desc = f['description'][:60]
    priority = f.get('priority', 'medium')
    print(f"{f['id']}: [{priority}] {desc}")
print()

# Check blocked features
blocked = []
for f in failing:
    deps = f.get('depends_on', [])
    if deps and not all(dep in passing_ids for dep in deps):
        missing = [dep for dep in deps if dep not in passing_ids]
        blocked.append((f['id'], missing))

print("=== BLOCKED FEATURES (waiting on dependencies) ===")
for fid, missing in blocked[:5]:
    print(f"{fid}: blocked by {', '.join(missing)}")
