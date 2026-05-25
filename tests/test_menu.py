from decimal import Decimal

import pytest

from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.schema import MenuItem, User, UserRole
from sisters_nook.services import (
    MenuService,
    OrderLineRequest,
    OrderService,
    PaymentMethod,
    PaymentService,
    UserService,
)


@pytest.fixture(scope="function")
def session():
    reset_database()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def menu_setup(session):
    admin = User(
        first_name="Admin",
        last_name="Menu",
        email="admin@sisters.local",
        password_hash="hash",
        role=UserRole.ADMIN,
    )
    employee = User(
        first_name="Employee",
        last_name="Menu",
        email="employee@sisters.local",
        password_hash="hash",
        role=UserRole.EMPLOYEE,
    )
    session.add_all([admin, employee])
    session.flush()
    menu_service = MenuService(session)
    latte = menu_service.create_menu_item(admin, "Latte", Decimal("4.50"), "Milk and espresso", sort_order=1)
    mocha = menu_service.create_menu_item(admin, "Mocha", Decimal("5.00"), "Chocolate espresso", sort_order=2)
    croissant = menu_service.create_menu_item(admin, "Croissant", Decimal("3.25"), "Flaky butter", sort_order=3)
    order_service = OrderService(session)
    payment_service = PaymentService(session)
    user_service = UserService(session)
    yield {
        "session": session,
        "menu_service": menu_service,
        "order_service": order_service,
        "payment_service": payment_service,
        "user_service": user_service,
        "admin": admin,
        "employee": employee,
        "items": [latte, mocha, croissant],
    }


def test_MENU_001_single_menu_model(menu_setup):
    menu_service = menu_setup["menu_service"]
    all_items = menu_service.list_all()
    assert len(all_items) == len(menu_setup["items"])
    assert all(isinstance(item, MenuItem) for item in all_items)


def test_MENU_002_menu_contains_multiple_items(menu_setup):
    items = menu_setup["items"]
    assert len(items) >= 2


def test_MENU_003_admin_can_create_menu_item(menu_setup):
    menu_service = menu_setup["menu_service"]
    admin = menu_setup["admin"]
    item = menu_service.create_menu_item(admin, "Espresso", Decimal("2.50"), "Shot", sort_order=4)
    assert item.name == "Espresso"


def test_MENU_004_admin_can_update_name(menu_setup):
    menu_service = menu_setup["menu_service"]
    admin = menu_setup["admin"]
    latte = menu_setup["items"][0]
    updated = menu_service.update_menu_item(admin, latte.id, name="Latte Deluxe")
    assert updated.name == "Latte Deluxe"


def test_MENU_005_admin_can_update_description(menu_setup):
    menu_service = menu_setup["menu_service"]
    admin = menu_setup["admin"]
    latte = menu_setup["items"][0]
    updated = menu_service.update_menu_item(admin, latte.id, description="Updated description")
    assert updated.description == "Updated description"


def test_MENU_006_admin_can_change_price(menu_setup):
    menu_service = menu_setup["menu_service"]
    admin = menu_setup["admin"]
    latte = menu_setup["items"][0]
    updated = menu_service.change_price(admin, latte.id, Decimal("4.75"))
    assert updated.current_price == Decimal("4.75")


def test_MENU_007_admin_can_deactivate_menu_item(menu_setup):
    menu_service = menu_setup["menu_service"]
    admin = menu_setup["admin"]
    item = menu_setup["items"][1]
    disabled = menu_service.deactivate_menu_item(admin, item.id)
    assert not disabled.is_active


def test_MENU_008_admin_can_reactivate_menu_item(menu_setup):
    menu_service = menu_setup["menu_service"]
    admin = menu_setup["admin"]
    item = menu_setup["items"][1]
    menu_service.deactivate_menu_item(admin, item.id)
    reenabled = menu_service.reactivate_menu_item(admin, item.id)
    assert reenabled.is_active


def test_MENU_009_admin_can_change_display_order(menu_setup):
    menu_service = menu_setup["menu_service"]
    admin = menu_setup["admin"]
    item = menu_setup["items"][2]
    updated = menu_service.update_menu_item(admin, item.id, sort_order=1)
    assert updated.sort_order == 1


def test_MENU_010_employee_can_view_active_items(menu_setup):
    menu_service = menu_setup["menu_service"]
    employees_view = menu_service.list_active()
    assert all(item.is_active for item in employees_view)


def test_MENU_011_employee_cannot_create_items(menu_setup):
    menu_service = menu_setup["menu_service"]
    employee = menu_setup["employee"]
    with pytest.raises(PermissionError):
        menu_service.create_menu_item(employee, "Flat White", Decimal("3.75"), "Milk")


def test_MENU_012_employee_cannot_update_item_details(menu_setup):
    menu_service = menu_setup["menu_service"]
    employee = menu_setup["employee"]
    item = menu_setup["items"][0]
    with pytest.raises(PermissionError):
        menu_service.update_menu_item(employee, item.id, name="Tamper")


def test_MENU_013_employee_cannot_change_price(menu_setup):
    menu_service = menu_setup["menu_service"]
    employee = menu_setup["employee"]
    item = menu_setup["items"][0]
    with pytest.raises(PermissionError):
        menu_service.change_price(employee, item.id, Decimal("5.00"))


def test_MENU_014_employee_cannot_deactivate_reactivate(menu_setup):
    menu_service = menu_setup["menu_service"]
    employee = menu_setup["employee"]
    item = menu_setup["items"][0]
    with pytest.raises(PermissionError):
        menu_service.deactivate_menu_item(employee, item.id)
    with pytest.raises(PermissionError):
        menu_service.reactivate_menu_item(employee, item.id)


def test_MENU_015_inactive_items_not_deleted(menu_setup):
    menu_service = menu_setup["menu_service"]
    admin = menu_setup["admin"]
    item = menu_setup["items"][0]
    menu_service.deactivate_menu_item(admin, item.id)
    all_items = menu_service.list_all()
    assert any(db_item.id == item.id for db_item in all_items)


def test_MENU_016_inactive_items_not_selectable(menu_setup):
    order_service = menu_setup["order_service"]
    user_service = menu_setup["user_service"]
    payment_service = menu_setup["payment_service"]
    menu_service = menu_setup["menu_service"]
    admin = menu_setup["admin"]
    employee = menu_setup["employee"]
    latte = menu_setup["items"][0]
    menu_service.deactivate_menu_item(admin, latte.id)
    with pytest.raises(ValueError):
        order = order_service.create_order(employee, [OrderLineRequest(menu_item_id=latte.id, quantity=1)])


def test_MENU_017_inactive_items_still_visible_in_history(menu_setup):
    menu_service = menu_setup["menu_service"]
    admin = menu_setup["admin"]
    item = menu_setup["items"][0]
    menu_service.deactivate_menu_item(admin, item.id)
    all_items = menu_service.list_all()
    assert any(db_item.id == item.id and not db_item.is_active for db_item in all_items)
