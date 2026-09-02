import json
import subprocess
from unittest.mock import Mock, patch

import python_on_whales

from posit_bakery.image.image_metadata import BuildMetadata
from posit_bakery.image.summary import (
    BuildSummary,
    BuildSummaryTarget,
    _inspect_local,
    _inspect_manifest,
    _inspect_registry,
    _repository_of,
)
from posit_bakery.parallel import CommandRunner
from posit_bakery.settings import SETTINGS


def _completed(returncode=0, stdout=b"", stderr=b"") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def _fake_image(size: int, layer_count: int) -> Mock:
    """Stand-in for python_on_whales.Image exposing just the .size/.root_fs.layers surface
    _inspect_local relies on."""
    image = Mock(size=size)
    image.root_fs.layers = [f"sha256:{i}" for i in range(layer_count)]
    return image


class _FakeRunner:
    """Duck-types CommandRunner.run() for tests, keyed by (kind, ref) so a test can control
    exactly what each inspect call returns without touching a real subprocess."""

    def __init__(self, responses: dict[tuple[str, str], subprocess.CompletedProcess]):
        self._responses = responses
        self.calls: list[list[str]] = []

    def run(self, cmd, **kwargs):
        self.calls.append(cmd)
        ref = cmd[-1]
        kind = "local" if "buildx" not in cmd else "registry"
        return self._responses.get((kind, ref), _completed(returncode=1, stderr=b"not found: " + ref.encode()))


CACHE_MANIFEST_JSON = json.dumps(
    {
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "schemaVersion": 2,
        "config": {"mediaType": "application/vnd.buildkit.cacheconfig.v0", "digest": "sha256:cfg", "size": 2920},
        "layers": [{"digest": "sha256:a", "size": 100}, {"digest": "sha256:b", "size": 200}],
    }
).encode()

SINGLE_PLATFORM_MANIFEST_JSON = json.dumps(
    {
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "schemaVersion": 2,
        "layers": [{"digest": "sha256:a", "size": 100}, {"digest": "sha256:b", "size": 200}],
    }
).encode()

INDEX_MANIFEST_JSON = json.dumps(
    {
        "mediaType": "application/vnd.oci.image.index.v1+json",
        "schemaVersion": 2,
        "manifests": [
            {"digest": "sha256:child-amd64", "size": 500, "platform": {"architecture": "amd64", "os": "linux"}},
            {"digest": "sha256:child-arm64", "size": 500, "platform": {"architecture": "arm64", "os": "linux"}},
        ],
    }
).encode()

_IMAGE_CHILD = {"digest": "sha256:child-amd64", "size": 500, "platform": {"architecture": "amd64", "os": "linux"}}
_ATTESTATION_CHILD = {
    "digest": "sha256:attestation",
    "size": 900,
    "platform": {"architecture": "unknown", "os": "unknown"},
    "annotations": {"vnd.docker.reference.type": "attestation-manifest"},
}


def _index_json(*children: dict) -> bytes:
    return json.dumps(
        {
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "schemaVersion": 2,
            "manifests": list(children),
        }
    ).encode()


ATTESTATION_MANIFEST_JSON = json.dumps(
    {
        "mediaType": "application/vnd.oci.image.manifest.v1+json",
        "schemaVersion": 2,
        "layers": [{"digest": "sha256:in-toto", "size": 10_000}],
    }
).encode()


class TestInspectLocal:
    def test_parses_size_and_returns_result(self):
        with patch("python_on_whales.docker.image.inspect") as inspect_mock:
            inspect_mock.return_value.size = 12_345
            result = _inspect_local("myimage:tag")

        assert result is not None
        assert result.size == 12_345
        inspect_mock.assert_called_once_with("myimage:tag")

    def test_returns_none_on_docker_exception(self):
        with patch("python_on_whales.docker.image.inspect") as inspect_mock:
            inspect_mock.side_effect = python_on_whales.exceptions.NoSuchImage([], 1, b"", b"no such image")
            assert _inspect_local("myimage:tag") is None


class TestRepositoryOf:
    def test_strips_a_trailing_tag(self):
        assert _repository_of("ghcr.io/posit-dev/connect:2026.01.1") == "ghcr.io/posit-dev/connect"

    def test_handles_a_registry_host_with_an_explicit_port(self):
        """The tag must be stripped from the end of the ref, not from the first colon --
        a `host:port` before the first `/` is not a tag separator."""
        assert _repository_of("localhost:5000/myrepo:tag") == "localhost:5000/myrepo"

    def test_ref_with_no_tag_is_returned_unchanged(self):
        assert _repository_of("ghcr.io/posit-dev/connect") == "ghcr.io/posit-dev/connect"

    def test_strips_a_digest_qualified_tag(self):
        """ImageTarget.ref() returns `repo:tag@digest` whenever build metadata is present --
        the digest suffix must go, not just the tag, and the split must not land inside the
        digest's own hex."""
        ref = "ghcr.io/posit-dev/connect:2026.01.1@sha256:" + "a" * 64
        assert _repository_of(ref) == "ghcr.io/posit-dev/connect"

    def test_strips_a_digest_only_ref_with_no_tag(self):
        ref = "ghcr.io/posit-dev/connect@sha256:" + "a" * 64
        assert _repository_of(ref) == "ghcr.io/posit-dev/connect"


class TestInspectManifest:
    def test_parses_a_manifest(self):
        runner = _FakeRunner({("registry", "myimage:tag"): _completed(stdout=SINGLE_PLATFORM_MANIFEST_JSON)})
        manifest = _inspect_manifest(runner, "myimage:tag")

        assert manifest is not None
        assert len(manifest.layers) == 2

    def test_returns_none_on_nonzero_exit(self):
        runner = _FakeRunner({("registry", "myimage:tag"): _completed(returncode=1, stderr=b"not found")})
        assert _inspect_manifest(runner, "myimage:tag") is None


class TestInspectRegistry:
    def test_single_platform_sums_layer_sizes(self):
        runner = _FakeRunner({("registry", "myimage:tag"): _completed(stdout=SINGLE_PLATFORM_MANIFEST_JSON)})
        result = _inspect_registry(runner, "myimage:tag")

        assert result == (300, 2)

    def test_multiplatform_index_fans_out_and_sums_across_children(self):
        runner = _FakeRunner(
            {
                ("registry", "myimage:tag"): _completed(stdout=INDEX_MANIFEST_JSON),
                ("registry", "myimage@sha256:child-amd64"): _completed(stdout=SINGLE_PLATFORM_MANIFEST_JSON),
                ("registry", "myimage@sha256:child-arm64"): _completed(stdout=SINGLE_PLATFORM_MANIFEST_JSON),
            }
        )
        result = _inspect_registry(runner, "myimage:tag")

        # 300 bytes per child x 2 children = 600; layer count uses only the first child (2), not summed.
        assert result == (600, 2)

    def test_returns_none_when_index_lookup_fails(self):
        runner = _FakeRunner({})  # no responses configured -> every call fails
        assert _inspect_registry(runner, "myimage:tag") is None

    def test_returns_none_when_all_children_fail(self):
        runner = _FakeRunner({("registry", "myimage:tag"): _completed(stdout=INDEX_MANIFEST_JSON)})
        assert _inspect_registry(runner, "myimage:tag") is None

    def test_attestation_children_are_excluded_from_the_byte_total(self):
        """buildx attaches provenance/SBOM manifests to the index under an unknown/unknown
        platform. Their blobs are not part of the image, so counting them inflates the
        reported Registry Size -- here by 10 KB against a 300-byte image."""
        runner = _FakeRunner(
            {
                ("registry", "myimage:tag"): _completed(stdout=_index_json(_IMAGE_CHILD, _ATTESTATION_CHILD)),
                ("registry", "myimage@sha256:child-amd64"): _completed(stdout=SINGLE_PLATFORM_MANIFEST_JSON),
                ("registry", "myimage@sha256:attestation"): _completed(stdout=ATTESTATION_MANIFEST_JSON),
            }
        )
        result = _inspect_registry(runner, "myimage:tag")

        assert result == (300, 2)

    def test_an_attestation_listed_first_does_not_become_the_layer_count(self):
        """Layer count takes the first child inspected. buildx happens to append
        attestations after image manifests today, but nothing in the OCI index spec
        guarantees that order -- so the filter, not the ordering, has to be what protects it."""
        runner = _FakeRunner(
            {
                ("registry", "myimage:tag"): _completed(stdout=_index_json(_ATTESTATION_CHILD, _IMAGE_CHILD)),
                ("registry", "myimage@sha256:child-amd64"): _completed(stdout=SINGLE_PLATFORM_MANIFEST_JSON),
                ("registry", "myimage@sha256:attestation"): _completed(stdout=ATTESTATION_MANIFEST_JSON),
            }
        )
        result = _inspect_registry(runner, "myimage:tag")

        assert result == (300, 2)

    def test_partial_child_failure_still_reports_the_successes(self):
        """One platform's inspect hiccupping must not blank out the whole target."""
        runner = _FakeRunner(
            {
                ("registry", "myimage:tag"): _completed(stdout=INDEX_MANIFEST_JSON),
                ("registry", "myimage@sha256:child-amd64"): _completed(stdout=SINGLE_PLATFORM_MANIFEST_JSON),
                # child-arm64 intentionally has no configured response -> fails
            }
        )
        result = _inspect_registry(runner, "myimage:tag")

        assert result == (300, 2)


class TestRefStaysIndexCompatibleForMultiPlatformBuilds:
    """Regression coverage for a question raised in review: could ImageTarget.ref() ever
    return a per-platform leaf digest for a target whose own build produced a multi-platform
    index, silently making _inspect_registry's fan-out never trigger and undercounting
    registry size?

    Verified against a real captured buildx --metadata-file output
    (test/config/testdata/build_metadata/expected.json): BuildMetadata.platform falls back
    to the build *machine's* own arch (via buildx.build.provenance), not None, for an index
    descriptor -- so ref()'s platform match does fire. But image_ref's digest is
    independently always correct regardless: it's built from the top-level
    containerimage.digest, which is the same digest as containerimage.descriptor.digest --
    the index's own digest here, never some other platform's leaf digest."""

    def test_ref_returns_the_index_digest_not_a_leaf(self, get_targets):
        target = get_targets("basic")[0]
        index_digest = "sha256:" + "a" * 64
        target.build_metadata.append(
            BuildMetadata.model_validate(
                {
                    "image.name": "ghcr.io/posit-dev/test-image:1.0.0",
                    "containerimage.digest": index_digest,
                    "containerimage.descriptor": {
                        "mediaType": "application/vnd.oci.image.index.v1+json",
                        "digest": index_digest,
                        "size": 855,
                    },
                    "buildx.build.provenance": {
                        "invocation": {"environment": {"platform": f"linux/{SETTINGS.architecture}"}}
                    },
                }
            )
        )

        assert target.ref() == f"ghcr.io/posit-dev/test-image:1.0.0@{index_digest}"

    def test_inspect_registry_fans_out_given_that_ref(self):
        index_digest = "sha256:" + "a" * 64
        ref = f"ghcr.io/posit-dev/test-image:1.0.0@{index_digest}"
        runner = _FakeRunner(
            {
                ("registry", ref): _completed(stdout=INDEX_MANIFEST_JSON),
                ("registry", "ghcr.io/posit-dev/test-image@sha256:child-amd64"): _completed(
                    stdout=SINGLE_PLATFORM_MANIFEST_JSON
                ),
                ("registry", "ghcr.io/posit-dev/test-image@sha256:child-arm64"): _completed(
                    stdout=SINGLE_PLATFORM_MANIFEST_JSON
                ),
            }
        )
        result = _inspect_registry(runner, ref)

        assert result == (600, 2)


class TestMeasureSizes:
    def test_skips_executor_entirely_when_neither_push_nor_load(self, get_targets):
        """Uses a non-empty target list deliberately: an empty list would no-op through
        run_jobs() regardless of whether the early-return guard exists, so that alone
        wouldn't prove the guard does anything."""
        targets = get_targets("basic")
        summary = BuildSummary.from_image_targets(targets)

        with patch("posit_bakery.image.summary.ParallelShellExecutor") as mock_executor_cls:
            summary.measure_sizes(targets, push=False, load=False)

        mock_executor_cls.assert_not_called()


class TestMeasureSizesEndToEnd:
    """Exercises the real ParallelShellExecutor/ShellJob/CommandRunner wiring; only the
    actual subprocess spawn (CommandRunner.run, python_on_whales.docker.image.inspect) is
    replaced."""

    def test_populates_local_size_and_layers_for_real_targets(self, get_targets):
        targets = get_targets("basic")
        summary = BuildSummary.from_image_targets(targets)

        with patch("python_on_whales.docker.image.inspect", return_value=_fake_image(12_345, 3)):
            summary.measure_sizes(targets, push=False, load=True)

        assert len(summary.targets) == len(targets)
        for row in summary.targets:
            assert row.local_size == 12_345
            assert row.layers == 3
            assert row.registry_size is None

    def test_measurement_lands_on_the_matching_target_by_uid(self, get_targets):
        """With several targets in flight concurrently, each measurement must land on its
        own row -- not get cross-assigned to a different target."""
        targets = get_targets("multiplatform")
        summary = BuildSummary.from_image_targets(targets)
        sizes_by_ref = {target.ref(): 1000 * (i + 1) for i, target in enumerate(targets)}

        def _fake_inspect(ref):
            return _fake_image(sizes_by_ref[ref], 0)

        with patch("python_on_whales.docker.image.inspect", side_effect=_fake_inspect):
            summary.measure_sizes(targets, push=False, load=True)

        rows_by_uid = {row.uid: row for row in summary.targets}
        for i, target in enumerate(targets):
            assert rows_by_uid[target.uid].local_size == 1000 * (i + 1)

    def test_registry_hiccup_leaves_dash_and_does_not_raise(self, get_targets):
        targets = get_targets("basic")
        summary = BuildSummary.from_image_targets(targets)

        def _fake_run(runner_self, cmd, **kwargs):
            return _completed(returncode=1, stderr=b"connection reset")

        with (
            patch.object(CommandRunner, "run", _fake_run),
            patch(
                "python_on_whales.docker.image.inspect",
                side_effect=python_on_whales.exceptions.DockerException([], 1, b"", b"connection reset"),
            ),
        ):
            summary.measure_sizes(targets, push=True, load=True)  # must not raise

        assert all(row.registry_size is None for row in summary.targets)
        assert all(row.local_size is None for row in summary.targets)


class TestMeasureSizesSucceededUids:
    """succeeded_uids narrows the registry lookup to targets that succeeded *this run*, so a
    target that failed isn't measured off whatever image already happens to sit at its tag
    from an earlier, unrelated push."""

    def test_excluded_uid_is_not_measured_even_though_the_registry_has_something(self, get_targets):
        targets = get_targets("multiplatform")
        assert len(targets) >= 2
        summary = BuildSummary.from_image_targets(targets)
        excluded_uid = targets[0].uid

        def _fake_run(runner_self, cmd, **kwargs):
            return _completed(stdout=SINGLE_PLATFORM_MANIFEST_JSON)

        with patch.object(CommandRunner, "run", _fake_run):
            summary.measure_sizes(
                targets, push=True, load=False, succeeded_uids={t.uid for t in targets if t.uid != excluded_uid}
            )

        rows_by_uid = {row.uid: row for row in summary.targets}
        assert rows_by_uid[excluded_uid].registry_size is None
        for target in targets:
            if target.uid != excluded_uid:
                assert rows_by_uid[target.uid].registry_size == 300

    def test_none_measures_every_target_matching_original_behavior(self, get_targets):
        targets = get_targets("basic")
        summary = BuildSummary.from_image_targets(targets)

        def _fake_run(runner_self, cmd, **kwargs):
            return _completed(stdout=SINGLE_PLATFORM_MANIFEST_JSON)

        with patch.object(CommandRunner, "run", _fake_run):
            summary.measure_sizes(targets, push=True, load=False, succeeded_uids=None)

        assert all(row.registry_size == 300 for row in summary.targets)


def _fake_run_registry_fails(runner_self, cmd, **kwargs):
    return _completed(returncode=1, stderr=b"not found")


def _fake_run_cache_only(runner_self, cmd, **kwargs):
    """Resolves only cache refs; every image inspect fails, so a measured `cache_size` can
    only have come from the cache lookup."""
    if "/cache:" in cmd[-1]:
        return _completed(stdout=CACHE_MANIFEST_JSON)
    return _completed(returncode=1, stderr=b"not found")


class TestMeasureSizesCache:
    def _summary_with_cache_ref(self, get_targets, suite="basic", registry="ghcr.io/posit-dev"):
        targets = get_targets(suite)
        for target in targets:
            target.settings.cache_registry = registry
        return targets, BuildSummary.from_image_targets(targets)

    def test_measured_when_push_is_false_but_cache_ref_present(self, get_targets):
        """A pull-only build (`push=False`) still resolves `cache_from` against whatever is
        currently at `cache_ref` -- the registry lookup needs a `cache_ref` to query, not
        this build to have pushed anything, so it must not be gated on `push`."""
        targets, summary = self._summary_with_cache_ref(get_targets)

        with patch.object(CommandRunner, "run", _fake_run_cache_only):
            summary.measure_sizes(targets, push=False, load=False)

        assert all(row.cache_size == 300 for row in summary.targets)
        assert all(row.registry_size is None for row in summary.targets)

    def test_measured_when_push_is_true(self, get_targets):
        targets, summary = self._summary_with_cache_ref(get_targets)

        with patch.object(CommandRunner, "run", _fake_run_cache_only):
            summary.measure_sizes(targets, push=True, load=False)

        assert all(row.cache_size == 300 for row in summary.targets)

    def test_measured_for_a_non_ghcr_cache_registry(self, get_targets):
        """`--cache-registry` accepts any registry, so measurement goes through the same
        `imagetools inspect` path as image sizes rather than a registry-specific API client."""
        targets, summary = self._summary_with_cache_ref(get_targets, registry="123456.dkr.ecr.us-east-1.amazonaws.com")

        with patch.object(CommandRunner, "run", _fake_run_cache_only):
            summary.measure_sizes(targets, push=True, load=False)

        assert all(row.cache_ref is not None and "amazonaws.com" in row.cache_ref for row in summary.targets)
        assert all(row.cache_size == 300 for row in summary.targets)

    def test_stays_none_without_a_cache_ref(self, get_targets):
        targets = get_targets("basic")  # no cache_registry set -> cache_ref is None
        summary = BuildSummary.from_image_targets(targets)
        runner_calls: list[list[str]] = []

        def _record(runner_self, cmd, **kwargs):
            runner_calls.append(cmd)
            return _completed(returncode=1, stderr=b"not found")

        with patch.object(CommandRunner, "run", _record):
            summary.measure_sizes(targets, push=True, load=False)

        assert not any("/cache:" in cmd[-1] for cmd in runner_calls)
        assert all(row.cache_size is None for row in summary.targets)

    def test_manifest_fetch_failure_leaves_dash_and_does_not_raise(self, get_targets):
        targets, summary = self._summary_with_cache_ref(get_targets)

        with patch.object(CommandRunner, "run", _fake_run_registry_fails):
            summary.measure_sizes(targets, push=True, load=False)  # must not raise

        assert all(row.cache_size is None for row in summary.targets)


def _attach_metadata(target, digest: str) -> None:
    """Give `target` the build metadata that `--metadata-file` would have produced, so
    `ref()` resolves to the digest actually pushed instead of falling back to `tags[0]`."""
    target.build_metadata.append(
        BuildMetadata.model_validate(
            {
                "image.name": "ghcr.io/posit-dev/test-image/tmp",
                "containerimage.digest": digest,
                "containerimage.descriptor": {
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "digest": digest,
                    "size": 855,
                },
                "buildx.build.provenance": {
                    "invocation": {"environment": {"platform": f"linux/{SETTINGS.architecture}"}}
                },
            }
        )
    )


class TestMeasureSizesTempRegistryGuard:
    """Under `--temp-registry`, `ImageTarget.build()` swaps the tag list for `temp_name` and
    pushes by digest, so the public tags are never written by this build. `ref()`'s `tags[0]`
    fallback therefore points at whatever the *previous* release left at that tag -- measuring
    it would report an unrelated image's size as this build's."""

    def _targets_with_temp_registry(self, get_targets):
        targets = get_targets("basic")
        for target in targets:
            target.settings.temp_registry = "ghcr.io/posit-dev"
        return targets

    def test_temp_registry_without_build_metadata_is_not_measured(self, get_targets):
        targets = self._targets_with_temp_registry(get_targets)
        summary = BuildSummary.from_image_targets(targets)
        calls: list[list[str]] = []

        def _record(runner_self, cmd, **kwargs):
            calls.append(cmd)
            return _completed(stdout=SINGLE_PLATFORM_MANIFEST_JSON)

        with patch.object(CommandRunner, "run", _record):
            summary.measure_sizes(targets, push=True, load=True)

        assert calls == []  # not "measured something wrong" -- measured nothing at all
        assert all(row.registry_size is None for row in summary.targets)
        assert all(row.local_size is None for row in summary.targets)

    def test_temp_registry_with_build_metadata_measures_the_pushed_digest(self, get_targets):
        digest = "sha256:" + "b" * 64
        targets = self._targets_with_temp_registry(get_targets)
        for target in targets:
            _attach_metadata(target, digest)
        summary = BuildSummary.from_image_targets(targets)
        refs: list[str] = []

        def _record(runner_self, cmd, **kwargs):
            refs.append(cmd[-1])
            return _completed(stdout=SINGLE_PLATFORM_MANIFEST_JSON)

        with patch.object(CommandRunner, "run", _record):
            summary.measure_sizes(targets, push=True, load=False)

        assert refs and all(digest in ref for ref in refs)
        assert all(row.registry_size == 300 for row in summary.targets)

    def test_public_tag_is_measured_when_no_temp_registry_is_configured(self, get_targets):
        targets = get_targets("basic")  # temp_registry unset -> temp_name is None
        summary = BuildSummary.from_image_targets(targets)

        def _fake_run(runner_self, cmd, **kwargs):
            return _completed(stdout=SINGLE_PLATFORM_MANIFEST_JSON)

        with patch.object(CommandRunner, "run", _fake_run):
            summary.measure_sizes(targets, push=True, load=False)

        assert all(row.registry_size == 300 for row in summary.targets)


class TestLayerCountSource:
    """`Layers` has to mean one thing regardless of flags: the local rootfs diff-ID count and
    the registry manifest's blob count measure different things (a metadata-only layer has a
    blob but no diff ID), so precedence can't be 'whichever ran first'."""

    def test_registry_manifest_count_wins_over_the_local_diff_id_count(self, get_targets):
        targets = get_targets("basic")
        summary = BuildSummary.from_image_targets(targets)

        def _fake_run(runner_self, cmd, **kwargs):
            return _completed(stdout=SINGLE_PLATFORM_MANIFEST_JSON)  # 2 layers

        with (
            patch.object(CommandRunner, "run", _fake_run),
            patch("python_on_whales.docker.image.inspect", return_value=_fake_image(12_345, 3)),  # 3 rootfs diff IDs
        ):
            summary.measure_sizes(targets, push=True, load=True)

        assert all(row.local_size == 12_345 for row in summary.targets)
        assert all(row.registry_size == 300 for row in summary.targets)
        assert all(row.layers == 2 for row in summary.targets)

    def test_falls_back_to_the_local_count_when_the_registry_is_unavailable(self, get_targets):
        targets = get_targets("basic")
        summary = BuildSummary.from_image_targets(targets)

        with patch("python_on_whales.docker.image.inspect", return_value=_fake_image(12_345, 3)):
            summary.measure_sizes(targets, push=False, load=True)

        assert all(row.layers == 3 for row in summary.targets)


class TestFromImageTargetsPerTargetRows:
    def test_builds_one_row_per_target_with_identity_and_counts(self, get_targets):
        targets = get_targets("basic")
        summary = BuildSummary.from_image_targets(targets)

        assert len(summary.targets) == len(targets)
        row = summary.targets[0]
        target = targets[0]
        assert row.uid == target.uid
        assert row.image_name == target.image_name
        assert row.version == target.image_version.name
        assert row.tags == len(target.tags)
        assert row.layers is None
        assert row.registry_size is None
        assert row.local_size is None

    def test_platform_override_is_reflected_per_target_row(self, get_targets):
        targets = get_targets("multiplatform")
        summary = BuildSummary.from_image_targets(targets, platforms=["linux/arm64"])

        assert all(row.platforms == 1 for row in summary.targets)


class TestFromImageTargetsCacheRef:
    def test_cache_ref_is_none_without_cache_registry(self, get_targets):
        targets = get_targets("basic")
        summary = BuildSummary.from_image_targets(targets)

        assert all(row.cache_ref is None for row in summary.targets)

    def test_cache_ref_matches_cache_name_for_the_targets_own_platform(self, get_targets):
        """No --image-platform override: a single-platform target's cache tag is suffixed
        with its one platform, mirroring ImageTarget.build()'s own cache_platform selection."""
        targets = get_targets("basic")
        for target in targets:
            target.settings.cache_registry = "ghcr.io/posit-dev"

        summary = BuildSummary.from_image_targets(targets)

        for row, target in zip(summary.targets, targets):
            platforms = target.image_os.platforms
            expected_platform = platforms[0] if len(platforms) == 1 else None
            assert row.cache_ref == target.cache_name(platform=expected_platform)
            assert row.cache_ref is not None

    def test_cache_ref_is_unsuffixed_for_a_true_multiplatform_target(self, get_targets):
        targets = get_targets("multiplatform")
        for target in targets:
            target.settings.cache_registry = "ghcr.io/posit-dev"

        summary = BuildSummary.from_image_targets(targets)

        multi = [t for t in targets if len(t.image_os.platforms) > 1]
        single = [t for t in targets if len(t.image_os.platforms) == 1]
        assert multi and single  # sanity: the fixture must actually exercise both shapes

        rows_by_uid = {row.uid: row for row in summary.targets}
        for target in multi:
            assert rows_by_uid[target.uid].cache_ref == target.cache_name(platform=None)
        for target in single:
            assert rows_by_uid[target.uid].cache_ref == target.cache_name(platform=target.image_os.platforms[0])

    def test_cache_ref_honors_the_image_platform_override(self, get_targets):
        """--image-platform is an any-match filter, not a narrowing one (config/config.py),
        so a target's own declared platform list is untouched; the override still forces
        every target's *cache* platform uniformly, exactly like a real build call does."""
        targets = get_targets("multiplatform")
        for target in targets:
            target.settings.cache_registry = "ghcr.io/posit-dev"

        summary = BuildSummary.from_image_targets(targets, platforms=["linux/arm64"])

        for row, target in zip(summary.targets, targets):
            assert row.cache_ref == target.cache_name(platform="linux/arm64")


class TestTableSizesView:
    def _row(self, **overrides):
        defaults = dict(
            uid="u",
            image_name="connect",
            version="2026.01.1",
            os="Ubuntu 24.04",
            variant="Standard",
            platforms=1,
            tags=8,
        )
        defaults.update(overrides)
        return BuildSummaryTarget(**defaults)

    def _cell(self, table, row_index, header):
        column = next(c for c in table.columns if c.header == header)
        return str(list(column.cells)[row_index])

    def test_dash_for_unmeasured_sizes(self):
        summary = BuildSummary(rows=[], targets=[self._row(uid="a")])
        table = summary.table(sizes=True)

        assert self._cell(table, 0, "Registry Size") == "—"
        assert self._cell(table, 0, "Local Size") == "—"
        assert self._cell(table, 0, "Layers") == "—"
        assert self._cell(table, 0, "Cache Size") == "—"

    def test_real_sizes_are_formatted_and_total_row_sums_them(self):
        summary = BuildSummary(
            rows=[],
            targets=[
                self._row(
                    uid="a",
                    variant="Standard",
                    registry_size=1_100_000_000,
                    local_size=2_900_000_000,
                    layers=8,
                    cache_ref="ghcr.io/posit-dev/connect/cache:std",
                    cache_size=300_000_000,
                ),
                self._row(
                    uid="b",
                    variant="Minimal",
                    registry_size=400_000_000,
                    local_size=1_000_000_000,
                    layers=6,
                    cache_ref="ghcr.io/posit-dev/connect/cache:min",
                    cache_size=200_000_000,
                ),
            ],
        )
        table = summary.table(sizes=True)

        # table() sorts by (image, version, os, variant); "Minimal" < "Standard" alphabetically,
        # so Minimal is row 0 here, not insertion order.
        assert self._cell(table, 0, "Registry Size") == "400.0 MB"  # Minimal
        assert self._cell(table, 1, "Registry Size") == "1.1 GB"  # Standard
        assert self._cell(table, 2, "Registry Size") == "1.5 GB"  # Total row
        assert self._cell(table, 2, "Local Size") == "3.9 GB"
        assert self._cell(table, 2, "Layers") == ""  # summing layer counts isn't meaningful
        assert self._cell(table, 0, "Cache Size") == "200.0 MB"  # Minimal
        assert self._cell(table, 1, "Cache Size") == "300.0 MB"  # Standard
        assert self._cell(table, 2, "Cache Size") == "500.0 MB"  # Total row

    def test_total_row_dedupes_a_cache_ref_shared_by_two_targets(self):
        """A true multi-platform target's un-suffixed cache tag can be shared by more than
        one row (e.g. two dev builds whose version differs only in build metadata that
        `cache_name()` strips) -- the Total row must count it once, not once per row."""
        shared_ref = "ghcr.io/posit-dev/connect/cache:shared"
        summary = BuildSummary(
            rows=[],
            targets=[
                self._row(uid="a", variant="Standard", cache_ref=shared_ref, cache_size=300_000_000),
                self._row(uid="b", variant="Minimal", cache_ref=shared_ref, cache_size=300_000_000),
            ],
        )
        table = summary.table(sizes=True)

        assert self._cell(table, 0, "Cache Size") == "300.0 MB"  # Minimal
        assert self._cell(table, 1, "Cache Size") == "300.0 MB"  # Standard
        assert self._cell(table, 2, "Cache Size") == "300.0 MB"  # Total row: not 600.0 MB

    def test_total_row_is_dash_when_nothing_was_measured(self):
        summary = BuildSummary(rows=[], targets=[self._row(uid="a"), self._row(uid="b", variant="Minimal")])
        table = summary.table(sizes=True)

        assert self._cell(table, 2, "Registry Size") == "—"
        assert self._cell(table, 2, "Local Size") == "—"
        assert self._cell(table, 2, "Cache Size") == "—"

    def test_partial_measurement_does_not_poison_the_total(self):
        """One target failing to measure must not blank the whole Total row -- the
        successes still sum."""
        summary = BuildSummary(
            rows=[],
            targets=[
                self._row(uid="a", variant="Standard", registry_size=1_000_000_000),
                self._row(uid="b", variant="Minimal", registry_size=None),
            ],
        )
        table = summary.table(sizes=True)

        assert self._cell(table, 2, "Registry Size") == "1.0 GB"


class TestAsDict:
    def test_includes_size_totals_and_per_target_breakdown(self):
        summary = BuildSummary(
            rows=[],
            targets=[
                BuildSummaryTarget(
                    uid="a",
                    image_name="connect",
                    version="1.0",
                    os="Ubuntu 24.04",
                    variant="Standard",
                    platforms=1,
                    tags=8,
                    registry_size=100,
                    local_size=200,
                    cache_ref="ghcr.io/posit-dev/connect/cache:std",
                    cache_size=300,
                )
            ],
        )
        data = summary.as_dict()

        assert data["registry_size_bytes"] == 100
        assert data["local_size_bytes"] == 200
        assert data["cache_size_bytes"] == 300
        assert data["targets"][0]["uid"] == "a"
        assert data["targets"][0]["cache_ref"] == "ghcr.io/posit-dev/connect/cache:std"

    def test_size_totals_are_null_not_zero_when_nothing_measured(self):
        summary = BuildSummary(
            rows=[],
            targets=[
                BuildSummaryTarget(uid="a", image_name="c", version="1.0", os="", variant="", platforms=1, tags=1)
            ],
        )
        data = summary.as_dict()

        assert data["registry_size_bytes"] is None
        assert data["local_size_bytes"] is None
        assert data["cache_size_bytes"] is None

    def test_cache_size_bytes_dedupes_a_shared_cache_ref(self):
        shared_ref = "ghcr.io/posit-dev/connect/cache:shared"
        summary = BuildSummary(
            rows=[],
            targets=[
                BuildSummaryTarget(
                    uid="a",
                    image_name="c",
                    version="1.0",
                    os="",
                    variant="Standard",
                    platforms=1,
                    tags=1,
                    cache_ref=shared_ref,
                    cache_size=300,
                ),
                BuildSummaryTarget(
                    uid="b",
                    image_name="c",
                    version="1.0",
                    os="",
                    variant="Minimal",
                    platforms=1,
                    tags=1,
                    cache_ref=shared_ref,
                    cache_size=300,
                ),
            ],
        )
        data = summary.as_dict()

        assert data["cache_size_bytes"] == 300  # not 600


class TestFromJsonFile:
    def test_reconstructs_targets_and_recomputes_rows(self, tmp_path):
        path = tmp_path / "a-summary.json"
        path.write_text(
            json.dumps(
                {
                    "build_targets": 1,
                    "platform_builds": 1,
                    "registry_tags": 8,
                    "registry_size_bytes": 100,
                    "local_size_bytes": 200,
                    "cache_size_bytes": None,
                    "targets": [
                        {
                            "uid": "a",
                            "image_name": "connect",
                            "version": "2026.01.1",
                            "os": "Ubuntu 24.04",
                            "variant": "Standard",
                            "platforms": 1,
                            "tags": 8,
                            "layers": 10,
                            "registry_size": 100,
                            "local_size": 200,
                            "cache_ref": None,
                            "cache_size": None,
                        }
                    ],
                }
            )
        )

        summary = BuildSummary.from_json_file(path)

        assert [t.uid for t in summary.targets] == ["a"]
        assert {row.key: row.value for row in summary.rows} == {
            "build_targets": 1,
            "platform_builds": 1,
            "registry_tags": 8,
        }


class TestMerge:
    def _target(self, **overrides):
        defaults = dict(
            uid="a",
            image_name="connect",
            version="2026.01.1",
            os="Ubuntu 24.04",
            variant="Standard",
            platforms=1,
            tags=8,
        )
        defaults.update(overrides)
        return BuildSummaryTarget(**defaults)

    def test_single_summary_round_trips_unchanged(self):
        summary = BuildSummary(rows=[], targets=[self._target()])

        merged = BuildSummary.merge([summary])

        assert len(merged.targets) == 1
        assert merged.targets[0].uid == "a"

    def test_platform_slices_of_the_same_uid_sum_not_double_count(self):
        """Two per-platform files for the same multi-platform target must not double
        `build_targets`/`registry_tags` -- only `platforms`/`registry_size` sum."""
        amd64 = BuildSummary(
            rows=[],
            targets=[self._target(platforms=1, tags=8, registry_size=100, local_size=200)],
        )
        arm64 = BuildSummary(
            rows=[],
            targets=[self._target(platforms=1, tags=8, registry_size=150, local_size=250)],
        )

        merged = BuildSummary.merge([amd64, arm64])

        assert len(merged.targets) == 1
        row = merged.targets[0]
        assert row.platforms == 2
        assert row.registry_size == 250
        assert row.local_size == 450
        assert row.tags == 8  # identity field: not summed
        aggregate = {row.key: row.value for row in merged.rows}
        assert aggregate["build_targets"] == 1  # one distinct uid, not two
        assert aggregate["platform_builds"] == 2
        assert aggregate["registry_tags"] == 8  # not 16

    def test_distinct_uids_across_files_both_survive(self):
        first = BuildSummary(rows=[], targets=[self._target(uid="a")])
        second = BuildSummary(rows=[], targets=[self._target(uid="b", variant="Minimal")])

        merged = BuildSummary.merge([first, second])

        assert {t.uid for t in merged.targets} == {"a", "b"}
        aggregate = {row.key: row.value for row in merged.rows}
        assert aggregate["build_targets"] == 2

    def test_layers_take_first_non_none_slice(self):
        no_layers = BuildSummary(rows=[], targets=[self._target(layers=None)])
        with_layers = BuildSummary(rows=[], targets=[self._target(layers=12)])

        merged = BuildSummary.merge([no_layers, with_layers])

        assert merged.targets[0].layers == 12

    def test_cache_size_deduped_by_shared_cache_ref_after_merge(self):
        """Two platform slices of the same uid can carry the same unsuffixed cache_ref
        (`ImageTarget.cache_name()` for a true multi-platform target) -- merging must not
        sum the same cache blob twice."""
        shared_ref = "ghcr.io/posit-dev/connect/cache:shared"
        amd64 = BuildSummary(rows=[], targets=[self._target(cache_ref=shared_ref, cache_size=300_000_000)])
        arm64 = BuildSummary(rows=[], targets=[self._target(cache_ref=shared_ref, cache_size=300_000_000)])

        merged = BuildSummary.merge([amd64, arm64])

        assert merged.targets[0].cache_ref == shared_ref
        assert merged.targets[0].cache_size == 300_000_000  # first slice's value, not summed


class TestToMarkdown:
    def _target(self, **overrides):
        defaults = dict(
            uid="a",
            image_name="connect",
            version="2026.01.1",
            os="Ubuntu 24.04",
            variant="Standard",
            platforms=1,
            tags=8,
        )
        defaults.update(overrides)
        return BuildSummaryTarget(**defaults)

    def test_renders_a_row_per_target_and_a_total_row(self):
        summary = BuildSummary(
            rows=[],
            targets=[
                self._target(uid="a", variant="Standard", registry_size=1_000_000_000, layers=8),
                self._target(uid="b", variant="Minimal", registry_size=500_000_000, layers=6),
            ],
        )

        markdown = summary.to_markdown()

        assert "connect" in markdown
        assert "Standard" in markdown
        assert "Minimal" in markdown
        assert "1.0 GB" in markdown
        assert "**Total" in markdown
        assert "1.5 GB" in markdown  # summed registry size

    def test_unmeasured_size_renders_as_dash_not_zero(self):
        summary = BuildSummary(rows=[], targets=[self._target()])

        markdown = summary.to_markdown()

        assert "—" in markdown

    def test_no_disclaimer_by_default(self):
        summary = BuildSummary(rows=[], targets=[self._target()])

        markdown = summary.to_markdown()

        assert "⚠️" not in markdown

    def test_disclaimer_is_prepended_as_a_banner(self):
        summary = BuildSummary(rows=[], targets=[self._target()])

        markdown = summary.to_markdown(disclaimer="This summary is incomplete.")

        assert markdown.index("⚠️") < markdown.index("| Image |")
        assert "This summary is incomplete." in markdown
