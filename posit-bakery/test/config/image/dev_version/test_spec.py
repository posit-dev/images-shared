import pytest
from pydantic import ValidationError

from posit_bakery.config.image.dev_version.spec import DevBuildSpec
from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestDevBuildSpec:
    def test_version_only(self):
        spec = DevBuildSpec(version="2026.06.0-daily+143")
        assert spec.version == "2026.06.0-daily+143"
        assert spec.release_branch is None

    def test_release_branch_only(self):
        spec = DevBuildSpec(release_branch="apple-blossom")
        assert spec.version is None
        assert spec.release_branch == "apple-blossom"

    def test_both_fields(self):
        spec = DevBuildSpec(version="2026.06.0-daily+143", release_branch="apple-blossom")
        assert spec.version == "2026.06.0-daily+143"
        assert spec.release_branch == "apple-blossom"

    def test_neither_field_raises(self):
        with pytest.raises(ValidationError, match="at least one of"):
            DevBuildSpec()

    def test_channel_only_raises(self):
        with pytest.raises(ValidationError, match="at least one of"):
            DevBuildSpec(channel=ReleaseChannelEnum.DAILY)

    def test_empty_version_raises(self):
        with pytest.raises(ValidationError, match="version must not be empty"):
            DevBuildSpec(version="   ")

    def test_empty_release_branch_raises(self):
        with pytest.raises(ValidationError, match="release_branch must not be empty"):
            DevBuildSpec(release_branch="")

    def test_model_validate_json_release_branch_only(self):
        spec = DevBuildSpec.model_validate_json('{"release_branch": "2026.07"}')
        assert spec.release_branch == "2026.07"
        assert spec.version is None

    def test_with_channel(self):
        spec = DevBuildSpec.model_validate_json('{"version": "2026.05.0-dev+185-gSHA", "channel": "daily"}')
        assert spec.channel == ReleaseChannelEnum.DAILY

    def test_invalid_channel_raises(self):
        with pytest.raises(ValidationError):
            DevBuildSpec.model_validate_json('{"version": "2026.05.0-dev+185-gSHA", "channel": "nightly"}')

    def test_whitespace_version_is_stripped(self):
        spec = DevBuildSpec.model_validate_json('{"version": "  2026.05.0-dev+185-gSHA  "}')
        assert spec.version == "2026.05.0-dev+185-gSHA"

    def test_unknown_fields_raise(self):
        with pytest.raises(ValidationError):
            DevBuildSpec.model_validate_json('{"version": "2026.05.0-dev+1-gSHA", "unexpected_field": "daily"}')

    def test_explicit_none_version_with_release_branch(self):
        spec = DevBuildSpec(version=None, release_branch="apple-blossom")
        assert spec.version is None
        assert spec.release_branch == "apple-blossom"

    def test_explicit_none_release_branch_with_version(self):
        spec = DevBuildSpec(version="2026.06.0-daily+143", release_branch=None)
        assert spec.version == "2026.06.0-daily+143"
        assert spec.release_branch is None

    def test_json_null_version_with_release_branch(self):
        spec = DevBuildSpec.model_validate_json('{"version": null, "release_branch": "apple-blossom"}')
        assert spec.version is None
        assert spec.release_branch == "apple-blossom"
