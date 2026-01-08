"""Tests for container image pinning with SHA256 digest."""

from unittest.mock import MagicMock, patch

import pytest

from src.trial_runner.image_pinning import (
    ImageDigest,
    format_image_provenance,
    get_image_digest_for_provenance,
    query_image_digest,
    verify_image_digest,
)


class TestImageDigest:
    """Tests for ImageDigest dataclass."""

    def test_create_image_digest_with_tag(self):
        """Test creating ImageDigest with tag."""
        image = ImageDigest(
            repository="efabless/openlane",
            tag="ci2504-dev-amd64",
        )

        assert image.repository == "efabless/openlane"
        assert image.tag == "ci2504-dev-amd64"
        assert image.digest is None
        assert image.image_ref == "efabless/openlane:ci2504-dev-amd64"
        assert not image.is_pinned

    def test_create_image_digest_with_digest(self):
        """Test creating ImageDigest with SHA256 digest."""
        image = ImageDigest(
            repository="efabless/openlane",
            digest="sha256:abc123def456",
        )

        assert image.repository == "efabless/openlane"
        assert image.tag is None
        assert image.digest == "sha256:abc123def456"
        assert image.image_ref == "efabless/openlane@sha256:abc123def456"
        assert image.is_pinned

    def test_create_image_digest_with_both_tag_and_digest(self):
        """Test that digest takes precedence when both are specified."""
        image = ImageDigest(
            repository="efabless/openlane",
            tag="ci2504-dev-amd64",
            digest="sha256:abc123def456",
        )

        # Digest-based reference is used
        assert image.image_ref == "efabless/openlane@sha256:abc123def456"
        assert image.is_pinned

    def test_image_digest_requires_tag_or_digest(self):
        """Test that ImageDigest requires either tag or digest."""
        with pytest.raises(ValueError, match="Either tag or digest must be specified"):
            ImageDigest(repository="efabless/openlane")

    def test_image_digest_validates_digest_format(self):
        """Test that digest must start with 'sha256:'."""
        with pytest.raises(ValueError, match="Digest must start with 'sha256:'"):
            ImageDigest(
                repository="efabless/openlane",
                digest="abc123def456",  # Missing sha256: prefix
            )

    def test_image_digest_to_dict(self):
        """Test converting ImageDigest to dictionary."""
        image = ImageDigest(
            repository="efabless/openlane",
            tag="ci2504-dev-amd64",
            digest="sha256:abc123def456",
        )

        data = image.to_dict()

        assert data["repository"] == "efabless/openlane"
        assert data["tag"] == "ci2504-dev-amd64"
        assert data["digest"] == "sha256:abc123def456"
        assert data["image_ref"] == "efabless/openlane@sha256:abc123def456"
        assert data["is_pinned"] is True


class TestImageDigestParsing:
    """Tests for parsing image reference strings."""

    def test_parse_tag_based_reference(self):
        """Test parsing tag-based image reference."""
        image = ImageDigest.from_string("efabless/openlane:ci2504-dev-amd64")

        assert image.repository == "efabless/openlane"
        assert image.tag == "ci2504-dev-amd64"
        assert image.digest is None
        assert not image.is_pinned

    def test_parse_digest_based_reference(self):
        """Test parsing digest-based image reference."""
        image = ImageDigest.from_string(
            "efabless/openlane@sha256:abc123def456789"
        )

        assert image.repository == "efabless/openlane"
        assert image.tag is None
        assert image.digest == "sha256:abc123def456789"
        assert image.is_pinned

    def test_parse_image_without_tag_defaults_to_latest(self):
        """Test that image without tag defaults to 'latest'."""
        image = ImageDigest.from_string("efabless/openlane")

        assert image.repository == "efabless/openlane"
        assert image.tag == "latest"
        assert image.digest is None

    def test_parse_multi_part_repository(self):
        """Test parsing image with multi-part repository name."""
        image = ImageDigest.from_string("docker.io/library/ubuntu:22.04")

        assert image.repository == "docker.io/library/ubuntu"
        assert image.tag == "22.04"


class TestQueryImageDigest:
    """Tests for querying image digest from Docker."""

    @patch("subprocess.run")
    def test_query_image_digest_success(self, mock_run):
        """Test querying image digest successfully."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "sha256:abc123def456789\n"
        mock_run.return_value = mock_result

        digest = query_image_digest("efabless/openlane:ci2504-dev-amd64")

        assert digest == "sha256:abc123def456789"

    @patch("subprocess.run")
    def test_query_image_digest_from_repo_digests(self, mock_run):
        """Test querying digest from RepoDigests when Id is short format."""
        # First call returns short ID
        mock_result1 = MagicMock()
        mock_result1.returncode = 0
        mock_result1.stdout = "abc123\n"  # Short ID without sha256: prefix

        # Second call returns RepoDigest
        mock_result2 = MagicMock()
        mock_result2.returncode = 0
        mock_result2.stdout = "efabless/openlane@sha256:def456789\n"

        mock_run.side_effect = [mock_result1, mock_result2]

        digest = query_image_digest("efabless/openlane:ci2504-dev-amd64")

        assert digest == "sha256:def456789"

    @patch("subprocess.run")
    def test_query_image_digest_failure(self, mock_run):
        """Test handling failure to query image digest."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_run.return_value = mock_result

        digest = query_image_digest("nonexistent/image:latest")

        assert digest is None

    @patch("subprocess.run")
    def test_query_image_digest_timeout(self, mock_run):
        """Test handling timeout during digest query."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired("docker", 10)

        digest = query_image_digest("efabless/openlane:ci2504-dev-amd64")

        assert digest is None

    @patch("subprocess.run")
    def test_query_image_digest_no_docker(self, mock_run):
        """Test handling Docker not installed."""
        mock_run.side_effect = FileNotFoundError("docker command not found")

        digest = query_image_digest("efabless/openlane:ci2504-dev-amd64")

        assert digest is None


class TestVerifyImageDigest:
    """Tests for verifying image digest."""

    @patch("src.trial_runner.image_pinning.query_image_digest")
    def test_verify_image_digest_match(self, mock_query):
        """Test verifying image digest when it matches."""
        mock_query.return_value = "sha256:abc123def456"

        # Step 2: Verify image digest before execution
        result = verify_image_digest(
            "efabless/openlane:ci2504-dev-amd64",
            "sha256:abc123def456",
        )

        assert result is True

    @patch("src.trial_runner.image_pinning.query_image_digest")
    def test_verify_image_digest_mismatch(self, mock_query):
        """Test verifying image digest when it doesn't match."""
        mock_query.return_value = "sha256:different123"

        result = verify_image_digest(
            "efabless/openlane:ci2504-dev-amd64",
            "sha256:abc123def456",
        )

        assert result is False

    @patch("src.trial_runner.image_pinning.query_image_digest")
    def test_verify_image_digest_query_failure(self, mock_query):
        """Test handling query failure during verification."""
        mock_query.return_value = None

        result = verify_image_digest(
            "nonexistent/image:latest",
            "sha256:abc123def456",
        )

        assert result is False

    @patch("src.trial_runner.image_pinning.query_image_digest")
    def test_verify_image_digest_normalizes_format(self, mock_query):
        """Test that verification normalizes digest formats."""
        # Actual digest has sha256: prefix
        mock_query.return_value = "sha256:abc123def456"

        # Expected digest may or may not have prefix
        result1 = verify_image_digest(
            "efabless/openlane:ci2504-dev-amd64",
            "sha256:abc123def456",
        )
        result2 = verify_image_digest(
            "efabless/openlane:ci2504-dev-amd64",
            "abc123def456",
        )

        assert result1 is True
        assert result2 is True


class TestConfigureStudyWithDigest:
    """Tests for configuring Study with SHA256 digest."""

    def test_configure_study_with_digest_pinned_image(self):
        """Test configuring Study with digest-pinned image."""
        # Step 1: Configure Study with container image specified by SHA256 digest
        image = ImageDigest(
            repository="efabless/openlane",
            digest="sha256:abc123def456",
        )

        assert image.is_pinned
        assert image.image_ref == "efabless/openlane@sha256:abc123def456"

    @patch("src.trial_runner.image_pinning.query_image_digest")
    def test_verify_digest_before_execution(self, mock_query):
        """Test verifying digest before trial execution."""
        mock_query.return_value = "sha256:abc123def456"

        image = ImageDigest(
            repository="efabless/openlane",
            digest="sha256:abc123def456",
        )

        # Step 2: Verify image digest before execution
        verified = verify_image_digest(
            image.image_ref,
            image.digest,
        )

        assert verified is True


class TestExecuteWithPinnedImage:
    """Tests for executing trials with pinned image."""

    def test_execute_trial_with_pinned_image(self):
        """Test that pinned image reference is used for trial execution."""
        # Step 3: Execute trial with pinned image
        image = ImageDigest(
            repository="efabless/openlane",
            digest="sha256:abc123def456",
        )

        # Image reference should be digest-based
        assert image.image_ref == "efabless/openlane@sha256:abc123def456"
        assert image.is_pinned

    def test_ensure_exact_image_version_across_trials(self):
        """Test that digest ensures exact image version."""
        # Step 4: Ensure exact image version is used across all trials
        image = ImageDigest(
            repository="efabless/openlane",
            digest="sha256:abc123def456",
        )

        # Create multiple "trial" references - all should be identical
        refs = [image.image_ref for _ in range(10)]

        # All references are identical (digest-based)
        assert len(set(refs)) == 1
        assert all(ref == "efabless/openlane@sha256:abc123def456" for ref in refs)


class TestDocumentDigestInProvenance:
    """Tests for documenting image digest in provenance."""

    def test_image_digest_to_dict_for_provenance(self):
        """Test converting image digest to dict for provenance metadata."""
        # Step 5: Document image digest in provenance metadata
        image = ImageDigest(
            repository="efabless/openlane",
            tag="ci2504-dev-amd64",
            digest="sha256:abc123def456",
        )

        data = image.to_dict()

        assert "digest" in data
        assert data["digest"] == "sha256:abc123def456"
        assert data["is_pinned"] is True

    @patch("src.trial_runner.image_pinning.query_image_digest")
    def test_get_image_digest_for_provenance(self, mock_query):
        """Test getting image digest for provenance metadata."""
        mock_query.return_value = "sha256:abc123def456"

        digest = get_image_digest_for_provenance(
            "efabless/openlane:ci2504-dev-amd64"
        )

        assert digest == "sha256:abc123def456"

    @patch("src.trial_runner.image_pinning.query_image_digest")
    def test_get_image_digest_fallback(self, mock_query):
        """Test fallback when digest query fails."""
        mock_query.return_value = None

        digest = get_image_digest_for_provenance(
            "efabless/openlane:ci2504-dev-amd64"
        )

        # Falls back to image reference
        assert digest == "efabless/openlane:ci2504-dev-amd64"


class TestFormatImageProvenance:
    """Tests for formatting image provenance."""

    def test_format_provenance_with_pinned_image(self):
        """Test formatting provenance for pinned image."""
        image = ImageDigest(
            repository="efabless/openlane",
            tag="ci2504-dev-amd64",
            digest="sha256:abc123def456",
        )

        provenance = format_image_provenance(image)

        assert "=== Container Image Provenance ===" in provenance
        assert "Repository: efabless/openlane" in provenance
        assert "Tag: ci2504-dev-amd64" in provenance
        assert "Digest: sha256:abc123def456" in provenance
        assert "Pinned: Yes (reproducible)" in provenance
        assert "Full Reference: efabless/openlane@sha256:abc123def456" in provenance

    def test_format_provenance_with_tag_only(self):
        """Test formatting provenance for tag-based image."""
        image = ImageDigest(
            repository="efabless/openlane",
            tag="ci2504-dev-amd64",
        )

        provenance = format_image_provenance(image)

        assert "Repository: efabless/openlane" in provenance
        assert "Tag: ci2504-dev-amd64" in provenance
        assert "Pinned: No (tag-based, may change)" in provenance
        assert "Full Reference: efabless/openlane:ci2504-dev-amd64" in provenance


class TestEndToEndImagePinning:
    """End-to-end tests for image pinning workflow."""

    @patch("src.trial_runner.image_pinning.query_image_digest")
    def test_complete_image_pinning_workflow(self, mock_query):
        """Test complete workflow from configuration to execution."""
        # Step 1: Configure Study with SHA256 digest
        image = ImageDigest.from_string(
            "efabless/openlane@sha256:abc123def456"
        )

        assert image.is_pinned
        assert image.digest == "sha256:abc123def456"

        # Step 2: Verify image digest before execution
        mock_query.return_value = "sha256:abc123def456"
        verified = verify_image_digest(image.image_ref, image.digest)
        assert verified is True

        # Step 3: Execute with pinned image
        # (In real implementation, this would be passed to Docker)
        assert image.image_ref == "efabless/openlane@sha256:abc123def456"

        # Step 4: Ensure exact version across trials
        refs = [image.image_ref for _ in range(5)]
        assert len(set(refs)) == 1

        # Step 5: Document in provenance
        provenance_data = image.to_dict()
        assert provenance_data["digest"] == "sha256:abc123def456"
        assert provenance_data["is_pinned"] is True
