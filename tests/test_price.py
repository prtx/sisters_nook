from decimal import Decimal

import pytest

from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.schema import MenuItemPriceHistory, Order, OrderItem, User, UserRole
from sisters_nook.services import MenuService, OrderLineRequest, OrderService, PaymentService, UserService


@pytest.fixture(scope="function")
def session():
    reset_database()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def price_setup(session):
    admin = User(
        first_name="Admin",
        last_name="Price",
        email="admin@sisters.local",
        password_hash="hash",
        role=UserRole.ADMIN,
    )
    employee = User(
        first_name="Employee",
        last_name="Price",
        email="employee@sisters.local",
        password_hash="hash",
        role=UserRole.EMPLOYEE,
    )
    session.add_all([admin, employee])
    session.flush()
    menu_service = MenuService(session)
    order_service = OrderService(session)
    payment_service = PaymentService(session)
    latte = menu_service.create_menu_item(admin, "Latte", Decimal("4.50"), "Milk espresso", sort_order=1)
    mocha = menu_service.create_menu_item(admin, "Mocha", Decimal("5.00"), "Chocolate espresso", sort_order=2)
    return {
        "session": session,
        "menu_service": menu_service,
        "order_service": order_service,
        "payment_service": payment_service,
        "admin": admin,
        "employee": employee,
        "latte": latte,
        "mocha": mocha,
    }


def test_PRICE_001_price_present_in_menu(price_setup):
    items = price_setup["menu_service"].list_all()
    assert all(item.current_price is not None for item in items)


def test_PRICE_002_only_admin_changes_price(price_setup):
    menu_service = price_setup["menu_service"]
    employee = price_setup["employee"]
    with pytest.raises(PermissionError):
        menu_service.change_price(employee, price_setup["latte"].id, Decimal("4.75"))


def test_PRICE_003_price_history_created(price_setup):
    menu_service = price_setup["menu_service"]
    session = price_setup["session"]
    admin = price_setup["admin"]
    latte = price_setup["latte"]
    menu_service.change_price(admin, latte.id, Decimal("4.75"))
    history = session.query(MenuItemPriceHistory).filter_by(menu_item_id=latte.id).all()
    assert len(history) == 1


def test_PRICE_004_price_history_fields(price_setup):
    menu_service = price_setup["menu_service"]
    session = price_setup["session"]
    admin = price_setup["admin"]
    latte = price_setup["latte"]
    menu_service.change_price(admin, latte.id, Decimal("4.75"))
    record = session.query(MenuItemPriceHistory).filter_by(menu_item_id=latte.id).one()
    assert record.old_price == Decimal("4.50")
    assert record.new_price == Decimal("4.75")
    assert record.changed_by_user_id == admin.id
    assert record.changed_at is not None


def test_PRICE_005_orders_use_current_price(price_setup):
    order_service = price_setup["order_service"]
    admin = price_setup["admin"]
    latte = price_setup["latte"]
    order = order_service.create_order(admin, [OrderLineRequest(menu_item_id=latte.id, quantity=1)])
    assert order.grand_total == Decimal("4.50")


def test_PRICE_006_old_orders_keep_old_price(price_setup):
    session = price_setup["session"]
    order_service = price_setup["order_service"]
    menu_service = price_setup["menu_service"]
    admin = price_setup["admin"]
    latte = price_setup["latte"]
    old_order = order_service.create_order(admin, [OrderLineRequest(menu_item_id=latte.id, quantity=1)])
    menu_service.change_price(admin, latte.id, Decimal("5.00"))
    items = session.query(OrderItem).filter_by(order_id=old_order.id).all()
    assert items[0].unit_price_snapshot == Decimal("4.50")


def test_PRICE_007_negative_price_rejected(price_setup):
    with pytest.raises(ValueError):
        price_setup["menu_service"].create_menu_item(
            price_setup["admin"], "Bad", Decimal("-1.00"), "Negative", sort_order=3
        )


def test_PRICE_008_two_decimal_places(price_setup):
    menu_service = price_setup["menu_service"]
    admin = price_setup["admin"]
    item = menu_service.create_menu_item(admin, "Rounded", Decimal("3.141"), "Test", sort_order=3)
    assert item.current_price == Decimal("3.14")
