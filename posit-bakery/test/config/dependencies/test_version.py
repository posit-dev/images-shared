import itertools

import pytest

from posit_bakery.config.dependencies.version import DependencyVersion, VersionConstraint


pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
    pytest.mark.dependency,
]

# Posit python-builds as of 2025-08-20
PYTHON_VERSIONS: list[str] = list(
    itertools.chain.from_iterable(
        [
            [f"3.9.{p}" for p in range(24)],  # 3.9.0 to 3.9.23
            [f"3.10.{p}" for p in range(19)],  # 3.10.0 to 3.10.18
            [f"3.11.{p}" for p in range(14)],  # 3.11.0 to 3.11.13
            [f"3.12.{p}" for p in range(12)],  # 3.12.0 to 3.12.11
            [f"3.13.{p}" for p in range(8)],  # 3.13.0 to 3.13.7
        ]
    )
)
assert len(PYTHON_VERSIONS) == 77
# Astral python-build-standalone releases only include the most recent patch
# https://github.com/astral-sh/python-build-standalone/releases/tag/20250818
ASTRAL_PYTHON_VERSIONS: list[str] = [
    "3.9.23",
    "3.10.18",
    "3.11.13",
    "3.12.11",
    "3.13.7",
]
# Posit r-builds as of 2025-08-20
R_VERSIONS: list[str] = list(
    itertools.chain.from_iterable(
        [
            [f"3.0.{p}" for p in range(4)],  # 3.0.0 to 3.0.3
            [f"3.1.{p}" for p in range(4)],  # 3.1.0 to 3.1.3
            [f"3.2.{p}" for p in range(6)],  # 3.2.0 to 3.2.5
            [f"3.3.{p}" for p in range(4)],  # 3.3.0 to 3.3.3
            [f"3.4.{p}" for p in range(5)],  # 3.4.0 to 3.4.4
            [f"3.5.{p}" for p in range(4)],  # 3.5.0 to 3.5.3
            [f"3.6.{p}" for p in range(4)],  # 3.6.0 to 3.6.3
            [f"4.0.{p}" for p in range(6)],  # 4.0.0 to 4.0.5
            [f"4.1.{p}" for p in range(4)],  # 4.1.0 to 4.1.3
            [f"4.2.{p}" for p in range(4)],  # 4.2.0 to 4.2.3
            [f"4.3.{p}" for p in range(4)],  # 4.3.0 to 4.3.3
            [f"4.4.{p}" for p in range(4)],  # 4.4.0 to 4.4.3
            [f"4.5.{p}" for p in range(2)],  # 4.5.0 to 4.5.1
        ]
    )
)
assert len(R_VERSIONS) == 55


class TestDependencyVersion:
    @pytest.mark.parametrize(
        "version,has_minor,has_micro",
        [
            pytest.param("1.0.0", True, True, id="full_version"),
            pytest.param("1.0", True, False, id="minor_only"),
            pytest.param("1", False, False, id="major_only"),
        ],
    )
    def test_dependency_version_valid(self, version, has_minor, has_micro):
        """Test that a valid dependency version is accepted and sets booleans correctly."""
        ver = DependencyVersion(version)

        assert ver.base_version == version
        assert (ver.minor is not None) == has_minor
        assert (ver.micro is not None) == has_micro

    def test_dependency_version_prefix(self):
        """Test that a version with a prefix is accepted."""
        ver = DependencyVersion("v1.2.3")

        assert ver.base_version == "1.2.3"
        assert ver.minor == 2
        assert ver.major == 1
        assert ver.micro == 3

    @pytest.mark.parametrize(
        "version_list",
        [
            pytest.param(PYTHON_VERSIONS, id="python-builds"),
            pytest.param(ASTRAL_PYTHON_VERSIONS, id="python-build-standalone"),
            pytest.param(R_VERSIONS, id="r-builds"),
        ],
    )
    def test_dependency_version_upstream(self, version_list):
        """Test that a list of upstream versions is valid"""
        for version in version_list:
            ver = DependencyVersion(version)

            # Base class attrs
            assert ver.base_version == version
            assert not ver.is_devrelease
            assert not ver.is_prerelease
            assert not ver.is_postrelease
            # Child class attrs
            assert ver.minor is not None
            assert ver.major is not None


class TestVersionConstraint:
    @pytest.mark.parametrize(
        "count,latest",
        [
            pytest.param(0, None, id="count_zero"),
            pytest.param(-15, None, id="count_negative"),
            pytest.param(None, 67, id="latest_int"),
            pytest.param(None, 3.14, id="latest_float"),
        ],
    )
    def test_version_constraint_invalid_values(self, count, latest):
        """Test that a version constraint with latest or count set passes validation."""
        with pytest.raises(ValueError):
            VersionConstraint(count=count, latest=latest)

    @pytest.mark.parametrize(
        "count,latest,max,min",
        [
            pytest.param(None, True, None, None, id="latest_only"),
            pytest.param(None, None, "2.0.0", None, id="max_only"),
            pytest.param(5, True, None, None, id="count_latest"),
            pytest.param(5, None, "3.0.0", None, id="count_max"),
            pytest.param(None, None, "3.0.0", "2.0.0", id="max_min"),
        ],
    )
    def test_version_constraint_minimal_definition(self, count, latest, max, min):
        """Test that a version constraint with latest, max, and min is mutually exclusive."""
        ver = VersionConstraint(count=count, latest=latest, max=max, min=min)

        # We exclude testing count because it may be computed from latest, max, and min.
        assert ver.latest == latest
        assert ver.max == max
        assert ver.min == min

    @pytest.mark.parametrize(
        "count,latest,max,min",
        [
            pytest.param(None, None, None, None, id="all_none"),
            pytest.param(5, None, None, None, id="count_only"),
            pytest.param(None, None, None, "2.0.0", id="min_only"),
        ],
    )
    def test_version_constraint_incomplete_definition(self, count, latest, max, min):
        """Test that an incomplete version constraint fails validation."""
        with pytest.raises(ValueError):
            VersionConstraint(count=count, latest=latest, max=max, min=min)

    @pytest.mark.parametrize(
        "count,latest,max,min",
        [
            pytest.param(None, True, "3.0.0", None, id="latest_max"),
            pytest.param(5, True, None, "2.0.0", id="latest_max_min"),
            pytest.param(5, None, "3.0.0", "2.0.0", id="count_max_min"),
        ],
    )
    def test_version_constraint_mutually_exclusive(self, count, latest, max, min):
        """Test that mutually exclusive fields in a version constraint raise ValueError."""
        with pytest.raises(ValueError):
            VersionConstraint(count=count, latest=latest, max=max, min=min)

    @pytest.mark.parametrize(
        "count,latest,max,min",
        [
            pytest.param(None, None, "2.0.0", "3.0.0", id="max-min-inverted"),
        ],
    )
    def test_version_constraint_combo_invalid(self, count, latest, max, min):
        """Test that a version constraint with an invalid combination raises ValueError."""
        with pytest.raises(ValueError):
            VersionConstraint(count=count, latest=latest, max=max, min=min)


class TestDepencencyConstraintResolution:
    @pytest.mark.parametrize(
        "available_versions,expected_version",
        [
            pytest.param(["4.5.1"], "4.5.1", id="r-single"),
            pytest.param(["4.3.3", "4.4.3", "4.5.1"], "4.5.1", id="r-multiple"),
            pytest.param(["4.4.3", "3.6.1", "4.2.1"], "4.4.3", id="r-unsorted"),
            pytest.param(["3.13.7"], "3.13.7", id="python-single"),
            pytest.param(["3.11.13", "3.12.11", "3.13.7"], "3.13.7", id="python-multiple"),
        ],
    )
    def test_resolve_latest(self, available_versions: list[str], expected_version: str):
        """Test resolving a version constraint with latest=True."""
        constraint = VersionConstraint(latest=True)
        versions = constraint.resolve_versions([DependencyVersion(v) for v in available_versions])

        assert len(versions) == 1
        assert versions[0] == DependencyVersion(expected_version)

    @pytest.mark.parametrize(
        "count,available_versions,expected_versions",
        [
            # These test cases have a single patch version per minor version
            pytest.param(1, ["4.5.1"], ["4.5.1"], id="r-single-1"),
            pytest.param(2, ["4.3.3", "4.4.3", "4.5.1"], ["4.5.1", "4.4.3"], id="r-multiple-2"),
            pytest.param(3, ["4.3.3", "4.4.3", "4.5.1"], ["4.5.1", "4.4.3", "4.3.3"], id="r-multiple-3"),
            pytest.param(1, ["3.13.7"], ["3.13.7"], id="python-single-1"),
            pytest.param(2, ["3.11.13", "3.12.11", "3.13.7"], ["3.13.7", "3.12.11"], id="python-multiple-2"),
            pytest.param(3, ["3.11.13", "3.12.11", "3.13.7"], ["3.13.7", "3.12.11", "3.11.13"], id="python-multiple-3"),
            # These tests cases have multiple patch versions with the same minor version
            # Use the contant versions that were retreived from upstream on 2025-08-20
            pytest.param(1, R_VERSIONS, ["4.5.1"], id="r-upstream-1"),
            pytest.param(2, R_VERSIONS, ["4.5.1", "4.4.3"], id="r-upstream-2"),
            pytest.param(
                7, R_VERSIONS, ["4.5.1", "4.4.3", "4.3.3", "4.2.3", "4.1.3", "4.0.5", "3.6.3"], id="r-upstream-1"
            ),
            pytest.param(1, PYTHON_VERSIONS, ["3.13.7"], id="python-upstream-1"),
            pytest.param(2, PYTHON_VERSIONS, ["3.13.7", "3.12.11"], id="python-upstream-2"),
            pytest.param(
                5, PYTHON_VERSIONS, ["3.13.7", "3.12.11", "3.11.13", "3.10.18", "3.9.23"], id="python-upstream-5"
            ),
            pytest.param(1, ASTRAL_PYTHON_VERSIONS, ["3.13.7"], id="astral-python-upstream-1"),
            pytest.param(3, ASTRAL_PYTHON_VERSIONS, ["3.13.7", "3.12.11", "3.11.13"], id="astral-python-upstream-3"),
        ],
    )
    def test_resolve_latest_count(self, count: int, available_versions: list[str], expected_versions: list[str]):
        """Test resolving a version constraint with latest=True and count set."""
        constraint = VersionConstraint(count=count, latest=True)
        versions = constraint.resolve_versions([DependencyVersion(v) for v in available_versions])

        assert len(versions) == len(expected_versions)
        assert versions == [DependencyVersion(v) for v in expected_versions]

    @pytest.mark.parametrize(
        "max,available_versions,expected_version,expected_count",
        [
            # Test constrainst specifying a full version
            pytest.param("1.1.0", ["1.0.0", "1.0.1", "1.1.0"], "1.1.0", 2, id="full-exact"),
            pytest.param("1.0.0", ["1.0.0", "1.0.1", "1.1.0"], "1.0.0", 1, id="full-low-filter"),
            pytest.param("1.0.1", ["1.0.0", "1.0.1", "1.1.0"], "1.0.1", 1, id="full-mid-filter"),
            pytest.param("2.0.0", ["1.1.0", "1.0.1", "1.1.0"], "1.1.0", 2, id="full-major-filter"),
            pytest.param(
                "1.0.0", ["0.9.1", "0.9.0", "0.8.1", "0.8.0", "0.7.2", "0.7.1"], "0.9.1", 3, id="full-multi-patch"
            ),
            pytest.param(
                "0.9.0", ["0.9.1", "0.9.0", "0.8.1", "0.8.0", "0.7.2", "0.7.1"], "0.9.0", 3, id="full-multi-patch"
            ),
            # Test constraints that specify a minor version
            pytest.param("2.5", ["2.4.0", "2.5.0", "2.6.0"], "2.5.0", 2, id="minor-exact"),
            pytest.param("2.5", ["2.4.0", "2.4.1", "2.5.0", "2.5.1", "2.6.0"], "2.5.1", 2, id="minor-multiple"),
            pytest.param(
                "3.1", ["3.0.0", "3.0.1", "3.1.0", "3.1.1", "3.1.2", "3.1.3", "3.1.4"], "3.1.4", 2, id="minor-many"
            ),
            # Test constraints that specify only a major version
            pytest.param("3", ["2.9.0", "3.0.0", "3.1.0", "3.2.0", "4.0.0"], "3.2.0", 4, id="major-exact"),
            pytest.param(
                "3",
                ["2.9.0", "2.9.1", "3.0.0", "3.0.1", "3.1.0", "3.1.1", "3.2.0", "3.2.1"],
                "3.2.1",
                4,
                id="major-many",
            ),
        ],
    )
    def test_resolve_max(self, max: str, available_versions: list[str], expected_version: str, expected_count: int):
        """Test resolving a version constraint with max set."""
        # Set count very high
        constraint = VersionConstraint(max=max)
        versions = constraint.resolve_versions([DependencyVersion(v) for v in available_versions])

        assert len(versions) == expected_count
        # Max should be listed first
        assert versions[0] == DependencyVersion(expected_version)

    @pytest.mark.parametrize(
        "min,available_versions,expected_version,expected_count",
        [
            pytest.param("1.0.0", ["1.0.0", "1.1.0"], "1.0.0", 2, id="exact"),
            pytest.param("1.0.0", ["0.9.0", "1.0.0", "1.1.1", "1.1.2", "1.1.0"], "1.0.0", 2, id="major-filter"),
            pytest.param("1.0.1", ["1.0.0", "1.0.1", "1.1.0", "1.2.0", "1.2.1"], "1.0.1", 3, id="patch-filter"),
            pytest.param("1.1.0", ["1.0.0", "1.0.1", "1.1.0"], "1.1.0", 1, id="minor-filter"),
        ],
    )
    def test_resolve_min(self, min: str, available_versions: list[str], expected_version: str, expected_count: int):
        """Test resolving a version constraint with min set."""
        # Set count very high
        constraint = VersionConstraint(latest=True, min=min)
        versions = constraint.resolve_versions([DependencyVersion(v) for v in available_versions])

        assert len(versions) == expected_count
        # Min should be listed last
        assert versions[-1] == DependencyVersion(expected_version)
