from prometheus_client import Counter

charging_sessions_activated_total = Counter(
    "scep_charging_sessions_activated_total", "Successfully activated Charging Sessions"
)
charging_sessions_completed_total = Counter(
    "scep_charging_sessions_completed_total", "Successfully completed Charging Sessions"
)
charging_session_failures_total = Counter(
    "scep_charging_session_failures_total",
    "Charging Session operation failures",
    ("operation", "reason"),
)
charging_session_conflicts_total = Counter(
    "scep_charging_session_conflicts_total",
    "Charging Session concurrency conflicts",
    ("resource",),
)
