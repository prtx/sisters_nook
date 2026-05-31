from decimal import Decimal

import pytest

from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.schema import PaymentMethod, User, UserRole
from sisters_nook.services import MenuService, OrderLineRequest, OrderService, PaymentService, RefundService, UserService


@pytest.fixture(scope="function")
def session():
    reset_database()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def perms_setup(session):
    admin = User(
        first_name="Admin",
        last_name="Perm",
        email="admin@sisters.local",
        password_hash="hash",
        role=UserRole.ADMIN,
    )
    employee = User(
        first_name="Employee",
        last_name="Perm",
        email="employee@sisters.local",
        password_hash="hash",
        role=UserRole.EMPLOYEE,
    )
    session.add_all([admin, employee])
    session.flush()
    menu_service = MenuService(session)
    order_service = OrderService(session)
    payment_service = PaymentService(session)
    refund_service = RefundService(session)
    user_service = UserService(session)
    latte = menu_service.create_menu_item(admin, "Latte", Decimal("4.50"), "Milk", sort_order=1)
    return {
        "session": session,
        "menu_service": menu_service,
        "order_service": order_service,
        "payment_service": payment_service,
        "refund_service": refund_service,
        "user_service": user_service,
        "admin": admin,
        "employee": employee,
        "latte": latte,
    }


def test_permissions_user_management_admin_only(perms_setup):
    user_service: UserService = perms_setup["user_service"]
    admin = perms_setup["admin"]
    employee = perms_setup["employee"]
    user_service.create_user(admin, "Test", "User", "test-manage@sisters.local", "hash", UserRole.EMPLOYEE)
    with pytest.raises(PermissionError):
        user_service.create_user(employee, "Bad", "Actor", "bad@sisters.local", "hash", UserRole.EMPLOYEE)


def test_permissions_menu_create_admin_only(perms_setup):
    menu_service = perms_setup["menu_service"]
    admin = perms_setup["admin"]
    employee = perms_setup["employee"]
    menu_service.create_menu_item(admin, "Admin Only", Decimal("3.00"), "Test", sort_order=2)
    with pytest.raises(PermissionError):
        menu_service.create_menu_item(employee, "Employee Item", Decimal("3.00"), "Test", sort_order=3)


def test_permissions_menu_view_active_both(perms_setup):
    menu_service = perms_setup["menu_service"]
    active = menu_service.list_active()
    assert active


def test_permissions_menu_view_inactive_admin_only(perms_setup):
    menu_service = perms_setup["menu_service"]
    menu_service.deactivate_menu_item(perms_setup["admin"], perms_setup["latte"].id)
    inactive = menu_service.list_all()
    assert any(not item.is_active for item in inactive)


def test_permissions_order_creation_both(perms_setup):
    order_service = perms_setup["order_service"]
    assert order_service.create_order(perms_setup["admin"], [OrderLineRequest(perms_setup["latte"].id, 1)])
    assert order_service.create_order(perms_setup["employee"], [OrderLineRequest(perms_setup["latte"].id, 1)])


def test_permissions_order_cancellation_admin_optional(perms_setup):
    order = perms_setup["order_service"].create_order(perms_setup["admin"], [OrderLineRequest(perms_setup["latte"].id, 1)])
    perms_setup["order_service"].cancel_order(perms_setup["admin"], order.id)
    with pytest.raises(PermissionError):
        perms_setup["order_service"].cancel_order(perms_setup["employee"], order.id)


def test_permissions_payments_both(perms_setup):
    payment_service = perms_setup["payment_service"]
    order = perms_setup["order_service"].create_order(perms_setup["admin"], [OrderLineRequest(perms_setup["latte"].id, 1)])
    payment_service.log_payment(perms_setup["admin"], order.id, order.grand_total, PaymentMethod.CASH)
    payment_service.log_payment(perms_setup["employee"], order.id, order.grand_total, PaymentMethod.CARD)


def test_permissions_refunds_allowed(perms_setup):
    refund_service = perms_setup["refund_service"]
    payment_service = perms_setup["payment_service"]
    order = perms_setup["order_service"].create_order(perms_setup["admin"], [OrderLineRequest(perms_setup["latte"].id, 1)])
    payment = payment_service.log_payment(perms_setup["admin"], order.id, order.grand_total, PaymentMethod.CASH)
    refund_service.create_refund(perms_setup["admin"], payment.id, Decimal("1.00"), "Need")
    refund = refund_service.create_refund(perms_setup["employee"], payment.id, Decimal("0.50"), "Employee handled")
    assert refund.refunded_by_user_id == perms_setup["employee"].id
