from uuid import UUID

from sqlalchemy.orm import Session

from app.modules.identity.domain.user import User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository


class IdentityDatasetReader:
    def __init__(self, session: Session) -> None:
        self.repository = SqlAlchemyUserRepository(session)

    def get_user(self, user_id: UUID) -> User | None:
        return self.repository.get(user_id)
