from sisters_nook.schema import PaymentMethod, PaymentStatus
from tests.test_api.conftest import admin_employee, api_headers


def test_PERMISSIONS_001_missing_role_is_forbidden(client, admin_employee):
    admin = admin_employee["admin"]
    resp = client.post(
        "/api/menu",
        headers={"X-User-Id": admin.id},
        json={"name": "Unauthorized", "price": "1.00"},
    )
    assert resp.status_code == 403


def test_PERMISSIONS_002_employee_cannot_hit_admin_endpoint(client, admin_employee):
    employee = admin_employee["employee"]
    resp = client.post(
        "/api/menu",
        headers=api_headers(employee),
        json={"name": "Flat White", "price": "3.50"},
    )
    assert resp.status_code == 403


def test_PERMISSIONS_003_invalid_user_id_becomes_bad_request(client):
    resp = client.post(
        "/api/menu",
        headers={"X-User-Id": "missing", "X-User-Role": "admin"},
        json={"name": "NoUser", "price": "2.00"},
    )
    assert resp.status_code == 400


def test_PERMISSIONS_004_admin_and_employee_can_view_menu(admin_employee, client):
    for user_key in ["admin", "employee"]:
        user = admin_employee[user_key]
        resp = client.get("/api/menu", headers=api_headers(user))
        assert resp.status_code == 200
        assert resp.get_json()


def test_PERMISSIONS_005_admin_sees_inactive_items(admin_employee, client):
    admin = admin_employee["admin"]
    latte = admin_employee["latte"]
    client.delete(f"/api/menu/{latte.id}", headers=api_headers(admin))
    resp = client.get("/api/menu", headers=api_headers(admin))
    inactive = [item for item in resp.get_json() if not item["active"]]
    assert any(item["id"] == latte.id for item in inactive)


def test_PERMISSIONS_006_roles_can_create_orders(admin_employee, client):
    latte = admin_employee["latte"]
    for user_key in ["admin", "employee"]:
        user = admin_employee[user_key]
        resp = client.post(
            "/api/orders",
            headers=api_headers(user),
            json={"items": [{"menu_item_id": latte.id, "quantity": 1}]},
        )
        assert resp.status_code == 201


def test_PERMISSIONS_007_admin_cancels_employee_order(admin_employee, client):
    employee = admin_employee["employee"]
    admin = admin_employee["admin"]
    latte = admin_employee["latte"]
    order_resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": latte.id, "quantity": 1}]},
    )
    order_id = order_resp.get_json()["id"]
    cancel_resp = client.post(f"/api/orders/{order_id}/cancel", headers=api_headers(admin))
    assert cancel_resp.status_code == 200


def test_PERMISSIONS_008_employee_logged_out_payment(admin_employee, client):
    latte = admin_employee["latte"]
    employee = admin_employee["employee"]
    order_resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": latte.id, "quantity": 1}]},
    )
    order_id = order_resp.get_json()["id"]
    pay_resp = client.post(
        "/api/payments",
        headers=api_headers(employee),
        json={
            "order_id": order_id,
            "amount": "4.50",
            "method": PaymentMethod.CASH.value,
            "status": PaymentStatus.PAID.value,
        },
    )
    assert pay_resp.status_code == 201
    admin = admin_employee["admin"]
    pay_resp = client.post(
        "/api/payments",
        headers=api_headers(admin),
        json={
            "order_id": order_id,
            "amount": "4.50",
            "method": PaymentMethod.CARD.value,
            "status": PaymentStatus.PAID.value,
        },
    )
    assert pay_resp.status_code == 201


def test_PERMISSIONS_009_refunds_admin_only(admin_employee, client):
    admin = admin_employee["admin"]
    employee = admin_employee["employee"]
    latte = admin_employee["latte"]
    order_resp = client.post(
        "/api/orders",
        headers=api_headers(admin),
        json={"items": [{"menu_item_id": latte.id, "quantity": 1}]},
    )
    order_id = order_resp.get_json()["id"]
    pay_resp = client.post(
        "/api/payments",
        headers=api_headers(admin),
        json={
            "order_id": order_id,
            "amount": "4.50",
            "method": PaymentMethod.CASH.value,
            "status": PaymentStatus.PAID.value,
        },
    )
    payment_id = pay_resp.get_json()["id"]
    ref_resp = client.post(
        "/api/refunds",
        headers=api_headers(employee),
        json={"payment_id": payment_id, "amount": "1.00", "reason": "Nope"},
    )
    assert ref_resp.status_code == 403
    ref_resp = client.post(
        "/api/refunds",
        headers=api_headers(admin),
        json={"payment_id": payment_id, "amount": "1.00", "reason": "Approved"},
    )
    assert ref_resp.status_code == 201
