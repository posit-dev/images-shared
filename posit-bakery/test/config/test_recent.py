import logging
import textwrap

import pytest
from pydantic import ValidationError

from posit_bakery.config.config import BakeryConfig
from posit_bakery.config.settings import BakeryConfigFilter, BakerySettings
from posit_bakery.targets.selection import apply_recent_versions
from posit_bakery.config.image import ImageVersion
from posit_bakery.const import DevVersionInclusionEnum

pytestmark = [pytest.mark.unit, pytest.mark.config]


def _write_config(tmp_path):
    config_file = tmp_path / "bakery.yaml"
    config_file.write_text(
        textwrap.dedent("""\
            repository:
              url: https://github.com/posit-dev/test
            images:
              - name: app
                versions:
                  - name: "1.0.0"
                    latest: true
                    os:
                      - name: Ubuntu 22.04
                        primary: true
                  - name: "2.0.0"
                    os:
                      - name: Ubuntu 22.04
                        primary: true
                  - name: "3.0.0"
                    os:
                      - name: Ubuntu 22.04
                        primary: true
                  - name: "4.0.0"
                    os:
                      - name: Ubuntu 22.04
                        primary: true
            """)
    )
    return config_file


def _target_versions(config: BakeryConfig) -> set[str]:
    return {target.image_version.name for target in config.targets}


def test_apply_recent_versions_sorts_releases_and_exempts_development_versions():
    versions = [
        ImageVersion(name="unparseable"),
        ImageVersion(name="1.0.0"),
        ImageVersion(name="3.0.0"),
        ImageVersion(name="2.0.0"),
        ImageVersion(name="4.0.0-dev+1", isDevelopmentVersion=True),
    ]

    selected = apply_recent_versions(versions, 2, "app")

    assert [version.name for version in selected] == ["3.0.0", "2.0.0", "4.0.0-dev+1"]


def test_recent_limits_generated_targets(tmp_path):
    config = BakeryConfig(_write_config(tmp_path), BakerySettings(recent=2))

    assert _target_versions(config) == {"4.0.0", "3.0.0"}


def test_recent_is_validated():
    for value in (0, -1):
        with pytest.raises(ValidationError):
            BakerySettings(recent=value)


def test_excluded_image_version_logs_a_warning(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        config = BakeryConfig(
            _write_config(tmp_path),
            BakerySettings(filter=BakeryConfigFilter(image_version="1.0.0"), recent=2),
        )

    assert config.targets == []
    assert "Version '1.0.0' in image 'app' matches --image-version filter" in caplog.text
    assert "excluded by --recent 2" in caplog.text


def test_latest_and_recent_log_combined_warning(tmp_path, caplog):
    with caplog.at_level(logging.WARNING):
        BakeryConfig(_write_config(tmp_path), BakerySettings(latest=True, recent=1))

    assert "--latest is set alongside a recent-version limit" in caplog.text


def test_dev_versions_only_still_excludes_limited_releases(tmp_path):
    config = BakeryConfig(
        _write_config(tmp_path),
        BakerySettings(dev_versions=DevVersionInclusionEnum.ONLY, recent=2),
    )

    assert config.targets == []
