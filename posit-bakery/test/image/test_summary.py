import json
import subprocess
from unittest.mock import MagicMock, patch

from python_on_whales.components.buildx.imagetools.models import Manifest

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


LOCAL_INSPECT_JSON = json.dumps(
    [{"Size": 12_345, "RootFS": {"Type": "layers", "Layers": ["sha256:a", "sha256:b", "sha256:c"]}}]
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


class TestInspectLocal:
    def test_parses_size_and_returns_result(self):
        runner = _FakeRunner({("local", "myimage:tag"): _completed(stdout=LOCAL_INSPECT_JSON)})
        result = _inspect_local(runner, "myimage:tag")

        assert result is not None
        assert result.size == 12_345

    def test_returns_none_on_nonzero_exit(self):
        runner = _FakeRunner({("local", "myimage:tag"): _completed(returncode=1, stderr=b"no such image")})
        assert _inspect_local(runner, "myimage:tag") is None

    def test_returns_none_on_unparseable_output(self):
        runner = _FakeRunner({("local", "myimage:tag"): _completed(stdout=b"not json")})
        assert _inspect_local(runner, "myimage:tag") is None


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


def _fake_run_local_only(runner_self, cmd, **kwargs):
    if "buildx" in cmd:
        return _completed(returncode=1, stderr=b"push=False, registry inspect should not be reachable")
    return _completed(stdout=LOCAL_INSPECT_JSON)


class TestMeasureSizesEndToEnd:
    """Exercises the real ParallelShellExecutor/ShellJob/CommandRunner wiring; only the
    actual subprocess spawn (CommandRunner.run) is replaced."""

    def test_populates_local_size_and_layers_for_real_targets(self, get_targets):
        targets = get_targets("basic")
        summary = BuildSummary.from_image_targets(targets)

        with patch.object(CommandRunner, "run", _fake_run_local_only):
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

        def _fake_run(runner_self, cmd, **kwargs):
            if "buildx" in cmd:
                return _completed(returncode=1)
            size = sizes_by_ref[cmd[-1]]
            return _completed(stdout=json.dumps([{"Size": size, "RootFS": {"Layers": []}}]).encode())

        with patch.object(CommandRunner, "run", _fake_run):
            summary.measure_sizes(targets, push=False, load=True)

        rows_by_uid = {row.uid: row for row in summary.targets}
        for i, target in enumerate(targets):
            assert rows_by_uid[target.uid].local_size == 1000 * (i + 1)

    def test_registry_hiccup_leaves_dash_and_does_not_raise(self, get_targets):
        targets = get_targets("basic")
        summary = BuildSummary.from_image_targets(targets)

        def _fake_run(runner_self, cmd, **kwargs):
            return _completed(returncode=1, stderr=b"connection reset")

        with patch.object(CommandRunner, "run", _fake_run):
            summary.measure_sizes(targets, push=True, load=True)  # must not raise

        assert all(row.registry_size is None for row in summary.targets)
        assert all(row.local_size is None for row in summary.targets)


def _fake_run_registry_fails(runner_self, cmd, **kwargs):
    return _completed(returncode=1, stderr=b"not found")


class TestMeasureSizesCache:
    def _summary_with_cache_ref(self, get_targets, suite="basic"):
        targets = get_targets(suite)
        for target in targets:
            target.settings.cache_registry = "ghcr.io/posit-dev"
        return targets, BuildSummary.from_image_targets(targets)

    def test_measured_when_push_is_false_but_cache_ref_present(self, get_targets):
        """A pull-only build (`push=False`) still resolves `cache_from` against whatever is
        currently at `cache_ref` -- the registry lookup needs a `cache_ref` to query, not
        this build to have pushed anything, so it must not be gated on `push`."""
        targets, summary = self._summary_with_cache_ref(get_targets)
        mock_client = MagicMock()
        mock_client.get_manifest.return_value = Manifest(**json.loads(SINGLE_PLATFORM_MANIFEST_JSON))

        with patch("posit_bakery.image.summary.GHCRManifestClient", return_value=mock_client):
            with patch.object(CommandRunner, "run", _fake_run_registry_fails):
                summary.measure_sizes(targets, push=False, load=False)

        assert all(row.cache_size == 300 for row in summary.targets)
        assert all(row.registry_size is None for row in summary.targets)

    def test_measured_when_push_is_true(self, get_targets):
        targets, summary = self._summary_with_cache_ref(get_targets)
        mock_client = MagicMock()
        mock_client.get_manifest.return_value = Manifest(**json.loads(SINGLE_PLATFORM_MANIFEST_JSON))

        with patch("posit_bakery.image.summary.GHCRManifestClient", return_value=mock_client):
            with patch.object(CommandRunner, "run", _fake_run_registry_fails):
                summary.measure_sizes(targets, push=True, load=False)

        assert all(row.cache_size == 300 for row in summary.targets)

    def test_stays_none_without_a_cache_ref(self, get_targets):
        targets = get_targets("basic")  # no cache_registry set -> cache_ref is None
        summary = BuildSummary.from_image_targets(targets)

        with patch("posit_bakery.image.summary.GHCRManifestClient") as mock_client_cls:
            with patch.object(CommandRunner, "run", _fake_run_registry_fails):
                summary.measure_sizes(targets, push=True, load=False)

        mock_client_cls.assert_not_called()
        assert all(row.cache_size is None for row in summary.targets)

    def test_missing_token_disables_cache_measurement_without_raising(self, get_targets):
        targets, summary = self._summary_with_cache_ref(get_targets)

        with patch("posit_bakery.image.summary.GHCRManifestClient", side_effect=ValueError("no token")):
            with patch.object(CommandRunner, "run", _fake_run_local_only):
                summary.measure_sizes(targets, push=True, load=True)  # must not raise

        assert all(row.cache_size is None for row in summary.targets)
        assert all(row.local_size == 12_345 for row in summary.targets)  # local measurement unaffected

    def test_manifest_fetch_failure_leaves_dash_and_does_not_raise(self, get_targets):
        targets, summary = self._summary_with_cache_ref(get_targets)
        mock_client = MagicMock()
        mock_client.get_manifest.return_value = None

        with patch("posit_bakery.image.summary.GHCRManifestClient", return_value=mock_client):
            with patch.object(CommandRunner, "run", _fake_run_registry_fails):
                summary.measure_sizes(targets, push=True, load=False)  # must not raise

        assert all(row.cache_size is None for row in summary.targets)


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
