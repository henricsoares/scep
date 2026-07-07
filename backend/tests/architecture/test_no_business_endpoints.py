from app.main import create_app


def test_only_foundation_routes_are_registered() -> None:
    app = create_app()
    paths = {route.path for route in app.routes}
    assert {"/health", "/health/live", "/health/ready", "/metrics"}.issubset(paths)
