from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for

from sisters_nook.db import get_session
from sqlalchemy.orm import selectinload

from sisters_nook.schema import Order, OrderStatus, Payment, PaymentMethod, PaymentStatus, UserRole
from sisters_nook.services import MenuService, OrderLineRequest, OrderService, PaymentService
from sisters_nook.web.auth_utils import admin_required, get_current_user, login_required

orders_bp = Blueprint("orders", __name__)


def _parse_line_items(form, menu_items) -> list[OrderLineRequest]:
    lines: list[OrderLineRequest] = []
    for item in menu_items:
        qty_raw = form.get(f"qty_{item.id}", "0")
        try:
            qty = int(qty_raw)
        except ValueError:
            qty = 0
        if qty > 0:
            lines.append(OrderLineRequest(menu_item_id=item.id, quantity=qty))
    if not lines:
        raise ValueError("Orders must contain at least one item.")
    return lines


@orders_bp.route("/orders")
@login_required
def history():
    status_filter = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")
    today_only = request.args.get("today") in {"1", "true", "yes"}
    if today_only:
        today = datetime.utcnow().date().isoformat()
        date_from = today
        date_to = today
    with get_session() as db_session:
        user = get_current_user(db_session)
        query = db_session.query(Order).order_by(Order.created_at.desc())
        if status_filter:
            query = query.filter(Order.status == OrderStatus(status_filter))
        if date_from:
            query = query.filter(Order.created_at >= datetime.fromisoformat(date_from))
        if date_to:
            end = datetime.fromisoformat(date_to)
            query = query.filter(Order.created_at <= end.replace(hour=23, minute=59, second=59))
        orders = query.all()
        is_admin = user.role == UserRole.ADMIN
    return render_template(
        "orders/history.html",
        orders=orders,
        is_admin=is_admin,
        status_filter=status_filter or "",
        date_from=date_from or "",
        date_to=date_to or "",
        today_only=today_only,
        statuses=[s.value for s in OrderStatus],
    )


@orders_bp.route("/orders/new", methods=["GET", "POST"])
@login_required
def create():
    with get_session() as db_session:
        user = get_current_user(db_session)
        menu_items = MenuService(db_session).list_active()
        order_service = OrderService(db_session)
        if request.method == "POST":
            try:
                lines = _parse_line_items(request.form, menu_items)
                order_name = request.form.get("order_name", "").strip() or None
                tax = Decimal(request.form.get("tax_total") or "0")
                discount = Decimal(request.form.get("discount_total") or "0")
                tip = Decimal(request.form.get("tip_total") or "0")
                notes = request.form.get("notes") or None
                order = order_service.create_order(
                    user,
                    lines,
                    order_name=order_name,
                    tax_total=tax,
                    discount_total=discount,
                    tip_total=tip,
                    notes=notes,
                )
                flash(f"Order {order.order_number} created.", "success")
                return redirect(url_for("orders.detail", order_id=order.id))
            except Exception as exc:
                flash(str(exc), "danger")
    return render_template("orders/create.html", menu_items=menu_items)


@orders_bp.route("/orders/<order_id>")
@login_required
def detail(order_id: str):
    with get_session() as db_session:
        user = get_current_user(db_session)
        order = (
            db_session.query(Order)
            .options(
                selectinload(Order.order_items),
                selectinload(Order.payments).selectinload(Payment.refunds),
            )
            .filter_by(id=order_id)
            .one_or_none()
        )
        if order is None:
            flash("Order not found.", "danger")
            return redirect(url_for("orders.history"))
        is_admin = user.role == UserRole.ADMIN
    return render_template("orders/detail.html", order=order, is_admin=is_admin)


@orders_bp.route("/orders/<order_id>/payment", methods=["GET", "POST"])
@login_required
def payment(order_id: str):
    with get_session() as db_session:
        user = get_current_user(db_session)
        order = db_session.get(Order, order_id)
        if order is None:
            flash("Order not found.", "danger")
            return redirect(url_for("orders.history"))
        if request.method == "POST":
            try:
                amount = Decimal(request.form.get("amount", "0"))
                method = PaymentMethod(request.form.get("method", PaymentMethod.CASH.value))
                status = PaymentStatus(request.form.get("status", PaymentStatus.PAID.value))
                PaymentService(db_session).log_payment(user, order_id, amount, method, status=status)
                flash("Payment logged.", "success")
                return redirect(url_for("orders.detail", order_id=order_id))
            except Exception as exc:
                flash(str(exc), "danger")
        methods = [m.value for m in PaymentMethod]
        statuses = [s.value for s in PaymentStatus]
    return render_template(
        "orders/payment.html",
        order=order,
        methods=methods,
        statuses=statuses,
    )


@orders_bp.route("/orders/<order_id>/cancel", methods=["POST"])
@admin_required
def cancel(order_id: str):
    with get_session() as db_session:
        user = get_current_user(db_session)
        try:
            OrderService(db_session).cancel_order(user, order_id)
            flash("Order cancelled.", "success")
        except Exception as exc:
            flash(str(exc), "danger")
    return redirect(url_for("orders.detail", order_id=order_id))
