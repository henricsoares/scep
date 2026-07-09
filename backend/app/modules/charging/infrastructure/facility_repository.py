from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.charging.domain.facility import Facility, FacilityStatus, FacilityType
from app.modules.charging.domain.repositories import FacilityRepository
from app.modules.charging.infrastructure.facility_model import FacilityModel


class SqlAlchemyFacilityRepository(FacilityRepository):
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, facility: Facility) -> Facility:
        model = self._to_model(facility)
        self.session.add(model)
        try:
            self.session.commit()
        except IntegrityError:
            self.session.rollback()
            raise
        self.session.refresh(model)
        return self._to_domain(model)

    def get(self, facility_id: UUID) -> Facility | None:
        model = self.session.get(FacilityModel, facility_id)
        return None if model is None else self._to_domain(model)

    def list(self) -> list[Facility]:
        stmt = select(FacilityModel).order_by(FacilityModel.created_at)
        models = self.session.scalars(stmt).all()
        return [self._to_domain(model) for model in models]

    def update(self, facility: Facility) -> Facility:
        model = self.session.get(FacilityModel, facility.id)
        if model is None:
            raise ValueError("facility not found")
        model.name = facility.name
        model.facility_type = facility.facility_type.value
        model.timezone = facility.timezone
        model.country = facility.country
        model.city = facility.city
        model.address = facility.address
        model.latitude = facility.latitude
        model.longitude = facility.longitude
        model.operating_hours = facility.operating_hours
        model.status = facility.status.value
        self.session.commit()
        self.session.refresh(model)
        return self._to_domain(model)

    def delete(self, facility_id: UUID) -> None:
        model = self.session.get(FacilityModel, facility_id)
        if model is not None:
            self.session.delete(model)
            self.session.commit()

    def exists_by_name(self, name: str, *, exclude_id: UUID | None = None) -> bool:
        stmt = select(FacilityModel.id).where(FacilityModel.name == name)
        if exclude_id is not None:
            stmt = stmt.where(FacilityModel.id != exclude_id)
        return self.session.scalar(stmt) is not None

    def _to_model(self, facility: Facility) -> FacilityModel:
        return FacilityModel(
            id=facility.id,
            name=facility.name,
            facility_type=facility.facility_type.value,
            timezone=facility.timezone,
            country=facility.country,
            city=facility.city,
            address=facility.address,
            latitude=facility.latitude,
            longitude=facility.longitude,
            operating_hours=facility.operating_hours,
            status=facility.status.value,
            created_at=facility.created_at,
            updated_at=facility.updated_at,
        )

    def _to_domain(self, model: FacilityModel) -> Facility:
        return Facility(
            id=model.id,
            name=model.name,
            facility_type=FacilityType(model.facility_type),
            timezone=model.timezone,
            country=model.country,
            city=model.city,
            address=model.address,
            latitude=model.latitude,
            longitude=model.longitude,
            operating_hours=model.operating_hours,
            status=FacilityStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
