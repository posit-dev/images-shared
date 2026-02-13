import datetime
import json

import pytest

from posit_bakery.image.image_metadata import BuildMetadata, MetadataFile


class TestBuildMetadata:
    def test_load_single_target_data(self, image_testdata_path):
        with open(image_testdata_path / "single-target.json") as f:
            data = json.load(f)

        metadata = BuildMetadata.model_validate(data)
        assert (
            metadata.container_image_digest == "sha256:bcaa64b18c7dbaede0840f90ba072b85a6ca2776e27d705102c5d59e176fe647"
        )
        assert (
            metadata.image_name
            == "docker.io/posit/test-multi:1.0.0-min,docker.io/posit/test-multi:1.0.0-ubuntu-22.04-min,docker.io/posit/test-multi:min,docker.io/posit/test-multi:ubuntu-22.04-min,ghcr.io/posit-dev/test-multi:1.0.0-min,ghcr.io/posit-dev/test-multi:1.0.0-ubuntu-22.04-min,ghcr.io/posit-dev/test-multi:min,ghcr.io/posit-dev/test-multi:ubuntu-22.04-min"
        )

    def test_load_multi_target_data(self, image_testdata_path):
        with open(image_testdata_path / "multi-target.json") as f:
            data = json.load(f)

        for target_uid, target_data in data.items():
            BuildMetadata.model_validate(target_data)

    def test_image_tags(self, image_testdata_path):
        with open(image_testdata_path / "single-target.json") as f:
            data = json.load(f)

        metadata = BuildMetadata.model_validate(data)
        expected_tags = [
            "docker.io/posit/test-multi:1.0.0-min",
            "docker.io/posit/test-multi:1.0.0-ubuntu-22.04-min",
            "docker.io/posit/test-multi:min",
            "docker.io/posit/test-multi:ubuntu-22.04-min",
            "ghcr.io/posit-dev/test-multi:1.0.0-min",
            "ghcr.io/posit-dev/test-multi:1.0.0-ubuntu-22.04-min",
            "ghcr.io/posit-dev/test-multi:min",
            "ghcr.io/posit-dev/test-multi:ubuntu-22.04-min",
        ]
        assert metadata.image_tags == expected_tags

    def test_image_ref(self, image_testdata_path):
        with open(image_testdata_path / "single-target.json") as f:
            data = json.load(f)

        metadata = BuildMetadata.model_validate(data)
        expected_ref = "docker.io/posit/test-multi:1.0.0-min@sha256:bcaa64b18c7dbaede0840f90ba072b85a6ca2776e27d705102c5d59e176fe647"
        assert metadata.image_ref == expected_ref

    def test_created_at_from_annotations(self, image_testdata_path):
        """Test created_at returns timestamp from container_image_descriptor.annotations."""
        with open(image_testdata_path / "multi-target.json") as f:
            data = json.load(f)

        # multi-target.json has annotations with org.opencontainers.image.created
        metadata = BuildMetadata.model_validate(data["test-multi-1-0-0-minimal-ubuntu-22-04"])
        expected_dt = datetime.datetime.fromisoformat("2025-11-19T16:29:33Z")
        assert metadata.created_at == expected_dt

    def test_created_at_from_build_provenance(self):
        """Test created_at falls back to build provenance label when annotations missing."""
        data = {
            "image.name": "test:latest",
            "containerimage.digest": "sha256:abc123",
            "containerimage.descriptor": {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": "sha256:abc123",
                "size": 100,
                # No annotations
            },
            "buildx.build.provenance": {
                "builder": {"id": ""},
                "buildType": "https://mobyproject.org/buildkit@v1",
                "materials": [],
                "invocation": {
                    "configSource": {},
                    "parameters": {"args": {"label:org.opencontainers.image.created": "2024-06-15T10:30:00"}},
                    "environment": {},
                },
            },
        }
        metadata = BuildMetadata.model_validate(data)
        expected_dt = datetime.datetime.fromisoformat("2024-06-15T10:30:00")
        assert metadata.created_at == expected_dt

    def test_created_at_defaults_to_now(self):
        """Test created_at defaults to current time when no timestamp available."""
        data = {
            "image.name": "test:latest",
            "containerimage.digest": "sha256:abc123",
        }
        metadata = BuildMetadata.model_validate(data)
        # Should be close to now (within a few seconds)
        now = datetime.datetime.now()
        assert abs((metadata.created_at - now).total_seconds()) < 5

    def test_platform_from_descriptor(self, image_testdata_path):
        """Test platform returns value from container_image_descriptor.platform."""
        with open(image_testdata_path / "multi-target.json") as f:
            data = json.load(f)

        # multi-target.json has platform in container_image_descriptor
        metadata = BuildMetadata.model_validate(data["test-multi-1-0-0-minimal-ubuntu-22-04"])
        assert metadata.platform == "linux/amd64"

    def test_platform_from_build_provenance_environment(self):
        """Test platform falls back to build provenance invocation environment."""
        data = {
            "image.name": "test:latest",
            "containerimage.digest": "sha256:abc123",
            "containerimage.descriptor": {
                "mediaType": "application/vnd.oci.image.manifest.v1+json",
                "digest": "sha256:abc123",
                "size": 100,
                # No platform
            },
            "buildx.build.provenance": {
                "builder": {"id": ""},
                "buildType": "https://mobyproject.org/buildkit@v1",
                "materials": [],
                "invocation": {
                    "configSource": {},
                    "parameters": {},
                    "environment": {"platform": "linux/arm64"},
                },
            },
        }
        metadata = BuildMetadata.model_validate(data)
        assert metadata.platform == "linux/arm64"

    def test_platform_returns_none_when_unavailable(self):
        """Test platform returns None when no platform information available."""
        data = {
            "image.name": "test:latest",
            "containerimage.digest": "sha256:abc123",
        }
        metadata = BuildMetadata.model_validate(data)
        assert metadata.platform is None


class TestMetadataFile:
    def test_metadata_file_load(self, image_testdata_path):
        metadata_filepath = image_testdata_path / "multi-target.json"
        metadata_file = MetadataFile.load(metadata_filepath)
        assert len(metadata_file.metadata_map.root.keys()) == 4
        assert metadata_file.filepath == metadata_filepath

    def test_metadata_file_loads(self, image_testdata_path):
        with open(image_testdata_path / "multi-target.json") as f:
            metadata_file = MetadataFile.loads(f.read())

        assert len(metadata_file.metadata_map.root.keys()) == 4
        assert metadata_file.filepath is None

    def test_metadata_file_no_filepath_or_metadata_value_error(self):
        with pytest.raises(ValueError):
            MetadataFile()

    def test_metadata_file_load_file_not_found(self, tmp_path):
        """Test load raises FileNotFoundError for non-existent file."""
        non_existent_path = tmp_path / "does-not-exist.json"
        with pytest.raises(FileNotFoundError) as exc_info:
            MetadataFile.load(non_existent_path)
        assert "does not exist" in str(exc_info.value)

    def test_get_target_metadata_by_uid_exists(self, image_testdata_path):
        """Test get_target_metadata_by_uid returns metadata for existing UID."""
        metadata_file = MetadataFile.load(image_testdata_path / "multi-target.json")
        metadata = metadata_file.get_target_metadata_by_uid("test-multi-1-0-0-minimal-ubuntu-22-04")

        assert metadata is not None
        assert isinstance(metadata, BuildMetadata)
        assert (
            metadata.container_image_digest == "sha256:f5d7d95a3801d05f91db1fa7b5bba9fdb3d5babc0332c56f0cca25407c93a2f1"
        )

    def test_get_target_metadata_by_uid_not_found(self, image_testdata_path):
        """Test get_target_metadata_by_uid returns None for non-existent UID."""
        metadata_file = MetadataFile.load(image_testdata_path / "multi-target.json")
        metadata = metadata_file.get_target_metadata_by_uid("non-existent-uid")

        assert metadata is None

    def test_repr(self, image_testdata_path):
        """Test __repr__ returns expected string representation."""
        metadata_filepath = image_testdata_path / "multi-target.json"
        metadata_file = MetadataFile.load(metadata_filepath)

        repr_str = repr(metadata_file)
        assert "MetadataFile" in repr_str
        assert str(metadata_filepath.absolute()) in repr_str
