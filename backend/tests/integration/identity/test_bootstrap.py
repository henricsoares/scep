import logging

import pytest
from app.modules.identity.application.user_service import (
    DuplicateEmailError,
    UserService,
    bootstrap_admin,
)
from app.modules.identity.domain.user import AccountStatus, HumanRole
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository

from tests.integration.identity.conftest import IdentityContext


def run_bootstrap(context: IdentityContext) -> None:
    with context.sessions() as session:
        bootstrap_admin(
            UserService(SqlAlchemyUserRepository(session)),
            "bootstrap@example.com",
            "BootstrapPassword123!",
            "Bootstrap Admin",
        )


def test_first_bootstrap_and_repeated_startup(identity_context: IdentityContext) -> None:
    run_bootstrap(identity_context)
    run_bootstrap(identity_context)

    with identity_context.sessions() as session:
        users = SqlAlchemyUserRepository(session).list(role=HumanRole.PLATFORM_ADMINISTRATOR)
    assert len(users) == 1
    assert users[0].status == AccountStatus.ACTIVE


@pytest.mark.parametrize("status", [AccountStatus.ACTIVE, AccountStatus.INACTIVE])
def test_existing_administrator_prevents_bootstrap(
    identity_context: IdentityContext, status: AccountStatus
) -> None:
    identity_context.create_user(
        email="existing@example.com",
        roles=[HumanRole.PLATFORM_ADMINISTRATOR],
        status=status,
    )

    run_bootstrap(identity_context)

    with identity_context.sessions() as session:
        repository = SqlAlchemyUserRepository(session)
        assert len(repository.list(role=HumanRole.PLATFORM_ADMINISTRATOR)) == 1
        assert repository.get_by_email("bootstrap@example.com") is None


def test_bootstrap_email_collision_fails_without_logging_password(
    identity_context: IdentityContext, caplog: pytest.LogCaptureFixture
) -> None:
    identity_context.create_user(email="bootstrap@example.com", roles=[HumanRole.RESEARCHER])

    with (
        caplog.at_level(logging.INFO),
        pytest.raises(DuplicateEmailError, match="email already exists"),
    ):
        run_bootstrap(identity_context)
    assert "BootstrapPassword123!" not in caplog.text
