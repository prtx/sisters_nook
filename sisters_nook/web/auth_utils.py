from __future__ import annotations

from functools import wraps

from flask import flash, redirect, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from sisters_nook.db import get_session
from sisters_nook.schema import User, UserRole


def hash_password(value: str) -> str:
    return generate_password_hash(value)


def verify_password(stored_hash: str, password: str) -> bool:
    if stored_hash == password:
        return True
    try:
        return check_password_hash(stored_hash, password)
    except (ValueError, TypeError):
        return False


def get_current_user(db_session) -> User | None:
    user_id = session.get("user_id")
    if not user_id:
        return None
    user = db_session.get(User, user_id)
    if user is None or not user.is_active:
        return None
    return user


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        with get_session() as db_session:
            user = get_current_user(db_session)
            if user is None:
                flash("Login required.", "warning")
                return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        with get_session() as db_session:
            user = get_current_user(db_session)
            if user is None:
                flash("Login required.", "warning")
                return redirect(url_for("auth.login"))
            if user.role != UserRole.ADMIN:
                flash("Admin access required.", "danger")
                return redirect(url_for("dashboard.index"))
        return view(*args, **kwargs)

    return wrapper


def employee_or_admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        with get_session() as db_session:
            user = get_current_user(db_session)
            if user is None:
                flash("Login required.", "warning")
                return redirect(url_for("auth.login"))
            if user.role not in (UserRole.ADMIN, UserRole.EMPLOYEE):
                flash("Access denied.", "danger")
                return redirect(url_for("dashboard.index"))
        return view(*args, **kwargs)

    return wrapper
