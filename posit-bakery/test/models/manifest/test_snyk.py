import pytest

from posit_bakery.models.manifest import snyk


@pytest.mark.manifest
@pytest.mark.schema
class TestManifestSnykTestOutput:
    def test_empty_init(self):
        """Test creating a generic ManifestSnykTestOutput object does not raise an exception"""
        snyk.ManifestSnykTestOutput()

    @pytest.mark.parametrize(
        "fmt,expect_warning",
        [
            ("sarif", False),
            ("json", False),
            ("default", False),
            ("invalid", True),
        ],
    )
    def test_format_validation(self, caplog, fmt, expect_warning):
        """Test the format field validation"""
        snyk.ManifestSnykTestOutput(format=fmt)
        if expect_warning:
            assert "WARNING" in caplog.text
        else:
            assert "WARNING" not in caplog.text


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
        assert t.output.format == "default"

    @pytest.mark.parametrize(
        "severity_threshold,expect_warning",
        [
            ("low", False),
            ("medium", False),
            ("high", False),
            ("critical", False),
            ("invalid", True),
        ],
    )
    def test_severity_threshold_validation(self, caplog, severity_threshold, expect_warning):
        """Test the severity_threshold field validation"""
        snyk.ManifestSnykTest(severity_threshold=severity_threshold)
        if expect_warning:
            assert "WARNING" in caplog.text
        else:
            assert "WARNING" not in caplog.text

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
        "environment,expect_warning",
        [
            ("frontend", False),
            ("backend", False),
            ("internal", False),
            ("external", False),
            ("mobile", False),
            ("saas", False),
            ("onprem", False),
            ("invalid", True),
            (["frontend", "backend"], False),
            (["frontend", "invalid"], True),
            ("frontend,internal", False),
            ("frontend,invalid", True),
        ],
    )
    def test_environment_validation(self, caplog, environment, expect_warning):
        """Test the environment field validation"""
        snyk.ManifestSnykMonitor(environment=environment)
        if expect_warning:
            assert "WARNING" in caplog.text
        else:
            assert "WARNING" not in caplog.text

    @pytest.mark.parametrize(
        "lifecycle,expect_warning",
        [
            ("development", False),
            ("sandbox", False),
            ("production", False),
            ("invalid", True),
            ("development,sandbox", False),
            ("development,invalid", True),
            (["development", "sandbox"], False),
            (["development", "invalid"], True),
        ],
    )
    def test_lifecycle_validation(self, caplog, lifecycle, expect_warning):
        """Test the lifecycle field validation"""
        snyk.ManifestSnykMonitor(lifecycle=lifecycle)
        if expect_warning:
            assert "WARNING" in caplog.text
        else:
            assert "WARNING" not in caplog.text

    @pytest.mark.parametrize(
        "business_criticality,expect_warning",
        [
            ("low", False),
            ("medium", False),
            ("high", False),
            ("critical", False),
            ("invalid", True),
            (["low", "medium"], False),
            (["low", "invalid"], True),
            ("low,medium", False),
            ("low,invalid", True),
        ],
    )
    def test_business_criticality_validation(self, caplog, business_criticality, expect_warning):
        """Test the business_criticality field validation"""
        snyk.ManifestSnykMonitor(business_criticality=business_criticality)
        if expect_warning:
            assert "WARNING" in caplog.text
        else:
            assert "WARNING" not in caplog.text

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
        "fmt,expect_warning",
        [
            ("cyclonedx1.4+json", False),
            ("cyclonedx1.4+xml", False),
            ("cyclonedx1.5+json", False),
            ("cyclonedx1.5+xml", False),
            ("cyclonedx1.6+json", False),
            ("cyclonedx1.6+xml", False),
            ("spdx2.3+json", False),
            ("invalid", True),
        ],
    )
    def test_format_validation(self, caplog, fmt, expect_warning):
        """Test the format field validation"""
        snyk.ManifestSnykSbom(format=fmt)
        if expect_warning:
            assert "WARNING" in caplog.text
        else:
            assert "WARNING" not in caplog.text


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

    def test_create(self, caplog):
        """Test creating a ManifestSnyk object with valid data does not raise an exception"""
        s = snyk.ManifestSnyk(
            test={
                "severity_threshold": "high",
                "include_base_image_vulns": True,
                "output": {
                    "format": "sarif",
                    "json_file": True,
                },
            },
            monitor={
                "output_json": True,
                "environment": ["distributed", "onprem", "hosted"],
                "lifecycle": "development,sandbox",
                "business_criticality": "high",
                "tags": {
                    "key-1": "value@1",
                    "key_2": "value?2",
                },
            },
            sbom={
                "format": "cyclonedx1.4+xml",
            },
        )
        assert "WARNING" not in caplog.text
        assert s.test.severity_threshold == "high"
        assert s.test.include_base_image_vulns is True
        assert s.test.output.format == "sarif"
        assert s.test.output.json_file is True
        assert s.monitor.output_json is True
        assert isinstance(s.monitor.environment, list)
        assert len(s.monitor.environment) == 3
        assert "distributed" in s.monitor.environment
        assert "onprem" in s.monitor.environment
        assert "hosted" in s.monitor.environment
        assert isinstance(s.monitor.lifecycle, list)
        assert len(s.monitor.lifecycle) == 2
        assert "development" in s.monitor.lifecycle
        assert "sandbox" in s.monitor.lifecycle
        assert s.monitor.business_criticality == "high"
        assert s.monitor.tags == {
            "key-1": "value@1",
            "key_2": "value?2",
        }
        assert s.sbom.format == "cyclonedx1.4+xml"
