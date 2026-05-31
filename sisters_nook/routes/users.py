from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from sisters_nook.db import get_session
from sisters_nook.schema import User, UserRole
from sisters_nook.services import UserService
from sisters_nook.web.auth_utils import admin_required, get_current_user, hash_password

users_bp = Blueprint("users", __name__)


@users_bp.route("/users")
@admin_required
def list_users():
    with get_session() as db_session:
        users = db_session.query(User).order_by(User.email).all()
    return render_template("users/list.html", users=users)


@users_bp.route("/users/new", methods=["GET", "POST"])
@admin_required
def create_user():
    if request.method == "POST":
        with get_session() as db_session:
            actor = get_current_user(db_session)
            user_service = UserService(db_session)
            try:
                user_service.create_user(
                    actor,
                    request.form.get("first_name", "").strip(),
                    request.form.get("last_name", "").strip(),
                    request.form.get("email", "").strip(),
                    hash_password(request.form.get("password", "")),
                    UserRole(request.form.get("role", UserRole.EMPLOYEE.value)),
                )
                flash("User created.", "success")
                return redirect(url_for("users.list_users"))
            except Exception as exc:
                flash(str(exc), "danger")
    roles = [r.value for r in UserRole]
    return render_template("users/create.html", roles=roles)


@users_bp.route("/users/<user_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_user(user_id: str):
    with get_session() as db_session:
        actor = get_current_user(db_session)
        user_service = UserService(db_session)
        user = db_session.get(User, user_id)
        if user is None:
            flash("User not found.", "danger")
            return redirect(url_for("users.list_users"))
        if request.method == "POST":
            try:
                role_raw = request.form.get("role")
                user_service.update_user(
                    actor,
                    user_id,
                    first_name=request.form.get("first_name") or None,
                    last_name=request.form.get("last_name") or None,
                    email=request.form.get("email") or None,
                    role=UserRole(role_raw) if role_raw else None,
                )
                flash("User updated.", "success")
                return redirect(url_for("users.list_users"))
            except Exception as exc:
                flash(str(exc), "danger")
        roles = [r.value for r in UserRole]
    return render_template("users/edit.html", user=user, roles=roles)


@users_bp.route("/users/<user_id>/deactivate", methods=["POST"])
@admin_required
def deactivate_user(user_id: str):
    with get_session() as db_session:
        actor = get_current_user(db_session)
        UserService(db_session).deactivate_user(actor, user_id)
        flash("User deactivated.", "success")
    return redirect(url_for("users.list_users"))


@users_bp.route("/users/<user_id>/reactivate", methods=["POST"])
@admin_required
def reactivate_user(user_id: str):
    with get_session() as db_session:
        actor = get_current_user(db_session)
        UserService(db_session).reactivate_user(actor, user_id)
        flash("User reactivated.", "success")
    return redirect(url_for("users.list_users"))
