from tests.integration.identity.conftest import IdentityContext


def test_openapi_security_and_sensitive_schemas(identity_context: IdentityContext) -> None:
    schema = identity_context.client.get("/openapi.json").json()

    assert schema["components"]["securitySchemes"]["HTTPBearer"] == {
        "type": "http",
        "scheme": "bearer",
    }
    for path, method in (
        ("/auth/me", "get"),
        ("/users", "get"),
        ("/users", "post"),
        ("/facilities", "get"),
        ("/facilities", "post"),
        ("/stations/{station_id}", "get"),
    ):
        assert schema["paths"][path][method]["security"] == [{"HTTPBearer": []}]

    for path, method in (
        ("/auth/login", "post"),
        ("/health", "get"),
        ("/health/live", "get"),
        ("/health/ready", "get"),
    ):
        assert "security" not in schema["paths"][path][method]

    schemas = str(schema["components"]["schemas"])
    assert "password_hash" not in schemas
