import pytest


from posit_bakery.config.dependencies.python import PythonDependencyConstraint
from posit_bakery.config.dependencies.quarto import QuartoDependencyConstraint
from posit_bakery.config.dependencies.r import RDependencyConstraint

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
    pytest.mark.dependency,
]


class TestDependencyConstraint:
    # See ./testdata/download-metadata.json for versions in mocked response
    @pytest.mark.parametrize(
        "constraint,expected_versions",
        [
            pytest.param({"latest": True}, ["3.13.7"], id="latest_only"),
            pytest.param(
                {"latest": True, "count": 5}, ["3.13.7", "3.12.11", "3.11.13", "3.10.18", "3.9.23"], id="latest_count_5"
            ),
            pytest.param({"max": "3", "count": 1}, ["3.13.7"], id="max_major"),
            pytest.param({"max": "3.10", "count": 1}, ["3.10.18"], id="max_minor"),
            pytest.param({"max": "3.11", "count": 2}, ["3.11.13", "3.10.18"], id="max_minor_count_2"),
            pytest.param({"max": "3.10.2", "count": 1}, ["3.10.2"], id="max_patch"),
            pytest.param({"max": "3.12", "min": "3.10"}, ["3.12.11", "3.11.13", "3.10.18"], id="min_max_minor"),
        ],
    )
    def test_python_constraints(self, patch_requests_get, constraint, expected_versions):
        """Test that a valid python dependency contsraint returns expected versions.

        This test mocks the request to fetch available python versions and checks
        that the constraint filtering logic works as expected.
        """

        dep = PythonDependencyConstraint(
            dependency="python",
            constraint=constraint,
        )

        vers = dep.resolve_versions()
        assert vers == expected_versions

    # See ./testdata/quarto_* for versions in mocked response
    @pytest.mark.parametrize(
        "constraint,prerelease,expected_versions",
        [
            pytest.param({"latest": True}, False, ["1.7.34"], id="latest_only"),
            pytest.param({"latest": True}, True, ["1.8.23"], id="latest_prerelease"),
            pytest.param({"max": "1.6", "count": 1}, False, ["1.6.43"], id="max_minor"),
        ],
    )
    def test_quarto_constraints(self, patch_requests_get, constraint, prerelease, expected_versions):
        """Test that a valid quarto dependency contsraint returns expected versions.

        This test mocks the request to fetch available quarto versions and checks
        that the constraint filtering logic works as expected.
        """

        dep = QuartoDependencyConstraint(
            dependency="quarto",
            prerelease=prerelease,
            constraint=constraint,
        )

        vers = dep.resolve_versions()
        assert vers == expected_versions

    # See ./testdata/quarto_* for versions in mocked response
    @pytest.mark.parametrize(
        "constraint,expected_versions",
        [
            pytest.param({"latest": True}, ["4.5.1"], id="latest_only"),
            pytest.param({"latest": True, "count": 2}, ["4.5.1", "4.4.3"], id="latest_count_2"),
            pytest.param({"latest": True, "min": "4.2"}, ["4.5.1", "4.4.3", "4.3.3", "4.2.3"], id="latest_min"),
            pytest.param({"max": "3", "count": 1}, ["3.6.3"], id="r_version_3"),
        ],
    )
    def test_r_constraints(self, patch_requests_get, constraint, expected_versions):
        """Test that a valid R dependency contsraint returns expected versions.

        This test mocks the request to fetch available R versions and checks
        that the constraint filtering logic works as expected.
        """

        dep = RDependencyConstraint(
            dependency="R",
            constraint=constraint,
        )

        vers = dep.resolve_versions()
        assert vers == expected_versions
