from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from app.modules.identity.application.user_service import (
    AuthenticationError,
    DuplicateEmailError,
    InactiveAccountError,
    InvalidAccountError,
    LastAdminError,
    UserNotFoundError,
    UserService,
    bootstrap_admin,
)
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from sqlalchemy.exc import IntegrityError


def make_user(**overrides: object) -> User:
    values: dict[str, object] = {
        "email": "user@example.com",
        "display_name": "User",
        "password_hash": "hash",
        "account_type": AccountType.HUMAN,
        "status": AccountStatus.ACTIVE,
        "roles": [HumanRole.RESEARCHER],
        "facility_ids": [],
    }
    values.update(overrides)
    return User.create(**values)  # type: ignore[arg-type]


def service_with(user: User | None = None) -> tuple[UserService, MagicMock]:
    repository = MagicMock()
    repository.get.return_value = user
    repository.get_by_email.return_value = user
    repository.update.side_effect = lambda value: value
    repository.add.side_effect = lambda value: value
    return UserService(repository), repository


@patch("app.modules.identity.application.user_service.hash_password", return_value="hashed")
def test_create_user_and_duplicate_email(_hash: MagicMock) -> None:
    service, repository = service_with()
    created = service.create_user(
        email=" New@Example.COM ",
        display_name="New User",
        password="SecurePassword123!",
        account_type=AccountType.HUMAN,
        status=AccountStatus.ACTIVE,
        roles=[HumanRole.RESEARCHER],
        facility_ids=[],
    )
    assert created.email == "new@example.com"
    assert created.password_hash == "hashed"

    repository.add.side_effect = IntegrityError("insert", {}, Exception())
    with pytest.raises(DuplicateEmailError):
        service.create_user(
            email="new@example.com",
            display_name="New User",
            password="SecurePassword123!",
            account_type=AccountType.HUMAN,
            status=AccountStatus.ACTIVE,
            roles=[HumanRole.RESEARCHER],
            facility_ids=[],
        )


@patch(
    "app.modules.identity.application.user_service.create_access_token",
    return_value=("jwt", 1800),
)
@patch("app.modules.identity.application.user_service.verify_password", return_value=True)
def test_successful_login_updates_last_login(_verify: MagicMock, _token: MagicMock) -> None:
    user = make_user()
    service, repository = service_with(user)
    token, expires, authenticated = service.login(user.email, "SecurePassword123!")
    assert (token, expires) == ("jwt", 1800)
    assert authenticated.last_login_at is not None
    repository.update.assert_called_once()


@patch("app.modules.identity.application.user_service.verify_password", return_value=False)
def test_login_rejects_unknown_wrong_password_and_inactive(_verify: MagicMock) -> None:
    service, repository = service_with(None)
    with pytest.raises(AuthenticationError, match="invalid credentials"):
        service.login("unknown@example.com", "WrongPassword123!")

    repository.get_by_email.return_value = make_user(status=AccountStatus.INACTIVE)
    _verify.return_value = True
    with pytest.raises(InactiveAccountError):
        service.login("user@example.com", "SecurePassword123!")


def test_get_list_and_missing_user() -> None:
    user = make_user()
    service, repository = service_with(user)
    repository.list.return_value = [user]
    assert service.get(user.id) == user
    assert service.list(status=AccountStatus.ACTIVE) == [user]
    repository.get.return_value = None
    with pytest.raises(UserNotFoundError):
        service.get(uuid4())


def test_last_active_administrator_is_protected() -> None:
    admin = make_user(roles=[HumanRole.PLATFORM_ADMINISTRATOR])
    service, repository = service_with(admin)
    repository.active_admin_count.return_value = 0
    with pytest.raises(LastAdminError):
        service.update_profile(admin.id, display_name=None, status=AccountStatus.INACTIVE)
    with pytest.raises(LastAdminError):
        service.replace_roles(admin.id, [HumanRole.RESEARCHER])


def test_role_and_facility_replacement_rules() -> None:
    facility_id = uuid4()
    operator = make_user(roles=[HumanRole.FACILITY_OPERATOR], facility_ids=[facility_id])
    service, _ = service_with(operator)
    changed = service.replace_roles(operator.id, [HumanRole.RESEARCHER])
    assert changed.roles == (HumanRole.RESEARCHER,)
    assert changed.facility_ids == ()

    technical = make_user(account_type=AccountType.TECHNICAL_CLIENT, roles=[])
    service, _ = service_with(technical)
    with pytest.raises(InvalidAccountError):
        service.replace_roles(technical.id, [HumanRole.RESEARCHER])


def test_facility_existence_is_validated() -> None:
    facility_id = uuid4()
    operator = make_user(roles=[HumanRole.FACILITY_OPERATOR])
    service, repository = service_with(operator)
    facilities = MagicMock()
    facilities.get.return_value = object()
    service.facilities = facilities
    assert service.replace_facilities(operator.id, [facility_id]).facility_ids == (facility_id,)
    facilities.get.return_value = None
    with pytest.raises(UserNotFoundError, match="facility"):
        service.replace_facilities(operator.id, [facility_id])
    repository.update.assert_called_once()


def test_bootstrap_is_optional_and_idempotent() -> None:
    service, repository = service_with()
    bootstrap_admin(service, None, None, None)
    repository.seed_roles.assert_not_called()

    repository.platform_admin_exists.return_value = True
    bootstrap_admin(service, "admin@example.com", "SecurePassword123!", "Admin")
    repository.seed_roles.assert_called_once()
    repository.add.assert_not_called()
