from prometheus_client import Counter, Histogram

analytics_requests_total = Counter(
    "scep_analytics_requests_total", "Analytics requests", ["endpoint"]
)
analytics_success_total = Counter(
    "scep_analytics_success_total", "Successful analytics requests", ["endpoint"]
)
analytics_failed_total = Counter(
    "scep_analytics_failed_total", "Failed analytics requests", ["endpoint", "reason"]
)
analytics_query_duration_seconds = Histogram(
    "scep_analytics_query_duration_seconds", "Analytics query duration", ["endpoint"]
)
analytics_returned_buckets_total = Counter(
    "scep_analytics_returned_buckets_total", "Analytics time buckets returned", ["endpoint"]
)
