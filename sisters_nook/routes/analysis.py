from __future__ import annotations

from flask import Blueprint, render_template, request

from sisters_nook.db import get_session
from sisters_nook.schema import OrderStatus, PaymentMethod, User
from sisters_nook.web.analysis import get_analysis_dashboard_data, resolve_date_range
from sisters_nook.web.auth_utils import admin_required, get_current_user

analysis_bp = Blueprint("analysis", __name__)

DATE_RANGE_OPTIONS = [
    ("today", "Today"),
    ("yesterday", "Yesterday"),
    ("this_week", "This week"),
    ("this_month", "This month"),
    ("custom", "Custom"),
]

COMPARE_OPTIONS = [
    ("none", "None"),
    ("previous_period", "Previous period"),
]

ORDER_STATUS_OPTIONS = [
    ("paid", "Paid"),
    ("cancelled", "Cancelled"),
    ("refunded", "Refunded"),
    ("all", "All"),
]


@analysis_bp.route("/analysis")
@admin_required
def index():
    date_range = request.args.get("date_range", "today")
    compare = request.args.get("compare", "none")
    user_filter = request.args.get("user") or None
    payment_method = request.args.get("payment_method") or None
    order_status = request.args.get("order_status", "paid")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")

    start_date, end_date = resolve_date_range(date_range, from_date, to_date)

    with get_session() as db_session:
        user = get_current_user(db_session)
        active_users = (
            db_session.query(User)
            .filter(User.is_active.is_(True))
            .order_by(User.email)
            .all()
        )
        data = get_analysis_dashboard_data(
            db_session,
            user,
            start_date,
            end_date,
            compare_mode=compare,
            user_id=user_filter,
            payment_method=payment_method,
            order_status=order_status,
            date_range=date_range,
            is_admin=True,
        )

    return render_template(
        "analysis/index.html",
        data=data,
        date_range=date_range,
        compare=compare,
        user_filter=user_filter or "",
        payment_method=payment_method or "",
        order_status=order_status,
        from_date=from_date or data["filters"]["from_date"],
        to_date=to_date or data["filters"]["to_date"],
        date_range_options=DATE_RANGE_OPTIONS,
        compare_options=COMPARE_OPTIONS,
        order_status_options=ORDER_STATUS_OPTIONS,
        payment_methods=[m.value for m in PaymentMethod],
        active_users=active_users,
        statuses=[s.value for s in OrderStatus],
    )
