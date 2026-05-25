from sisters_nook.schema import UserRole
from tests.test_api.conftest import api_headers


def test_USERS_001_admin_can_create_and_list(client, admin_employee):
    admin = admin_employee["admin"]
    resp = client.post(
        "/api/users",
        headers=api_headers(admin),
        json={
            "first_name": "New",
            "last_name": "User",
            "email": "new.user@sisters.local",
            "password_hash": "hash",
            "role": UserRole.EMPLOYEE.value,
        },
    )
    assert resp.status_code == 201
    user_id = resp.get_json()["id"]

    list_resp = client.get("/api/users", headers=api_headers(admin))
    assert any(user["id"] == user_id for user in list_resp.get_json())


def test_USERS_002_admin_can_update_role(client, admin_employee):
    admin = admin_employee["admin"]
    resp = client.post(
        "/api/users",
        headers=api_headers(admin),
        json={
            "first_name": "Promote",
            "last_name": "User",
            "email": "promote@sisters.local",
            "password_hash": "hash",
            "role": UserRole.EMPLOYEE.value,
        },
    )
    user_id = resp.get_json()["id"]

    update_resp = client.put(
        f"/api/users/{user_id}",
        headers=api_headers(admin),
        json={
            "role": UserRole.ADMIN.value,
        },
    )
    assert update_resp.status_code == 200

    # ensure role change persisted
    list_resp = client.get("/api/users", headers=api_headers(admin))
    updated = next(user for user in list_resp.get_json() if user["id"] == user_id)
    assert updated["role"] == UserRole.ADMIN.value


def test_USERS_003_admin_can_update_name_and_email(client, admin_employee):
    admin = admin_employee["admin"]
    resp = client.post(
        "/api/users",
        headers=api_headers(admin),
        json={
            "first_name": "Rewrite",
            "last_name": "Name",
            "email": "rewrite@sisters.local",
            "password_hash": "hash",
            "role": UserRole.EMPLOYEE.value,
        },
    )
    user_id = resp.get_json()["id"]
    update_resp = client.put(
        f"/api/users/{user_id}",
        headers=api_headers(admin),
        json={
            "first_name": "Fresh",
            "email": "fresh@sisters.local",
        },
    )
    assert update_resp.status_code == 200
    list_resp = client.get("/api/users", headers=api_headers(admin))
    updated = next(user for user in list_resp.get_json() if user["id"] == user_id)
    assert updated["email"] == "fresh@sisters.local"
    assert updated["active"]


def test_USERS_004_admin_can_deactivate_and_reactivate_user(client, admin_employee):
    admin = admin_employee["admin"]
    resp = client.post(
        "/api/users",
        headers=api_headers(admin),
        json={
            "first_name": "Toggle",
            "last_name": "User",
            "email": "toggle@sisters.local",
            "password_hash": "hash",
            "role": UserRole.EMPLOYEE.value,
        },
    )
    user_id = resp.get_json()["id"]
    deactivate_resp = client.post(
        f"/api/users/{user_id}/deactivate",
        headers=api_headers(admin),
    )
    assert deactivate_resp.status_code == 200
    list_resp = client.get("/api/users", headers=api_headers(admin))
    updated = next(user for user in list_resp.get_json() if user["id"] == user_id)
    assert not updated["active"]
    reactivate_resp = client.post(
        f"/api/users/{user_id}/reactivate",
        headers=api_headers(admin),
    )
    assert reactivate_resp.status_code == 200
    list_resp = client.get("/api/users", headers=api_headers(admin))
    updated = next(user for user in list_resp.get_json() if user["id"] == user_id)
    assert updated["active"]


def test_USERS_005_employee_cannot_manage_users(client, admin_employee):
    employee = admin_employee["employee"]
    resp = client.post(
        "/api/users",
        headers=api_headers(employee),
        json={
            "first_name": "Blocked",
            "last_name": "User",
            "email": "blocked@sisters.local",
            "password_hash": "hash",
            "role": UserRole.EMPLOYEE.value,
        },
    )
    assert resp.status_code == 403


def test_USERS_006_inactive_user_remains_listed(client, admin_employee):
    admin = admin_employee["admin"]
    resp = client.post(
        "/api/users",
        headers=api_headers(admin),
        json={
            "first_name": "Soft",
            "last_name": "Delete",
            "email": "soft@sisters.local",
            "password_hash": "hash",
            "role": UserRole.EMPLOYEE.value,
        },
    )
    user_id = resp.get_json()["id"]
    client.post(f"/api/users/{user_id}/deactivate", headers=api_headers(admin))
    list_resp = client.get("/api/users", headers=api_headers(admin))
    entries = [user for user in list_resp.get_json() if user["id"] == user_id]
    assert entries
    assert not entries[0]["active"]
