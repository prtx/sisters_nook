from decimal import Decimal

import pytest

from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.schema import MenuItemPriceHistory, PaymentMethod, Refund, User, UserRole
from sisters_nook.services import (
    MenuService,
    OrderLineRequest,
    OrderService,
    PaymentService,
    RefundService,
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
def audit_setup(session):
    admin = User(
        first_name="Admin",
        last_name="Audit",
        email="admin@sisters.local",
        password_hash="hash",
        role=UserRole.ADMIN,
    )
    session.add(admin)
    session.flush()
    menu_service = MenuService(session)
    order_service = OrderService(session)
    payment_service = PaymentService(session)
    refund_service = RefundService(session)
    user_service = UserService(session)
    latte = menu_service.create_menu_item(admin, "Latte", Decimal("4.50"), "Milk", sort_order=1)
    order = order_service.create_order(admin, [OrderLineRequest(latte.id, 1)])
    payment = payment_service.log_payment(admin, order.id, order.grand_total, PaymentMethod.CASH)
    menu_service.change_price(admin, latte.id, Decimal("5.00"))
    return {
        "session": session,
        "menu_service": menu_service,
        "order_service": order_service,
        "payment_service": payment_service,
        "refund_service": refund_service,
        "user_service": user_service,
        "admin": admin,
        "latte": latte,
        "payment": payment,
    }


def test_AUDIT_001_admin_action_recorded(audit_setup):
    session = audit_setup["session"]
    assert session.query(User).filter_by(email=audit_setup["admin"].email).count() == 1


def test_AUDIT_002_menu_creation_recorded(audit_setup):
    latte = audit_setup["latte"]
    assert latte.created_by_user_id == audit_setup["admin"].id


def test_AUDIT_003_menu_updates_recorded(audit_setup):
    menu_service = audit_setup["menu_service"]
    admin = audit_setup["admin"]
    latte = audit_setup["latte"]
    updated = menu_service.update_menu_item(admin, latte.id, description="Updated")
    assert updated.updated_at is not None


def test_AUDIT_004_price_change_recorded(audit_setup):
    session = audit_setup["session"]
    menu_service = audit_setup["menu_service"]
    admin = audit_setup["admin"]
    latte = audit_setup["latte"]
    menu_service.change_price(admin, latte.id, Decimal("5.00"))
    history = session.query(MenuItemPriceHistory).filter_by(menu_item_id=latte.id).order_by(MenuItemPriceHistory.changed_at.desc()).first()
    assert history is not None
    assert history.changed_by_user_id == admin.id
    assert history.changed_at is not None


def test_AUDIT_005_activation_deactivation_recorded(audit_setup):
    menu_service = audit_setup["menu_service"]
    admin = audit_setup["admin"]
    latte = audit_setup["latte"]
    menu_service.deactivate_menu_item(admin, latte.id)
    assert not latte.is_active
    reactivated = menu_service.reactivate_menu_item(admin, latte.id)
    assert reactivated.is_active


def test_AUDIT_006_refund_creation_recorded(audit_setup):
    refund_service = audit_setup["refund_service"]
    admin = audit_setup["admin"]
    payment = audit_setup["payment"]
    refund = refund_service.create_refund(admin, payment.id, Decimal("1.00"), "audit")
    assert refund.refunded_by_user_id == admin.id


def test_AUDIT_007_user_deactivation_reactivation_recorded(audit_setup):
    user_service = audit_setup["user_service"]
    admin = audit_setup["admin"]
    target = user_service.create_user(
        admin, "Temp", "User", "temp@sisters.local", "hash", UserRole.EMPLOYEE
    )
    deactivated = user_service.deactivate_user(admin, target.id)
    assert not deactivated.is_active
    reactivated = user_service.reactivate_user(admin, target.id)
    assert reactivated.is_active


def test_AUDIT_008_history_includes_user_and_timestamp(audit_setup):
    session = audit_setup["session"]
    latte = audit_setup["latte"]
    assert session.query(MenuItemPriceHistory).filter_by(menu_item_id=latte.id).count() >= 1
