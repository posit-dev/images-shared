import pytest

from posit_bakery.cli.common import __make_value_map as make_value_map

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
