import pytest
from pydantic import ValidationError

from posit_bakery.models.manifest import snyk


@pytest.mark.manifest
@pytest.mark.schema
class TestManifestSnykTestOutput:
    def test_empty_init(self):
        """Test creating a generic ManifestSnykTestOutput object does not raise an exception"""
        snyk.ManifestSnykTestOutput()


@pytest.mark.manifest
@pytest.mark.schema
class TestManifestSnykTest:
    def test_empty_init(self):
        """Test creating a generic ManifestSnykTest object does not raise an exception"""
        snyk.ManifestSnykTest()

    def test_empty_init_creates_output_object(self):
        """Test creating a generic ManifestSnykTest object does not raise an exception"""
        t = snyk.ManifestSnykTest()
        assert t.output is not None
        assert t.output.json is False

    @pytest.mark.parametrize(
        "severity_threshold,expect_error",
        [
            ("low", False),
            ("medium", False),
            ("high", False),
            ("critical", False),
            ("invalid", True),
        ],
    )
    def test_severity_threshold_validation(self, severity_threshold, expect_error):
        """Test the severity_threshold field validation"""
        if expect_error:
            with pytest.raises(ValidationError):
                snyk.ManifestSnykTest(severity_threshold=severity_threshold)
        else:
            snyk.ManifestSnykTest(severity_threshold=severity_threshold)

    def test_output_validation(self):
        """Test the output field can be passed in"""
        snyk.ManifestSnykTest(output=snyk.ManifestSnykTestOutput(json=True))


@pytest.mark.manifest
@pytest.mark.schema
class TestManifestSnykMonitor:
    def test_empty_init(self):
        """Test creating a generic ManifestSnykMonitor object does not raise an exception"""
        snyk.ManifestSnykMonitor()

    @pytest.mark.parametrize(
        "environment,expect_error",
        [
            ("frontend", False),
            ("backend", False),
            ("internal", False),
            ("external", False),
            ("mobile", False),
            ("saas", False),
            ("onprem", False),
            ("invalid", True),
        ],
    )
    def test_environment_validation(self, environment, expect_error):
        """Test the environment field validation"""
        if expect_error:
            with pytest.raises(ValidationError):
                snyk.ManifestSnykMonitor(environment=environment)
        else:
            snyk.ManifestSnykMonitor(environment=environment)

    @pytest.mark.parametrize(
        "lifecycle,expect_error",
        [
            ("development", False),
            ("sandbox", False),
            ("production", False),
            ("invalid", True),
        ],
    )
    def test_lifecycle_validation(self, lifecycle, expect_error):
        """Test the lifecycle field validation"""
        if expect_error:
            with pytest.raises(ValidationError):
                snyk.ManifestSnykMonitor(lifecycle=lifecycle)
        else:
            snyk.ManifestSnykMonitor(lifecycle=lifecycle)

    @pytest.mark.parametrize(
        "business_criticality,expect_error",
        [
            ("low", False),
            ("medium", False),
            ("high", False),
            ("critical", False),
            ("invalid", True),
        ],
    )
    def test_business_criticality_validation(self, business_criticality, expect_error):
        """Test the business_criticality field validation"""
        if expect_error:
            with pytest.raises(ValidationError):
                snyk.ManifestSnykMonitor(business_criticality=business_criticality)
        else:
            snyk.ManifestSnykMonitor(business_criticality=business_criticality)

    @pytest.mark.parametrize(
        "tags,expect_warning",
        [
            ({"k": "v"}, False),
            ({"complicated_key1": "complex#value?:is=ok~"}, False),
            ({"k": "v" * 257}, True),
            ({"k" * 33: "v"}, True),
            ({"key": "value!"}, True),
            ({"key!": "value"}, True),
        ]
    )
    def test_tags_validation(self, caplog, tags, expect_warning):
        """Test the tags field validation"""
        snyk.ManifestSnykMonitor(tags=tags)
        if expect_warning:
            assert "WARNING" in caplog.text
        else:
            assert "WARNING" not in caplog.text


class TestManifestSnykSbom:
    def test_empty_init(self):
        """Test creating a generic ManifestSnykSbom object does not raise an exception"""
        snyk.ManifestSnykSbom()

    @pytest.mark.parametrize(
        "format,expect_error",
        [
            ("cyclonedx1.4+json", False),
            ("cyclonedx1.4+xml", False),
            ("cyclonedx1.5+json", False),
            ("cyclonedx1.5+xml", False),
            ("spdx2.3+json", False),
            ("invalid", True),
        ],
    )
    def test_format_validation(self, format, expect_error):
        """Test the format field validation"""
        if expect_error:
            with pytest.raises(ValidationError):
                snyk.ManifestSnykSbom(format=format)
        else:
            snyk.ManifestSnykSbom(format=format)


@pytest.mark.manifest
@pytest.mark.schema
class TestManifestSnyk:
    def test_empty_init(self):
        """Test creating a generic ManifestSnyk object does not raise an exception"""
        s = snyk.ManifestSnyk()
        assert isinstance(s.test, snyk.ManifestSnykTest)
        assert isinstance(s.test.output, snyk.ManifestSnykTestOutput)
        assert isinstance(s.monitor, snyk.ManifestSnykMonitor)
        assert isinstance(s.sbom, snyk.ManifestSnykSbom)
