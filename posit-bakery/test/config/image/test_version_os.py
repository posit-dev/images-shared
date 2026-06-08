import pytest
from pydantic import ValidationError

from posit_bakery.config import ImageVersionOS
from posit_bakery.config.image.build_os import SUPPORTED_OS

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestImageVersionOS:
    def test_name_required(self):
        """Test that an ImageVersionOS object requires a name."""
        with pytest.raises(ValidationError, match="Field required"):
            ImageVersionOS()

    def test_valid_name_only(self):
        """Test creating an ImageVersionOS object with only the name does not raise an exception.

        Test that the default values for extension and tagDisplayName are set correctly.
        Test that the primary field defaults to False.
        """
        i = ImageVersionOS(name="Ubuntu 22.04")

        assert not i.primary
        assert i.extension == "ubuntu2204"
        assert i.tagDisplayName == "ubuntu-22.04"
        assert i.buildOS == SUPPORTED_OS["ubuntu"]["22"]

    def test_valid(self):
        """Test creating a valid ImageVersionOS object with all fields."""
        i = ImageVersionOS(name="Ubuntu 22.04", extension="ubuntu", tagDisplayName="jammy", primary=True)

        assert i.primary
        assert i.extension == "ubuntu"
        assert i.tagDisplayName == "jammy"
        assert i.buildOS == SUPPORTED_OS["ubuntu"]["22"]

    def test_extension_validation(self):
        """Test that the extension field only allows alphanumeric characters, underscores, and hyphens."""
        with pytest.raises(ValidationError):
            ImageVersionOS(name="Ubuntu 22.04", extension="invalid_extension!")

    def test_tag_display_name_validation(self):
        """Test that the tagDisplayName field only allows alphanumeric characters, underscores, hyphens, and periods."""
        with pytest.raises(ValidationError):
            ImageVersionOS(name="Ubuntu 22.04", tagDisplayName="invalid tag name!")

    @pytest.mark.parametrize(
        "input_url,is_valid",
        [
            pytest.param(
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect_2025.03.0~ubuntu24_amd64.deb",
                True,
                id="standard-debian-url",
            ),
            pytest.param(
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el8.x86_64.rpm",
                True,
                id="standard-rhel-url",
            ),
            pytest.param(
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect_2025.03.0~ubuntu24_$TARGETARCH.deb",
                True,
                id="generalized-debian-url",
            ),
            pytest.param(
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el8.$TARGETARCH.rpm",
                True,
                id="generalized-rhel-url",
            ),
            pytest.param(
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect_2025.03.0~ubuntu24_${TARGETARCH}.deb",
                True,
                id="generalized-debian-url-with-brackets",
            ),
            pytest.param(
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect-2025.03.0.el8.${TARGETARCH}.rpm",
                True,
                id="generalized-rhel-url-with-brackets",
            ),
            pytest.param("invalid_url", False, id="not-a-url"),
            pytest.param(
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect^2025.03.0[ubuntu24]_amd64.deb",
                False,
                id="invalid-standard-with-invalid-characters",
            ),
            pytest.param(
                "https://cdn.rstudio.com/connect/2025.03/rstudio-connect^2025.03.0[ubuntu24]_$TARGETARCH.deb",
                False,
                id="invalid-generalized-with-invalid-characters",
            ),
        ],
    )
    def test_artifactDownloadURL_regex_pattern(self, input_url, is_valid):
        """Test that the artifactDownloadURL field validates URLs correctly."""
        if is_valid:
            os = ImageVersionOS(name="Ubuntu 22.04", artifactDownloadURL=input_url)
            assert os.artifactDownloadURL == input_url
        else:
            with pytest.raises(ValidationError):
                ImageVersionOS(name="Ubuntu 22.04", artifactDownloadURL=input_url)

    def test_hash(self):
        """Test that the hash method returns a unique hash based on the name."""
        os1 = ImageVersionOS(name="Ubuntu 22.04")
        os2 = ImageVersionOS(name="Ubuntu 22.04")
        os3 = ImageVersionOS(name="Ubuntu 24.04")

        assert hash(os1) == hash(os2)
        assert hash(os1) != hash(os3)

    def test_equality(self):
        """Test that the equality operator compares based on name."""
        os1 = ImageVersionOS(name="Ubuntu 22.04")
        os2 = ImageVersionOS(name="Ubuntu 22.04", primary=True)
        os3 = ImageVersionOS(name="Ubuntu 24.04")

        assert os1 == os2
        assert os1 != os3
        assert os2 != os3

    def test_scratch_derives_empty_extension_and_tag(self):
        i = ImageVersionOS(name="scratch")
        assert i.extension == ""
        assert i.tagDisplayName == ""

    def test_scratch_case_insensitive(self):
        i = ImageVersionOS(name="Scratch")
        assert i.extension == ""
        assert i.tagDisplayName == ""

    def test_empty_extension_accepted_explicitly(self):
        i = ImageVersionOS(name="Ubuntu 22.04", extension="", tagDisplayName="")
        assert i.extension == ""
        assert i.tagDisplayName == ""

    @pytest.mark.parametrize(
        "input_name,expected_build_os",
        [
            ("Ubuntu 22.04", SUPPORTED_OS["ubuntu"]["22"]),
            ("Ubuntu 22", SUPPORTED_OS["ubuntu"]["22"]),
            ("Ubuntu 24.04", SUPPORTED_OS["ubuntu"]["24"]),
            ("Ubuntu 24", SUPPORTED_OS["ubuntu"]["24"]),
            ("Ubuntu 26.04", SUPPORTED_OS["ubuntu"]["26"]),
            ("Ubuntu 26", SUPPORTED_OS["ubuntu"]["26"]),
            ("Ubuntu", SUPPORTED_OS["ubuntu"]["26"]),
            ("Debian 11", SUPPORTED_OS["debian"]["11"]),
            ("Debian 11.0", SUPPORTED_OS["debian"]["11"]),
            ("Debian", SUPPORTED_OS["debian"]["13"]),
            ("RHEL 10", SUPPORTED_OS["rhel"]["10"]),
            ("Red Hat 10", SUPPORTED_OS["rhel"]["10"]),
            ("RHEL", SUPPORTED_OS["rhel"]["10"]),
            ("RH 9", SUPPORTED_OS["rhel"]["9"]),
            ("EL8", SUPPORTED_OS["rhel"]["8"]),
            ("Alma 9", SUPPORTED_OS["alma"]["9"]),
            ("AlmaLinux 8", SUPPORTED_OS["alma"]["8"]),
            ("Alma Linux", SUPPORTED_OS["alma"]["10"]),
            ("Rocky Linux 10", SUPPORTED_OS["rocky"]["10"]),
            ("Rocky 9", SUPPORTED_OS["rocky"]["9"]),
            ("Rocky", SUPPORTED_OS["rocky"]["10"]),
        ],
    )
    def test_populate_build_os(self, input_name, expected_build_os):
        """Test that the buildOS field is correctly populated based on the name."""
        os = ImageVersionOS(name=input_name)

        assert os.buildOS == expected_build_os


class TestImageVersionOSArtifactOs:
    def test_artifact_os_accepted_for_known_os(self):
        i = ImageVersionOS(name="scratch", artifactOs="ubuntu-24.04")
        assert i.artifactOs == "ubuntu-24.04"

    def test_artifact_os_rejected_for_unknown_os(self):
        with pytest.raises(ValidationError, match="not a recognized OS name"):
            ImageVersionOS(name="scratch", artifactOs="not-a-real-os")

    def test_artifact_os_defaults_to_none(self):
        i = ImageVersionOS(name="scratch")
        assert i.artifactOs is None

    def test_artifact_build_os_returns_resolved_os_when_set(self):
        i = ImageVersionOS(name="scratch", artifactOs="ubuntu-24.04")
        assert i.artifact_build_os == SUPPORTED_OS["ubuntu"]["24"]

    def test_artifact_build_os_falls_back_to_build_os_when_unset(self):
        i = ImageVersionOS(name="Ubuntu 22.04")
        assert i.artifact_build_os == SUPPORTED_OS["ubuntu"]["22"]

    def test_artifact_build_os_for_scratch_without_artifact_os(self):
        i = ImageVersionOS(name="scratch")
        assert i.artifact_build_os == SUPPORTED_OS["scratch"]
