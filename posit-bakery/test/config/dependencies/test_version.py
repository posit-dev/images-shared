import itertools

import pytest


pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
    pytest.mark.dependency,
]

from posit_bakery.config.dependencies.version import DependencyVersion, VersionConstraint

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
        assert ver.has_minor == has_minor
        assert ver.has_micro == has_micro

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
            assert ver.has_minor
            assert ver.has_micro


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
