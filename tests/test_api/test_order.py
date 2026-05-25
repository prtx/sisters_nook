from decimal import Decimal

from sisters_nook.schema import MenuItem, Order, OrderStatus
from tests.test_api.conftest import api_headers


def test_ORDER_001_employee_can_create_and_list(admin_employee, client):
    employee = admin_employee["employee"]
    latte = admin_employee["latte"]
    resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": latte.id, "quantity": 2}]},
    )
    assert resp.status_code == 201
    order_id = resp.get_json()["id"]

    list_resp = client.get("/api/orders", headers=api_headers(employee))
    assert list_resp.status_code == 200
    orders = list_resp.get_json()
    assert any(order["id"] == order_id for order in orders)
    assert any(order["total"] == str(Decimal("9.00")) for order in orders)


def test_ORDER_002_admin_can_cancel(admin_employee, client):
    employee = admin_employee["employee"]
    admin = admin_employee["admin"]
    latte = admin_employee["latte"]
    create_resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": latte.id, "quantity": 1}]},
    )
    order_id = create_resp.get_json()["id"]

    cancel_resp = client.post(f"/api/orders/{order_id}/cancel", headers=api_headers(admin))
    assert cancel_resp.status_code == 200

    session = admin_employee["session"]
    session.expire_all()
    order = session.get(Order, order_id)
    assert order.status == OrderStatus.CANCELLED


def test_ORDER_003_employee_cannot_cancel(admin_employee, client):
    employee = admin_employee["employee"]
    latte = admin_employee["latte"]
    create_resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": latte.id, "quantity": 1}]},
    )
    order_id = create_resp.get_json()["id"]

    cancel_resp = client.post(f"/api/orders/{order_id}/cancel", headers=api_headers(employee))
    assert cancel_resp.status_code == 403


def test_ORDER_008_subtotal_and_totals_stored(admin_employee, client):
    employee = admin_employee["employee"]
    latte = admin_employee["latte"]
    session = admin_employee["session"]
    resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": latte.id, "quantity": 2}]},
    )
    order_id = resp.get_json()["id"]
    session.expire_all()
    order = session.get(Order, order_id)
    subtotal = sum(item.line_total for item in order.order_items)
    assert order.subtotal == subtotal
    assert order.grand_total == subtotal


def test_ORDER_013_snapshots_capture_menu_data(admin_employee, client):
    employee = admin_employee["employee"]
    latte = admin_employee["latte"]
    session = admin_employee["session"]
    resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": latte.id, "quantity": 1}]},
    )
    order_id = resp.get_json()["id"]
    session.expire_all()
    item = session.get(Order, order_id).order_items[0]
    assert item.item_name_snapshot == latte.name
    assert item.unit_price_snapshot == latte.current_price


def test_ORDER_015_order_timestamp_and_persistence(admin_employee, client):
    employee = admin_employee["employee"]
    session = admin_employee["session"]
    latte = admin_employee["latte"]
    resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": latte.id, "quantity": 1}]},
    )
    order_id = resp.get_json()["id"]
    session.expire_all()
    order = session.get(Order, order_id)
    assert order.created_at is not None
    assert session.query(Order).filter_by(id=order_id).one_or_none() is not None


def test_ORDER_naive_invalid_quantity_rejected(admin_employee, client):
    employee = admin_employee["employee"]
    latte = admin_employee["latte"]
    resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": latte.id, "quantity": 0}]},
    )
    assert resp.status_code == 400


def test_ORDER_inactive_items_rejected(admin_employee, client):
    employee = admin_employee["employee"]
    session = admin_employee["session"]
    latte = session.get(MenuItem, admin_employee["latte"].id)
    latte.is_active = False
    session.add(latte)
    session.commit()
    resp = client.post(
        "/api/orders",
        headers=api_headers(employee),
        json={"items": [{"menu_item_id": latte.id, "quantity": 1}]},
    )
    assert resp.status_code == 400
