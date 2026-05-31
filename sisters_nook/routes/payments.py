from __future__ import annotations

from flask import Blueprint, render_template, request

from sisters_nook.db import get_session
from sqlalchemy.orm import selectinload

from sisters_nook.schema import Payment, PaymentMethod, User
from sisters_nook.web.auth_utils import get_current_user, login_required

payments_bp = Blueprint("payments", __name__)


@payments_bp.route("/payments")
@login_required
def list_payments():
    method_filter = request.args.get("method")
    with get_session() as db_session:
        get_current_user(db_session)
        query = (
            db_session.query(Payment)
            .options(selectinload(Payment.order))
            .order_by(Payment.created_at.desc())
        )
        if method_filter:
            query = query.filter(Payment.payment_method == PaymentMethod(method_filter))
        payments = query.all()
        user_emails = {}
        for payment in payments:
            if payment.logged_by_user_id not in user_emails:
                u = db_session.get(User, payment.logged_by_user_id)
                user_emails[payment.logged_by_user_id] = u.email if u else "unknown"
        methods = [m.value for m in PaymentMethod]
    return render_template(
        "payments/list.html",
        payments=payments,
        user_emails=user_emails,
        method_filter=method_filter or "",
        methods=methods,
    )
