import pytest

from posit_bakery.config.dependencies import PythonDependencyVersions, RDependencyVersions, QuartoDependencyVersions
from posit_bakery.config.image.matrix import generate_default_name_pattern


@pytest.mark.parametrize(
    "data,expected",
    [
        pytest.param(
            {},
            ValueError,
            id="no-parameters",
        ),
        pytest.param(
            {
                "dependencies": [
                    PythonDependencyVersions(
                        dependency="python",
                        versions=["3.8", "3.9", "3.10"],
                    ),
                ],
            },
            "{{ Dependencies.python }}",
            id="one-dependency",
        ),
        pytest.param(
            {
                "dependencies": [
                    PythonDependencyVersions(
                        dependency="python",
                        versions=["3.8", "3.9", "3.10"],
                    ),
                    RDependencyVersions(
                        dependency="R",
                        versions=["4.0", "4.1"],
                    ),
                    QuartoDependencyVersions(
                        dependency="quarto",
                        versions=["1.2", "1.3"],
                    ),
                ],
            },
            "{{ Dependencies.python }}-{{ Dependencies.R }}-{{ Dependencies.quarto }}",
            id="multiple-dependencies",
        ),
        pytest.param(
            {
                "values": {"go_version": ["1.24", "1.25"]},
            },
            "{{ Values.go_version }}",
            id="one-value",
        ),
        pytest.param(
            {
                "values": {"go_version": ["1.24", "1.25"], "pro_drivers_version": "2025.07.0"},
            },
            "{{ Values.go_version }}-{{ Values.pro_drivers_version }}",
            id="multiple-values",
        ),
        pytest.param(
            {
                "dependencies": [
                    PythonDependencyVersions(
                        dependency="python",
                        versions=["3.8", "3.9", "3.10"],
                    ),
                    RDependencyVersions(
                        dependency="R",
                        versions=["4.0", "4.1"],
                    ),
                ],
                "values": {"go_version": ["1.24", "1.25"]},
            },
            "{{ Dependencies.python }}-{{ Dependencies.R }}-{{ Values.go_version }}",
            id="dependencies-and-values",
        ),
    ],
)
def test_generate_default_name_pattern(data, expected):
    if expected is ValueError:
        with pytest.raises(expected):
            generate_default_name_pattern(data)
    else:
        pattern = generate_default_name_pattern(data)
        assert pattern == expected
