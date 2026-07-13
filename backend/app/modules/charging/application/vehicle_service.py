from uuid import UUID

from app.modules.charging.domain.vehicle import Vehicle, VehicleStatus
from app.modules.charging.infrastructure.reservation_repository import SqlAlchemyVehicleRepository
from app.modules.identity.application.authorization import is_admin
from app.modules.identity.domain.user import AccountStatus, User
from app.modules.identity.infrastructure.user_repository import SqlAlchemyUserRepository
from app.shared.clock import Clock


class VehicleNotFoundError(Exception):
    pass


class VehicleService:
    def __init__(
        self,
        repository: SqlAlchemyVehicleRepository,
        users: SqlAlchemyUserRepository,
        clock: Clock,
    ) -> None:
        self.repository = repository
        self.users = users
        self.clock = clock

    def create(self, *, actor: User, display_name: str, owner_id: UUID | None = None) -> Vehicle:
        owner = actor
        if owner_id is not None and owner_id != actor.id:
            if not is_admin(actor):
                raise PermissionError("owner_id is restricted to Platform Administrators")
            target = self.users.get(owner_id)
            if target is None or target.status != AccountStatus.ACTIVE:
                raise ValueError("owner must be an active authenticated identity")
            owner = target
        return self.repository.add(
            Vehicle.create(owner_id=owner.id, display_name=display_name, now=self.clock.now())
        )

    def list(
        self,
        *,
        actor: User,
        owner_id: UUID | None,
        status: VehicleStatus | None,
        offset: int,
        limit: int,
    ) -> list[Vehicle]:
        if not is_admin(actor):
            owner_id = actor.id
        return self.repository.list(owner_id=owner_id, status=status, offset=offset, limit=limit)

    def get(self, vehicle_id: UUID, *, actor: User) -> Vehicle:
        vehicle = self.repository.get(vehicle_id)
        if vehicle is None or (vehicle.owner_id != actor.id and not is_admin(actor)):
            raise VehicleNotFoundError("vehicle not found")
        return vehicle

    def update(
        self,
        vehicle_id: UUID,
        *,
        actor: User,
        display_name: str | None,
        status: VehicleStatus | None,
    ) -> Vehicle:
        vehicle = self.get(vehicle_id, actor=actor)
        now = self.clock.now()
        if display_name is not None:
            vehicle = vehicle.rename(display_name, now=now)
        if status == VehicleStatus.ACTIVE:
            vehicle = vehicle.activate(now=now)
        elif status == VehicleStatus.INACTIVE:
            vehicle = vehicle.deactivate(now=now)
        return self.repository.update(vehicle)
