from datetime import UTC, datetime, timedelta

import jwt
from app.core.config import get_settings
from app.modules.identity.application.security import create_access_token
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository

from tests.integration.identity.conftest import IdentityContext


def test_missing_invalid_and_expired_tokens_are_rejected(
    identity_context: IdentityContext,
) -> None:
    client = identity_context.client
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000000",
            "email": "expired@example.com",
            "roles": [],
            "account_type": "TechnicalClient",
            "iat": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
            "exp": int((datetime.now(UTC) - timedelta(minutes=1)).timestamp()),
        },
        settings.jwt_secret_key,
        algorithm="HS256",
    )

    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_inactive_account_and_changed_roles_invalidate_existing_tokens(
    identity_context: IdentityContext,
) -> None:
    user = identity_context.create_user(
        email="researcher@example.com", roles=[HumanRole.RESEARCHER]
    )
    old_headers = identity_context.headers(user)

    with identity_context.sessions() as session:
        repository = SqlAlchemyUserRepository(session)
        repository.update(user.with_profile(status=AccountStatus.INACTIVE))
    assert identity_context.client.get("/auth/me", headers=old_headers).status_code == 401

    with identity_context.sessions() as session:
        repository = SqlAlchemyUserRepository(session)
        inactive = repository.get(user.id)
        assert inactive is not None
        active = repository.update(inactive.with_profile(status=AccountStatus.ACTIVE))
        current_headers = identity_context.headers(active)
        repository.update(active.with_roles([HumanRole.DATA_SCIENTIST]))
    assert identity_context.client.get("/auth/me", headers=current_headers).status_code == 401


def test_technical_client_current_identity_is_validated(
    identity_context: IdentityContext,
) -> None:
    technical = identity_context.create_user(
        email="simulation@example.com", account_type=AccountType.TECHNICAL_CLIENT
    )
    response = identity_context.client.get("/auth/me", headers=identity_context.headers(technical))

    assert response.status_code == 200
    assert response.json()["account_type"] == "TechnicalClient"
    assert response.json()["roles"] == []

    token, _ = create_access_token(technical)
    claims = jwt.decode(
        token, get_settings().jwt_secret_key, algorithms=["HS256"], options={"verify_exp": False}
    )
    claims["roles"] = ["PlatformAdministrator"]
    forged = jwt.encode(claims, get_settings().jwt_secret_key, algorithm="HS256")
    assert (
        identity_context.client.get(
            "/auth/me", headers={"Authorization": f"Bearer {forged}"}
        ).status_code
        == 401
    )


def test_login_and_current_identity(identity_context: IdentityContext) -> None:
    user = identity_context.create_user(email="driver@example.com", roles=[HumanRole.EV_DRIVER])
    login = identity_context.client.post(
        "/auth/login", json={"email": user.email, "password": "SecurePassword123!"}
    )

    assert login.status_code == 200
    me = identity_context.client.get(
        "/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["id"] == str(user.id)
