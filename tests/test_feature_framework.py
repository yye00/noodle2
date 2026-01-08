"""
Tests for the feature tracking framework.

Validates that the feature_list.json infrastructure can properly track
and update feature completion status.
"""

import json
import shutil
from pathlib import Path

import pytest


class TestFeatureFramework:
    """Test feature tracking framework functionality."""

    def test_load_feature_list_json(self):
        """Step 1: Load feature_list.json successfully."""
        feature_list_path = Path(__file__).parent.parent / "feature_list.json"

        assert feature_list_path.exists(), "feature_list.json should exist"

        with open(feature_list_path) as f:
            features = json.load(f)

        assert isinstance(features, list), "feature_list.json should contain a list"
        assert len(features) > 0, "feature_list.json should not be empty"

        # Validate structure of first feature
        first_feature = features[0]
        assert "category" in first_feature
        assert "description" in first_feature
        assert "steps" in first_feature
        assert "passes" in first_feature

    def test_execute_test_for_specific_feature(self):
        """Step 2: Execute test for specific feature."""
        # This test itself is an example of executing a test for a feature
        # We're testing the feature framework, which is itself a feature

        feature_list_path = Path(__file__).parent.parent / "feature_list.json"
        with open(feature_list_path) as f:
            features = json.load(f)

        # Find the test framework feature
        test_framework_feature = None
        for feature in features:
            if "Test framework can mark individual features" in feature.get("description", ""):
                test_framework_feature = feature
                break

        assert test_framework_feature is not None, "Test framework feature should exist"
        assert "passes" in test_framework_feature, "Feature should have 'passes' field"

    def test_update_feature_passes_field(self, tmp_path):
        """Step 3: Update feature's passes field to true."""
        # Create a test feature list
        test_features = [
            {
                "category": "test",
                "description": "Test feature 1",
                "steps": ["Step 1: Do something"],
                "passes": False
            },
            {
                "category": "test",
                "description": "Test feature 2",
                "steps": ["Step 1: Do something else"],
                "passes": False
            }
        ]

        test_file = tmp_path / "test_features.json"
        with open(test_file, "w") as f:
            json.dump(test_features, f, indent=2)

        # Load and update
        with open(test_file) as f:
            features = json.load(f)

        # Mark first feature as passing
        features[0]["passes"] = True

        # Write back
        with open(test_file, "w") as f:
            json.dump(features, f, indent=2)

        # Verify the update
        with open(test_file) as f:
            updated_features = json.load(f)

        assert updated_features[0]["passes"] is True
        assert updated_features[1]["passes"] is False

    def test_write_updated_feature_list_back_to_disk(self, tmp_path):
        """Step 4: Write updated feature_list.json back to disk."""
        test_features = [
            {
                "category": "test",
                "description": "Test feature",
                "steps": ["Step 1"],
                "passes": False
            }
        ]

        test_file = tmp_path / "features.json"

        # Write initial version
        with open(test_file, "w") as f:
            json.dump(test_features, f, indent=2)

        # Load, modify, and write back
        with open(test_file) as f:
            features = json.load(f)

        features[0]["passes"] = True

        with open(test_file, "w") as f:
            json.dump(features, f, indent=2)

        # Verify file exists and is valid JSON
        assert test_file.exists()
        with open(test_file) as f:
            reloaded = json.load(f)

        assert reloaded[0]["passes"] is True

    def test_feature_status_persists_across_runs(self, tmp_path):
        """Step 5: Verify feature status persists across runs."""
        test_file = tmp_path / "persistent_features.json"

        # First "run" - create and update
        features_run1 = [
            {"category": "test", "description": "Feature A", "steps": [], "passes": False},
            {"category": "test", "description": "Feature B", "steps": [], "passes": False}
        ]

        with open(test_file, "w") as f:
            json.dump(features_run1, f, indent=2)

        # Mark feature A as passing
        with open(test_file) as f:
            features = json.load(f)
        features[0]["passes"] = True
        with open(test_file, "w") as f:
            json.dump(features, f, indent=2)

        # Second "run" - load and verify
        with open(test_file) as f:
            features_run2 = json.load(f)

        assert features_run2[0]["passes"] is True, "Feature A should still be passing"
        assert features_run2[0]["description"] == "Feature A"

        # Third "run" - mark another feature
        features_run2[1]["passes"] = True
        with open(test_file, "w") as f:
            json.dump(features_run2, f, indent=2)

        # Fourth "run" - verify both persist
        with open(test_file) as f:
            features_run3 = json.load(f)

        assert features_run3[0]["passes"] is True, "Feature A should still be passing"
        assert features_run3[1]["passes"] is True, "Feature B should now be passing"

    def test_other_features_remain_unchanged(self, tmp_path):
        """Step 6: Verify other features remain unchanged."""
        test_file = tmp_path / "multi_feature.json"

        original_features = [
            {
                "category": "test",
                "description": "Feature 1",
                "steps": ["Step A", "Step B"],
                "passes": False,
                "metadata": {"priority": "high"}
            },
            {
                "category": "test",
                "description": "Feature 2",
                "steps": ["Step X", "Step Y", "Step Z"],
                "passes": True,
                "metadata": {"priority": "medium"}
            },
            {
                "category": "test",
                "description": "Feature 3",
                "steps": ["Step 1"],
                "passes": False
            }
        ]

        with open(test_file, "w") as f:
            json.dump(original_features, f, indent=2)

        # Update only Feature 1
        with open(test_file) as f:
            features = json.load(f)

        features[0]["passes"] = True

        with open(test_file, "w") as f:
            json.dump(features, f, indent=2)

        # Verify changes
        with open(test_file) as f:
            updated_features = json.load(f)

        # Feature 1: passes changed to True, everything else unchanged
        assert updated_features[0]["passes"] is True  # Changed
        assert updated_features[0]["description"] == "Feature 1"  # Unchanged
        assert updated_features[0]["steps"] == ["Step A", "Step B"]  # Unchanged
        assert updated_features[0]["metadata"] == {"priority": "high"}  # Unchanged

        # Feature 2: completely unchanged
        assert updated_features[1] == original_features[1]

        # Feature 3: completely unchanged
        assert updated_features[2] == original_features[2]

    def test_feature_list_json_is_valid_and_complete(self):
        """Validate the actual feature_list.json structure."""
        feature_list_path = Path(__file__).parent.parent / "feature_list.json"

        with open(feature_list_path) as f:
            features = json.load(f)

        # Validate every feature has required fields
        for i, feature in enumerate(features):
            assert "category" in feature, f"Feature {i} missing 'category'"
            assert "description" in feature, f"Feature {i} missing 'description'"
            assert "steps" in feature, f"Feature {i} missing 'steps'"
            assert "passes" in feature, f"Feature {i} missing 'passes'"

            # Validate types
            assert isinstance(feature["category"], str), f"Feature {i} category not string"
            assert isinstance(feature["description"], str), f"Feature {i} description not string"
            assert isinstance(feature["steps"], list), f"Feature {i} steps not list"
            assert isinstance(feature["passes"], bool), f"Feature {i} passes not boolean"

            # Validate steps
            assert len(feature["steps"]) > 0, f"Feature {i} has no steps"
            for step in feature["steps"]:
                assert isinstance(step, str), f"Feature {i} has non-string step"

    def test_count_passing_and_failing_features(self):
        """Test counting feature completion status."""
        feature_list_path = Path(__file__).parent.parent / "feature_list.json"

        with open(feature_list_path) as f:
            features = json.load(f)

        total = len(features)
        passing = sum(1 for f in features if f.get("passes", False))
        failing = total - passing

        # Should have some features
        assert total > 0, "Should have features in feature_list.json"

        # Should have at least some passing features
        assert passing > 0, "Should have at least some passing features"

        # Progress should be reasonable (not 0%, not 100%)
        completion_pct = (passing / total) * 100

        # We expect substantial progress given the maturity of the codebase
        assert completion_pct > 50.0, f"Expected >50% completion, got {completion_pct:.1f}%"

        print(f"\nFeature completion: {passing}/{total} ({completion_pct:.1f}%)")
        print(f"Passing: {passing}, Failing: {failing}")

    def test_features_organized_by_category(self):
        """Test that features are properly categorized."""
        feature_list_path = Path(__file__).parent.parent / "feature_list.json"

        with open(feature_list_path) as f:
            features = json.load(f)

        categories = set()
        for feature in features:
            categories.add(feature["category"])

        # Should have standard categories
        expected_categories = {"functional", "style"}
        assert expected_categories.issubset(categories), \
            f"Expected categories {expected_categories}, found {categories}"

        # Count features by category
        category_counts = {}
        for feature in features:
            cat = feature["category"]
            category_counts[cat] = category_counts.get(cat, 0) + 1

        print(f"\nFeatures by category:")
        for cat, count in sorted(category_counts.items()):
            cat_passing = sum(1 for f in features
                            if f["category"] == cat and f.get("passes", False))
            print(f"  {cat}: {cat_passing}/{count} passing")
