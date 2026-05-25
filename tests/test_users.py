from decimal import Decimal

import pytest

from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.schema import User, UserRole
from sisters_nook.services import UserService


@pytest.fixture(scope="function")
def session():
    reset_database()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def user_services(session):
    admin = User(
        first_name="Admin",
        last_name="User",
        email="admin@sisters.local",
        password_hash="hash",
        role=UserRole.ADMIN,
    )
    employee = User(
        first_name="Employee",
        last_name="User",
        email="employee@sisters.local",
        password_hash="hash",
        role=UserRole.EMPLOYEE,
    )
    session.add_all([admin, employee])
    session.flush()
    yield {
        "session": session,
        "user_service": UserService(session),
        "admin": admin,
        "employee": employee,
    }


def test_USER_001_admin_can_create_employee_accounts(user_services):
    user_service: UserService = user_services["user_service"]
    admin: User = user_services["admin"]
    new_user = user_service.create_user(admin, "Barista", "New", "barista@sisters.local", "hash", UserRole.EMPLOYEE)
    fetched = user_services["session"].query(User).filter_by(email="barista@sisters.local").one_or_none()
    assert fetched is not None
    assert fetched.role == UserRole.EMPLOYEE


def test_USER_002_admin_can_create_admin_accounts(user_services):
    user_service: UserService = user_services["user_service"]
    admin: User = user_services["admin"]
    new_user = user_service.create_user(admin, "Admin", "Assistant", "assistant@sisters.local", "hash", UserRole.ADMIN)
    fetched = user_services["session"].query(User).filter_by(email="assistant@sisters.local").one_or_none()
    assert fetched is not None
    assert fetched.role == UserRole.ADMIN


def test_USER_003_admin_can_update_name_and_email(user_services):
    user_service: UserService = user_services["user_service"]
    admin: User = user_services["admin"]
    target = user_service.create_user(admin, "Old", "Name", "old@sisters.local", "hash", UserRole.EMPLOYEE)
    updated = user_service.update_user(admin, target.id, first_name="New", email="new@sisters.local")
    assert updated.first_name == "New"
    assert updated.email == "new@sisters.local"


def test_USER_004_admin_can_change_role(user_services):
    user_service: UserService = user_services["user_service"]
    admin: User = user_services["admin"]
    target = user_service.create_user(admin, "Staff", "Member", "staff@sisters.local", "hash", UserRole.EMPLOYEE)
    updated = user_service.update_user(admin, target.id, role=UserRole.ADMIN)
    assert updated.role == UserRole.ADMIN


def test_USER_005_admin_can_deactivate_user(user_services):
    user_service: UserService = user_services["user_service"]
    admin: User = user_services["admin"]
    target = user_service.create_user(admin, "Deact", "Target", "deact@sisters.local", "hash", UserRole.EMPLOYEE)
    deactivated = user_service.deactivate_user(admin, target.id)
    assert not deactivated.is_active


def test_USER_006_admin_can_reactivate_user(user_services):
    user_service: UserService = user_services["user_service"]
    admin: User = user_services["admin"]
    target = user_service.create_user(admin, "React", "Target", "react@sisters.local", "hash", UserRole.EMPLOYEE)
    user_service.deactivate_user(admin, target.id)
    reactivated = user_service.reactivate_user(admin, target.id)
    assert reactivated.is_active


def test_USER_007_employees_cannot_manage_users(user_services):
    user_service: UserService = user_services["user_service"]
    employee: User = user_services["employee"]
    with pytest.raises(PermissionError):
        user_service.create_user(employee, "Blocked", "User", "blocked@sisters.local", "hash", UserRole.ADMIN)


def test_USER_008_users_not_hard_deleted(user_services):
    user_service: UserService = user_services["user_service"]
    admin: User = user_services["admin"]
    target = user_service.create_user(admin, "Soft", "Delete", "soft@sisters.local", "hash", UserRole.EMPLOYEE)
    user_service.deactivate_user(admin, target.id)
    fetched = user_services["session"].query(User).filter_by(email="soft@sisters.local").one_or_none()
    assert fetched is not None
    assert not fetched.is_active
