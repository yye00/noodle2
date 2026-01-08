"""
Tests for Git repository initialization and configuration.

Feature: Git repository is initialized with proper .gitignore for artifacts and caches
"""

import pytest
from pathlib import Path
import subprocess


class TestGitRepository:
    """Test Git repository initialization."""

    def test_verify_git_directory_exists(self):
        """Step 1: Verify .git directory exists."""
        project_root = Path(__file__).parent.parent
        git_dir = project_root / ".git"

        assert git_dir.exists(), ".git directory not found"
        assert git_dir.is_dir(), ".git is not a directory"

    def test_check_gitignore_file_is_present(self):
        """Step 2: Check .gitignore file is present."""
        project_root = Path(__file__).parent.parent
        gitignore = project_root / ".gitignore"

        assert gitignore.exists(), ".gitignore file not found"
        assert gitignore.is_file(), ".gitignore is not a file"

    def test_verify_gitignore_excludes_artifact_directories(self):
        """Step 3: Verify .gitignore excludes artifact directories."""
        project_root = Path(__file__).parent.parent
        gitignore = project_root / ".gitignore"

        content = gitignore.read_text()

        # Check for artifact directory patterns
        assert "artifacts/" in content or "artifact" in content.lower(), \
            ".gitignore should exclude artifact directories"
        assert "telemetry" in content.lower(), \
            ".gitignore should exclude telemetry directories"

    def test_verify_gitignore_excludes_python_cache_files(self):
        """Step 4: Verify .gitignore excludes Python cache files."""
        project_root = Path(__file__).parent.parent
        gitignore = project_root / ".gitignore"

        content = gitignore.read_text()

        # Check for Python cache patterns
        assert "__pycache__" in content, ".gitignore should exclude __pycache__"
        assert "*.pyc" in content or "*.py[cod]" in content, \
            ".gitignore should exclude .pyc files"
        assert ".pytest_cache" in content, ".gitignore should exclude .pytest_cache"

    def test_verify_gitignore_excludes_container_volumes(self):
        """Step 5: Verify .gitignore excludes container volumes."""
        project_root = Path(__file__).parent.parent
        gitignore = project_root / ".gitignore"

        content = gitignore.read_text()

        # Check for container volume patterns
        assert "volumes/" in content or "volume" in content.lower(), \
            ".gitignore should exclude container volumes"

    def test_that_artifacts_are_not_tracked_by_git(self):
        """Step 6: Test that artifacts are not tracked by git."""
        project_root = Path(__file__).parent.parent

        # Create test artifact directory
        test_artifact_dir = project_root / "artifacts" / "test_artifact"
        test_artifact_dir.mkdir(parents=True, exist_ok=True)

        # Create test file
        test_file = test_artifact_dir / "test.txt"
        test_file.write_text("test content")

        try:
            # Check git status to see if file is tracked
            result = subprocess.run(
                ["git", "status", "--porcelain", str(test_file)],
                cwd=project_root,
                capture_output=True,
                text=True,
            )

            # File should not appear in git status (should be ignored)
            # If it appears, it will have a status like "?? artifacts/..."
            # An ignored file won't appear at all
            output = result.stdout.strip()

            # The file should either not appear, or if it does, it should not be untracked
            # In most cases, it won't appear at all due to .gitignore
            if output:
                # If it appears, it should not start with ?? (untracked)
                assert not output.startswith("??"), \
                    f"Artifact file {test_file} is being tracked by git (not ignored)"

        finally:
            # Cleanup
            if test_file.exists():
                test_file.unlink()
            if test_artifact_dir.exists():
                test_artifact_dir.rmdir()


class TestGitConfiguration:
    """Test Git configuration and best practices."""

    def test_git_repository_is_initialized(self):
        """Verify git repository is properly initialized."""
        project_root = Path(__file__).parent.parent

        # Check that git commands work
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, "Git repository not properly initialized"
        assert ".git" in result.stdout

    def test_gitignore_covers_common_patterns(self):
        """Verify .gitignore covers common development patterns."""
        project_root = Path(__file__).parent.parent
        gitignore = project_root / ".gitignore"

        content = gitignore.read_text().lower()

        # Common patterns that should be ignored
        patterns = [
            "pycache",  # Python cache
            "pyc",  # Compiled Python
            "venv",  # Virtual environment
            "egg-info",  # Python package metadata
            ".pytest_cache",  # Pytest cache
            ".coverage",  # Coverage reports
        ]

        for pattern in patterns:
            assert pattern in content, f"Pattern '{pattern}' not found in .gitignore"

    def test_gitignore_excludes_ray_artifacts(self):
        """Verify .gitignore excludes Ray-related artifacts."""
        project_root = Path(__file__).parent.parent
        gitignore = project_root / ".gitignore"

        content = gitignore.read_text().lower()

        # Ray should have its temp files ignored
        assert "ray" in content, ".gitignore should exclude Ray artifacts"

    def test_project_has_git_commits(self):
        """Verify project has git history."""
        project_root = Path(__file__).parent.parent

        # Check that there are commits
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, "Failed to read git log"
        assert len(result.stdout) > 0, "Repository has no commits"
