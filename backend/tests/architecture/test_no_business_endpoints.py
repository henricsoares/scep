from app.main import create_app
from starlette.routing import Route


def test_only_foundation_routes_are_registered() -> None:
    app = create_app()
    paths = {route.path for route in app.routes if isinstance(route, Route)}
    assert {"/health", "/health/live", "/health/ready", "/metrics"}.issubset(paths)
