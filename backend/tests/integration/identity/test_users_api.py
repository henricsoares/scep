from app.modules.identity.domain.user import AccountStatus, HumanRole, User

from tests.integration.identity.conftest import IdentityContext


def user_payload(email: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "email": email,
        "display_name": "Example User",
        "password": "SecurePassword123!",
        "account_type": "Human",
        "status": "Active",
        "roles": ["Researcher"],
        "facility_ids": [],
    }
    payload.update(overrides)
    return payload


def test_user_management_lifecycle(identity_context: IdentityContext, admin: User) -> None:
    client = identity_context.client
    headers = identity_context.headers(admin)

    human = client.post("/users", json=user_payload("Human@Example.com"), headers=headers)
    technical = client.post(
        "/users",
        json=user_payload(
            "client@example.com",
            account_type="TechnicalClient",
            roles=[],
            display_name="Simulation Client",
        ),
        headers=headers,
    )

    assert human.status_code == 201
    assert human.json()["email"] == "human@example.com"
    assert technical.status_code == 201
    assert technical.json()["roles"] == []
    assert "password" not in human.json()
    assert "password_hash" not in human.json()

    duplicate = client.post("/users", json=user_payload(" HUMAN@example.COM "), headers=headers)
    assert duplicate.status_code == 409

    users = client.get("/users", headers=headers)
    assert users.status_code == 200
    assert len(users.json()) == 3
    assert client.get(f"/users/{human.json()['id']}", headers=headers).status_code == 200


def test_user_patch_supports_each_partial_shape(
    identity_context: IdentityContext, admin: User
) -> None:
    client = identity_context.client
    headers = identity_context.headers(admin)
    created = client.post("/users", json=user_payload("operator@example.com"), headers=headers)
    user_id = created.json()["id"]

    status_only = client.patch(f"/users/{user_id}", json={"status": "Inactive"}, headers=headers)
    display_only = client.patch(
        f"/users/{user_id}", json={"display_name": "Renamed Operator"}, headers=headers
    )
    both = client.patch(
        f"/users/{user_id}",
        json={"display_name": "Active Operator", "status": "Active"},
        headers=headers,
    )

    assert status_only.status_code == 200
    assert status_only.json()["status"] == "Inactive"
    assert display_only.status_code == 200
    assert display_only.json()["display_name"] == "Renamed Operator"
    assert both.status_code == 200
    assert both.json()["display_name"] == "Active Operator"
    assert both.json()["status"] == "Active"
    assert client.patch(f"/users/{user_id}", json={}, headers=headers).status_code == 422


def test_invalid_status_transition_and_last_admin_are_rejected(
    identity_context: IdentityContext, admin: User
) -> None:
    client = identity_context.client
    headers = identity_context.headers(admin)
    inactive = client.post(
        "/users",
        json=user_payload("pending@example.com", status="Inactive", roles=[]),
        headers=headers,
    )

    invalid = client.patch(
        f"/users/{inactive.json()['id']}", json={"status": "Active"}, headers=headers
    )
    protected = client.patch(f"/users/{admin.id}", json={"status": "Inactive"}, headers=headers)

    assert invalid.status_code == 422
    assert invalid.json()["detail"] == "Active Human accounts must have at least one Role"
    assert protected.status_code == 409


def test_role_and_facility_replacement(identity_context: IdentityContext, admin: User) -> None:
    client = identity_context.client
    headers = identity_context.headers(admin)
    facility = client.post(
        "/facilities",
        json={
            "name": "Identity Facility",
            "facility_type": "University",
            "timezone": "UTC",
            "country": "Brazil",
            "city": "Juiz de Fora",
            "address": "Campus",
        },
        headers=headers,
    ).json()
    created = client.post(
        "/users", json=user_payload("operator@example.com"), headers=headers
    ).json()

    roles = client.put(
        f"/users/{created['id']}/roles",
        json={"roles": ["FacilityOperator", "Researcher"]},
        headers=headers,
    )
    facilities = client.put(
        f"/users/{created['id']}/facilities",
        json={"facility_ids": [facility["id"]]},
        headers=headers,
    )

    assert roles.status_code == 200
    assert roles.json()["roles"] == ["FacilityOperator", "Researcher"]
    assert facilities.status_code == 200
    assert facilities.json()["facility_ids"] == [facility["id"]]


def test_filters_and_last_admin_role_protection(
    identity_context: IdentityContext, admin: User
) -> None:
    client = identity_context.client
    headers = identity_context.headers(admin)
    identity_context.create_user(
        email="inactive@example.com",
        roles=[HumanRole.RESEARCHER],
        status=AccountStatus.INACTIVE,
    )

    filtered = client.get("/users?status=Inactive&role=Researcher", headers=headers)
    remove_admin = client.put(
        f"/users/{admin.id}/roles", json={"roles": ["Researcher"]}, headers=headers
    )

    assert filtered.status_code == 200
    assert [user["email"] for user in filtered.json()] == ["inactive@example.com"]
    assert remove_admin.status_code == 409
