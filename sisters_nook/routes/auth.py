from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from sisters_nook.db import get_session
from sisters_nook.services import UserService
from sisters_nook.web.auth_utils import get_current_user, hash_password, verify_password

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        with get_session() as db_session:
            user_service = UserService(db_session)
            user = user_service.find_by_email(email)
            if user and user.is_active and verify_password(user.password_hash, password):
                user_service.record_login(user.id)
                session["user_id"] = user.id
                session["user_role"] = user.role.value
                flash("Successfully signed in.", "success")
                return redirect(url_for("dashboard.index"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_role", None)
    flash("Logged out.", "info")
    return redirect(url_for("auth.login"))
