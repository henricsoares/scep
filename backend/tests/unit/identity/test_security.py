from datetime import UTC, datetime, timedelta

import jwt
import pytest
from app.core.config import get_settings
from app.modules.identity.application.security import (
    create_access_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User


def make_user(account_type: AccountType = AccountType.HUMAN) -> User:
    return User.create(
        email="user@example.com",
        display_name="User",
        password_hash="hash",
        account_type=account_type,
        status=AccountStatus.ACTIVE,
        roles=[HumanRole.RESEARCHER] if account_type == AccountType.HUMAN else [],
        facility_ids=[],
    )


def test_password_is_hashed_and_verified() -> None:
    encoded = hash_password("SecurePassword123!")

    assert encoded != "SecurePassword123!"
    assert verify_password("SecurePassword123!", encoded)
    assert not verify_password("WrongPassword123!", encoded)


def test_access_token_contains_required_claims() -> None:
    user = make_user()
    token, expires_in = create_access_token(user)
    claims = decode_token(token)

    assert claims["sub"] == str(user.id)
    assert claims["email"] == user.email
    assert claims["roles"] == [HumanRole.RESEARCHER.value]
    assert claims["account_type"] == AccountType.HUMAN.value
    assert isinstance(claims["iat"], int)
    assert isinstance(claims["exp"], int)
    assert expires_in == 1800


def test_technical_client_token_has_no_human_roles() -> None:
    token, _ = create_access_token(make_user(AccountType.TECHNICAL_CLIENT))
    assert decode_token(token)["roles"] == []


def test_expired_and_invalid_signature_tokens_are_rejected() -> None:
    expired = jwt.encode(
        {"sub": "x", "exp": datetime.now(UTC) - timedelta(seconds=1)},
        get_settings().jwt_secret_key,
        algorithm="HS256",
    )
    wrong_signature = jwt.encode(
        {"sub": "x", "exp": datetime.now(UTC) + timedelta(minutes=1)},
        "wrong-secret",
        algorithm="HS256",
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(expired)
    with pytest.raises(jwt.InvalidSignatureError):
        decode_token(wrong_signature)
