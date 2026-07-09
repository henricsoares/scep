from app.main import create_app
from starlette.routing import Route


def test_foundation_and_facility_routes_are_registered() -> None:
    app = create_app()
    schema_paths = set(app.openapi()["paths"])
    route_paths = {route.path for route in app.routes if isinstance(route, Route)}

    expected_paths = {
        "/health",
        "/health/live",
        "/health/ready",
        "/facilities",
        "/facilities/{facilityId}",
    }
    assert expected_paths.issubset(schema_paths)
    assert "/metrics" in route_paths
