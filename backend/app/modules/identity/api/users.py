from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.infrastructure.database import get_db
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.identity.api.dependencies import require_admin
from app.modules.identity.application.user_service import (
    DuplicateEmailError,
    InvalidAccountError,
    LastAdminError,
    UserNotFoundError,
    UserService,
)
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository

router = APIRouter(prefix="/users", tags=["Identity"])


class UserCreate(BaseModel):
    email: str
    display_name: str
    password: str
    account_type: AccountType
    status: AccountStatus = AccountStatus.ACTIVE
    roles: list[HumanRole] = []
    facility_ids: list[UUID] = []


class UserPatch(BaseModel):
    display_name: str | None = None
    status: AccountStatus | None = None
    model_config = ConfigDict(extra="forbid")


class RolesPayload(BaseModel):
    roles: list[HumanRole]


class FacilitiesPayload(BaseModel):
    facility_ids: list[UUID]


class UserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    account_type: AccountType
    status: AccountStatus
    roles: list[HumanRole]
    facility_ids: list[UUID]
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None


def svc(db: Session) -> UserService:
    return UserService(SqlAlchemyUserRepository(db), SqlAlchemyFacilityRepository(db))


def resp(u: User) -> UserResponse:
    return UserResponse(
        id=u.id,
        email=u.email,
        display_name=u.display_name,
        account_type=u.account_type,
        status=u.status,
        roles=list(u.roles),
        facility_ids=list(u.facility_ids),
        created_at=u.created_at,
        updated_at=u.updated_at,
        last_login_at=u.last_login_at,
    )


def map_exc(exc: Exception) -> HTTPException:
    if isinstance(exc, DuplicateEmailError):
        return HTTPException(409, "email already exists")
    if isinstance(exc, LastAdminError):
        return HTTPException(409, str(exc))
    if isinstance(exc, UserNotFoundError):
        return HTTPException(404, str(exc))
    if isinstance(exc, InvalidAccountError | ValueError):
        return HTTPException(422, str(exc))
    return HTTPException(422, "invalid account data")


@router.post("", response_model=UserResponse, status_code=201)
def create(
    payload: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> UserResponse:
    try:
        return resp(svc(db).create_user(**payload.model_dump()))
    except Exception as exc:
        raise map_exc(exc) from exc


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
    status: AccountStatus | None = None,
    role: HumanRole | None = None,
    account_type: AccountType | None = None,
) -> list[UserResponse]:
    return [resp(u) for u in svc(db).list(status=status, role=role, account_type=account_type)]


@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> UserResponse:
    try:
        return resp(svc(db).get(user_id))
    except Exception as exc:
        raise map_exc(exc) from exc


@router.patch("/{user_id}", response_model=UserResponse)
def patch_user(
    user_id: UUID,
    payload: UserPatch,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> UserResponse:
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(422, "at least one field is required")
    try:
        return resp(svc(db).update_profile(user_id, **changes))
    except (LastAdminError, UserNotFoundError, ValueError) as exc:
        raise map_exc(exc) from exc


@router.put("/{user_id}/roles", response_model=UserResponse)
def put_roles(
    user_id: UUID,
    payload: RolesPayload,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> UserResponse:
    try:
        return resp(svc(db).replace_roles(user_id, payload.roles))
    except Exception as exc:
        raise map_exc(exc) from exc


@router.put("/{user_id}/facilities", response_model=UserResponse)
def put_facilities(
    user_id: UUID,
    payload: FacilitiesPayload,
    db: Annotated[Session, Depends(get_db)],
    _admin: Annotated[User, Depends(require_admin)],
) -> UserResponse:
    try:
        return resp(svc(db).replace_facilities(user_id, payload.facility_ids))
    except Exception as exc:
        raise map_exc(exc) from exc
