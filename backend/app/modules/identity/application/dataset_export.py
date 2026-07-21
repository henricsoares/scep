from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.modules.identity.domain.user import User


class DatasetExportIdentityReadPort(Protocol):
    def get_user(self, user_id: UUID) -> User | None: ...
