from app.main import create_app
from starlette.routing import Route


def test_only_foundation_routes_are_registered() -> None:
    app = create_app()
    schema_paths = set(app.openapi()["paths"])
    route_paths = {route.path for route in app.routes if isinstance(route, Route)}

    assert {"/health", "/health/live", "/health/ready"}.issubset(schema_paths)
    assert "/metrics" in route_paths
