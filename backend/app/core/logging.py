import logging
import sys
from collections.abc import Mapping
from contextvars import ContextVar, Token
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from pythonjsonlogger.json import JsonFormatter

SERVICE_NAME = "scep-backend"
_request_context: ContextVar[dict[str, str | int | float] | None] = ContextVar(
    "request_context", default=None
)
_SENSITIVE_KEYS = ("password", "password_hash", "token", "secret", "credential")


def set_request_context(
    **values: str | int | float,
) -> Token[dict[str, str | int | float] | None]:
    return _request_context.set(values)


def reset_request_context(token: Token[dict[str, str | int | float] | None]) -> None:
    _request_context.reset(token)


def _is_sensitive(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return any(part in normalized for part in _SENSITIVE_KEYS)


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): "[REDACTED]" if _is_sensitive(str(key)) else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive(item) for item in value)
    return value


class ObservabilityFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.service = SERVICE_NAME
        record.module = record.module or record.name
        for key, value in (_request_context.get() or {}).items():
            setattr(record, key, value)
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            record.trace_id = trace.format_trace_id(span_context.trace_id)
            record.span_id = trace.format_span_id(span_context.span_id)
        else:
            record.trace_id = None
            record.span_id = None
        for key, value in list(record.__dict__.items()):
            if _is_sensitive(key):
                setattr(record, key, "[REDACTED]")
            elif isinstance(value, Mapping | list | tuple):
                setattr(record, key, redact_sensitive(value))
        return True


class OtlpExportFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith(("opentelemetry.exporter", "grpc"))


def configure_logging(level: str, otlp_endpoint: str | None = None) -> LoggerProvider | None:
    context_filter = ObservabilityFilter()
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(context_filter)
    handler.setFormatter(
        JsonFormatter(
            "%(asctime)s %(levelname)s %(service)s %(module)s %(name)s %(message)s "
            "%(request_id)s %(correlation_id)s %(trace_id)s %(span_id)s %(http_method)s "
            "%(route)s %(status_code)s %(execution_time_ms)s",
            rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
        )
    )
    handlers: list[logging.Handler] = [handler]
    provider = None
    if otlp_endpoint:
        provider = LoggerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
        provider.add_log_record_processor(
            BatchLogRecordProcessor(OTLPLogExporter(endpoint=otlp_endpoint, insecure=True))
        )
        otlp_handler = LoggingHandler(
            level=logging.getLevelNamesMapping().get(level.upper(), logging.INFO),
            logger_provider=provider,
        )
        otlp_handler.addFilter(context_filter)
        otlp_handler.addFilter(OtlpExportFilter())
        handlers.append(otlp_handler)
    logging.basicConfig(level=level.upper(), handlers=handlers, force=True)
    return provider
