import pytest

from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.schema import User, UserRole
from sisters_nook.services import AuditService, OrderLineRequest, OrderService, UserService
from sisters_nook.web import queries


@pytest.fixture(scope="function")
def admin_delete_setup():
    reset_database()
    session = SessionLocal()
    admin = User(
        first_name="Admin",
        last_name="Delete",
        email="admin@sisters.local",
        password_hash="hash",
        role=UserRole.ADMIN,
    )
    employee = User(
        first_name="Employee",
        last_name="Delete",
        email="employee@sisters.local",
        password_hash="hash",
        role=UserRole.EMPLOYEE,
    )
    session.add_all([admin, employee])
    session.flush()
    from sisters_nook.cli import seed_users_and_menu

    seed_users_and_menu(session)
    session.commit()
    yield {"session": session, "admin": admin, "employee": employee}
    session.close()


def test_admin_cannot_delete_own_account(admin_delete_setup):
    user_service = UserService(admin_delete_setup["session"])
    with pytest.raises(ValueError, match="your own account"):
        user_service.deactivate_user(admin_delete_setup["admin"], admin_delete_setup["admin"].id)


def test_admin_can_delete_other_user(admin_delete_setup):
    session = admin_delete_setup["session"]
    user_service = UserService(session)
    target = session.query(User).filter_by(email="employee@sisters.local").one()
    deactivated = user_service.deactivate_user(admin_delete_setup["admin"], target.id)
    assert not deactivated.is_active


def test_admin_can_delete_open_order_without_payments(admin_delete_setup):
    session = admin_delete_setup["session"]
    from sisters_nook.services import MenuService

    admin = admin_delete_setup["admin"]
    menu_service = MenuService(session)
    order_service = OrderService(session)
    items = menu_service.list_active()
    assert items
    order = order_service.create_order(admin, [OrderLineRequest(items[0].id, 1)])
    order_service.cancel_order(admin, order.id)
    assert order.status.value == "cancelled"


def test_admin_can_delete_paid_order(admin_delete_setup):
    session = admin_delete_setup["session"]
    from sisters_nook.schema import PaymentMethod, PaymentStatus
    from sisters_nook.services import MenuService, PaymentService

    admin = admin_delete_setup["admin"]
    menu_service = MenuService(session)
    order_service = OrderService(session)
    payment_service = PaymentService(session)
    items = menu_service.list_active()
    assert items
    order = order_service.create_order(admin, [OrderLineRequest(items[0].id, 1)])
    payment_service.log_payment(
        admin, order.id, order.grand_total, PaymentMethod.CASH, status=PaymentStatus.PAID
    )
    assert order.status.value == "paid"
    order_service.cancel_order(admin, order.id)
    assert order.status.value == "cancelled"
    assert order.cancelled_at is not None


def test_admin_can_remove_audit_entry(admin_delete_setup):
    session = admin_delete_setup["session"]
    admin = admin_delete_setup["admin"]
    events = queries.audit_events(session, limit=1000)
    assert events
    target = events[0]
    AuditService(session).suppress_event(admin, target.event_key)
    session.commit()

    session = SessionLocal()
    remaining = queries.audit_events(session, limit=1000)
    session.close()
    assert all(event.event_key != target.event_key for event in remaining)
