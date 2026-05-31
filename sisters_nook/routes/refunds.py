from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for

from sisters_nook.db import get_session
from sisters_nook.schema import Payment, Refund, User
from sisters_nook.services import RefundService
from sisters_nook.web.auth_utils import admin_required, employee_or_admin_required, get_current_user, login_required

refunds_bp = Blueprint("refunds", __name__)


@refunds_bp.route("/refunds")
@admin_required
def list_refunds():
    with get_session() as db_session:
        refunds = db_session.query(Refund).order_by(Refund.created_at.desc()).all()
        user_emails = {}
        for refund in refunds:
            if refund.refunded_by_user_id not in user_emails:
                u = db_session.get(User, refund.refunded_by_user_id)
                user_emails[refund.refunded_by_user_id] = u.email if u else "unknown"
    return render_template("refunds/list.html", refunds=refunds, user_emails=user_emails)


@refunds_bp.route("/payments/<payment_id>/refund", methods=["GET", "POST"])
@login_required
@employee_or_admin_required
def create_refund(payment_id: str):
    with get_session() as db_session:
        user = get_current_user(db_session)
        payment = db_session.get(Payment, payment_id)
        if payment is None:
            flash("Payment not found.", "danger")
            return redirect(url_for("refunds.list_refunds"))
        order_number = payment.order.order_number if payment.order else payment.order_id
        if request.method == "POST":
            try:
                amount = Decimal(request.form.get("amount", "0"))
                reason = request.form.get("reason", "").strip()
                RefundService(db_session).create_refund(user, payment_id, amount, reason)
                flash("Refund created.", "success")
                return redirect(url_for("refunds.list_refunds"))
            except Exception as exc:
                flash(str(exc), "danger")
    return render_template("refunds/create.html", payment=payment, order_number=order_number)
