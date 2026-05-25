from decimal import Decimal
from typing import cast

from sisters_nook.schema import MenuItem, MenuItemPriceHistory
from tests.test_api.conftest import admin_employee, api_headers


def test_MENU_001_list_returns_seeded_item(admin_employee, client):
    admin = admin_employee["admin"]
    session = admin_employee["session"]
    resp = client.get("/api/menu", headers=api_headers(admin))
    assert resp.status_code == 200
    assert any(item["id"] == admin_employee["latte"].id for item in resp.get_json())

    session.expire_all()
    stored_item = session.get(MenuItem, admin_employee["latte"].id)
    assert stored_item is not None


def test_MENU_002_multiple_items_visible(admin_employee, client):
    admin = admin_employee["admin"]
    resp = client.get("/api/menu", headers=api_headers(admin))
    assert len(resp.get_json()) >= 1


def test_MENU_003_admin_can_create_and_update_and_history(admin_employee, client):
    admin = admin_employee["admin"]
    session = admin_employee["session"]
    create_resp = client.post(
        "/api/menu",
        headers=api_headers(admin),
        json={"name": "Mocha", "price": "5.00", "description": "Chocolate", "sort_order": 2},
    )
    assert create_resp.status_code == 201
    menu_id = create_resp.get_json()["id"]

    update_resp = client.put(
        f"/api/menu/{menu_id}",
        headers=api_headers(admin),
        json={"price": "5.25"},
    )
    assert update_resp.status_code == 200

    session.expire_all()
    history = (
        session.query(MenuItemPriceHistory)
        .filter_by(menu_item_id=menu_id)
        .order_by(MenuItemPriceHistory.changed_at.desc())
        .all()
    )
    assert len(history) == 1
    assert history[0].new_price == Decimal("5.25")


def test_MENU_004_admin_can_update_name(admin_employee, client):
    admin = admin_employee["admin"]
    session = admin_employee["session"]
    item_id = admin_employee["latte"].id
    resp = client.put(
        f"/api/menu/{item_id}",
        headers=api_headers(admin),
        json={"name": "Latte Latte"},
    )
    assert resp.status_code == 200
    session.expire_all()
    assert session.get(MenuItem, item_id).name == "Latte Latte"


def test_MENU_005_admin_can_update_description(admin_employee, client):
    admin = admin_employee["admin"]
    session = admin_employee["session"]
    item_id = admin_employee["latte"].id
    resp = client.put(
        f"/api/menu/{item_id}",
        headers=api_headers(admin),
        json={"description": "New desc"},
    )
    assert resp.status_code == 200
    session.expire_all()
    assert session.get(MenuItem, item_id).description == "New desc"


def test_MENU_009_admin_can_change_sort_order(admin_employee, client):
    admin = admin_employee["admin"]
    session = admin_employee["session"]
    item_id = admin_employee["latte"].id
    resp = client.put(
        f"/api/menu/{item_id}",
        headers=api_headers(admin),
        json={"sort_order": 5},
    )
    assert resp.status_code == 200
    session.expire_all()
    assert session.get(MenuItem, item_id).sort_order == 5


def test_MENU_008_price_rounding_and_soft_delete(admin_employee, client):
    admin = admin_employee["admin"]
    session = admin_employee["session"]
    resp = client.post(
        "/api/menu",
        headers=api_headers(admin),
        json={"name": "Rounded", "price": "3.141", "description": "Precision", "sort_order": 4},
    )
    menu_id = resp.get_json()["id"]
    assert resp.status_code == 201

    session.expire_all()
    rounded_item = cast(MenuItem, session.get(MenuItem, menu_id))
    assert rounded_item.current_price == Decimal("3.14")

    delete_resp = client.delete(f"/api/menu/{admin_employee['latte'].id}", headers=api_headers(admin))
    assert delete_resp.status_code == 200
    list_resp = client.get("/api/menu", headers=api_headers(admin))
    assert any(item["id"] == admin_employee["latte"].id and not item["active"] for item in list_resp.get_json())


def test_MENU_011_employee_cannot_modify(admin_employee, client):
    employee = admin_employee["employee"]
    resp = client.post(
        "/api/menu",
        headers=api_headers(employee),
        json={"name": "Flat White", "price": "3.75", "description": "Milk"},
    )
    assert resp.status_code == 403

    latte = admin_employee["latte"]
    update_resp = client.put(
        f"/api/menu/{latte.id}",
        headers=api_headers(employee),
        json={"name": "Tampered Latte"},
    )
    assert update_resp.status_code == 403
