from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings
from app.modules.identity.domain.user import AccountType, User

_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _hasher.verify(password, password_hash)


def create_access_token(user: User) -> tuple[str, int]:
    settings = get_settings()
    now = datetime.now(UTC)
    exp = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    claims = {
        "sub": str(user.id),
        "email": user.email,
        "roles": [r.value for r in user.roles] if user.account_type == AccountType.HUMAN else [],
        "account_type": user.account_type.value,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    return (
        jwt.encode(claims, settings.jwt_secret_key, algorithm="HS256"),
        settings.jwt_access_token_expire_minutes * 60,
    )


def decode_token(token: str) -> dict[str, object]:
    return jwt.decode(token, get_settings().jwt_secret_key, algorithms=["HS256"])
