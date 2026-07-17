from prometheus_client import Counter, Gauge

events_persisted_total = Counter(
    "domain_events_persisted_total", "Persisted domain events", ["event_type"]
)
deliveries_total = Counter(
    "domain_event_deliveries_total", "Successful event deliveries", ["consumer"]
)
delivery_retries_total = Counter(
    "domain_event_delivery_retries_total", "Retried event deliveries", ["consumer"]
)
delivery_failures_total = Counter(
    "domain_event_delivery_failures_total", "Failed event deliveries", ["consumer"]
)
pending_deliveries = Gauge("domain_event_pending_deliveries", "Pending and failed deliveries")
registered_consumers = Gauge("domain_event_registered_consumers", "Registered event consumers")
