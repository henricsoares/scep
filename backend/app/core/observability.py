import logging
import re
import time
import uuid
from typing import Any

from fastapi import Request, Response
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.logging import SERVICE_NAME, reset_request_context, set_request_context

logger = logging.getLogger(__name__)
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def valid_request_id(value: str | None) -> bool:
    return value is not None and _REQUEST_ID_PATTERN.fullmatch(value) is not None


def request_id(value: str | None) -> str:
    if value is not None and valid_request_id(value):
        return value
    return str(uuid.uuid4())


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        current_request_id = request_id(request.headers.get("x-request-id"))
        method = request.method
        path = request.url.path
        started = time.perf_counter()
        status_code = 500
        token = set_request_context(
            request_id=current_request_id,
            correlation_id=current_request_id,
            http_method=method,
            route=path,
        )
        span = trace.get_current_span()
        if span.get_span_context().is_valid:
            span.set_attribute("http.request_id", current_request_id)
            span.set_attribute("correlation.id", current_request_id)

        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = current_request_id
            return response
        finally:
            route = getattr(request.scope.get("route"), "path", path)
            elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
            set_request_context(
                request_id=current_request_id,
                correlation_id=current_request_id,
                http_method=method,
                route=route,
                status_code=status_code,
                execution_time_ms=elapsed_ms,
            )
            logger.info("HTTP request completed", extra={"event_type": "http.request"})
            reset_request_context(token)


def configure_tracing(app: Any, endpoint: str) -> TracerProvider:
    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
    )
    FastAPIInstrumentor.instrument_app(app, tracer_provider=provider, excluded_urls=None)
    return provider
