"""Test Study artifact directory structure organization and self-documentation.

This test suite validates that Study artifact directories are:
1. Well-organized with clear naming conventions
2. Self-documenting with README
3. Easy to navigate

This addresses Feature: "Study artifact directory structure is well-organized and self-documenting"
"""

import pytest
from pathlib import Path
from src.controller.artifact_structure import (
    ArtifactDirectoryLayout,
    create_study_artifact_structure,
    generate_readme_content,
    write_readme,
    get_key_files_summary,
    is_well_organized,
)


class TestArtifactDirectoryLayout:
    """Test the standard directory layout definition."""

    def test_layout_defines_standard_directories(self, tmp_path):
        """Layout should define all standard directories."""
        layout = ArtifactDirectoryLayout(study_root=tmp_path)

        # Verify all key directories are defined
        assert layout.summary_dir == tmp_path / "summaries"
        assert layout.cases_dir == tmp_path / "cases"
        assert layout.stages_dir == tmp_path / "stages"
        assert layout.telemetry_dir == tmp_path / "telemetry"
        assert layout.reports_dir == tmp_path / "reports"
        assert layout.checkpoints_dir == tmp_path / "checkpoints"
        assert layout.logs_dir == tmp_path / "logs"

    def test_layout_provides_case_navigation(self, tmp_path):
        """Layout should provide methods to navigate to case directories."""
        layout = ArtifactDirectoryLayout(study_root=tmp_path)

        case_dir = layout.case_dir("nangate45_0_1")
        assert case_dir == tmp_path / "cases" / "nangate45_0_1"

        stage_dir = layout.case_stage_dir("nangate45_0_1", 2)
        assert stage_dir == tmp_path / "cases" / "nangate45_0_1" / "stage_2"

        trial_dir = layout.trial_dir("nangate45_0_1", 2, 5)
        assert trial_dir == tmp_path / "cases" / "nangate45_0_1" / "stage_2" / "trial_5"

    def test_layout_provides_key_file_paths(self, tmp_path):
        """Layout should provide paths to key files."""
        layout = ArtifactDirectoryLayout(study_root=tmp_path)

        assert layout.config_file == tmp_path / "study_config.yaml"
        assert layout.readme_file == tmp_path / "README.txt"
        assert layout.stage_summary_file(0) == tmp_path / "stages" / "stage_0_summary.json"

    def test_create_structure_creates_directories(self, tmp_path):
        """Create structure should create all standard directories."""
        layout = ArtifactDirectoryLayout(study_root=tmp_path / "my_study")
        layout.create_structure()

        # Verify all directories exist
        assert layout.study_root.exists()
        assert layout.summary_dir.exists()
        assert layout.cases_dir.exists()
        assert layout.stages_dir.exists()
        assert layout.telemetry_dir.exists()
        assert layout.reports_dir.exists()
        assert layout.checkpoints_dir.exists()
        assert layout.logs_dir.exists()

    def test_create_structure_is_idempotent(self, tmp_path):
        """Creating structure multiple times should be safe."""
        layout = ArtifactDirectoryLayout(study_root=tmp_path / "my_study")
        layout.create_structure()
        layout.create_structure()  # Should not fail

        # Verify structure still exists
        assert layout.summary_dir.exists()


class TestReadmeGeneration:
    """Test README generation and content."""

    def test_readme_includes_study_name(self):
        """README should prominently display Study name."""
        readme = generate_readme_content("nangate45_demo")
        assert "nangate45_demo" in readme

    def test_readme_explains_directory_structure(self):
        """README should explain each directory's purpose."""
        readme = generate_readme_content("test_study")

        # Check for directory descriptions
        assert "summaries/" in readme
        assert "cases/" in readme
        assert "stages/" in readme
        assert "telemetry/" in readme
        assert "reports/" in readme
        assert "checkpoints/" in readme
        assert "logs/" in readme

    def test_readme_includes_quick_reference(self):
        """README should include quick reference for common tasks."""
        readme = generate_readme_content("test_study")

        # Check for key file locations
        assert "study_summary.json" in readme
        assert "winner_selection.json" in readme
        assert "eco_leaderboard.json" in readme

    def test_readme_explains_naming_conventions(self):
        """README should explain file naming conventions."""
        readme = generate_readme_content("test_study")

        # Check for naming convention explanations
        assert "nangate45_0_5" in readme or "case" in readme.lower()
        assert "stage_0" in readme or "stage" in readme.lower()
        assert "trial_3" in readme or "trial" in readme.lower()

    def test_readme_provides_navigation_tips(self):
        """README should guide operators to find information."""
        readme = generate_readme_content("test_study")

        # Check for navigation guidance
        assert "summaries/" in readme
        assert "cases/" in readme

    def test_write_readme_creates_file(self, tmp_path):
        """Writing README should create the file."""
        layout = ArtifactDirectoryLayout(study_root=tmp_path)
        layout.create_structure()

        write_readme(layout, "test_study")

        assert layout.readme_file.exists()
        content = layout.readme_file.read_text()
        assert "test_study" in content


class TestCompleteStudyStructure:
    """Test complete Study artifact structure creation."""

    def test_create_complete_structure(self, tmp_path):
        """Should create complete, organized structure in one call."""
        study_root = tmp_path / "nangate45_demo"
        layout = create_study_artifact_structure(study_root, "nangate45_demo")

        # Verify all directories exist
        assert layout.summary_dir.exists()
        assert layout.cases_dir.exists()
        assert layout.stages_dir.exists()
        assert layout.telemetry_dir.exists()
        assert layout.reports_dir.exists()
        assert layout.checkpoints_dir.exists()
        assert layout.logs_dir.exists()

        # Verify README exists
        assert layout.readme_file.exists()

    def test_directory_naming_is_clear(self, tmp_path):
        """Directory names should be self-explanatory."""
        layout = create_study_artifact_structure(tmp_path / "test", "test")

        # Names should be descriptive, not cryptic
        assert "summaries" in str(layout.summary_dir)
        assert "cases" in str(layout.cases_dir)
        assert "telemetry" in str(layout.telemetry_dir)

    def test_key_files_are_locatable(self, tmp_path):
        """Key files should be easy to locate."""
        layout = create_study_artifact_structure(tmp_path / "test", "test")
        key_files = get_key_files_summary(layout)

        # Verify all key files are documented
        assert "study_summary" in key_files
        assert "winner_selection" in key_files
        assert "eco_leaderboard" in key_files
        assert "run_legality_report" in key_files
        assert "safety_trace" in key_files
        assert "case_lineage" in key_files
        assert "controller_log" in key_files
        assert "readme" in key_files


class TestStructureValidation:
    """Test validation of directory structure completeness."""

    def test_validate_complete_structure(self, tmp_path):
        """Complete structure should validate successfully."""
        layout = create_study_artifact_structure(tmp_path / "test", "test")
        validation = layout.validate_structure()

        # All directories should exist except config (not created by layout)
        assert validation["study_root"]
        assert validation["summaries"]
        assert validation["cases"]
        assert validation["stages"]
        assert validation["telemetry"]
        assert validation["reports"]
        assert validation["checkpoints"]
        assert validation["logs"]
        assert validation["readme"]

    def test_validate_incomplete_structure(self, tmp_path):
        """Incomplete structure should be detected."""
        layout = ArtifactDirectoryLayout(study_root=tmp_path / "incomplete")
        # Don't create structure
        validation = layout.validate_structure()

        # Should detect missing directories
        assert not validation["study_root"]

    def test_is_well_organized_helper(self, tmp_path):
        """is_well_organized should detect organization quality."""
        study_root = tmp_path / "test"

        # Before creation - not organized
        is_org, missing = is_well_organized(study_root)
        assert not is_org
        assert len(missing) > 0

        # After creation - well organized
        create_study_artifact_structure(study_root, "test")
        is_org, missing = is_well_organized(study_root)
        assert is_org
        assert len(missing) == 0


class TestDirectoryOrganization:
    """Test that directory organization meets usability requirements."""

    def test_hierarchical_organization(self, tmp_path):
        """Directory hierarchy should be logical and shallow."""
        layout = create_study_artifact_structure(tmp_path / "test", "test")

        # Cases should be organized by case name, then stage, then trial
        case_dir = layout.case_dir("nangate45_0_1")
        stage_dir = layout.case_stage_dir("nangate45_0_1", 0)
        trial_dir = layout.trial_dir("nangate45_0_1", 0, 0)

        # Verify depth is reasonable (not too deeply nested)
        assert len(trial_dir.relative_to(layout.study_root).parts) == 4
        # study_root/cases/nangate45_0_1/stage_0/trial_0

    def test_parallel_organization(self, tmp_path):
        """Top-level directories should be parallel, not nested."""
        layout = create_study_artifact_structure(tmp_path / "test", "test")

        # All major directories should be siblings under study_root
        assert layout.summary_dir.parent == layout.study_root
        assert layout.cases_dir.parent == layout.study_root
        assert layout.stages_dir.parent == layout.study_root
        assert layout.telemetry_dir.parent == layout.study_root

    def test_consistent_naming_conventions(self, tmp_path):
        """All directory and file names should follow consistent patterns."""
        layout = create_study_artifact_structure(tmp_path / "test", "test")

        # Stage directories use stage_N pattern
        assert "stage_0" in str(layout.case_stage_dir("case", 0))
        assert "stage_5" in str(layout.case_stage_dir("case", 5))

        # Trial directories use trial_N pattern
        assert "trial_0" in str(layout.trial_dir("case", 0, 0))
        assert "trial_10" in str(layout.trial_dir("case", 0, 10))

        # Stage summaries use consistent naming
        assert "stage_0_summary.json" in str(layout.stage_summary_file(0))


class TestSelfDocumentation:
    """Test that structure is self-documenting."""

    def test_readme_is_created_automatically(self, tmp_path):
        """README should be created automatically with structure."""
        layout = create_study_artifact_structure(tmp_path / "test", "test")
        assert layout.readme_file.exists()

    def test_readme_is_comprehensive(self, tmp_path):
        """README should comprehensively explain structure."""
        layout = create_study_artifact_structure(tmp_path / "test", "test_study")
        readme_content = layout.readme_file.read_text()

        # Should cover all major sections
        assert "Directory Structure" in readme_content
        assert "Key Files Quick Reference" in readme_content
        assert "Navigation Tips" in readme_content
        assert "File Naming Conventions" in readme_content

    def test_readme_uses_plain_text(self, tmp_path):
        """README should be plain text for universal accessibility."""
        layout = create_study_artifact_structure(tmp_path / "test", "test")
        assert layout.readme_file.suffix == ".txt"

    def test_key_files_summary_is_available(self, tmp_path):
        """Key files summary should help locate important files."""
        layout = create_study_artifact_structure(tmp_path / "test", "test")
        summary = get_key_files_summary(layout)

        # Should be a dictionary
        assert isinstance(summary, dict)
        # Should have multiple entries
        assert len(summary) >= 8
        # Each entry should be a file path
        for key, value in summary.items():
            assert isinstance(value, str)
            assert len(value) > 0


class TestEndToEndUsability:
    """Test end-to-end usability of artifact structure."""

    def test_new_operator_can_find_results(self, tmp_path):
        """A new operator should easily find Study results."""
        # Simulate Study execution
        study_root = tmp_path / "nangate45_demo"
        layout = create_study_artifact_structure(study_root, "nangate45_demo")

        # Create some dummy result files
        (layout.summary_dir / "study_summary.json").write_text("{}")
        (layout.summary_dir / "winner_selection.json").write_text("{}")

        # Operator reads README
        readme = layout.readme_file.read_text()

        # Should clearly indicate where to find results
        assert "summaries/" in readme
        assert "study_summary.json" in readme
        assert "winner_selection.json" in readme

    def test_operator_can_navigate_to_specific_trial(self, tmp_path):
        """Operator should be able to navigate to specific trial outputs."""
        layout = create_study_artifact_structure(tmp_path / "test", "test")

        # Given case name, stage, and trial index
        trial_dir = layout.trial_dir("nangate45_0_3", 1, 5)

        # Path should be logical and predictable
        expected = tmp_path / "test" / "cases" / "nangate45_0_3" / "stage_1" / "trial_5"
        assert trial_dir == expected

    def test_operator_can_compare_across_stages(self, tmp_path):
        """Stage summaries should be easy to compare."""
        layout = create_study_artifact_structure(tmp_path / "test", "test")

        # Stage summaries are in one directory with consistent naming
        stage0 = layout.stage_summary_file(0)
        stage1 = layout.stage_summary_file(1)

        assert stage0.parent == stage1.parent
        assert "stage_0" in stage0.name
        assert "stage_1" in stage1.name
