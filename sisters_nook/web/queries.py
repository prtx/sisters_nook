from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from sisters_nook.schema import (
    AuditEventSuppression,
    MenuItem,
    MenuItemPriceHistory,
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    Refund,
    User,
)


def _today_start() -> datetime:
    now = datetime.utcnow()
    return datetime(now.year, now.month, now.day)


def today_sales_total(db_session: Session) -> Decimal:
    start = _today_start()
    payments = (
        db_session.query(Payment)
        .filter(Payment.created_at >= start, Payment.status == PaymentStatus.PAID)
        .all()
    )
    return sum((p.amount for p in payments), Decimal("0.00"))


def order_counts_by_status(db_session: Session) -> dict[str, int]:
    counts = {status.value: 0 for status in OrderStatus}
    for order in db_session.query(Order).all():
        counts[order.status.value] += 1
    return counts


def count_orders_today(db_session: Session, status: OrderStatus | None = None) -> int:
    start = _today_start()
    query = db_session.query(Order).filter(Order.created_at >= start)
    if status:
        query = query.filter(Order.status == status)
    return query.count()


def count_payments_today(db_session: Session) -> int:
    start = _today_start()
    return db_session.query(Payment).filter(Payment.created_at >= start).count()


def active_menu_count(db_session: Session) -> int:
    return db_session.query(MenuItem).filter_by(is_active=True).count()


def inactive_menu_count(db_session: Session) -> int:
    return db_session.query(MenuItem).filter_by(is_active=False).count()


def user_count(db_session: Session) -> int:
    return db_session.query(User).count()


def recent_orders(db_session: Session, limit: int = 10) -> list[Order]:
    return db_session.query(Order).order_by(Order.created_at.desc()).limit(limit).all()


def open_orders_list(db_session: Session, limit: int = 50) -> list[Order]:
    return (
        db_session.query(Order)
        .filter(Order.status == OrderStatus.OPEN)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .all()
    )


def recent_payments(db_session: Session, limit: int = 10) -> list[Payment]:
    return db_session.query(Payment).order_by(Payment.created_at.desc()).limit(limit).all()


def recent_refunds(db_session: Session, limit: int = 10) -> list[Refund]:
    return db_session.query(Refund).order_by(Refund.created_at.desc()).limit(limit).all()


def recent_price_changes(db_session: Session, limit: int = 10) -> list[MenuItemPriceHistory]:
    return (
        db_session.query(MenuItemPriceHistory)
        .order_by(MenuItemPriceHistory.changed_at.desc())
        .limit(limit)
        .all()
    )


def inactive_menu_items(db_session: Session, limit: int = 10) -> list[MenuItem]:
    return (
        db_session.query(MenuItem)
        .filter_by(is_active=False)
        .order_by(MenuItem.updated_at.desc())
        .limit(limit)
        .all()
    )


@dataclass
class AuditEvent:
    timestamp: datetime
    user_email: str
    action: str
    target: str
    old_value: str
    new_value: str
    event_key: str = ""


def audit_event_key(timestamp: datetime, action: str, target: str, user_email: str) -> str:
    ts = timestamp.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")
    raw = f"{ts}|{action}|{target}|{user_email}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _audit_event(
    timestamp: datetime,
    user_email: str,
    action: str,
    target: str,
    old_value: str,
    new_value: str,
) -> AuditEvent:
    return AuditEvent(
        timestamp=timestamp,
        user_email=user_email,
        action=action,
        target=target,
        old_value=old_value,
        new_value=new_value,
        event_key=audit_event_key(timestamp, action, target, user_email),
    )


def _user_email(db_session: Session, user_id: str | None) -> str:
    if not user_id:
        return "unknown"
    user = db_session.get(User, user_id)
    return user.email if user else "unknown"


def audit_events(db_session: Session, limit: int = 100) -> list[AuditEvent]:
    events: list[AuditEvent] = []
    suppressed = {
        row.event_key
        for row in db_session.query(AuditEventSuppression.event_key).all()
    }

    for order in db_session.query(Order).all():
        events.append(
            _audit_event(
                timestamp=order.created_at,
                user_email=_user_email(db_session, order.created_by_user_id),
                action="order_created",
                target=order.order_number,
                old_value="",
                new_value=f"{order.status.value} (NRs {order.grand_total})",
            )
        )
        if order.paid_at:
            events.append(
                _audit_event(
                    timestamp=order.paid_at,
                    user_email=_user_email(db_session, order.created_by_user_id),
                    action="order_paid",
                    target=order.order_number,
                    old_value="open",
                    new_value="paid",
                )
            )
        if order.cancelled_at:
            events.append(
                _audit_event(
                    timestamp=order.cancelled_at,
                    user_email=_user_email(db_session, order.created_by_user_id),
                    action="order_cancelled",
                    target=order.order_number,
                    old_value="open",
                    new_value="cancelled",
                )
            )

    for payment in db_session.query(Payment).all():
        events.append(
            _audit_event(
                timestamp=payment.created_at,
                user_email=_user_email(db_session, payment.logged_by_user_id),
                action="payment_logged",
                target=payment.order.order_number if payment.order else payment.order_id,
                old_value="",
                new_value=f"{payment.status.value} NRs {payment.amount} ({payment.payment_method.value})",
            )
        )

    for item in db_session.query(MenuItem).all():
        events.append(
            _audit_event(
                timestamp=item.created_at,
                user_email=_user_email(db_session, item.created_by_user_id),
                action="menu_created",
                target=item.name,
                old_value="",
                new_value=str(item.current_price),
            )
        )

    for record in db_session.query(MenuItemPriceHistory).all():
        item = db_session.get(MenuItem, record.menu_item_id)
        events.append(
            _audit_event(
                timestamp=record.changed_at,
                user_email=_user_email(db_session, record.changed_by_user_id),
                action="price_change",
                target=item.name if item else record.menu_item_id,
                old_value=str(record.old_price or ""),
                new_value=str(record.new_price),
            )
        )

    for refund in db_session.query(Refund).all():
        events.append(
            _audit_event(
                timestamp=refund.created_at,
                user_email=_user_email(db_session, refund.refunded_by_user_id),
                action="refund_created",
                target=refund.payment_id,
                old_value="",
                new_value=str(refund.amount),
            )
        )

    for user in db_session.query(User).all():
        if user.updated_at and user.updated_at > user.created_at + timedelta(seconds=1):
            events.append(
                _audit_event(
                    timestamp=user.updated_at,
                    user_email=user.email,
                    action="user_updated",
                    target=user.email,
                    old_value="",
                    new_value="active" if user.is_active else "inactive",
                )
            )

    events = [event for event in events if event.event_key not in suppressed]
    events.sort(key=lambda e: e.timestamp, reverse=True)
    return events[:limit]
