import subprocess
from unittest.mock import patch

import pytest

from posit_bakery.image.image_metadata import BuildMetadata
from posit_bakery.plugins.builtin.wizcli.tag import tag_published_repositories

pytestmark = [
    pytest.mark.unit,
    pytest.mark.wizcli,
]


def add_build_metadata(target, *, platform: str = "linux/amd64", digest: str = "sha256:built-digest"):
    target.build_metadata = [
        BuildMetadata.model_validate(
            {
                "image.name": "ghcr.io/posit-dev/test-image/tmp:latest",
                "containerimage.digest": digest,
                "containerimage.descriptor": {
                    "platform": {
                        "os": platform.split("/", 1)[0],
                        "architecture": platform.split("/", 1)[1],
                    },
                    "annotations": {"org.opencontainers.image.created": "2026-01-01T00:00:00+00:00"},
                },
            }
        )
    ]


class TestTagPublishedRepositories:
    def test_tags_one_local_alias_per_final_repository(self, basic_standard_image_target):
        add_build_metadata(basic_standard_image_target)
        completed = subprocess.CompletedProcess([], 0, stdout="tagged", stderr="")

        with (
            patch("posit_bakery.plugins.builtin.wizcli.tag.find_bin", return_value="/tools/wizcli"),
            patch("posit_bakery.plugins.builtin.wizcli.tag.python_on_whales.docker.image.tag") as docker_tag,
            patch("posit_bakery.plugins.builtin.wizcli.tag.subprocess.run", return_value=completed) as run,
        ):
            failures = tag_published_repositories(
                basic_standard_image_target.context.base_path,
                [basic_standard_image_target],
                platform="linux/amd64",
                projects="project-id",
            )

        assert failures == []
        assert docker_tag.call_count == 2
        assert run.call_count == 2

        source_refs = {call.args[0] for call in docker_tag.call_args_list}
        assert source_refs == {"ghcr.io/posit-dev/test-image/tmp@sha256:built-digest"}

        destination_tags = {call.args[1] for call in docker_tag.call_args_list}
        assert len(destination_tags) == 2
        assert any(ref.startswith("docker.io/posit/test-image:") for ref in destination_tags)
        assert any(ref.startswith("ghcr.io/posit-dev/test-image:") for ref in destination_tags)

        for call in run.call_args_list:
            command = call.args[0]
            assert command[:2] == ["/tools/wizcli", "tag"]
            assert command[2] in destination_tags
            assert command[command.index("--digest") + 1] == "sha256:built-digest"
            assert command[command.index("--projects") + 1] == "project-id"

    def test_passes_credentials_through_environment_not_arguments(self, basic_standard_image_target):
        add_build_metadata(basic_standard_image_target)
        completed = subprocess.CompletedProcess([], 0, stdout="tagged", stderr="")

        with (
            patch("posit_bakery.plugins.builtin.wizcli.tag.find_bin", return_value="/tools/wizcli"),
            patch("posit_bakery.plugins.builtin.wizcli.tag.python_on_whales.docker.image.tag"),
            patch("posit_bakery.plugins.builtin.wizcli.tag.subprocess.run", return_value=completed) as run,
        ):
            failures = tag_published_repositories(
                basic_standard_image_target.context.base_path,
                [basic_standard_image_target],
                platform="linux/amd64",
                client_id="client-id",
                client_secret="client-secret",
            )

        assert failures == []
        for call in run.call_args_list:
            assert "client-id" not in call.args[0]
            assert "client-secret" not in call.args[0]
            assert call.kwargs["env"]["WIZ_CLIENT_ID"] == "client-id"
            assert call.kwargs["env"]["WIZ_CLIENT_SECRET"] == "client-secret"

    def test_missing_platform_metadata_is_a_failure(self, basic_standard_image_target):
        add_build_metadata(basic_standard_image_target, platform="linux/arm64")

        with (
            patch("posit_bakery.plugins.builtin.wizcli.tag.find_bin", return_value="/tools/wizcli"),
            patch("posit_bakery.plugins.builtin.wizcli.tag.python_on_whales.docker.image.tag") as docker_tag,
            patch("posit_bakery.plugins.builtin.wizcli.tag.subprocess.run") as run,
        ):
            failures = tag_published_repositories(
                basic_standard_image_target.context.base_path,
                [basic_standard_image_target],
                platform="linux/amd64",
            )

        assert failures == [f"{basic_standard_image_target}: no build digest for linux/amd64"]
        docker_tag.assert_not_called()
        run.assert_not_called()

    def test_wizcli_failure_identifies_repository_and_digest(self, basic_standard_image_target):
        add_build_metadata(basic_standard_image_target)
        completed = subprocess.CompletedProcess([], 1, stdout="unknown image", stderr="")

        with (
            patch("posit_bakery.plugins.builtin.wizcli.tag.find_bin", return_value="/tools/wizcli"),
            patch("posit_bakery.plugins.builtin.wizcli.tag.python_on_whales.docker.image.tag"),
            patch("posit_bakery.plugins.builtin.wizcli.tag.subprocess.run", return_value=completed),
        ):
            failures = tag_published_repositories(
                basic_standard_image_target.context.base_path,
                [basic_standard_image_target],
                platform="linux/amd64",
            )

        assert len(failures) == 2
        assert all("@sha256:built-digest: unknown image" in failure for failure in failures)
