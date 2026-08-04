from enum import StrEnum
from uuid import UUID

from app.modules.charging.domain.facility import Facility, FacilityStatus
from app.modules.identity.domain.user import (
    AccountStatus,
    AccountType,
    HumanRole,
    TechnicalClientProfile,
    User,
)


class Capability(StrEnum):
    RESEARCH_DATASET_EXPORT = "research:dataset-export"
    PUBLISH_OCCUPANCY_PREDICTIONS = "predictions:publish"
    READ_TECHNICAL_PREDICTIONS = "predictions:read-technical"
    MANAGE_SIMULATION_RUNS = "simulations:manage"


ROLE_CAPABILITIES: dict[HumanRole, frozenset[Capability]] = {
    HumanRole.PLATFORM_ADMINISTRATOR: frozenset(Capability),
    HumanRole.RESEARCHER: frozenset({Capability.MANAGE_SIMULATION_RUNS}),
    HumanRole.DATA_SCIENTIST: frozenset(
        {
            Capability.RESEARCH_DATASET_EXPORT,
            Capability.PUBLISH_OCCUPANCY_PREDICTIONS,
            Capability.READ_TECHNICAL_PREDICTIONS,
        }
    ),
}

TECHNICAL_PROFILE_CAPABILITIES: dict[TechnicalClientProfile, frozenset[Capability]] = {
    TechnicalClientProfile.AI_RESEARCH_ENVIRONMENT: frozenset(
        {
            Capability.RESEARCH_DATASET_EXPORT,
            Capability.PUBLISH_OCCUPANCY_PREDICTIONS,
            Capability.READ_TECHNICAL_PREDICTIONS,
        }
    )
}


def has_capability(user: User, capability: Capability) -> bool:
    if user.status != AccountStatus.ACTIVE:
        return False
    if user.account_type == AccountType.HUMAN:
        return any(capability in ROLE_CAPABILITIES.get(role, frozenset()) for role in user.roles)
    if user.technical_profile is None:
        return False
    return capability in TECHNICAL_PROFILE_CAPABILITIES.get(user.technical_profile, frozenset())


def prediction_publisher_subject_id(user: User) -> UUID:
    if not has_capability(user, Capability.PUBLISH_OCCUPANCY_PREDICTIONS):
        raise PermissionError("subject is not authorized to publish predictions")
    return user.id


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
