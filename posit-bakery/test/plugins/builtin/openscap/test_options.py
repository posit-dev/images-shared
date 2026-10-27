import pytest
from pydantic import ValidationError

from posit_bakery.plugins.builtin.openscap.options import FailOnEnum, OpenSCAPOptions, OutputFormatEnum

pytestmark = [pytest.mark.unit, pytest.mark.openscap]


def test_update_keeps_explicit_values():
    variant = OpenSCAPOptions(profile="cis_level2_server")
    image = OpenSCAPOptions(profile="cis_level1_server", failOn=FailOnEnum.HIGH, skipRules=["x"])
    merged = variant.update(image)
    assert merged.profile == "cis_level2_server"
    assert merged.failOn == FailOnEnum.HIGH
    assert merged.skipRules == ["x"]


def test_formats_normalised():
    assert OpenSCAPOptions.model_validate({"formats": ["JSON", " html"]}).formats == [
        OutputFormatEnum.JSON,
        OutputFormatEnum.HTML,
    ]


@pytest.mark.parametrize("formats", [["pdf"], []])
def test_formats_rejected(formats):
    with pytest.raises(ValidationError):
        OpenSCAPOptions.model_validate({"formats": formats})


def test_fail_on_rejected():
    with pytest.raises(ValidationError):
        OpenSCAPOptions.model_validate({"failOn": "critical"})
