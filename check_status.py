#!/usr/bin/env python3
import json

with open('feature_list.json') as f:
    features = json.load(f)

total = len(features)
passing = sum(1 for f in features if f['passes'])
failing = sum(1 for f in features if not f['passes'])
needs_reverif = sum(1 for f in features if f.get('needs_reverification', False))

print(f"Features: {passing}/{total} passing")
print(f"Failing: {failing}")
print(f"Needs reverification: {needs_reverif}")
print(f"Completion: {100*passing//total}%")
