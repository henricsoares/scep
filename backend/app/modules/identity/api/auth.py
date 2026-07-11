from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.identity.api.dependencies import current_user
from app.modules.identity.application.user_service import (
    AuthenticationError,
    InactiveAccountError,
    UserService,
)
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    account_type: AccountType
    status: AccountStatus
    roles: list[HumanRole]
    facility_ids: list[UUID]


def me_resp(u: User) -> MeResponse:
    return MeResponse(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        account_type=u.account_type,
        status=u.status,
        roles=list(u.roles),
        facility_ids=list(u.facility_ids),
    )


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Annotated[Session, Depends(get_db)]) -> LoginResponse:
    try:
        token, expires, _ = UserService(SqlAlchemyUserRepository(db)).login(
            payload.email, payload.password
        )
        return LoginResponse(access_token=token, expires_in=expires)
    except InactiveAccountError as exc:
        raise HTTPException(403, "account is Inactive") from exc
    except (AuthenticationError, ValueError) as exc:
        raise HTTPException(401, "invalid credentials") from exc


@router.get("/me", response_model=MeResponse)
def me(user: Annotated[User, Depends(current_user)]) -> MeResponse:
    return me_resp(user)
