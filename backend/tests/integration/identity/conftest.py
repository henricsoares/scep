from collections.abc import Iterator
from dataclasses import dataclass
from uuid import UUID

import pytest
from app.infrastructure.database import Base, get_db
from app.main import create_app
from app.modules.identity.application.security import create_access_token, hash_password
from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from fastapi.testclient import TestClient
from pytest import MonkeyPatch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@dataclass
class IdentityContext:
    client: TestClient
    sessions: sessionmaker[Session]

    def create_user(
        self,
        *,
        email: str,
        roles: list[HumanRole] | None = None,
        account_type: AccountType = AccountType.HUMAN,
        status: AccountStatus = AccountStatus.ACTIVE,
        facility_ids: list[UUID] | None = None,
    ) -> User:
        user = User.create(
            email=email,
            display_name=email.split("@", maxsplit=1)[0],
            password_hash=hash_password("SecurePassword123!"),
            account_type=account_type,
            status=status,
            roles=roles or [],
            facility_ids=facility_ids or [],
        )
        with self.sessions() as session:
            return SqlAlchemyUserRepository(session).add(user)

    def headers(self, user: User) -> dict[str, str]:
        token, _ = create_access_token(user)
        return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def identity_context(monkeypatch: MonkeyPatch) -> Iterator[IdentityContext]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Iterator[Session]:
        with sessions() as session:
            yield session

    monkeypatch.setattr("app.main.bootstrap_admin", lambda *_args: None)
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield IdentityContext(client, sessions)
    Base.metadata.drop_all(engine)


@pytest.fixture
def admin(identity_context: IdentityContext) -> User:
    return identity_context.create_user(
        email="admin@example.com", roles=[HumanRole.PLATFORM_ADMINISTRATOR]
    )
