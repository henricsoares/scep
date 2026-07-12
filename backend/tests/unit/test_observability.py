import json
import logging
from io import StringIO

from app.core.logging import (
    ObservabilityFilter,
    redact_sensitive,
    reset_request_context,
    set_request_context,
)
from app.core.observability import request_id, valid_request_id
from pythonjsonlogger.json import JsonFormatter


def test_request_id_reuses_only_bounded_well_formed_values() -> None:
    assert request_id("client-request_123") == "client-request_123"
    assert valid_request_id("a" * 128)
    assert not valid_request_id("a" * 129)
    assert not valid_request_id("contains spaces")
    assert request_id("contains spaces") != "contains spaces"


def test_structured_log_contains_correlation_context() -> None:
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(ObservabilityFilter())
    handler.setFormatter(JsonFormatter("%(service)s %(request_id)s %(correlation_id)s"))
    test_logger = logging.getLogger("test.structured")
    test_logger.handlers = [handler]
    test_logger.propagate = False
    token = set_request_context(request_id="request-1", correlation_id="request-1")
    try:
        test_logger.warning("handled")
    finally:
        reset_request_context(token)

    event = json.loads(stream.getvalue())
    assert event["service"] == "scep-backend"
    assert event["request_id"] == "request-1"
    assert event["correlation_id"] == "request-1"


def test_sensitive_structured_fields_are_recursively_redacted() -> None:
    assert redact_sensitive(
        {
            "email": "person@example.test",
            "password": "secret",
            "nested": {"access_token": "jwt"},
        }
    ) == {
        "email": "person@example.test",
        "password": "[REDACTED]",
        "nested": {"access_token": "[REDACTED]"},
    }
