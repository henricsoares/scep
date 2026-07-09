from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.charging.domain.facility import Facility


class FacilityRepository(ABC):
    @abstractmethod
    def add(self, facility: Facility) -> Facility: ...

    @abstractmethod
    def get(self, facility_id: UUID) -> Facility | None: ...

    @abstractmethod
    def list(self) -> list[Facility]: ...

    @abstractmethod
    def update(self, facility: Facility) -> Facility: ...

    @abstractmethod
    def delete(self, facility_id: UUID) -> None: ...

    @abstractmethod
    def exists_by_name(self, name: str, *, exclude_id: UUID | None = None) -> bool: ...
