"""Tests for posit_bakery.log module.

Tests cover the logging initialization and configuration.
"""

import logging

import pytest
from rich.logging import RichHandler

from posit_bakery.log import init_logging, stdout_console, stderr_console, default_theme


pytestmark = [pytest.mark.unit]


class TestLogging:
    def test_default_theme_colors(self):
        """Test that default theme has expected styles."""
        assert "info" in default_theme.styles
        assert "error" in default_theme.styles
        assert "success" in default_theme.styles
        assert "quiet" in default_theme.styles

    def test_consoles_exist(self):
        """Test that stdout and stderr consoles are configured."""
        assert stdout_console is not None
        assert stderr_console is not None
        assert stderr_console.stderr is True

    def test_init_logging_default(self):
        """Test init_logging with default INFO level."""
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers.copy()
        original_level = root_logger.level
        root_logger.handlers.clear()

        try:
            init_logging()
            assert root_logger.level == logging.INFO
        finally:
            root_logger.handlers = original_handlers
            root_logger.setLevel(original_level)

    def test_init_logging_debug_level(self):
        """Test init_logging with DEBUG level enables traceback frames."""
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers.copy()
        original_level = root_logger.level
        root_logger.handlers.clear()

        try:
            init_logging(log_level=logging.DEBUG)
            assert root_logger.level == logging.DEBUG

            # Find the RichHandler and verify its traceback settings
            rich_handlers = [h for h in root_logger.handlers if isinstance(h, RichHandler)]
            assert len(rich_handlers) == 1, "Expected exactly one RichHandler"
            handler = rich_handlers[0]
            assert handler.tracebacks_max_frames == 20
            assert handler.tracebacks_show_locals is True
        finally:
            root_logger.handlers = original_handlers
            root_logger.setLevel(original_level)

    def test_init_logging_warning_level(self):
        """Test init_logging with WARNING level."""
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers.copy()
        original_level = root_logger.level
        root_logger.handlers.clear()

        try:
            init_logging(log_level=logging.WARNING)
            assert root_logger.level == logging.WARNING
        finally:
            root_logger.handlers = original_handlers
            root_logger.setLevel(original_level)

    def test_init_logging_string_level(self):
        """Test init_logging accepts string log level."""
        root_logger = logging.getLogger()
        original_handlers = root_logger.handlers.copy()
        original_level = root_logger.level
        root_logger.handlers.clear()

        try:
            init_logging(log_level="ERROR")
            assert root_logger.level == logging.ERROR
        finally:
            root_logger.handlers = original_handlers
            root_logger.setLevel(original_level)
