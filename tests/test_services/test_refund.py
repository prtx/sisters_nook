from decimal import Decimal

import pytest

from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.schema import PaymentMethod, Refund, User, UserRole
from sisters_nook.services import MenuService, OrderLineRequest, OrderService, PaymentService, RefundService


@pytest.fixture(scope="function")
def session():
    reset_database()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def refund_setup(session):
    admin = User(
        first_name="Admin",
        last_name="Refund",
        email="admin@sisters.local",
        password_hash="hash",
        role=UserRole.ADMIN,
    )
    employee = User(
        first_name="Employee",
        last_name="Refund",
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
    latte = menu_service.create_menu_item(admin, "Latte", Decimal("4.50"), "Milk", sort_order=1)
    order = order_service.create_order(admin, [OrderLineRequest(latte.id, 1)])
    payment = payment_service.log_payment(admin, order.id, order.grand_total, PaymentMethod.CASH)
    return {
        "session": session,
        "menu_service": menu_service,
        "order": order,
        "payment": payment,
        "payment_service": payment_service,
        "refund_service": refund_service,
        "admin": admin,
        "employee": employee,
    }


def test_REFUND_001_admin_can_create_refund(refund_setup):
    refund_service = refund_setup["refund_service"]
    admin = refund_setup["admin"]
    payment = refund_setup["payment"]
    refund = refund_service.create_refund(admin, payment.id, Decimal("1.00"), "Reason")
    assert refund.payment_id == payment.id


def test_REFUND_002_employee_cannot_create_refund(refund_setup):
    refund_service = refund_setup["refund_service"]
    employee = refund_setup["employee"]
    payment = refund_setup["payment"]
    with pytest.raises(PermissionError):
        refund_service.create_refund(employee, payment.id, Decimal("1.00"), "Reason")


def test_REFUND_003_refund_belongs_to_payment(refund_setup):
    refund_service = refund_setup["refund_service"]
    admin = refund_setup["admin"]
    payment = refund_setup["payment"]
    refund = refund_service.create_refund(admin, payment.id, Decimal("1.00"), "Reason")
    session = refund_setup["session"]
    assert session.query(Refund).filter_by(id=refund.id).one_or_none() is not None


def test_REFUND_004_and_REFUND_005_store_amount_reason(refund_setup):
    refund_service = refund_setup["refund_service"]
    admin = refund_setup["admin"]
    payment = refund_setup["payment"]
    refund = refund_service.create_refund(admin, payment.id, Decimal("1.00"), "Reason")
    assert refund.amount == Decimal("1.00")
    assert refund.reason == "Reason"


def test_REFUND_006_and_REFUND_007_store_admin_and_timestamp(refund_setup):
    refund_service = refund_setup["refund_service"]
    admin = refund_setup["admin"]
    payment = refund_setup["payment"]
    refund = refund_service.create_refund(admin, payment.id, Decimal("1.00"), "Reason")
    assert refund.refunded_by_user_id == admin.id
    assert refund.created_at is not None


def test_REFUND_008_refunds_not_deleted(refund_setup):
    refund_service = refund_setup["refund_service"]
    admin = refund_setup["admin"]
    payment = refund_setup["payment"]
    refund = refund_service.create_refund(admin, payment.id, Decimal("1.00"), "Reason")
    assert refund_setup["session"].query(Refund).filter_by(id=refund.id).count() == 1
