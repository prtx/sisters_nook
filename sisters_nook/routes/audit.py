from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from sisters_nook.db import get_session
from sisters_nook.services import AuditService
from sisters_nook.web import queries
from sisters_nook.web.auth_utils import admin_required, get_current_user

audit_bp = Blueprint("audit", __name__)

ACTION_LABELS = {
    "order_created": "Order created",
    "order_paid": "Order paid",
    "order_cancelled": "Order cancelled",
    "payment_logged": "Payment logged",
    "menu_created": "Menu item created",
    "price_change": "Price changed",
    "refund_created": "Refund created",
    "user_updated": "User updated",
}

CATEGORY_ACTIONS = {
    "orders": {"order_created", "order_paid", "order_cancelled"},
    "payments": {"payment_logged"},
    "menu": {"menu_created", "price_change"},
    "refunds": {"refund_created"},
    "users": {"user_updated"},
}


@audit_bp.route("/audit")
@admin_required
def list_audit():
    action_filter = request.args.get("action", "")
    category_filter = request.args.get("category", "")
    user_filter = request.args.get("user", "")
    date_from = request.args.get("date_from", "")
    date_to = request.args.get("date_to", "")
    search_query = request.args.get("q", "").strip().lower()
    today_only = request.args.get("today") in {"1", "true", "yes"}

    if today_only:
        today = datetime.utcnow().date().isoformat()
        date_from = today
        date_to = today

    with get_session() as db_session:
        events = sorted(
            queries.audit_events(db_session, limit=1000),
            key=lambda event: event.timestamp,
            reverse=True,
        )

    user_emails = sorted({event.user_email for event in events})

    filtered = events
    if category_filter and category_filter in CATEGORY_ACTIONS:
        allowed = CATEGORY_ACTIONS[category_filter]
        filtered = [e for e in filtered if e.action in allowed]
    if action_filter:
        filtered = [e for e in filtered if e.action == action_filter]
    if user_filter:
        filtered = [e for e in filtered if e.user_email == user_filter]
    if date_from:
        start = datetime.fromisoformat(date_from)
        filtered = [e for e in filtered if e.timestamp >= start]
    if date_to:
        end = datetime.fromisoformat(date_to).replace(hour=23, minute=59, second=59)
        filtered = [e for e in filtered if e.timestamp <= end]
    if search_query:
        filtered = [
            e
            for e in filtered
            if search_query in e.user_email.lower()
            or search_query in e.action.lower()
            or search_query in e.target.lower()
            or search_query in (e.old_value or "").lower()
            or search_query in (e.new_value or "").lower()
            or search_query in ACTION_LABELS.get(e.action, "").lower()
        ]

    return render_template(
        "audit/list.html",
        events=filtered,
        action_labels=ACTION_LABELS,
        actions=sorted(ACTION_LABELS.keys()),
        categories=[
            ("orders", "Orders"),
            ("payments", "Payments"),
            ("menu", "Menu"),
            ("refunds", "Refunds"),
            ("users", "Users"),
        ],
        action_filter=action_filter,
        category_filter=category_filter,
        user_filter=user_filter,
        user_emails=user_emails,
        date_from=date_from,
        date_to=date_to,
        search_query=search_query,
        today_only=today_only,
        total_count=len(events),
        filtered_count=len(filtered),
    )


@audit_bp.route("/audit/delete", methods=["POST"])
@admin_required
def delete_event():
    event_key = request.form.get("event_key", "").strip()
    with get_session() as db_session:
        actor = get_current_user(db_session)
        try:
            AuditService(db_session).suppress_event(actor, event_key)
            flash("Audit entry removed.", "success")
        except Exception as exc:
            flash(str(exc), "danger")
    return redirect(request.referrer or url_for("audit.list_audit"))
