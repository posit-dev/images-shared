import datetime
import json
import re

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


STRATEGY_METADATA_FIXTURES = ("strategy-bake-metadata.json", "strategy-build-metadata.json")
"""Real metadata files captured from both `bakery build` strategies for the same targets.

Both files were produced from the same `images-package-manager` checkout (commit
`adec3d9184f76c6e7725da5f28bdb9410010833c`) for `package-manager` 2026.06.0 --- 6 targets,
Standard/Minimal x Ubuntu 22.04/24.04/26.04 --- with:

    bakery build --strategy bake  --image-name '^package-manager$' --image-platform linux/amd64 \\
        --temp-registry ghcr.io/posit-dev --push --metadata-file ./bake-amd64-metadata.json
    bakery build --strategy build --image-name '^package-manager$' --image-platform linux/amd64 \\
        --temp-registry ghcr.io/posit-dev --push --metadata-file ./build-amd64-metadata.json

They are committed verbatim (only renamed) so the two producers can be compared as-shipped:
`--strategy bake` output is raw `docker buildx bake --metadata-file` passthrough, while
`--strategy build` output is synthesized by
`BakeryConfig._merge_sequential_build_metadata_files()`. Regenerate with the commands above
if the metadata contract intentionally changes.
"""


class TestStrategyMetadataCompatibility:
    """Pin the metadata contract shared by `--strategy bake` and `--strategy build`.

    `bakery dgoss run --metadata-file` and `bakery ci publish` consume metadata files through
    `MetadataFile.load()` -> `get_target_metadata_by_uid()` -> `image_ref`/`platform`/
    `created_at`, and must keep working regardless of which strategy produced the file. The two
    shapes come from entirely separate code paths, so without these assertions they can drift
    silently and only fail in CI at publish time.
    """

    @pytest.mark.parametrize("fixture_name", STRATEGY_METADATA_FIXTURES)
    def test_fixture_loads(self, image_testdata_path, fixture_name):
        """Both real fixtures validate through the same loader consumers use."""
        metadata_file = MetadataFile.load(image_testdata_path / fixture_name)
        assert len(metadata_file.metadata_map.root) == 6

    @pytest.mark.parametrize("fixture_name", STRATEGY_METADATA_FIXTURES)
    def test_uid_keys_are_target_uids(self, image_testdata_path, fixture_name):
        """Top-level keys are image target UIDs, which is how consumers look entries up."""
        metadata_file = MetadataFile.load(image_testdata_path / fixture_name)
        assert sorted(metadata_file.metadata_map.root) == [
            "package-manager-2026-06-0-minimal-ubuntu-22-04",
            "package-manager-2026-06-0-minimal-ubuntu-24-04",
            "package-manager-2026-06-0-minimal-ubuntu-26-04",
            "package-manager-2026-06-0-standard-ubuntu-22-04",
            "package-manager-2026-06-0-standard-ubuntu-24-04",
            "package-manager-2026-06-0-standard-ubuntu-26-04",
        ]

    @pytest.mark.parametrize("fixture_name", STRATEGY_METADATA_FIXTURES)
    def test_every_entry_has_resolvable_image_ref(self, image_testdata_path, fixture_name):
        """`ImageTarget.get_merge_sources()` emits nothing for entries without an image ref."""
        metadata_file = MetadataFile.load(image_testdata_path / fixture_name)
        for uid, metadata in metadata_file.metadata_map.root.items():
            assert metadata.image_ref is not None, uid
            assert re.fullmatch(r"[^@]+@sha256:[0-9a-f]{64}", metadata.image_ref), uid
            assert metadata.image_ref.endswith(f"@{metadata.container_image_digest}"), uid

    @pytest.mark.parametrize("fixture_name", STRATEGY_METADATA_FIXTURES)
    def test_every_entry_reports_platform(self, image_testdata_path, fixture_name):
        """Platform drives dgoss reference selection and per-platform merge sources."""
        metadata_file = MetadataFile.load(image_testdata_path / fixture_name)
        for uid, metadata in metadata_file.metadata_map.root.items():
            assert metadata.platform == "linux/amd64", uid

    @pytest.mark.parametrize("fixture_name", STRATEGY_METADATA_FIXTURES)
    def test_created_at_resolves_from_descriptor_annotation(self, image_testdata_path, fixture_name):
        """`created_at` must come from the descriptor, not the `datetime.now()` fallback.

        The fallback silently makes every entry look freshly built, which breaks the
        most-recent-wins ordering in `image_reference()` and `get_merge_sources()`.
        """
        metadata_file = MetadataFile.load(image_testdata_path / fixture_name)
        for uid, metadata in metadata_file.metadata_map.root.items():
            annotations = metadata.container_image_descriptor.annotations
            expected = datetime.datetime.fromisoformat(annotations["org.opencontainers.image.created"])
            assert metadata.created_at == expected, uid

    def test_strategies_agree_on_uids_and_primary_tags(self, image_testdata_path):
        """The two strategies are interchangeable for the fields consumers actually read."""
        bake, build = (MetadataFile.load(image_testdata_path / name) for name in STRATEGY_METADATA_FIXTURES)

        assert bake.metadata_map.root.keys() == build.metadata_map.root.keys()
        for uid, bake_metadata in bake.metadata_map.root.items():
            build_metadata = build.get_target_metadata_by_uid(uid)
            assert build_metadata is not None, uid
            # Digests differ (different builds); the tag set and primary tag must not.
            assert bake_metadata.image_tags == build_metadata.image_tags, uid
            assert bake_metadata.image_tags[0] == build_metadata.image_tags[0], uid
            assert bake_metadata.platform == build_metadata.platform, uid

    def test_multiplatform_entry_has_no_platform(self):
        """Document the degradation when one invocation builds several platforms.

        A multi-platform build emits a single index descriptor with no `platform`, for both
        strategies. `platform` is then None, so `ImageTarget.image_reference(platform=...)`
        falls back to a tag reference and `get_merge_sources()` collapses to one source. This
        is why CI must keep one platform per `bakery build` invocation.
        """
        metadata = BuildMetadata.model_validate(
            {
                "image.name": "ghcr.io/posit-dev/package-manager/tmp",
                "containerimage.digest": "sha256:" + "ab" * 32,
                "containerimage.descriptor": {
                    "mediaType": "application/vnd.oci.image.index.v1+json",
                    "digest": "sha256:" + "ab" * 32,
                    "size": 1234,
                    "annotations": {"org.opencontainers.image.created": "2026-08-11T15:50:15Z"},
                    # No platform: an index covers several platforms.
                },
            }
        )

        assert metadata.platform is None
        assert metadata.image_ref == "ghcr.io/posit-dev/package-manager/tmp@sha256:" + "ab" * 32
