from __future__ import annotations

import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from sisters_nook.db import get_session, reset_database
from sisters_nook.schema import UserRole
from sisters_nook.web import queries
from sisters_nook.web.auth_utils import admin_required, get_current_user, login_required

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    with get_session() as db_session:
        user = get_current_user(db_session)
        is_admin = user.role == UserRole.ADMIN
        context = {
            "is_admin": is_admin,
            "today_sales": queries.today_sales_total(db_session),
            "active_menu_count": queries.active_menu_count(db_session),
            "open_orders_list": queries.open_orders_list(db_session),
            "open_orders": queries.order_counts_by_status(db_session).get("open", 0),
            "payments_today": queries.count_payments_today(db_session),
        }
    return render_template("dashboard.html", **context)


@dashboard_bp.route("/reset-db", methods=["POST"])
@admin_required
def reset_db():
    if not (current_app.debug or os.environ.get("ALLOW_RESET") == "1"):
        flash("Database reset is disabled.", "danger")
        return redirect(url_for("dashboard.index"))
    reset_database()
    flash("Database reset.", "success")
    return redirect(url_for("dashboard.index"))
