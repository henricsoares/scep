from dataclasses import replace

import pytest
from app.modules.identity.application.authorization import (
    Capability,
    has_capability,
    prediction_publisher_subject_id,
)
from app.modules.identity.domain.user import (
    AccountStatus,
    AccountType,
    HumanRole,
    TechnicalClientProfile,
    User,
)


def actor(role: HumanRole) -> User:
    return User.create(
        email=f"{role.value.lower()}@example.com",
        display_name=role.value,
        password_hash="hash",
        account_type=AccountType.HUMAN,
        status=AccountStatus.ACTIVE,
        roles=[role],
        facility_ids=[],
    )


@pytest.mark.parametrize(
    ("role", "allowed", "denied"),
    [
        (
            HumanRole.RESEARCHER,
            Capability.MANAGE_SIMULATION_RUNS,
            Capability.PUBLISH_OCCUPANCY_PREDICTIONS,
        ),
        (
            HumanRole.DATA_SCIENTIST,
            Capability.RESEARCH_DATASET_EXPORT,
            Capability.MANAGE_SIMULATION_RUNS,
        ),
    ],
)
def test_research_roles_have_distinct_static_capabilities(
    role: HumanRole, allowed: Capability, denied: Capability
) -> None:
    user = actor(role)
    assert has_capability(user, allowed)
    assert not has_capability(user, denied)


def test_platform_administrator_has_all_research_capabilities() -> None:
    administrator = actor(HumanRole.PLATFORM_ADMINISTRATOR)
    assert all(has_capability(administrator, capability) for capability in Capability)


@pytest.mark.parametrize("role", [HumanRole.FACILITY_OPERATOR, HumanRole.EV_DRIVER])
def test_operational_roles_receive_no_research_capabilities(role: HumanRole) -> None:
    user = actor(role)
    assert not any(has_capability(user, capability) for capability in Capability)


def test_only_explicit_ai_research_technical_client_gets_research_capabilities() -> None:
    legacy = User.create(
        email="legacy-client@example.com",
        display_name="Legacy client",
        password_hash="hash",
        account_type=AccountType.TECHNICAL_CLIENT,
        status=AccountStatus.ACTIVE,
        roles=[],
        facility_ids=[],
    )
    ai = replace(legacy, technical_profile=TechnicalClientProfile.AI_RESEARCH_ENVIRONMENT)
    assert not any(has_capability(legacy, capability) for capability in Capability)
    assert has_capability(ai, Capability.RESEARCH_DATASET_EXPORT)
    assert has_capability(ai, Capability.PUBLISH_OCCUPANCY_PREDICTIONS)
    assert not has_capability(ai, Capability.MANAGE_SIMULATION_RUNS)
    assert not has_capability(
        replace(ai, status=AccountStatus.INACTIVE), Capability.PUBLISH_OCCUPANCY_PREDICTIONS
    )


def test_prediction_publisher_identity_is_always_the_authenticated_subject() -> None:
    data_scientist = actor(HumanRole.DATA_SCIENTIST)
    assert prediction_publisher_subject_id(data_scientist) == data_scientist.id
    with pytest.raises(PermissionError):
        prediction_publisher_subject_id(actor(HumanRole.RESEARCHER))
