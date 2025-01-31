from pathlib import Path

from posit_bakery.models.manifest import guess_os_list


class TestOS:
    def test_guess_os_list(self, tmpdir):
        """Test the guess_image_os_list method of a Manifest object returns expected OS list"""
        files = [
            "Containerfile.ubuntu2204.min",
            "Containerfile.ubuntu2204.std",
            "Containerfile.ubuntu2404.min",
            "Containerfile.ubuntu2404.std",
            "Containerfile.rockylinux9.min",
            "Containerfile.rockylinux9.std",
        ]
        context = Path(tmpdir)
        for f in files:
            (context / f).touch(exist_ok=True)
        os_list = guess_os_list(context)

        assert len(os_list) == 3
        pretty_names = [os.pretty for os in os_list]
        assert "Ubuntu 22.04" in pretty_names
        assert "Ubuntu 24.04" in pretty_names
        assert "Rocky Linux 9" in pretty_names
