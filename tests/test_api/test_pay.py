from decimal import Decimal

from sisters_nook.schema import Order, OrderStatus, PaymentMethod, PaymentStatus
from tests.test_api.conftest import admin_employee, api_headers


def test_PAY_001_order_required(client, admin_employee):
    employee = admin_employee["employee"]
    resp = client.post(
        "/api/payments",
        headers=api_headers(employee),
        json={"order_id": "missing", "amount": "1.00", "method": PaymentMethod.CASH.value},
    )
    assert resp.status_code == 400


def test_PAY_002_overpayment_rejected(admin_employee, client):
    employee = admin_employee["employee"]
    latte = admin_employee["latte"]
    order_resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": latte.id, "quantity": 1}]},
    )
    order_id = order_resp.get_json()["id"]
    resp = client.post(
        "/api/payments",
        headers=api_headers(employee),
        json={
            "order_id": order_id,
            "amount": "10.00",
            "method": PaymentMethod.CASH.value,
        },
    )
    assert resp.status_code == 400


def test_PAY_003_payment_marks_order_paid(admin_employee, client):
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
    assert pay_resp.status_code == 201
    session.expire_all()
    order = session.get(Order, order_id)
    assert order.status == OrderStatus.PAID
