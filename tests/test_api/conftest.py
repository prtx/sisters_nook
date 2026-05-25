from __future__ import annotations

from decimal import Decimal

import pytest

from sisters_nook.app import app
from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.schema import MenuItem, User, UserRole
from sisters_nook.services import MenuService


@pytest.fixture(scope="function")
def session():
    reset_database()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def admin_employee(session):
    admin = User(
        first_name="Admin",
        last_name="Api",
        email="admin@sisters.local",
        password_hash="hash",
        role=UserRole.ADMIN,
    )
    employee = User(
        first_name="Employee",
        last_name="Api",
        email="employee@sisters.local",
        password_hash="hash",
        role=UserRole.EMPLOYEE,
    )
    session.add_all([admin, employee])
    session.flush()
    menu_service = MenuService(session)
    latte = menu_service.create_menu_item(admin, "Latte", Decimal("4.50"), "Milk", sort_order=1)
    session.commit()
    return {
        "session": session,
        "admin": session.get(User, admin.id),
        "employee": session.get(User, employee.id),
        "latte": session.get(MenuItem, latte.id),
    }


@pytest.fixture(scope="function")
def client():
    with app.test_client() as client:
        yield client


def api_headers(user: User) -> dict[str, str]:
    return {"X-User-Id": user.id, "X-User-Role": user.role.value}
