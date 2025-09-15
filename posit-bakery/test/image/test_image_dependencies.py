from pydantic import BaseModel
import pytest

from posit_bakery.config.dependencies import DependencyVersion, DependencyConstraintField, DependencyVersionsField
from posit_bakery.config.image import Image, ImageVersion


class TestImageDependencyConstraints:
    @pytest.mark.parametrize(
        "constraints",
        [
            [{"dependency": "R", "constraint": {"latest": True}}],
        ],
    )
    def test_dependency_constraint_valid(self, constraints):
        img = Image(
            **{
                "name": "test-image",
                "dependencyConstraints": constraints,
            }
        )

    def test_dependency_versions_invalid(self):
        """Test that passing versions instead of constraints fails validation."""
        with pytest.raises(ValueError):
            Image(
                **{
                    "name": "test-image",
                    "dependencyConstraints": [{"dependency": "R", "versions": ["4.5.1"]}],
                }
            )


class TestImageDependencyVersions:
    @pytest.mark.parametrize(
        "dependencies",
        [
            pytest.param(
                [{"dependency": "R", "versions": ["4.5.1"]}],
                id="r_single",
            ),
            pytest.param(
                [{"dependency": "R", "versions": ["4.4.3", "4.2.1"]}],
                id="r_multiple",
            ),
        ],
    )
    def test_dependency_versions_valid(self, dependencies):
        """Test that a valid dependency versions list is accepted."""
        ver = ImageVersion(
            **{
                "name": "test-image",
                "dependencies": dependencies,
            }
        )

    def test_dependency_constraint_invalid(self):
        """Test that passing versions instead of constraints fails validation."""
        with pytest.raises(ValueError):
            ImageVersion(
                **{
                    "name": "test-image",
                    "dependencies": [{"dependency": "python", "constraint": {"latest": True}}],
                }
            )
