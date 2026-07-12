from uuid import uuid4

import pytest
from app.modules.identity.domain.user import (
    AccountStatus,
    AccountType,
    HumanRole,
    User,
    normalize_email,
    validate_password,
)


def make_user(**overrides: object) -> User:
    values: dict[str, object] = {
        "email": " User@Example.COM ",
        "display_name": "Example User",
        "password_hash": "hashed",
        "account_type": AccountType.HUMAN,
        "status": AccountStatus.ACTIVE,
        "roles": [HumanRole.RESEARCHER],
        "facility_ids": [],
    }
    values.update(overrides)
    return User.create(**values)  # type: ignore[arg-type]


def test_user_creation_normalizes_email_and_deduplicates_relations() -> None:
    facility_id = uuid4()
    user = make_user(
        roles=[HumanRole.FACILITY_OPERATOR, HumanRole.FACILITY_OPERATOR],
        facility_ids=[facility_id, facility_id],
    )

    assert user.email == "user@example.com"
    assert user.roles == (HumanRole.FACILITY_OPERATOR,)
    assert user.facility_ids == (facility_id,)
    assert user.created_at == user.updated_at


@pytest.mark.parametrize("email", ["", "missing-at.example.com", "a@b", "a b@example.com"])
def test_invalid_emails_are_rejected(email: str) -> None:
    with pytest.raises(ValueError, match="invalid email"):
        normalize_email(email)


@pytest.mark.parametrize(
    ("password", "message"),
    [
        ("Short1!", "12 characters"),
        ("lowercase123!", "uppercase"),
        ("UPPERCASE123!", "lowercase"),
        ("NoNumbersHere!", "numeric"),
        ("NoSpecial1234", "special"),
        ("user@example.com-A1!", "email address"),
    ],
)
def test_password_rules_are_enforced(password: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_password(password, "user@example.com")


def test_valid_password_is_accepted() -> None:
    validate_password("SecurePassword123!", "user@example.com")


def test_active_human_requires_role() -> None:
    with pytest.raises(ValueError, match="at least one Role"):
        make_user(roles=[])


def test_facility_assignment_requires_operator_role() -> None:
    with pytest.raises(ValueError, match="Facility assignments require"):
        make_user(facility_ids=[uuid4()])


def test_technical_client_rejects_roles_and_facilities() -> None:
    with pytest.raises(ValueError, match="must not have Human Roles"):
        make_user(account_type=AccountType.TECHNICAL_CLIENT, roles=[HumanRole.RESEARCHER])
    with pytest.raises(ValueError, match="must not have Facility assignments"):
        make_user(account_type=AccountType.TECHNICAL_CLIENT, roles=[], facility_ids=[uuid4()])


def test_profile_roles_facilities_and_last_login_updates() -> None:
    facility_id = uuid4()
    user = make_user(roles=[HumanRole.FACILITY_OPERATOR])

    profiled = user.with_profile(display_name="Renamed", status=AccountStatus.INACTIVE)
    assigned = profiled.with_facilities([facility_id])
    multi_role = assigned.with_roles([HumanRole.FACILITY_OPERATOR, HumanRole.RESEARCHER])
    logged_in = multi_role.with_last_login()

    assert profiled.display_name == "Renamed"
    assert profiled.status == AccountStatus.INACTIVE
    assert assigned.facility_ids == (facility_id,)
    assert multi_role.roles == (HumanRole.FACILITY_OPERATOR, HumanRole.RESEARCHER)
    assert logged_in.last_login_at is not None


def test_display_name_and_password_hash_are_required() -> None:
    with pytest.raises(ValueError, match="display name"):
        make_user(display_name=" ")
    with pytest.raises(ValueError, match="password hash"):
        make_user(password_hash="")
