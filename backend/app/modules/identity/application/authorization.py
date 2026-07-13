from uuid import UUID

from app.modules.charging.domain.facility import Facility, FacilityStatus
from app.modules.identity.domain.user import AccountType, HumanRole, User


def is_admin(u: User) -> bool:
    return HumanRole.PLATFORM_ADMINISTRATOR in u.roles


def can_read_facility(u: User, f: Facility) -> bool:
    if is_admin(u) or HumanRole.RESEARCHER in u.roles or HumanRole.DATA_SCIENTIST in u.roles:
        return True
    if HumanRole.FACILITY_OPERATOR in u.roles:
        return f.id in u.facility_ids
    if HumanRole.EV_DRIVER in u.roles or u.account_type == AccountType.TECHNICAL_CLIENT:
        return f.status == FacilityStatus.ACTIVE
    return False


def can_manage_facility(u: User, facility_id: UUID) -> bool:
    return is_admin(u) or (HumanRole.FACILITY_OPERATOR in u.roles and facility_id in u.facility_ids)


def can_create_facility(u: User) -> bool:
    return is_admin(u)


def can_manage_owned_resource(u: User, owner_id: UUID) -> bool:
    return is_admin(u) or u.id == owner_id


def can_read_reservation_owner(u: User, owner_id: UUID) -> bool:
    return (
        can_manage_owned_resource(u, owner_id)
        or HumanRole.RESEARCHER in u.roles
        or HumanRole.DATA_SCIENTIST in u.roles
    )
