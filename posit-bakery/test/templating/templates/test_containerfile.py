import pytest

from posit_bakery.templating.filters import render_template
from posit_bakery.templating.templates.containerfile import TPL_CONTAINERFILE

pytestmark = [
    pytest.mark.unit,
]


def test_containerfile_template_render():
    containerfile_data = render_template(TPL_CONTAINERFILE, base_tag="ubuntu:22.04")
    assert containerfile_data.startswith("FROM ubuntu:22.04")
