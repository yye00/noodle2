"""
Tests for README.md completeness and quality.

Feature: README provides clear setup instructions and project overview
"""
import re
from pathlib import Path


class TestREADMEExists:
    """Test that README.md exists and is readable."""

    def test_readme_file_exists(self) -> None:
        """Step 1: Open README.md - verify file exists."""
        readme_path = Path("README.md")
        assert readme_path.exists(), "README.md must exist in project root"
        assert readme_path.is_file(), "README.md must be a file"

    def test_readme_is_readable(self) -> None:
        """Step 1: Open README.md - verify file is readable."""
        readme_path = Path("README.md")
        content = readme_path.read_text()
        assert len(content) > 100, "README.md must have substantial content"


class TestREADMEProjectDescription:
    """Test that README contains accurate project description."""

    def test_project_name_in_title(self) -> None:
        """Step 2: Verify project description - check title."""
        content = Path("README.md").read_text()
        assert "Noodle 2" in content, "README must mention project name 'Noodle 2'"
        # Check for title/header
        assert re.search(r"^#\s+Noodle 2", content, re.MULTILINE), \
            "README must have Noodle 2 as main heading"

    def test_executive_summary_present(self) -> None:
        """Step 2: Verify project description - check summary."""
        content = Path("README.md").read_text()
        # Look for executive summary or similar high-level description
        assert any(keyword in content.lower() for keyword in [
            "executive summary", "summary", "overview", "orchestration"
        ]), "README must have project overview/summary section"

    def test_key_concepts_explained(self) -> None:
        """Step 2: Verify project description - check core concepts."""
        content = Path("README.md").read_text()
        # Core concepts that should be mentioned
        core_concepts = ["Study", "Case", "Stage", "ECO"]
        for concept in core_concepts:
            assert concept in content, \
                f"README must explain core concept: {concept}"

    def test_value_proposition_clear(self) -> None:
        """Step 2: Verify project description - check value prop."""
        content = Path("README.md").read_text()
        # Should explain what Noodle 2 does
        keywords = ["safety", "policy", "orchestration", "experimentation"]
        found_count = sum(1 for kw in keywords if kw.lower() in content.lower())
        assert found_count >= 3, \
            "README must clearly explain what Noodle 2 does (safety/policy/orchestration)"


class TestREADMEPrerequisites:
    """Test that README lists all prerequisites."""

    def test_prerequisites_section_exists(self) -> None:
        """Step 3: Verify prerequisites are listed - check section."""
        content = Path("README.md").read_text()
        assert re.search(r"##\s+Prerequisites", content, re.IGNORECASE), \
            "README must have Prerequisites section"

    def test_python_version_specified(self) -> None:
        """Step 3: Verify prerequisites - check Python version."""
        content = Path("README.md").read_text()
        # Should mention Python 3.10 or 3.10+
        assert re.search(r"Python\s+3\.1[0-9]\+?", content), \
            "README must specify Python version requirement (3.10+)"

    def test_docker_requirement_listed(self) -> None:
        """Step 3: Verify prerequisites - check Docker."""
        content = Path("README.md").read_text()
        assert "Docker" in content or "docker" in content, \
            "README must list Docker as prerequisite"

    def test_system_requirements_mentioned(self) -> None:
        """Step 3: Verify prerequisites - check system requirements."""
        content = Path("README.md").read_text()
        # Should mention RAM or system requirements
        has_ram = re.search(r"\d+\s*GB", content)
        assert has_ram, \
            "README should mention system requirements (RAM, etc.)"


class TestREADMESetupInstructions:
    """Test that setup instructions are complete and step-by-step."""

    def test_quick_start_section_exists(self) -> None:
        """Step 4: Verify setup instructions - check section exists."""
        content = Path("README.md").read_text()
        # Look for setup/quick start/installation section
        assert re.search(r"##\s+(Quick Start|Setup|Installation)", content, re.IGNORECASE), \
            "README must have Quick Start or Setup section"

    def test_clone_instructions_present(self) -> None:
        """Step 4: Verify setup instructions - check clone/download."""
        content = Path("README.md").read_text()
        # Should mention cloning or extracting
        assert "clone" in content.lower() or "extract" in content.lower(), \
            "README must explain how to get the code"

    def test_init_script_instructions(self) -> None:
        """Step 4: Verify setup instructions - check init.sh."""
        content = Path("README.md").read_text()
        # Should mention init.sh
        assert "init.sh" in content, \
            "README must mention init.sh setup script"
        # Should show how to run it
        assert "./init.sh" in content or "bash init.sh" in content, \
            "README must show command to run init.sh"

    def test_environment_activation_explained(self) -> None:
        """Step 4: Verify setup instructions - check environment activation."""
        content = Path("README.md").read_text()
        # Should explain how to activate virtualenv
        assert "source" in content and "activate" in content, \
            "README must explain how to activate virtual environment"

    def test_ray_dashboard_access_explained(self) -> None:
        """Step 4: Verify setup instructions - check dashboard access."""
        content = Path("README.md").read_text()
        # Should mention Ray Dashboard and URL
        assert "8265" in content or "localhost:8265" in content, \
            "README must explain how to access Ray Dashboard"

    def test_setup_steps_are_numbered(self) -> None:
        """Step 4: Verify setup instructions are step-by-step."""
        content = Path("README.md").read_text()
        # Look for numbered steps or clear sequence
        # Either markdown numbered lists (1., 2., 3.) or ### headings with numbers
        has_numbered = re.search(r"^(1\.|###\s+1\.)", content, re.MULTILINE)
        assert has_numbered, \
            "README setup instructions should be numbered/sequential"


class TestREADMEBasicUsage:
    """Test that README provides examples of basic usage."""

    def test_common_tasks_section_exists(self) -> None:
        """Step 5: Verify examples - check usage section."""
        content = Path("README.md").read_text()
        # Look for usage examples, common tasks, etc.
        has_usage = any(section in content for section in [
            "Common Tasks", "Usage", "Examples", "Getting Started"
        ])
        assert has_usage, \
            "README must have section showing basic usage/examples"

    def test_ray_start_command_shown(self) -> None:
        """Step 5: Verify examples - check Ray start."""
        content = Path("README.md").read_text()
        # Should show how to start Ray
        assert "ray start" in content, \
            "README must show how to start Ray cluster"

    def test_ray_stop_command_shown(self) -> None:
        """Step 5: Verify examples - check Ray stop."""
        content = Path("README.md").read_text()
        # Should show how to stop Ray
        assert "ray stop" in content, \
            "README must show how to stop Ray cluster"

    def test_code_examples_use_code_blocks(self) -> None:
        """Step 5: Verify examples - check formatting."""
        content = Path("README.md").read_text()
        # Should have code blocks (```)
        assert "```bash" in content or "```python" in content, \
            "README must use proper markdown code blocks for examples"

    def test_study_execution_example_mentioned(self) -> None:
        """Step 5: Verify examples - check Study execution."""
        content = Path("README.md").read_text()
        # Should mention or show how to run a study (even if marked "future")
        assert "study" in content.lower() or "Study" in content, \
            "README must mention Study execution"


class TestREADMEDocumentationLinks:
    """Test that README includes links to detailed documentation."""

    def test_references_section_exists(self) -> None:
        """Step 6: Verify links - check references section."""
        content = Path("README.md").read_text()
        # Look for Resources, References, Documentation section
        has_refs = re.search(r"##\s+(Resources?|References?|Documentation)", content, re.IGNORECASE)
        assert has_refs, \
            "README must have Resources/References section"

    def test_app_spec_reference(self) -> None:
        """Step 6: Verify links - check app_spec.txt reference."""
        content = Path("README.md").read_text()
        assert "app_spec.txt" in content, \
            "README must reference app_spec.txt for detailed specification"

    def test_feature_list_reference(self) -> None:
        """Step 6: Verify links - check feature_list.json reference."""
        content = Path("README.md").read_text()
        assert "feature_list.json" in content, \
            "README must reference feature_list.json"

    def test_external_documentation_links(self) -> None:
        """Step 6: Verify links - check external docs."""
        content = Path("README.md").read_text()
        # Should link to Ray and OpenROAD docs
        assert "ray.io" in content or "docs.ray.io" in content, \
            "README should link to Ray documentation"
        assert "openroad" in content.lower(), \
            "README should mention OpenROAD documentation"

    def test_project_structure_documented(self) -> None:
        """Step 6: Verify links - check project structure."""
        content = Path("README.md").read_text()
        # Should document directory structure
        assert "src/" in content or "source" in content.lower(), \
            "README should document project structure"


class TestREADMECompleteness:
    """Test overall README completeness."""

    def test_readme_has_multiple_sections(self) -> None:
        """Verify README is well-organized with multiple sections."""
        content = Path("README.md").read_text()
        # Count ## headings (sections)
        sections = re.findall(r"^##\s+", content, re.MULTILINE)
        assert len(sections) >= 8, \
            "README should have at least 8 major sections for completeness"

    def test_readme_length_is_substantial(self) -> None:
        """Verify README has substantial content."""
        content = Path("README.md").read_text()
        # Should be at least 200 lines or 8000 characters
        lines = content.count('\n')
        assert lines >= 200 or len(content) >= 8000, \
            "README should have substantial content (200+ lines)"

    def test_readme_has_code_examples(self) -> None:
        """Verify README includes multiple code examples."""
        content = Path("README.md").read_text()
        code_blocks = content.count("```")
        assert code_blocks >= 10, \
            "README should have multiple code examples (5+ code blocks)"


class TestREADMEQuality:
    """Test README quality and professionalism."""

    def test_markdown_formatting_valid(self) -> None:
        """Verify basic markdown formatting is correct."""
        content = Path("README.md").read_text()
        # Check that code blocks are closed (even number of ```)
        code_block_count = content.count("```")
        assert code_block_count % 2 == 0, \
            "README markdown code blocks must be properly closed"

    def test_consistent_terminology(self) -> None:
        """Verify README uses consistent terminology."""
        content = Path("README.md").read_text()
        # Should consistently use "Noodle 2" not "noodle2" in prose
        # (though noodle2 is OK in paths/commands)
        # Just verify key terms are present
        assert "Study" in content and "Case" in content and "Stage" in content, \
            "README must use consistent capitalized terminology for core concepts"
