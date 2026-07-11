from builtins import list as builtin_list
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.modules.charging.domain.repositories import FacilityRepository
from app.modules.identity.application.metrics import (
    account_created_total,
    auth_failed_total,
    auth_inactive_total,
    auth_success_total,
)
from app.modules.identity.application.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.modules.identity.domain.user import (
    AccountStatus,
    AccountType,
    HumanRole,
    User,
    normalize_email,
    validate_password,
)
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository


class AuthenticationError(Exception):
    pass


class InactiveAccountError(Exception):
    pass


class UserNotFoundError(Exception):
    pass


class DuplicateEmailError(Exception):
    pass


class LastAdminError(Exception):
    pass


class InvalidAccountError(Exception):
    pass


class UserService:
    def __init__(
        self, users: SqlAlchemyUserRepository, facilities: FacilityRepository | None = None
    ) -> None:
        self.users = users
        self.facilities = facilities

    def create_user(
        self,
        *,
        email: str,
        display_name: str,
        password: str,
        account_type: AccountType,
        status: AccountStatus,
        roles: builtin_list[HumanRole],
        facility_ids: builtin_list[UUID],
    ) -> User:
        normalized = normalize_email(email)
        validate_password(password, normalized)
        self._validate_facilities(facility_ids)
        user = User.create(
            email=normalized,
            display_name=display_name,
            password_hash=hash_password(password),
            account_type=account_type,
            status=status,
            roles=roles,
            facility_ids=facility_ids,
        )
        try:
            created = self.users.add(user)
            account_created_total.inc()
            return created
        except IntegrityError as exc:
            raise DuplicateEmailError("email already exists") from exc

    def login(self, email: str, password: str) -> tuple[str, int, User]:
        user = self.users.get_by_email(normalize_email(email))
        if user is None or not verify_password(password, user.password_hash):
            auth_failed_total.inc()
            raise AuthenticationError("invalid credentials")
        if user.status != AccountStatus.ACTIVE:
            auth_inactive_total.inc()
            raise InactiveAccountError("account is Inactive")
        try:
            user.validate()
        except ValueError as exc:
            auth_failed_total.inc()
            raise AuthenticationError("invalid credentials") from exc
        user = self.users.update(user.with_last_login())
        auth_success_total.inc()
        token, expires = create_access_token(user)
        return token, expires, user

    def get(self, user_id: UUID) -> User:
        user = self.users.get(user_id)
        if user is None:
            raise UserNotFoundError("user not found")
        return user

    def list(self, **filters: object) -> list[User]:
        return self.users.list(**filters)  # type: ignore[arg-type]

    def update_profile(
        self, user_id: UUID, *, display_name: str | None, status: AccountStatus | None
    ) -> User:
        user = self.get(user_id)
        if (
            status == AccountStatus.INACTIVE
            and HumanRole.PLATFORM_ADMINISTRATOR in user.roles
            and self.users.active_admin_count(exclude_id=user.id) == 0
        ):
            raise LastAdminError("operation would remove the last Active Platform Administrator")
        return self.users.update(user.with_profile(display_name=display_name, status=status))

    def replace_roles(self, user_id: UUID, roles: builtin_list[HumanRole]) -> User:
        user = self.get(user_id)
        if user.account_type == AccountType.TECHNICAL_CLIENT and roles:
            raise InvalidAccountError("Technical Client accounts must not have Human Roles")
        if (
            HumanRole.PLATFORM_ADMINISTRATOR in user.roles
            and HumanRole.PLATFORM_ADMINISTRATOR not in roles
            and user.status == AccountStatus.ACTIVE
            and self.users.active_admin_count(exclude_id=user.id) == 0
        ):
            raise LastAdminError("operation would remove the last Active Platform Administrator")
        facilities = builtin_list(user.facility_ids) if HumanRole.FACILITY_OPERATOR in roles else []
        return self.users.update(user.with_roles(roles).with_facilities(facilities))

    def replace_facilities(self, user_id: UUID, facility_ids: builtin_list[UUID]) -> User:
        user = self.get(user_id)
        self._validate_facilities(facility_ids)
        return self.users.update(user.with_facilities(facility_ids))

    def _validate_facilities(self, facility_ids: builtin_list[UUID]) -> None:
        if self.facilities:
            for f in facility_ids:
                if self.facilities.get(f) is None:
                    raise UserNotFoundError("facility not found")


def bootstrap_admin(
    service: UserService, email: str | None, password: str | None, display_name: str | None
) -> None:
    if not (email and password and display_name):
        return
    service.users.seed_roles()
    if service.users.platform_admin_exists():
        return
    service.create_user(
        email=email,
        display_name=display_name,
        password=password,
        account_type=AccountType.HUMAN,
        status=AccountStatus.ACTIVE,
        roles=[HumanRole.PLATFORM_ADMINISTRATOR],
        facility_ids=[],
    )
