import json

import pytest

from posit_bakery.cli.common import (
    __make_value_map as make_value_map,
    __parse_dependency_constraint as parse_dependency_constraint,
    __parse_dependency_versions as parse_dependency_versions,
)
from posit_bakery.config.dependencies import (
    PythonDependencyConstraint,
    RDependencyConstraint,
    QuartoDependencyConstraint,
    PythonDependencyVersions,
    RDependencyVersions,
    QuartoDependencyVersions,
)

pytestmark = [
    pytest.mark.unit,
]


class TestMakeValueMap:
    """Tests for the __make_value_map function"""

    def test_none_input(self):
        """Test that None input returns empty dict with no errors"""
        result, errors = make_value_map(None)
        assert result == {}
        assert errors == []

    def test_empty_list(self):
        """Test that empty list returns empty dict with no errors"""
        result, errors = make_value_map([])
        assert result == {}
        assert errors == []

    def test_single_key_value_pair(self):
        """Test parsing a single key=value pair"""
        result, errors = make_value_map(["key=value"])
        assert result == {"key": "value"}
        assert errors == []

    def test_multiple_key_value_pairs(self):
        """Test parsing multiple key=value pairs"""
        result, errors = make_value_map(["key1=value1", "key2=value2", "key3=value3"])
        assert result == {"key1": "value1", "key2": "value2", "key3": "value3"}
        assert errors == []

    def test_value_with_equals_sign(self):
        """Test parsing key=value where value contains an equals sign"""
        result, errors = make_value_map(["key=value=with=equals"])
        assert result == {"key": "value=with=equals"}
        assert errors == []

    def test_empty_value(self):
        """Test parsing key=value where value is empty"""
        result, errors = make_value_map(["key="])
        assert result == {"key": ""}
        assert errors == []

    def test_empty_key(self):
        """Test parsing key=value where key is empty"""
        result, errors = make_value_map(["=value"])
        assert result == {"": "value"}
        assert errors == []

    def test_invalid_no_equals_sign(self):
        """Test that input without equals sign returns an error"""
        result, errors = make_value_map(["invalid"])
        assert result == {}
        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)
        assert "Invalid key=value pair: invalid" in str(errors[0])

    def test_multiple_invalid_inputs(self):
        """Test that multiple invalid inputs return multiple errors"""
        result, errors = make_value_map(["invalid1", "invalid2", "invalid3"])
        assert result == {}
        assert len(errors) == 3
        for error in errors:
            assert isinstance(error, ValueError)

    def test_mixed_valid_and_invalid(self):
        """Test that valid pairs are parsed even when invalid pairs are present"""
        result, errors = make_value_map(["valid=pair", "invalid", "another=valid"])
        assert result == {"valid": "pair", "another": "valid"}
        assert len(errors) == 1
        assert isinstance(errors[0], ValueError)
        assert "Invalid key=value pair: invalid" in str(errors[0])

    def test_duplicate_keys(self):
        """Test that duplicate keys overwrite previous values"""
        result, errors = make_value_map(["key=value1", "key=value2"])
        assert result == {"key": "value2"}
        assert errors == []

    def test_special_characters_in_value(self):
        """Test parsing values with special characters"""
        result, errors = make_value_map(["key=value with spaces", "path=/usr/local/bin", "url=https://example.com"])
        assert result == {"key": "value with spaces", "path": "/usr/local/bin", "url": "https://example.com"}
        assert errors == []

    def test_special_characters_in_key(self):
        """Test parsing keys with special characters"""
        result, errors = make_value_map(["my-key=value", "my_key=value2", "MY.KEY=value3"])
        assert result == {"my-key": "value", "my_key": "value2", "MY.KEY": "value3"}
        assert errors == []


class TestParseDependencyConstraint:
    """Tests for the __parse_dependency_constraint function"""

    def test_python_constraint_with_latest(self):
        """Test parsing a Python dependency constraint with latest=true"""
        input_str = '{"dependency": "python", "constraint": {"latest": true}}'
        result = parse_dependency_constraint(input_str)
        assert isinstance(result, PythonDependencyConstraint)
        assert result.dependency == "python"
        assert result.constraint.latest is True
        assert result.constraint.count == 1  # Default when only latest is set

    def test_python_constraint_with_count(self):
        """Test parsing a Python dependency constraint with count"""
        input_str = '{"dependency": "python", "constraint": {"latest": true, "count": 3}}'
        result = parse_dependency_constraint(input_str)
        assert isinstance(result, PythonDependencyConstraint)
        assert result.constraint.latest is True
        assert result.constraint.count == 3

    def test_python_constraint_with_max(self):
        """Test parsing a Python dependency constraint with max version"""
        input_str = '{"dependency": "python", "constraint": {"max": "3.12", "count": 1}}'
        result = parse_dependency_constraint(input_str)
        assert isinstance(result, PythonDependencyConstraint)
        assert result.constraint.max == "3.12"
        assert result.constraint.count == 1

    def test_python_constraint_with_min(self):
        """Test parsing a Python dependency constraint with min version"""
        input_str = '{"dependency": "python", "constraint": {"latest": true, "min": "3.10"}}'
        result = parse_dependency_constraint(input_str)
        assert isinstance(result, PythonDependencyConstraint)
        assert result.constraint.latest is True
        assert result.constraint.min == "3.10"

    def test_python_constraint_with_min_max(self):
        """Test parsing a Python dependency constraint with min and max versions"""
        input_str = '{"dependency": "python", "constraint": {"min": "3.10", "max": "3.12"}}'
        result = parse_dependency_constraint(input_str)
        assert isinstance(result, PythonDependencyConstraint)
        assert result.constraint.min == "3.10"
        assert result.constraint.max == "3.12"

    def test_r_constraint_with_latest(self):
        """Test parsing an R dependency constraint with latest=true"""
        input_str = '{"dependency": "R", "constraint": {"latest": true, "count": 2}}'
        result = parse_dependency_constraint(input_str)
        assert isinstance(result, RDependencyConstraint)
        assert result.dependency == "R"
        assert result.constraint.latest is True
        assert result.constraint.count == 2

    def test_r_constraint_with_max(self):
        """Test parsing an R dependency constraint with max version"""
        input_str = '{"dependency": "R", "constraint": {"max": "4.3", "count": 1}}'
        result = parse_dependency_constraint(input_str)
        assert isinstance(result, RDependencyConstraint)
        assert result.constraint.max == "4.3"

    def test_quarto_constraint_with_latest(self):
        """Test parsing a Quarto dependency constraint with latest=true"""
        input_str = '{"dependency": "quarto", "constraint": {"latest": true}}'
        result = parse_dependency_constraint(input_str)
        assert isinstance(result, QuartoDependencyConstraint)
        assert result.dependency == "quarto"
        assert result.constraint.latest is True

    def test_quarto_constraint_with_prerelease(self):
        """Test parsing a Quarto dependency constraint with prerelease flag"""
        input_str = '{"dependency": "quarto", "constraint": {"latest": true}, "prerelease": true}'
        result = parse_dependency_constraint(input_str)
        assert isinstance(result, QuartoDependencyConstraint)
        assert result.prerelease is True
        assert result.constraint.latest is True

    def test_quarto_constraint_without_prerelease(self):
        """Test parsing a Quarto dependency constraint without prerelease flag"""
        input_str = '{"dependency": "quarto", "constraint": {"latest": true}}'
        result = parse_dependency_constraint(input_str)
        assert isinstance(result, QuartoDependencyConstraint)
        assert result.prerelease is False  # Default value

    def test_invalid_json(self):
        """Test that invalid JSON raises an error"""
        with pytest.raises(json.JSONDecodeError):
            parse_dependency_constraint("not valid json")

    def test_missing_dependency_field(self):
        """Test that missing dependency field raises ValueError"""
        input_str = '{"constraint": {"latest": true}}'
        with pytest.raises(ValueError) as exc_info:
            parse_dependency_constraint(input_str)
        assert "Dependency constraint must have a 'dependency' field" in str(exc_info.value)

    def test_empty_dependency_field(self):
        """Test that empty dependency field raises ValueError"""
        input_str = '{"dependency": "", "constraint": {"latest": true}}'
        with pytest.raises(ValueError) as exc_info:
            parse_dependency_constraint(input_str)
        assert "Dependency constraint must have a 'dependency' field" in str(exc_info.value)

    def test_null_dependency_field(self):
        """Test that null dependency field raises ValueError"""
        input_str = '{"dependency": null, "constraint": {"latest": true}}'
        with pytest.raises(ValueError) as exc_info:
            parse_dependency_constraint(input_str)
        assert "Dependency constraint must have a 'dependency' field" in str(exc_info.value)

    def test_unsupported_dependency(self):
        """Test that unsupported dependency name raises ValueError"""
        input_str = '{"dependency": "ruby", "constraint": {"latest": true}}'
        with pytest.raises(ValueError) as exc_info:
            parse_dependency_constraint(input_str)
        assert "Unsupported dependency name: ruby" in str(exc_info.value)

    def test_missing_constraint_field(self):
        """Test that missing constraint field raises validation error"""
        input_str = '{"dependency": "python"}'
        with pytest.raises(Exception):  # Pydantic ValidationError
            parse_dependency_constraint(input_str)

    def test_invalid_constraint_empty_object(self):
        """Test that empty constraint object raises validation error"""
        input_str = '{"dependency": "python", "constraint": {}}'
        with pytest.raises(Exception):  # Pydantic ValidationError
            parse_dependency_constraint(input_str)

    def test_invalid_constraint_negative_count(self):
        """Test that negative count raises validation error"""
        input_str = '{"dependency": "python", "constraint": {"latest": true, "count": -1}}'
        with pytest.raises(Exception):  # Pydantic ValidationError
            parse_dependency_constraint(input_str)

    def test_invalid_constraint_zero_count(self):
        """Test that zero count raises validation error"""
        input_str = '{"dependency": "python", "constraint": {"latest": true, "count": 0}}'
        with pytest.raises(Exception):  # Pydantic ValidationError
            parse_dependency_constraint(input_str)

    def test_invalid_constraint_both_latest_and_max(self):
        """Test that both latest and max raises validation error"""
        input_str = '{"dependency": "python", "constraint": {"latest": true, "max": "3.12"}}'
        with pytest.raises(Exception):  # Pydantic ValidationError
            parse_dependency_constraint(input_str)

    def test_invalid_constraint_min_greater_than_max(self):
        """Test that min > max raises validation error"""
        input_str = '{"dependency": "python", "constraint": {"min": "3.12", "max": "3.10"}}'
        with pytest.raises(Exception):  # Pydantic ValidationError
            parse_dependency_constraint(input_str)

    def test_extra_fields_python(self):
        """Test that extra fields in Python constraint raise validation error"""
        input_str = '{"dependency": "python", "constraint": {"latest": true}, "extra_field": "value"}'
        with pytest.raises(Exception):  # Pydantic ValidationError - extra='forbid'
            parse_dependency_constraint(input_str)

    def test_extra_fields_r(self):
        """Test that extra fields in R constraint raise validation error"""
        input_str = '{"dependency": "R", "constraint": {"latest": true}, "invalid": true}'
        with pytest.raises(Exception):  # Pydantic ValidationError - extra='forbid'
            parse_dependency_constraint(input_str)

    def test_case_sensitive_dependency_name(self):
        """Test that dependency names are case-sensitive"""
        # "Python" (capitalized) should not match "python"
        input_str = '{"dependency": "Python", "constraint": {"latest": true}}'
        with pytest.raises(ValueError) as exc_info:
            parse_dependency_constraint(input_str)
        assert "Unsupported dependency name: Python" in str(exc_info.value)


class TestParseDependencyVersions:
    """Tests for the __parse_dependency_versions function"""

    def test_python_versions_list(self):
        """Test parsing a Python dependency with a list of versions"""
        input_str = '{"dependency": "python", "versions": ["3.10.12", "3.11.8", "3.12.2"]}'
        result = parse_dependency_versions(input_str)
        assert isinstance(result, PythonDependencyVersions)
        assert result.dependency == "python"
        assert result.versions == ["3.10.12", "3.11.8", "3.12.2"]

    def test_python_single_version(self):
        """Test parsing a Python dependency with a single version"""
        input_str = '{"dependency": "python", "versions": ["3.12.2"]}'
        result = parse_dependency_versions(input_str)
        assert isinstance(result, PythonDependencyVersions)
        assert result.versions == ["3.12.2"]

    def test_python_versions_alias_singular(self):
        """Test parsing using 'version' alias instead of 'versions'"""
        input_str = '{"dependency": "python", "version": ["3.11.8"]}'
        result = parse_dependency_versions(input_str)
        assert isinstance(result, PythonDependencyVersions)
        assert result.versions == ["3.11.8"]

    def test_python_comma_separated_string(self):
        """Test parsing versions as a comma-separated string"""
        input_str = '{"dependency": "python", "versions": "3.10.12, 3.11.8, 3.12.2"}'
        result = parse_dependency_versions(input_str)
        assert isinstance(result, PythonDependencyVersions)
        assert result.versions == ["3.10.12", "3.11.8", "3.12.2"]

    def test_python_single_string_version(self):
        """Test parsing a single version as a string (not in a list)"""
        input_str = '{"dependency": "python", "versions": "3.12.2"}'
        result = parse_dependency_versions(input_str)
        assert isinstance(result, PythonDependencyVersions)
        assert result.versions == ["3.12.2"]

    def test_r_versions_list(self):
        """Test parsing an R dependency with a list of versions"""
        input_str = '{"dependency": "R", "versions": ["4.3.3", "4.4.0", "4.4.1"]}'
        result = parse_dependency_versions(input_str)
        assert isinstance(result, RDependencyVersions)
        assert result.dependency == "R"
        assert result.versions == ["4.3.3", "4.4.0", "4.4.1"]

    def test_r_single_version(self):
        """Test parsing an R dependency with a single version"""
        input_str = '{"dependency": "R", "versions": ["4.4.1"]}'
        result = parse_dependency_versions(input_str)
        assert isinstance(result, RDependencyVersions)
        assert result.versions == ["4.4.1"]

    def test_r_comma_separated_string(self):
        """Test parsing R versions as a comma-separated string"""
        input_str = '{"dependency": "R", "versions": "4.3.3, 4.4.1"}'
        result = parse_dependency_versions(input_str)
        assert isinstance(result, RDependencyVersions)
        assert result.versions == ["4.3.3", "4.4.1"]

    def test_quarto_versions_list(self):
        """Test parsing a Quarto dependency with a list of versions"""
        input_str = '{"dependency": "quarto", "versions": ["1.4.550", "1.5.23"]}'
        result = parse_dependency_versions(input_str)
        assert isinstance(result, QuartoDependencyVersions)
        assert result.dependency == "quarto"
        assert result.versions == ["1.4.550", "1.5.23"]

    def test_quarto_single_version(self):
        """Test parsing a Quarto dependency with a single version"""
        input_str = '{"dependency": "quarto", "versions": ["1.5.23"]}'
        result = parse_dependency_versions(input_str)
        assert isinstance(result, QuartoDependencyVersions)
        assert result.versions == ["1.5.23"]

    def test_quarto_with_prerelease(self):
        """Test parsing Quarto versions with prerelease flag"""
        input_str = '{"dependency": "quarto", "versions": ["1.5.23"], "prerelease": true}'
        result = parse_dependency_versions(input_str)
        assert isinstance(result, QuartoDependencyVersions)
        assert result.prerelease is True
        assert result.versions == ["1.5.23"]

    def test_quarto_without_prerelease(self):
        """Test parsing Quarto versions without prerelease flag (default)"""
        input_str = '{"dependency": "quarto", "versions": ["1.5.23"]}'
        result = parse_dependency_versions(input_str)
        assert isinstance(result, QuartoDependencyVersions)
        assert result.prerelease is False  # Default value

    def test_versions_with_whitespace(self):
        """Test that whitespace in comma-separated versions is trimmed"""
        input_str = '{"dependency": "python", "versions": "3.10.12,  3.11.8  , 3.12.2"}'
        result = parse_dependency_versions(input_str)
        assert result.versions == ["3.10.12", "3.11.8", "3.12.2"]

    def test_invalid_json(self):
        """Test that invalid JSON raises an error"""
        with pytest.raises(json.JSONDecodeError):
            parse_dependency_versions("not valid json")

    def test_missing_dependency_field(self):
        """Test that missing dependency field raises ValueError"""
        input_str = '{"versions": ["3.12.2"]}'
        with pytest.raises(ValueError) as exc_info:
            parse_dependency_versions(input_str)
        assert "Dependency versions must have a 'dependency' field" in str(exc_info.value)

    def test_empty_dependency_field(self):
        """Test that empty dependency field raises ValueError"""
        input_str = '{"dependency": "", "versions": ["3.12.2"]}'
        with pytest.raises(ValueError) as exc_info:
            parse_dependency_versions(input_str)
        assert "Dependency versions must have a 'dependency' field" in str(exc_info.value)

    def test_null_dependency_field(self):
        """Test that null dependency field raises ValueError"""
        input_str = '{"dependency": null, "versions": ["3.12.2"]}'
        with pytest.raises(ValueError) as exc_info:
            parse_dependency_versions(input_str)
        assert "Dependency versions must have a 'dependency' field" in str(exc_info.value)

    def test_unsupported_dependency(self):
        """Test that unsupported dependency name raises ValueError"""
        input_str = '{"dependency": "ruby", "versions": ["3.2.0"]}'
        with pytest.raises(ValueError) as exc_info:
            parse_dependency_versions(input_str)
        assert "Unsupported dependency name: ruby" in str(exc_info.value)

    def test_missing_versions_field(self):
        """Test that missing versions field uses default empty list"""
        input_str = '{"dependency": "python"}'
        with pytest.raises(Exception):  # Pydantic ValidationError - empty list not allowed
            parse_dependency_versions(input_str)

    def test_empty_versions_list(self):
        """Test that empty versions list raises validation error"""
        input_str = '{"dependency": "python", "versions": []}'
        with pytest.raises(Exception):  # Pydantic ValidationError
            parse_dependency_versions(input_str)

    def test_empty_string_in_versions(self):
        """Test that empty string in versions list is preserved"""
        input_str = '{"dependency": "python", "versions": ["3.12.2", "", "3.11.8"]}'
        result = parse_dependency_versions(input_str)
        # Empty strings are preserved as-is
        assert result.versions == ["3.12.2", "", "3.11.8"]

    def test_null_in_versions_list(self):
        """Test that null in versions list raises validation error"""
        input_str = '{"dependency": "python", "versions": ["3.12.2", null, "3.11.8"]}'
        with pytest.raises(Exception):  # Pydantic ValidationError
            parse_dependency_versions(input_str)

    def test_invalid_version_format(self):
        """Test that any string format is accepted as a version"""
        # The function doesn't validate version format, just accepts strings
        input_str = '{"dependency": "python", "versions": ["not.a.version", "arbitrary-string"]}'
        result = parse_dependency_versions(input_str)
        assert result.versions == ["not.a.version", "arbitrary-string"]

    def test_extra_fields(self):
        """Test that extra fields raise validation error"""
        input_str = '{"dependency": "python", "versions": ["3.12.2"], "extra_field": "value"}'
        with pytest.raises(Exception):  # Pydantic ValidationError - extra='forbid'
            parse_dependency_versions(input_str)

    def test_case_sensitive_dependency_name(self):
        """Test that dependency names are case-sensitive"""
        # "Python" (capitalized) should not match "python"
        input_str = '{"dependency": "Python", "versions": ["3.12.2"]}'
        with pytest.raises(ValueError) as exc_info:
            parse_dependency_versions(input_str)
        assert "Unsupported dependency name: Python" in str(exc_info.value)

    def test_duplicate_versions(self):
        """Test that duplicate versions are allowed (not deduplicated)"""
        input_str = '{"dependency": "python", "versions": ["3.12.2", "3.12.2", "3.11.8"]}'
        result = parse_dependency_versions(input_str)
        # The function should preserve duplicates as-is
        assert result.versions == ["3.12.2", "3.12.2", "3.11.8"]

    def test_versions_not_sorted(self):
        """Test that versions maintain input order (not automatically sorted)"""
        input_str = '{"dependency": "python", "versions": ["3.12.2", "3.10.12", "3.11.8"]}'
        result = parse_dependency_versions(input_str)
        assert result.versions == ["3.12.2", "3.10.12", "3.11.8"]
