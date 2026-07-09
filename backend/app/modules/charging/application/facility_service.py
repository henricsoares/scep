from uuid import UUID

from app.modules.charging.domain.facility import Facility, FacilityStatus, FacilityType
from app.modules.charging.domain.repositories import FacilityRepository


class FacilityNotFoundError(Exception):
    pass


class FacilityNameAlreadyExistsError(Exception):
    pass


class FacilityService:
    def __init__(self, repository: FacilityRepository) -> None:
        self.repository = repository

    def create_facility(
        self,
        *,
        name: str,
        facility_type: FacilityType,
        timezone: str,
        country: str,
        city: str,
        address: str,
        latitude: float | None,
        longitude: float | None,
        operating_hours: dict[str, object] | None,
        status: FacilityStatus,
    ) -> Facility:
        if self.repository.exists_by_name(name):
            raise FacilityNameAlreadyExistsError(name)
        facility = Facility.create(
            name=name,
            facility_type=facility_type,
            timezone=timezone,
            country=country,
            city=city,
            address=address,
            latitude=latitude,
            longitude=longitude,
            operating_hours=operating_hours,
            status=status,
        )
        return self.repository.add(facility)

    def list_facilities(self) -> list[Facility]:
        return self.repository.list()

    def get_facility(self, facility_id: UUID) -> Facility:
        facility = self.repository.get(facility_id)
        if facility is None:
            raise FacilityNotFoundError(str(facility_id))
        return facility

    def update_facility(self, facility_id: UUID, **changes: object) -> Facility:
        facility = self.get_facility(facility_id)
        name = changes["name"]
        if not isinstance(name, str):
            raise ValueError("name is required")
        if self.repository.exists_by_name(name, exclude_id=facility_id):
            raise FacilityNameAlreadyExistsError(name)
        updated = facility.update(**changes)  # type: ignore[arg-type]
        return self.repository.update(updated)

    def delete_facility(self, facility_id: UUID) -> None:
        if self.repository.get(facility_id) is None:
            raise FacilityNotFoundError(str(facility_id))
        self.repository.delete(facility_id)
