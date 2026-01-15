"""Tests for the shared validation utilities and mixins."""

import logging

import pytest
from pydantic import ValidationError

from posit_bakery.config.validators import (
    check_duplicates_or_raise,
    deduplicate_with_warning,
)


class TestDeduplicateWithWarning:
    """Tests for deduplicate_with_warning utility function."""

    def test_removes_duplicates(self):
        """Test that duplicates are removed."""
        items = ["a", "b", "a", "c", "b"]
        result = deduplicate_with_warning(items, key=lambda x: x)
        assert result == ["a", "b", "c"]

    def test_sorts_by_key(self):
        """Test that results are sorted by the key function."""
        items = ["c", "a", "b"]
        result = deduplicate_with_warning(items, key=lambda x: x)
        assert result == ["a", "b", "c"]

    def test_logs_warning_for_duplicates(self, caplog):
        """Test that a warning is logged for each duplicate."""
        items = ["a", "b", "a"]
        with caplog.at_level(logging.WARNING):
            deduplicate_with_warning(
                items,
                key=lambda x: x,
                warn_message_func=lambda x: f"Duplicate: {x}",
            )
        assert "Duplicate: a" in caplog.text

    def test_no_warning_when_no_duplicates(self, caplog):
        """Test that no warning is logged when there are no duplicates."""
        items = ["a", "b", "c"]
        with caplog.at_level(logging.WARNING):
            deduplicate_with_warning(
                items,
                key=lambda x: x,
                warn_message_func=lambda x: f"Duplicate: {x}",
            )
        assert caplog.text == ""

    def test_no_warning_when_func_is_none(self, caplog):
        """Test that no warning is logged when warn_message_func is None."""
        items = ["a", "b", "a"]
        with caplog.at_level(logging.WARNING):
            deduplicate_with_warning(items, key=lambda x: x, warn_message_func=None)
        assert caplog.text == ""

    def test_empty_list(self):
        """Test that an empty list returns an empty list."""
        result = deduplicate_with_warning([], key=lambda x: x)
        assert result == []

    def test_does_not_modify_original(self):
        """Test that the original list is not modified."""
        items = ["c", "a", "b"]
        deduplicate_with_warning(items, key=lambda x: x)
        assert items == ["c", "a", "b"]


class TestCheckDuplicatesOrRaise:
    """Tests for check_duplicates_or_raise utility function."""

    def test_no_duplicates_returns_original(self):
        """Test that the original list is returned when there are no duplicates."""
        items = ["a", "b", "c"]
        result = check_duplicates_or_raise(
            items,
            key_func=lambda x: x,
            error_message_func=lambda dupes: f"Duplicates: {dupes}",
        )
        assert result == items
        assert result is items  # Same object

    def test_raises_on_duplicates(self):
        """Test that ValueError is raised when duplicates are found."""
        items = ["a", "b", "a"]
        with pytest.raises(ValueError) as exc_info:
            check_duplicates_or_raise(
                items,
                key_func=lambda x: x,
                error_message_func=lambda dupes: f"Duplicates found: {', '.join(dupes)}",
            )
        assert "Duplicates found: a" in str(exc_info.value)

    def test_multiple_duplicates(self):
        """Test that all duplicate keys are reported."""
        items = ["a", "b", "a", "c", "b"]
        with pytest.raises(ValueError) as exc_info:
            check_duplicates_or_raise(
                items,
                key_func=lambda x: x,
                error_message_func=lambda dupes: f"Duplicates: {', '.join(sorted(dupes))}",
            )
        assert "a" in str(exc_info.value)
        assert "b" in str(exc_info.value)

    def test_custom_key_func(self):
        """Test with a custom key function for objects."""

        class Item:
            def __init__(self, name):
                self.name = name

        items = [Item("a"), Item("b"), Item("a")]
        with pytest.raises(ValueError) as exc_info:
            check_duplicates_or_raise(
                items,
                key_func=lambda x: x.name,
                error_message_func=lambda dupes: f"Duplicate names: {', '.join(dupes)}",
            )
        assert "Duplicate names: a" in str(exc_info.value)

    def test_empty_list(self):
        """Test that an empty list returns an empty list."""
        result = check_duplicates_or_raise(
            [],
            key_func=lambda x: x,
            error_message_func=lambda dupes: f"Duplicates: {dupes}",
        )
        assert result == []

    def test_single_item(self):
        """Test that a single item list returns unchanged."""
        items = ["a"]
        result = check_duplicates_or_raise(
            items,
            key_func=lambda x: x,
            error_message_func=lambda dupes: f"Duplicates: {dupes}",
        )
        assert result == ["a"]
