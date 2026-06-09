import pytest
from pydantic import ValidationError

from posit_bakery.config.image.dev_version.spec import DevBuildSpec
from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum

pytestmark = [pytest.mark.unit, pytest.mark.config]


class TestDevBuildSpec:
    def test_version_required(self):
        with pytest.raises(ValidationError):
            DevBuildSpec.model_validate_json("{}")

    def test_minimal_valid(self):
        spec = DevBuildSpec.model_validate_json('{"version": "2026.05.0-dev+185-gSHA"}')
        assert spec.version == "2026.05.0-dev+185-gSHA"
        assert spec.channel is None

    def test_with_channel(self):
        spec = DevBuildSpec.model_validate_json('{"version": "2026.05.0-dev+185-gSHA", "channel": "daily"}')
        assert spec.channel == ReleaseChannelEnum.DAILY

    def test_invalid_channel_raises(self):
        with pytest.raises(ValidationError):
            DevBuildSpec.model_validate_json('{"version": "2026.05.0-dev+185-gSHA", "channel": "nightly"}')

    def test_empty_version_raises(self):
        with pytest.raises(ValidationError):
            DevBuildSpec(version="")
        with pytest.raises(ValidationError):
            DevBuildSpec(version="   ")

    def test_whitespace_version_is_stripped(self):
        spec = DevBuildSpec.model_validate_json('{"version": "  2026.05.0-dev+185-gSHA  "}')
        assert spec.version == "2026.05.0-dev+185-gSHA"

    def test_unknown_fields_raise(self):
        with pytest.raises(ValidationError):
            DevBuildSpec.model_validate_json('{"version": "2026.05.0-dev+1-gSHA", "chanenl": "daily"}')
