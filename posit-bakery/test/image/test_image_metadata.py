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


class TestMetadataFile:
    def test_metadata_file_from_file(self, image_testdata_path):
        metadata_filepath = image_testdata_path / "single-target.json"
        metadata_file = MetadataFile(target_uid="test-multi-1-0-0-minimal-ubuntu-22-04", filepath=metadata_filepath)
        assert metadata_file.metadata is not None
        assert (
            metadata_file.metadata.container_image_digest
            == "sha256:bcaa64b18c7dbaede0840f90ba072b85a6ca2776e27d705102c5d59e176fe647"
        )
        assert (
            metadata_file.metadata.image_name
            == "docker.io/posit/test-multi:1.0.0-min,docker.io/posit/test-multi:1.0.0-ubuntu-22.04-min,docker.io/posit/test-multi:min,docker.io/posit/test-multi:ubuntu-22.04-min,ghcr.io/posit-dev/test-multi:1.0.0-min,ghcr.io/posit-dev/test-multi:1.0.0-ubuntu-22.04-min,ghcr.io/posit-dev/test-multi:min,ghcr.io/posit-dev/test-multi:ubuntu-22.04-min"
        )

    def test_metadata_file_from_direct_data(self, image_testdata_path):
        with open(image_testdata_path / "single-target.json") as f:
            data = json.load(f)

        metadata = BuildMetadata.model_validate(data)
        metadata_file = MetadataFile(target_uid="test-multi-1-0-0-minimal-ubuntu-22-04", metadata=metadata)
        assert metadata_file.metadata is not None
        assert metadata_file.filepath is None
        assert (
            metadata_file.metadata.container_image_digest
            == "sha256:bcaa64b18c7dbaede0840f90ba072b85a6ca2776e27d705102c5d59e176fe647"
        )
        assert (
            metadata_file.metadata.image_name
            == "docker.io/posit/test-multi:1.0.0-min,docker.io/posit/test-multi:1.0.0-ubuntu-22.04-min,docker.io/posit/test-multi:min,docker.io/posit/test-multi:ubuntu-22.04-min,ghcr.io/posit-dev/test-multi:1.0.0-min,ghcr.io/posit-dev/test-multi:1.0.0-ubuntu-22.04-min,ghcr.io/posit-dev/test-multi:min,ghcr.io/posit-dev/test-multi:ubuntu-22.04-min"
        )

    def test_metadata_file_no_filepath_or_metadata_value_error(self):
        with pytest.raises(ValueError):
            MetadataFile(target_uid="test-multi-1-0-0-minimal-ubuntu-22-04")
