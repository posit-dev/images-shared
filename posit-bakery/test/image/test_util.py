from posit_bakery.image import util


def test_inspect_image():
    """Test inspecting an image for tools metadata"""
    metadata = util.inspect_image("busybox:latest")
    assert isinstance(metadata, util.ImageToolsInspectionMetadata)
    assert len(metadata.manifests) > 1
    assert metadata.digest is not None
