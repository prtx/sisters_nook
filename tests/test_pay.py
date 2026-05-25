from decimal import Decimal

import pytest

from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.schema import Order, OrderStatus, PaymentMethod, PaymentStatus, User, UserRole
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
def pay_setup(session):
    admin = User(
        first_name="Admin",
        last_name="Pay",
        email="admin@sisters.local",
        password_hash="hash",
        role=UserRole.ADMIN,
    )
    employee = User(
        first_name="Employee",
        last_name="Pay",
        email="employee@sisters.local",
        password_hash="hash",
        role=UserRole.EMPLOYEE,
    )
    session.add_all([admin, employee])
    session.flush()
    menu_service = MenuService(session)
    order_service = OrderService(session)
    payment_service = PaymentService(session)
    latte = menu_service.create_menu_item(admin, "Latte", Decimal("4.50"), "Milk", sort_order=1)
    order = order_service.create_order(admin, [OrderLineRequest(latte.id, 1)])
    return {
        "session": session,
        "menu_service": menu_service,
        "order_service": order_service,
        "payment_service": payment_service,
        "user_service": UserService(session),
        "admin": admin,
        "employee": employee,
        "order": order,
    }


def test_PAY_001_admin_logs_payment(pay_setup):
    payment_service = pay_setup["payment_service"]
    admin = pay_setup["admin"]
    order = pay_setup["order"]
    payment = payment_service.log_payment(admin, order.id, order.grand_total, PaymentMethod.CASH)
    assert payment.logged_by_user_id == admin.id


def test_PAY_001_employee_logs_payment(pay_setup):
    payment_service = pay_setup["payment_service"]
    employee = pay_setup["employee"]
    order = pay_setup["order"]
    payment = payment_service.log_payment(employee, order.id, order.grand_total, PaymentMethod.CARD)
    assert payment.logged_by_user_id == employee.id


def test_PAY_002_payment_belongs_to_order(pay_setup):
    payment_service = pay_setup["payment_service"]
    admin = pay_setup["admin"]
    order = pay_setup["order"]
    payment = payment_service.log_payment(admin, order.id, order.grand_total, PaymentMethod.ONLINE)
    assert payment.order_id == order.id


def test_PAY_003_and_PAY_004_amount_and_method_stored(pay_setup):
    payment_service = pay_setup["payment_service"]
    admin = pay_setup["admin"]
    order = pay_setup["order"]
    payment = payment_service.log_payment(admin, order.id, Decimal("2.50"), PaymentMethod.OTHER, status=PaymentStatus.PAID)
    assert payment.amount == Decimal("2.50")
    assert payment.payment_method == PaymentMethod.OTHER


def test_PAY_006_user_stored_and_status_recorded(pay_setup):
    payment_service = pay_setup["payment_service"]
    admin = pay_setup["admin"]
    order = pay_setup["order"]
    payment = payment_service.log_payment(admin, order.id, order.grand_total, PaymentMethod.CARD, status=PaymentStatus.PENDING)
    assert payment.logged_by_user_id == admin.id
    assert payment.status == PaymentStatus.PENDING


def test_PAY_009_payment_timestamp(pay_setup):
    payment_service = pay_setup["payment_service"]
    admin = pay_setup["admin"]
    order = pay_setup["order"]
    payment = payment_service.log_payment(admin, order.id, order.grand_total, PaymentMethod.CASH, status=PaymentStatus.PAID)
    assert payment.paid_at is not None


def test_PAY_011_order_marked_paid(pay_setup):
    payment_service = pay_setup["payment_service"]
    admin = pay_setup["admin"]
    order = pay_setup["order"]
    payment_service.log_payment(admin, order.id, order.grand_total, PaymentMethod.CASH, status=PaymentStatus.PAID)
    assert order.status == OrderStatus.PAID


def test_PAY_012_prevent_overpayment(pay_setup):
    payment_service = pay_setup["payment_service"]
    admin = pay_setup["admin"]
    order = pay_setup["order"]
    with pytest.raises(ValueError):
        payment_service.log_payment(admin, order.id, order.grand_total + Decimal("1.00"), PaymentMethod.CASH)
