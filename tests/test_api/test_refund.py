from decimal import Decimal

from sisters_nook.schema import Order, OrderStatus, PaymentMethod, PaymentStatus
from tests.test_api.conftest import admin_employee, api_headers


def test_REFUND_001_employee_can_create_refund(admin_employee, client):
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
    resp = client.post(
        "/api/refunds",
        headers=api_headers(employee),
        json={"payment_id": payment_id, "amount": "1.00", "reason": "Need"},
    )
    assert resp.status_code == 201


def test_REFUND_002_admin_updates_order(admin_employee, client):
    admin = admin_employee["admin"]
    employee = admin_employee["employee"]
    latte = admin_employee["latte"]
    session = admin_employee["session"]
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
    payment_id = pay_resp.get_json()["id"]
    ref_resp = client.post(
        "/api/refunds",
        headers=api_headers(admin),
        json={"payment_id": payment_id, "amount": "1.00", "reason": "Refund"},
    )
    assert ref_resp.status_code == 201
    session.expire_all()
    order = session.get(Order, order_id)
    assert order.status == OrderStatus.REFUNDED
