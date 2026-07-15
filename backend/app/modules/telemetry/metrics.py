from prometheus_client import Counter

telemetry_samples_received_total = Counter(
    "scep_telemetry_samples_received_total", "Telemetry samples submitted"
)
telemetry_samples_persisted_total = Counter(
    "scep_telemetry_samples_persisted_total", "Telemetry samples persisted"
)
telemetry_batch_ingestions_total = Counter(
    "scep_telemetry_batch_ingestions_total", "Telemetry batch ingestion attempts"
)
telemetry_batch_failures_total = Counter(
    "scep_telemetry_batch_failures_total", "Telemetry batch failures", ("reason",)
)
telemetry_validation_failures_total = Counter(
    "scep_telemetry_validation_failures_total", "Telemetry validation failures"
)
telemetry_duplicate_submissions_total = Counter(
    "scep_telemetry_duplicate_submissions_total", "Identical telemetry retries"
)
