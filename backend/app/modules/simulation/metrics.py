from prometheus_client import Counter, Gauge, Histogram

simulation_runs = Gauge(
    "scep_simulation_runs", "Persisted SimulationRuns by lifecycle status", ("status",)
)
simulation_operations_total = Counter(
    "scep_simulation_operations_total",
    "Simulated mutation outcomes",
    ("operation", "outcome"),
)
simulation_rejections_total = Counter(
    "scep_simulation_rejections_total", "Simulation context rejections", ("reason",)
)
simulation_transaction_duration_seconds = Histogram(
    "scep_simulation_transaction_duration_seconds",
    "Coordinated simulated mutation duration",
    ("operation",),
)
simulation_no_show_reconciliations_total = Counter(
    "scep_simulation_no_show_reconciliations_total",
    "Reservations reconciled as no-show under simulation context",
)
