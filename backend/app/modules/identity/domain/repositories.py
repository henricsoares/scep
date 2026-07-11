from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.identity.domain.user import AccountStatus, AccountType, HumanRole, User


class UserRepositoryError(Exception):
    pass


class DuplicateUserEmailError(UserRepositoryError):
    pass


class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> User: ...

    @abstractmethod
    def get(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def list(
        self,
        *,
        status: AccountStatus | None = None,
        role: HumanRole | None = None,
        account_type: AccountType | None = None,
    ) -> list[User]: ...

    @abstractmethod
    def update(self, user: User) -> User: ...

    @abstractmethod
    def active_admin_count(self, *, exclude_id: UUID | None = None) -> int: ...

    @abstractmethod
    def platform_admin_exists(self) -> bool: ...
