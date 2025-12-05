import json

from posit_bakery.image.image_metadata import BuildMetadata


def test_load_metadata(image_testdata):
    """Test loading image metadata from an example metadata JSON file."""
    manifest_path = image_testdata / "build_metadata.json"
    with open(manifest_path, "r") as f:
        metadata = BuildMetadata(**json.load(f))

    assert metadata.image_name == "cripittwood.azurecr.io/posit/test-multi/tmp:latest"
    assert metadata.container_image_digest == "sha256:b0f70c272157281f3e70fcd1d890d6927a9268f4bd315e6d7cba677182bd6098"


def test_metadata_image_ref(image_testdata):
    """Test the image_ref computed property of BuildMetadata."""
    manifest_path = image_testdata / "build_metadata.json"
    with open(manifest_path, "r") as f:
        metadata = BuildMetadata(**json.load(f))

    assert (
        metadata.image_ref
        == "cripittwood.azurecr.io/posit/test-multi/tmp:latest@sha256:b0f70c272157281f3e70fcd1d890d6927a9268f4bd315e6d7cba677182bd6098"
    )
