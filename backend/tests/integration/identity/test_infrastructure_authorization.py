from uuid import UUID

from app.modules.identity.domain.user import AccountType, HumanRole, User

from tests.integration.identity.conftest import IdentityContext


def facility_payload(name: str) -> dict[str, object]:
    return {
        "name": name,
        "facility_type": "University",
        "timezone": "UTC",
        "country": "Brazil",
        "city": "Juiz de Fora",
        "address": "Campus",
    }


def test_existing_api_authorization_matrix(identity_context: IdentityContext, admin: User) -> None:
    client = identity_context.client
    admin_headers = identity_context.headers(admin)
    assigned = client.post(
        "/facilities", json=facility_payload("Assigned"), headers=admin_headers
    ).json()
    unassigned = client.post(
        "/facilities", json=facility_payload("Unassigned"), headers=admin_headers
    ).json()
    operator = identity_context.create_user(
        email="operator@example.com",
        roles=[HumanRole.FACILITY_OPERATOR],
        facility_ids=[UUID(assigned["id"])],
    )
    researcher = identity_context.create_user(
        email="researcher@example.com", roles=[HumanRole.RESEARCHER]
    )
    technical = identity_context.create_user(
        email="technical@example.com", account_type=AccountType.TECHNICAL_CLIENT
    )

    assert client.get("/facilities").status_code == 401
    assert client.get("/facilities", headers=admin_headers).status_code == 200

    operator_headers = identity_context.headers(operator)
    visible = client.get("/facilities", headers=operator_headers)
    assert [facility["id"] for facility in visible.json()] == [assigned["id"]]
    assert (
        client.put(
            f"/facilities/{unassigned['id']}",
            json=facility_payload("Still Unassigned"),
            headers=operator_headers,
        ).status_code
        == 404
    )

    for actor in (researcher, technical):
        headers = identity_context.headers(actor)
        assert client.get("/facilities", headers=headers).status_code == 200
        response = client.post("/facilities", json=facility_payload("Forbidden"), headers=headers)
        assert response.status_code == 403
