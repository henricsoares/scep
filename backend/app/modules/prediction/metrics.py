from prometheus_client import Counter, Histogram

publication_outcomes_total = Counter(
    "scep_prediction_publications_total",
    "Weekly occupancy prediction publication outcomes",
    ("outcome", "scope_type"),
)
idempotent_retries_total = Counter(
    "scep_prediction_idempotent_retries_total",
    "Identical prediction publication retries",
    ("scope_type",),
)
content_conflicts_total = Counter(
    "scep_prediction_content_conflicts_total",
    "Prediction publication content conflicts",
    ("scope_type",),
)
bucket_validation_failures_total = Counter(
    "scep_prediction_bucket_validation_failures_total",
    "Prediction bucket validation failures",
    ("reason",),
)
publication_duration_seconds = Histogram(
    "scep_prediction_publication_duration_seconds",
    "Prediction publication duration",
    ("outcome",),
)
queries_total = Counter(
    "scep_prediction_queries_total",
    "Prediction query outcomes",
    ("operation", "outcome"),
)
query_duration_seconds = Histogram(
    "scep_prediction_query_duration_seconds",
    "Prediction query duration",
    ("operation", "outcome"),
)
recommendations_total = Counter(
    "scep_prediction_recommendations_total",
    "Prediction recommendation outcomes",
    ("outcome",),
)
recommendation_candidates = Histogram(
    "scep_prediction_recommendation_candidates",
    "Eligible prediction recommendation candidates",
    ("outcome",),
)
missing_current_total = Counter(
    "scep_prediction_missing_current_total",
    "Prediction queries without a current publication",
    ("operation", "scope_type"),
)
authorization_failures_total = Counter(
    "scep_prediction_authorization_failures_total",
    "Prediction authorization failures",
    ("operation",),
)
persistence_failures_total = Counter(
    "scep_prediction_persistence_failures_total",
    "Prediction persistence failures",
    ("operation",),
)
