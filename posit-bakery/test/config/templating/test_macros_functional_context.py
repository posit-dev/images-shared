"""Structural checks for the macros-functional blackbox test context.

The images in this context are only built and tested by the CI blackbox job. These
fast checks catch layout mistakes that would otherwise surface there as confusing
failures, or silently reduce coverage.
"""

import pytest

from posit_bakery.config import BakeryConfig

pytestmark = [
    pytest.mark.unit,
]


@pytest.fixture(scope="module")
def macros_functional_images(resource_path):
    return BakeryConfig.from_context(resource_path / "macros-functional").model.images


def test_every_variant_has_a_goss_scenario(macros_functional_images):
    """goss.yaml includes test/scenarios/<variant name>.yaml; a missing file fails dgoss."""
    for image in macros_functional_images:
        scenarios_path = image.template_path / "test" / "scenarios"
        scenarios = {p.name.removesuffix(".jinja2").removesuffix(".yaml") for p in scenarios_path.iterdir()}
        variants = {v.name for v in image.variants}
        assert scenarios == variants, f"{image.name}: scenarios {sorted(scenarios)} != variants {sorted(variants)}"


def test_every_os_has_an_identical_containerfile(macros_functional_images):
    """Each OS must run the same scenarios, so per-OS Containerfile templates must not diverge."""
    for image in macros_functional_images:
        containerfiles = {
            p.name.split(".")[1]: p.read_text() for p in image.template_path.glob("Containerfile.*.jinja2")
        }
        for version in image.versions:
            assert set(containerfiles) == {os.extension for os in version.os}, image.name
        assert len(set(containerfiles.values())) == 1, f"{image.name}: Containerfile templates differ between OSes"
