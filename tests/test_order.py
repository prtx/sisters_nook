from decimal import Decimal
from datetime import datetime

import pytest

from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.schema import Order, OrderItem, OrderStatus, User, UserRole
from sisters_nook.services import MenuService, OrderLineRequest, OrderService, UserService


@pytest.fixture(scope="function")
def session():
    reset_database()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def order_setup(session):
    admin = User(
        first_name="Admin",
        last_name="Order",
        email="admin@sisters.local",
        password_hash="hash",
        role=UserRole.ADMIN,
    )
    employee = User(
        first_name="Employee",
        last_name="Order",
        email="employee@sisters.local",
        password_hash="hash",
        role=UserRole.EMPLOYEE,
    )
    session.add_all([admin, employee])
    session.flush()
    menu_service = MenuService(session)
    order_service = OrderService(session)
    user_service = UserService(session)
    latte = menu_service.create_menu_item(admin, "Latte", Decimal("4.50"), "Milk and espresso", sort_order=1)
    mocha = menu_service.create_menu_item(admin, "Mocha", Decimal("5.00"), "Chocolate espresso", sort_order=2)
    return {
        "session": session,
        "menu_service": menu_service,
        "order_service": order_service,
        "user_service": user_service,
        "admin": admin,
        "employee": employee,
        "latte": latte,
        "mocha": mocha,
    }


def test_ORDER_001_admin_can_create_order(order_setup):
    order_service: OrderService = order_setup["order_service"]
    admin = order_setup["admin"]
    order = order_service.create_order(admin, [OrderLineRequest(order_setup["latte"].id, 1)])
    assert order is not None


def test_ORDER_001_employee_can_create_order(order_setup):
    order_service: OrderService = order_setup["order_service"]
    employee = order_setup["employee"]
    order = order_service.create_order(employee, [OrderLineRequest(order_setup["latte"].id, 1)])
    assert order is not None


def test_ORDER_002_order_contains_items(order_setup):
    order_service: OrderService = order_setup["order_service"]
    admin = order_setup["admin"]
    order = order_service.create_order(admin, [OrderLineRequest(order_setup["latte"].id, 2)])
    assert len(order.order_items) >= 1


def test_ORDER_003_order_item_references_menu_item(order_setup):
    order_service: OrderService = order_setup["order_service"]
    admin = order_setup["admin"]
    latte = order_setup["latte"]
    order = order_service.create_order(admin, [OrderLineRequest(latte.id, 1)])
    assert all(item.menu_item_id == latte.id for item in order.order_items)


def test_ORDER_004_and_ORDER_005_snapshots_store_name_and_price(order_setup):
    order_service: OrderService = order_setup["order_service"]
    admin = order_setup["admin"]
    latte = order_setup["latte"]
    order = order_service.create_order(admin, [OrderLineRequest(latte.id, 1)])
    item = order.order_items[0]
    assert item.item_name_snapshot == latte.name
    assert item.unit_price_snapshot == latte.current_price


def test_ORDER_006_quantity_and_line_total(order_setup):
    order_service: OrderService = order_setup["order_service"]
    admin = order_setup["admin"]
    latte = order_setup["latte"]
    order = order_service.create_order(admin, [OrderLineRequest(latte.id, 3)])
    item = order.order_items[0]
    assert item.quantity == 3
    assert item.line_total == latte.current_price * Decimal(3)


def test_ORDER_008_and_ORDER_009_subtotal_grand_total(order_setup):
    order_service: OrderService = order_setup["order_service"]
    admin = order_setup["admin"]
    latte = order_setup["latte"]
    order = order_service.create_order(
        admin,
        [OrderLineRequest(latte.id, 2)],
        tax_total=Decimal("0.50"),
        discount_total=Decimal("0.25"),
        tip_total=Decimal("1.00"),
    )
    subtotal = sum(item.line_total for item in order.order_items)
    assert order.subtotal == subtotal
    assert order.grand_total == subtotal + Decimal("0.50") + Decimal("1.00") - Decimal("0.25")


def test_ORDER_010_status_transitions(order_setup):
    order_service: OrderService = order_setup["order_service"]
    admin = order_setup["admin"]
    latte = order_setup["latte"]
    order = order_service.create_order(admin, [OrderLineRequest(latte.id, 1)])
    assert order.status == OrderStatus.OPEN
    order_service.cancel_order(admin, order.id)
    assert order.status == OrderStatus.CANCELLED


def test_ORDER_013_records_timestamps(order_setup):
    order_service: OrderService = order_setup["order_service"]
    admin = order_setup["admin"]
    latte = order_setup["latte"]
    order = order_service.create_order(admin, [OrderLineRequest(latte.id, 1)])
    assert order.created_at is not None
    assert order.created_at <= datetime.utcnow()


def test_ORDER_015_orders_not_deleted(order_setup):
    order_service: OrderService = order_setup["order_service"]
    admin = order_setup["admin"]
    latte = order_setup["latte"]
    order = order_service.create_order(admin, [OrderLineRequest(latte.id, 1)])
    assert order_setup["session"].query(Order).filter_by(id=order.id).one_or_none() is not None
