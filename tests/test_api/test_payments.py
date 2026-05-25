from decimal import Decimal

from sisters_nook.schema import Order, OrderStatus, PaymentStatus
from tests.test_api.conftest import api_headers


def test_PAYMENTS_log_and_refund(admin_employee, client):
    admin = admin_employee["admin"]
    employee = admin_employee["employee"]
    latte = admin_employee["latte"]
    order_resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": latte.id, "quantity": 1}]},
    )
    order_id = order_resp.get_json()["id"]

    pay_resp = client.post(
        "/api/payments",
        headers=api_headers(employee),
        json={"order_id": order_id, "amount": "4.50", "method": "cash", "status": PaymentStatus.PAID.value},
    )
    assert pay_resp.status_code == 201

    session = admin_employee["session"]
    session.expire_all()
    order = session.get(Order, order_id)
    assert order.status == OrderStatus.PAID

    payment_id = pay_resp.get_json()["id"]
    refund_resp = client.post(
        "/api/refunds",
        headers=api_headers(admin),
        json={"payment_id": payment_id, "amount": "1.00", "reason": "Test refund"},
    )
    assert refund_resp.status_code == 201

    session.expire_all()
    order = session.get(Order, order_id)
    assert order.status == OrderStatus.REFUNDED
