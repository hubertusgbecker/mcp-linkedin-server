"""Tests for logging_config: formatters and configure_logging function."""

import io
import json
import logging

from mcp_linkedin_server.logging_config import (
    CompactFormatter,
    MCPJSONFormatter,
    configure_logging,
)


class TestMCPJSONFormatter:
    def test_basic_format_is_valid_json(self):
        fmt = MCPJSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="hello world",
            args=None,
            exc_info=None,
        )
        output = fmt.format(record)
        data = json.loads(output)
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "hello world"
        assert "timestamp" in data

    def test_includes_error_type_attribute(self):
        fmt = MCPJSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="fail",
            args=None,
            exc_info=None,
        )
        record.error_type = "ValueError"  # type: ignore[attr-defined]
        data = json.loads(fmt.format(record))
        assert data["error_type"] == "ValueError"

    def test_includes_error_details_attribute(self):
        fmt = MCPJSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="fail",
            args=None,
            exc_info=None,
        )
        record.error_details = "some detail"  # type: ignore[attr-defined]
        data = json.loads(fmt.format(record))
        assert data["error_details"] == "some detail"

    def test_includes_exception_info(self):
        fmt = MCPJSONFormatter()
        try:
            raise RuntimeError("boom")
        except RuntimeError:
            import sys

            exc_info = sys.exc_info()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="error",
            args=None,
            exc_info=exc_info,
        )
        data = json.loads(fmt.format(record))
        assert "exception" in data
        assert "RuntimeError" in data["exception"]

    def test_no_extra_keys_without_attributes(self):
        fmt = MCPJSONFormatter()
        record = logging.LogRecord(
            name="t",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="msg",
            args=None,
            exc_info=None,
        )
        data = json.loads(fmt.format(record))
        assert "error_type" not in data
        assert "error_details" not in data
        assert "exception" not in data

    def test_message_with_args(self):
        fmt = MCPJSONFormatter()
        record = logging.LogRecord(
            name="t",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="count=%d",
            args=(42,),
            exc_info=None,
        )
        data = json.loads(fmt.format(record))
        assert data["message"] == "count=42"


class TestCompactFormatter:
    def test_shortens_mcp_prefix(self):
        fmt = CompactFormatter()
        record = logging.LogRecord(
            name="mcp_linkedin_server.tools.person",
            level=logging.INFO,
            pathname="person.py",
            lineno=10,
            msg="scraping",
            args=None,
            exc_info=None,
        )
        output = fmt.format(record)
        assert "tools.person" in output
        assert "mcp_linkedin_server." not in output

    def test_preserves_non_mcp_logger_name(self):
        fmt = CompactFormatter()
        record = logging.LogRecord(
            name="other.module",
            level=logging.WARNING,
            pathname="",
            lineno=0,
            msg="warn",
            args=None,
            exc_info=None,
        )
        output = fmt.format(record)
        assert "other.module" in output

    def test_uses_hms_time_format(self):
        fmt = CompactFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="",
            lineno=0,
            msg="debug msg",
            args=None,
            exc_info=None,
        )
        output = fmt.format(record)
        # Should contain HH:MM:SS pattern
        parts = output.split(" - ")
        assert len(parts) >= 3
        time_part = parts[0]
        assert ":" in time_part  # HH:MM:SS format

    def test_includes_level_and_message(self):
        fmt = CompactFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="something broke",
            args=None,
            exc_info=None,
        )
        output = fmt.format(record)
        assert "ERROR" in output
        assert "something broke" in output


class TestConfigureLogging:
    def setup_method(self):
        """Save root logger state."""
        self._root = logging.getLogger()
        self._original_handlers = self._root.handlers[:]
        self._original_level = self._root.level

    def teardown_method(self):
        """Restore root logger state."""
        root = logging.getLogger()
        root.handlers = self._original_handlers
        root.level = self._original_level

    def test_sets_log_level(self):
        configure_logging(log_level="DEBUG")
        root = logging.getLogger()
        assert root.level == logging.DEBUG

    def test_sets_warning_by_default(self):
        configure_logging()
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_json_format_uses_json_formatter(self):
        configure_logging(json_format=True)
        root = logging.getLogger()
        assert any(isinstance(h.formatter, MCPJSONFormatter) for h in root.handlers)

    def test_compact_format_by_default(self):
        configure_logging(json_format=False)
        root = logging.getLogger()
        assert any(isinstance(h.formatter, CompactFormatter) for h in root.handlers)

    def test_removes_existing_handlers(self):
        root = logging.getLogger()
        extra = logging.StreamHandler(io.StringIO())
        root.addHandler(extra)
        configure_logging()
        # The extra handler should have been removed
        assert extra not in root.handlers

    def test_reduces_urllib3_noise(self):
        configure_logging()
        assert logging.getLogger("urllib3").level == logging.ERROR
        assert logging.getLogger("urllib3.connectionpool").level == logging.ERROR

    def test_reduces_fakeredis_noise(self):
        configure_logging()
        assert logging.getLogger("fakeredis").level == logging.WARNING

    def test_invalid_log_level_defaults_to_warning(self):
        configure_logging(log_level="INVALID")
        root = logging.getLogger()
        assert root.level == logging.WARNING

    def test_case_insensitive_log_level(self):
        configure_logging(log_level="info")
        root = logging.getLogger()
        assert root.level == logging.INFO
