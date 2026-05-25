from datetime import datetime

from sisters_nook.schema import User, UserRole
from tests.test_api.conftest import admin_employee, api_headers


def test_AUTH_001_actor_header_required_for_orders(client):
    resp = client.post(
        "/api/orders",
        headers={"X-User-Role": UserRole.EMPLOYEE.value},
        json={"items": [{"menu_item_id": "missing", "quantity": 1}]},
    )
    assert resp.status_code == 400


def test_AUTH_002_invalid_user_id_for_payment(client):
    resp = client.post(
        "/api/payments",
        headers={
            "X-User-Role": UserRole.EMPLOYEE.value,
            "X-User-Id": "missing",
        },
        json={"order_id": "missing", "amount": "1.00", "method": "cash"},
    )
    assert resp.status_code == 400


def test_AUTH_003_roles_propagated_in_user_list(admin_employee, client):
    admin = admin_employee["admin"]
    resp = client.get("/api/users", headers=api_headers(admin))
    assert resp.status_code == 200
    users = resp.get_json()
    assert any(user["role"] == UserRole.ADMIN.value for user in users)


def test_AUTH_004_inactive_user_cannot_order(admin_employee, client):
    session = admin_employee["session"]
    employee = session.get(User, admin_employee["employee"].id)
    employee.is_active = False
    session.add(employee)
    session.commit()
    session.expire_all()

    resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": admin_employee["latte"].id, "quantity": 1}]},
    )
    assert resp.status_code == 403


def test_AUTH_005_record_login_updates_timestamp(admin_employee, client):
    admin = admin_employee["admin"]
    session = admin_employee["session"]
    resp = client.post(
        f"/api/users/{admin.id}/record-login",
        headers=api_headers(admin),
    )
    assert resp.status_code == 200
    session.expire_all()
    updated = session.get(User, admin.id)
    assert updated.last_login_at is not None
    assert updated.last_login_at <= datetime.utcnow()


def test_AUTH_006_employee_role_blocked_from_admin_list(admin_employee, client):
    employee = admin_employee["employee"]
    resp = client.get("/api/users", headers=api_headers(employee))
    assert resp.status_code == 403
