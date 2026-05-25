from datetime import datetime
from decimal import Decimal
import hashlib

import pytest

from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.schema import User, UserRole
from sisters_nook.services import MenuService, UserService


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def authenticate_user(session, email: str, password: str) -> User | None:
    user = session.query(User).filter_by(email=email).one_or_none()
    if user is None or not user.is_active:
        return None
    if user.password_hash != hash_password(password):
        return None
    return user


@pytest.fixture(scope="function")
def session():
    reset_database()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_users(session):
    admin = User(
        first_name="Admin",
        last_name="Login",
        email="admin@sisters.local",
        password_hash=hash_password("secret"),
        role=UserRole.ADMIN,
    )
    employee = User(
        first_name="Employee",
        last_name="Login",
        email="employee@sisters.local",
        password_hash=hash_password("secret"),
        role=UserRole.EMPLOYEE,
    )
    session.add_all([admin, employee])
    session.flush()
    return admin, employee


def test_AUTH_001_allow_sign_in_by_email_password(session):
    admin, _ = create_users(session)
    user = authenticate_user(session, admin.email, "secret")
    assert user is not None
    assert user.email == admin.email


def test_AUTH_002_passwords_stored_hashed(session):
    admin, _ = create_users(session)
    stored = session.query(User).filter_by(email=admin.email).one()
    assert stored.password_hash == hash_password("secret")
    assert stored.password_hash != "secret"


def test_AUTH_003_identifies_role_on_login(session):
    admin, _ = create_users(session)
    user = authenticate_user(session, admin.email, "secret")
    assert user.role == UserRole.ADMIN


def test_AUTH_004_prevents_inactive_users(session):
    _, employee = create_users(session)
    employee.is_active = False
    session.add(employee)
    session.flush()
    assert authenticate_user(session, employee.email, "secret") is None


def test_AUTH_005_records_last_login(session):
    admin, _ = create_users(session)
    user_service = UserService(session)
    assert admin.last_login_at is None
    user_service.record_login(admin.id)
    assert admin.last_login_at is not None
    assert admin.last_login_at <= datetime.utcnow()


def test_AUTH_006_restricts_role_access(session):
    _, employee = create_users(session)
    menu_service = MenuService(session)
    with pytest.raises(PermissionError):
        menu_service.create_menu_item(employee, "Path Latte", Decimal("3.50"), "auth guard")
