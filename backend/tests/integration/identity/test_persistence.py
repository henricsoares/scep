from uuid import UUID, uuid4

import pytest
from app.modules.charging.domain.facility import Facility, FacilityStatus, FacilityType
from app.modules.charging.infrastructure.facility_repository import SqlAlchemyFacilityRepository
from app.modules.identity.application.security import hash_password
from app.modules.identity.domain.repositories import DuplicateUserEmailError
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_model import UserModel
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from sqlalchemy.exc import IntegrityError

from tests.integration.identity.conftest import IdentityContext


def make_user(email: str, *, facility_ids: list[UUID] | None = None) -> User:
    return User.create(
        email=email,
        display_name="Operator",
        password_hash=hash_password("SecurePassword123!"),
        account_type=AccountType.HUMAN,
        status=AccountStatus.ACTIVE,
        roles=[HumanRole.FACILITY_OPERATOR],
        facility_ids=facility_ids or [],
    )


def test_normalized_email_uniqueness_and_relationships(
    identity_context: IdentityContext,
) -> None:
    facility = Facility.create(
        name="Repository Facility",
        facility_type=FacilityType.UNIVERSITY,
        timezone="UTC",
        country="Brazil",
        city="Juiz de Fora",
        address="Campus",
        status=FacilityStatus.ACTIVE,
    )
    with identity_context.sessions() as session:
        SqlAlchemyFacilityRepository(session).add(facility)
        repository = SqlAlchemyUserRepository(session)
        created = repository.add(make_user(" Operator@Example.COM ", facility_ids=[facility.id]))

        assert created.email == "operator@example.com"
        assert created.roles == (HumanRole.FACILITY_OPERATOR,)
        assert created.facility_ids == (facility.id,)

        with pytest.raises(DuplicateUserEmailError):
            repository.add(make_user("OPERATOR@example.com"))


@pytest.mark.parametrize(
    ("account_type", "status"),
    [("Unknown", "Active"), ("Human", "Unknown")],
)
def test_invalid_account_type_and_status_are_rejected_by_database(
    identity_context: IdentityContext, account_type: str, status: str
) -> None:
    with identity_context.sessions() as session:
        session.add(
            UserModel(
                id=uuid4(),
                email=f"{account_type}-{status}@example.com".lower(),
                display_name="Invalid",
                password_hash="hash",
                account_type=account_type,
                status=status,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_valid_account_types_and_statuses_are_persisted(
    identity_context: IdentityContext,
) -> None:
    human = identity_context.create_user(
        email="inactive@example.com",
        roles=[HumanRole.RESEARCHER],
        status=AccountStatus.INACTIVE,
    )
    technical = identity_context.create_user(
        email="technical@example.com", account_type=AccountType.TECHNICAL_CLIENT
    )

    assert human.status == AccountStatus.INACTIVE
    assert technical.account_type == AccountType.TECHNICAL_CLIENT
