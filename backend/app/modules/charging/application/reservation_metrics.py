from prometheus_client import Counter

reservations_created_total = Counter(
    "scep_reservations_created_total", "Successfully created Reservations"
)
reservations_cancelled_total = Counter(
    "scep_reservations_cancelled_total",
    "Cancelled Reservations",
    ("classification",),
)
reservations_no_show_total = Counter(
    "scep_reservations_no_show_total", "Reservations reconciled as No-Show"
)
reservation_conflicts_total = Counter(
    "scep_reservation_conflicts_total",
    "Reservation scheduling conflicts",
    ("resource",),
)
