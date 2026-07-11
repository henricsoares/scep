from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.identity.application.metrics import authorization_denied_total
from app.modules.identity.application.security import decode_token
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository

bearer_scheme = HTTPBearer()


def current_user(
    db: Annotated[Session, Depends(get_db)],
    creds: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
) -> User:
    try:
        claims = decode_token(creds.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc
    required = {"sub", "email", "roles", "account_type", "iat", "exp"}
    if not required.issubset(claims):
        raise HTTPException(status_code=401, detail="invalid token")
    try:
        user_id = UUID(str(claims["sub"]))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc
    user = SqlAlchemyUserRepository(db).get(user_id)
    if user is None or user.status != AccountStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="invalid token")
    if claims.get("email") != user.email or claims.get("account_type") != user.account_type.value:
        raise HTTPException(status_code=401, detail="invalid token")
    token_roles = claims.get("roles", [])
    if not isinstance(token_roles, list):
        raise HTTPException(status_code=401, detail="invalid token")
    if sorted(str(role) for role in token_roles) != sorted(
        [r.value for r in user.roles] if user.account_type == AccountType.HUMAN else []
    ):
        raise HTTPException(status_code=401, detail="invalid token")
    try:
        user.validate()
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="invalid token") from exc
    return user


def require_admin(user: Annotated[User, Depends(current_user)]) -> User:
    if HumanRole.PLATFORM_ADMINISTRATOR not in user.roles:
        authorization_denied_total.inc()
        raise HTTPException(status_code=403, detail="insufficient permission")
    return user
