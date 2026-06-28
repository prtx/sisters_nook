from datetime import datetime, timedelta

import pytest

from sisters_nook.cli import seed_users_and_menu
from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.mock_seed import populate_mock_sales
from sisters_nook.schema import Order, OrderStatus, Payment, Refund, User, UserRole
from sisters_nook.web.auth_utils import hash_password


@pytest.fixture
def mock_seed_setup():
    reset_database()
    session = SessionLocal()
    admin = User(
        first_name="Admin",
        last_name="Mock",
        email="admin@sisters.local",
        password_hash=hash_password("hash"),
        role=UserRole.ADMIN,
    )
    employee = User(
        first_name="Employee",
        last_name="Mock",
        email="employee@sisters.local",
        password_hash=hash_password("hash"),
        role=UserRole.EMPLOYEE,
    )
    session.add_all([admin, employee])
    session.commit()
    session.close()

    with SessionLocal() as session:
        seed_users_and_menu(session)
        session.commit()

    yield
    SessionLocal().close()


def test_mock_seed_populates_sales_history(mock_seed_setup):
    session = SessionLocal()
    admin = session.query(User).filter_by(email="admin@sisters.local").one()
    employee = session.query(User).filter_by(email="employee@sisters.local").one()

    stats = populate_mock_sales(session, admin, employee, days=14, seed=7)
    session.commit()

    assert stats["paid_orders"] > 20
    assert session.query(Order).filter(Order.status == OrderStatus.PAID).count() > 0
    assert session.query(Payment).count() > 0
    assert session.query(Refund).count() >= 1

    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_paid = (
        session.query(Order)
        .filter(
            Order.status.in_([OrderStatus.PAID, OrderStatus.REFUNDED]),
            Order.paid_at >= today_start,
        )
        .count()
    )
    assert today_paid > 0

    older_than_week = (
        session.query(Order)
        .filter(Order.paid_at <= today_start - timedelta(days=7))
        .count()
    )
    assert older_than_week > 0
    session.close()
