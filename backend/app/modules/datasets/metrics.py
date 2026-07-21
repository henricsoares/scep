from prometheus_client import Counter, Gauge, Histogram

export_requests_total = Counter(
    "scep_dataset_export_requests_total",
    "Dataset export requests",
    ["dataset_type", "profile", "format"],
)
export_outcomes_total = Counter(
    "scep_dataset_export_outcomes_total",
    "Dataset export outcomes",
    ["outcome", "dataset_type", "profile", "format"],
)
export_failures_total = Counter(
    "scep_dataset_export_failures_total", "Dataset export failures", ["failure_code"]
)
processing_duration_seconds = Histogram(
    "scep_dataset_export_processing_duration_seconds", "Dataset export processing duration"
)
pending_duration_seconds = Histogram(
    "scep_dataset_export_pending_duration_seconds", "Dataset export pending duration"
)
generated_rows = Histogram("scep_dataset_export_generated_rows", "Generated dataset rows")
artifact_size_bytes = Histogram(
    "scep_dataset_export_artifact_size_bytes", "Generated artifact size"
)
currently_processing = Gauge(
    "scep_dataset_exports_currently_processing", "Currently processing dataset exports"
)
expired_artifacts_total = Counter(
    "scep_dataset_export_expired_artifacts_total", "Expired dataset artifacts"
)
storage_failures_total = Counter(
    "scep_dataset_export_storage_failures_total", "Dataset artifact storage failures", ["operation"]
)
downloads_total = Counter(
    "scep_dataset_export_downloads_total", "Dataset artifact download outcomes", ["outcome"]
)
