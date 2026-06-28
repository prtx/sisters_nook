from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from sisters_nook.schema import (
    MenuItem,
    MenuItemPriceHistory,
    Order,
    OrderItem,
    OrderStatus,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Refund,
    User,
)

TWO_PLACES = Decimal("0.01")


def _normalize(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES)


def format_currency(amount: Decimal | float | int) -> str:
    value = _normalize(Decimal(str(amount)))
    return f"NRs {value:,.2f}"


def format_percent(rate: Decimal) -> str:
    if rate <= Decimal("0"):
        return "0.0%"
    return f"{(rate * Decimal('100')).quantize(Decimal('0.1'))}%"


def _day_start(value: datetime) -> datetime:
    return datetime(value.year, value.month, value.day)


def _day_end(value: datetime) -> datetime:
    return _day_start(value).replace(hour=23, minute=59, second=59, microsecond=999999)


def _week_start(value: datetime) -> datetime:
    start = _day_start(value)
    return start - timedelta(days=start.weekday())


def _month_start(value: datetime) -> datetime:
    return datetime(value.year, value.month, 1)


def resolve_date_range(
    date_range: str,
    from_date: str | None = None,
    to_date: str | None = None,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Resolve UI date-range presets to inclusive UTC start/end datetimes."""
    current = now or datetime.utcnow()
    today = _day_start(current)

    if date_range == "yesterday":
        day = today - timedelta(days=1)
        return day, _day_end(day)
    if date_range == "this_week":
        return _week_start(current), _day_end(current)
    if date_range == "this_month":
        return _month_start(current), _day_end(current)
    if date_range == "custom" and from_date and to_date:
        start = datetime.fromisoformat(from_date)
        end = _day_end(datetime.fromisoformat(to_date))
        return _day_start(start), end
    return today, _day_end(current)


def previous_period(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    duration = end - start
    prev_end = start - timedelta(microseconds=1)
    prev_start = prev_end - duration
    return prev_start, prev_end


def _comparison_text(current: Decimal, previous: Decimal) -> dict[str, str] | None:
    if previous == Decimal("0.00"):
        if current == Decimal("0.00"):
            return {"text": "No change vs previous period", "class": "neutral"}
        return {"text": "Up from NRs 0.00 previous period", "class": "positive"}
    change = ((current - previous) / previous) * Decimal("100")
    rounded = change.quantize(Decimal("0.1"))
    if rounded > 0:
        return {"text": f"Up {rounded}% vs previous period", "class": "positive"}
    if rounded < 0:
        return {"text": f"Down {abs(rounded)}% vs previous period", "class": "negative"}
    return {"text": "No change vs previous period", "class": "neutral"}


def _payment_timestamp():
    """Sales/payment metrics use paid_at when set, otherwise created_at."""
    return func.coalesce(Payment.paid_at, Payment.created_at)


def _order_sales_timestamp():
    """Paid-order revenue uses paid_at when set, otherwise created_at."""
    return func.coalesce(Order.paid_at, Order.created_at)


@dataclass
class AnalysisContext:
    start: datetime
    end: datetime
    compare_start: datetime | None
    compare_end: datetime | None
    user_id: str | None
    payment_method: PaymentMethod | None
    order_status: OrderStatus | None
    include_all_statuses: bool
    group_by_hour: bool


def _build_context(
    start_date: datetime,
    end_date: datetime,
    compare_mode: str,
    user_id: str | None,
    payment_method: str | None,
    order_status: str | None,
    date_range: str,
) -> AnalysisContext:
    compare_start = compare_end = None
    if compare_mode == "previous_period":
        compare_start, compare_end = previous_period(start_date, end_date)

    method = PaymentMethod(payment_method) if payment_method else None
    status = None
    include_all = order_status in (None, "", "all")
    if order_status and order_status not in ("", "all"):
        status = OrderStatus(order_status)

    return AnalysisContext(
        start=start_date,
        end=end_date,
        compare_start=compare_start,
        compare_end=compare_end,
        user_id=user_id or None,
        payment_method=method,
        order_status=status,
        include_all_statuses=include_all,
        group_by_hour=date_range == "today",
    )


def _orders_query(session: Session, ctx: AnalysisContext):
    ts = _order_sales_timestamp()
    query = session.query(Order).filter(ts >= ctx.start, ts <= ctx.end)
    if ctx.user_id:
        query = query.filter(Order.created_by_user_id == ctx.user_id)
    if not ctx.include_all_statuses and ctx.order_status:
        query = query.filter(Order.status == ctx.order_status)
    elif not ctx.include_all_statuses:
        query = query.filter(Order.status == OrderStatus.PAID)
    return query


def _paid_payments_query(session: Session, ctx: AnalysisContext):
    ts = _payment_timestamp()
    query = session.query(Payment).filter(
        ts >= ctx.start,
        ts <= ctx.end,
        Payment.status.in_([PaymentStatus.PAID, PaymentStatus.REFUNDED]),
    )
    if ctx.user_id:
        query = query.filter(Payment.logged_by_user_id == ctx.user_id)
    if ctx.payment_method:
        query = query.filter(Payment.payment_method == ctx.payment_method)
    return query


def _summary_for_period(session: Session, ctx: AnalysisContext, start: datetime, end: datetime) -> dict[str, Any]:
    period = AnalysisContext(
        start=start,
        end=end,
        compare_start=None,
        compare_end=None,
        user_id=ctx.user_id,
        payment_method=ctx.payment_method,
        order_status=ctx.order_status,
        include_all_statuses=ctx.include_all_statuses,
        group_by_hour=ctx.group_by_hour,
    )

    order_ts = _order_sales_timestamp()
    orders_q = session.query(Order).filter(order_ts >= start, order_ts <= end)
    if period.user_id:
        orders_q = orders_q.filter(Order.created_by_user_id == period.user_id)
    if not period.include_all_statuses and period.order_status:
        orders_q = orders_q.filter(Order.status == period.order_status)
    elif not period.include_all_statuses:
        orders_q = orders_q.filter(Order.status == OrderStatus.PAID)

    paid_orders_q = orders_q.filter(Order.status.in_([OrderStatus.PAID, OrderStatus.REFUNDED]))
    paid_orders = paid_orders_q.all()

    gross_sales = sum((o.grand_total for o in paid_orders), Decimal("0.00"))
    discounts = sum((o.discount_total for o in paid_orders), Decimal("0.00"))
    tips = sum((o.tip_total for o in paid_orders), Decimal("0.00"))
    orders_paid = orders_q.filter(Order.status == OrderStatus.PAID).count()

    payments_q = session.query(Payment).filter(
        _payment_timestamp() >= start,
        _payment_timestamp() <= end,
        Payment.status.in_([PaymentStatus.PAID, PaymentStatus.REFUNDED]),
    )
    if period.user_id:
        payments_q = payments_q.filter(Payment.logged_by_user_id == period.user_id)
    if period.payment_method:
        payments_q = payments_q.filter(Payment.payment_method == period.payment_method)
    paid_total = sum((p.amount for p in payments_q.all()), Decimal("0.00"))

    refunds_q = session.query(Refund).filter(Refund.created_at >= start, Refund.created_at <= end)
    refund_total = sum((r.amount for r in refunds_q.all()), Decimal("0.00"))

    net_sales = paid_total - refund_total
    avg_order = net_sales / orders_paid if orders_paid else Decimal("0.00")

    return {
        "gross_sales": _normalize(gross_sales),
        "net_sales": _normalize(net_sales),
        "orders_paid": orders_paid,
        "average_order_value": _normalize(avg_order),
        "discounts": _normalize(discounts),
        "tips": _normalize(tips),
        "refunds": _normalize(refund_total),
    }


def _summary_cards(session: Session, ctx: AnalysisContext) -> list[dict[str, Any]]:
    current = _summary_for_period(session, ctx, ctx.start, ctx.end)
    previous = None
    if ctx.compare_start and ctx.compare_end:
        previous = _summary_for_period(session, ctx, ctx.compare_start, ctx.compare_end)

    labels = [
        ("gross_sales", "Gross sales"),
        ("net_sales", "Net sales"),
        ("orders_paid", "Orders paid"),
        ("average_order_value", "Average order value"),
        ("discounts", "Discounts given"),
        ("tips", "Tips collected"),
        ("refunds", "Refunds"),
    ]
    cards = []
    for key, label in labels:
        value = current[key]
        display = format_currency(value) if key != "orders_paid" else str(value)
        comparison = None
        if previous is not None:
            prev_val = Decimal(str(previous[key])) if key != "orders_paid" else Decimal(previous[key])
            cur_val = Decimal(str(value)) if key != "orders_paid" else Decimal(value)
            comparison = _comparison_text(cur_val, prev_val)
        cards.append({"key": key, "label": label, "value": display, "comparison": comparison})
    return cards


def _sales_over_time(session: Session, ctx: AnalysisContext) -> list[dict[str, Any]]:
    paid_orders = (
        session.query(Order)
        .filter(
            Order.status.in_([OrderStatus.PAID, OrderStatus.REFUNDED]),
            _order_sales_timestamp() >= ctx.start,
            _order_sales_timestamp() <= ctx.end,
        )
        .all()
    )
    buckets: dict[str, dict[str, Decimal | int]] = {}

    for order in paid_orders:
        ts = order.paid_at or order.created_at
        if ctx.group_by_hour:
            label = ts.strftime("%H:00")
        else:
            label = ts.strftime("%Y-%m-%d")
        if label not in buckets:
            buckets[label] = {"sales": Decimal("0.00"), "orders": 0}
        buckets[label]["sales"] = buckets[label]["sales"] + order.grand_total  # type: ignore[operator]
        buckets[label]["orders"] = int(buckets[label]["orders"]) + 1  # type: ignore[assignment]

    rows = []
    for label in sorted(buckets.keys()):
        data = buckets[label]
        rows.append(
            {
                "label": label,
                "sales": _normalize(data["sales"]),  # type: ignore[arg-type]
                "orders": data["orders"],
                "sales_display": format_currency(data["sales"]),  # type: ignore[arg-type]
            }
        )
    return rows


def _payment_method_breakdown(session: Session, ctx: AnalysisContext) -> list[dict[str, Any]]:
    payments = _paid_payments_query(session, ctx).all()
    total = sum((p.amount for p in payments), Decimal("0.00"))
    grouped: dict[str, dict[str, Any]] = {}
    for payment in payments:
        key = payment.payment_method.value
        if key not in grouped:
            grouped[key] = {"amount": Decimal("0.00"), "count": 0}
        grouped[key]["amount"] += payment.amount
        grouped[key]["count"] += 1

    rows = []
    for method in PaymentMethod:
        data = grouped.get(method.value, {"amount": Decimal("0.00"), "count": 0})
        amount = _normalize(data["amount"])
        pct = (amount / total * Decimal("100")) if total > 0 else Decimal("0.00")
        rows.append(
            {
                "method": method.value,
                "amount": amount,
                "count": data["count"],
                "percent": pct,
                "amount_display": format_currency(amount),
                "percent_display": format_percent(pct / Decimal("100")),
            }
        )
    return rows


def _discounts_tax_tips(session: Session, ctx: AnalysisContext) -> dict[str, Any]:
    paid_orders = (
        _orders_query(session, ctx)
        .filter(Order.status.in_([OrderStatus.PAID, OrderStatus.REFUNDED]))
        .all()
    )
    subtotal = sum((o.subtotal for o in paid_orders), Decimal("0.00"))
    discounts = sum((o.discount_total for o in paid_orders), Decimal("0.00"))
    tax = sum((o.tax_total for o in paid_orders), Decimal("0.00"))
    tips = sum((o.tip_total for o in paid_orders), Decimal("0.00"))
    base = subtotal if subtotal > 0 else Decimal("0.00")
    return {
        "subtotal": format_currency(subtotal),
        "discounts": format_currency(discounts),
        "discount_rate": format_percent(discounts / base if base else Decimal("0")),
        "tax_collected": format_currency(tax),
        "tax_rate": format_percent(tax / base if base else Decimal("0")),
        "tips_collected": format_currency(tips),
        "tip_rate": format_percent(tips / base if base else Decimal("0")),
    }


def _item_rows(session: Session, ctx: AnalysisContext, sort_key: str, limit: int | None = 5) -> list[dict[str, Any]]:
    rows = (
        session.query(
            OrderItem.item_name_snapshot.label("item_name"),
            func.sum(OrderItem.quantity).label("quantity"),
            func.sum(OrderItem.line_total).label("revenue"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .filter(
            Order.status.in_([OrderStatus.PAID, OrderStatus.REFUNDED]),
            _order_sales_timestamp() >= ctx.start,
            _order_sales_timestamp() <= ctx.end,
        )
        .group_by(OrderItem.item_name_snapshot)
        .all()
    )
    items = []
    for row in rows:
        qty = int(row.quantity or 0)
        revenue = _normalize(Decimal(row.revenue or 0))
        avg = _normalize(revenue / qty) if qty else Decimal("0.00")
        items.append(
            {
                "item": row.item_name,
                "quantity": qty,
                "revenue": revenue,
                "revenue_display": format_currency(revenue),
                "average_price": format_currency(avg),
            }
        )
    if sort_key == "quantity":
        items.sort(key=lambda x: x["quantity"], reverse=True)
    else:
        items.sort(key=lambda x: x["revenue"], reverse=True)
    if limit is not None:
        items = items[:limit]
    for idx, item in enumerate(items, start=1):
        item["rank"] = idx
    return items


def _lowest_selling_active_items(session: Session, ctx: AnalysisContext, limit: int = 5) -> list[dict[str, Any]]:
    sold_rows = (
        session.query(
            OrderItem.item_name_snapshot.label("item_name"),
            func.sum(OrderItem.quantity).label("quantity"),
            func.sum(OrderItem.line_total).label("revenue"),
        )
        .join(Order, OrderItem.order_id == Order.id)
        .filter(
            Order.status.in_([OrderStatus.PAID, OrderStatus.REFUNDED]),
            _order_sales_timestamp() >= ctx.start,
            _order_sales_timestamp() <= ctx.end,
        )
        .group_by(OrderItem.item_name_snapshot)
        .all()
    )
    sold_map = {
        row.item_name: {"quantity": int(row.quantity or 0), "revenue": _normalize(Decimal(row.revenue or 0))}
        for row in sold_rows
    }

    active_items = session.query(MenuItem).filter(MenuItem.is_active.is_(True)).order_by(MenuItem.name).all()
    combined = []
    seen_names = set()
    for item in active_items:
        stats = sold_map.get(item.name, {"quantity": 0, "revenue": Decimal("0.00")})
        combined.append(
            {
                "item": item.name,
                "quantity": stats["quantity"],
                "revenue": stats["revenue"],
                "revenue_display": format_currency(stats["revenue"]),
            }
        )
        seen_names.add(item.name)

    for name, stats in sold_map.items():
        if name not in seen_names:
            combined.append(
                {
                    "item": name,
                    "quantity": stats["quantity"],
                    "revenue": stats["revenue"],
                    "revenue_display": format_currency(stats["revenue"]),
                }
            )

    combined.sort(key=lambda x: (x["quantity"], x["revenue"]))
    combined = combined[:limit]
    for idx, item in enumerate(combined, start=1):
        item["rank"] = idx
    return combined


def _staff_activity(session: Session, ctx: AnalysisContext) -> list[dict[str, Any]]:
    users = session.query(User).filter(User.is_active.is_(True)).order_by(User.email).all()
    rows = []
    for user in users:
        orders_created = (
            session.query(Order)
            .filter(
                Order.created_by_user_id == user.id,
                Order.created_at >= ctx.start,
                Order.created_at <= ctx.end,
            )
            .count()
        )
        payments = (
            session.query(Payment)
            .filter(
                Payment.logged_by_user_id == user.id,
                _payment_timestamp() >= ctx.start,
                _payment_timestamp() <= ctx.end,
                Payment.status.in_([PaymentStatus.PAID, PaymentStatus.REFUNDED]),
            )
            .all()
        )
        sales_handled = sum((p.amount for p in payments), Decimal("0.00"))
        rows.append(
            {
                "user": f"{user.first_name} {user.last_name}",
                "email": user.email,
                "orders_created": orders_created,
                "payments_logged": len(payments),
                "sales_handled": format_currency(sales_handled),
                "_sales_numeric": sales_handled,
            }
        )
    rows.sort(key=lambda x: x["_sales_numeric"], reverse=True)
    for row in rows:
        row.pop("_sales_numeric", None)
    return rows


def _refunds_and_cancellations(session: Session, ctx: AnalysisContext) -> dict[str, Any]:
    refunds = session.query(Refund).filter(Refund.created_at >= ctx.start, Refund.created_at <= ctx.end).all()
    refund_total = sum((r.amount for r in refunds), Decimal("0.00"))

    cancelled = (
        session.query(Order)
        .filter(
            Order.status == OrderStatus.CANCELLED,
            Order.cancelled_at.isnot(None),
            Order.cancelled_at >= ctx.start,
            Order.cancelled_at <= ctx.end,
        )
        .all()
    )
    cancelled_value = sum((o.grand_total for o in cancelled), Decimal("0.00"))

    recent = []
    for refund in sorted(refunds, key=lambda r: r.created_at, reverse=True)[:5]:
        user = session.get(User, refund.refunded_by_user_id)
        recent.append(
            {
                "date": refund.created_at.strftime("%Y-%m-%d %H:%M"),
                "amount": format_currency(refund.amount),
                "reason": refund.reason or "-",
                "refunded_by": user.email if user else "unknown",
            }
        )

    return {
        "refund_total": format_currency(refund_total),
        "refund_count": len(refunds),
        "cancelled_orders": len(cancelled),
        "cancelled_value": format_currency(cancelled_value),
        "recent_refunds": recent,
    }


def _recent_price_changes(session: Session, ctx: AnalysisContext, limit: int = 5) -> list[dict[str, Any]]:
    records = (
        session.query(MenuItemPriceHistory)
        .filter(MenuItemPriceHistory.changed_at >= ctx.start, MenuItemPriceHistory.changed_at <= ctx.end)
        .order_by(MenuItemPriceHistory.changed_at.desc())
        .limit(limit)
        .all()
    )
    if not records:
        records = (
            session.query(MenuItemPriceHistory)
            .order_by(MenuItemPriceHistory.changed_at.desc())
            .limit(limit)
            .all()
        )

    rows = []
    for record in records:
        item = session.get(MenuItem, record.menu_item_id)
        user = session.get(User, record.changed_by_user_id)
        rows.append(
            {
                "item": item.name if item else record.menu_item_id,
                "old_price": format_currency(record.old_price or Decimal("0.00")),
                "new_price": format_currency(record.new_price),
                "changed_by": user.email if user else "unknown",
                "changed_at": record.changed_at.strftime("%Y-%m-%d %H:%M"),
            }
        )
    return rows


def get_analysis_dashboard_data(
    session: Session,
    actor: User,
    start_date: datetime,
    end_date: datetime,
    compare_mode: str = "none",
    user_id: str | None = None,
    payment_method: str | None = None,
    order_status: str | None = "paid",
    date_range: str = "today",
    is_admin: bool = True,
) -> dict[str, Any]:
    ctx = _build_context(start_date, end_date, compare_mode, user_id, payment_method, order_status, date_range)

    data: dict[str, Any] = {
        "filters": {
            "date_range": date_range,
            "compare": compare_mode,
            "user_id": user_id or "",
            "payment_method": payment_method or "",
            "order_status": order_status or "paid",
            "from_date": start_date.date().isoformat(),
            "to_date": end_date.date().isoformat(),
        },
        "summary_cards": _summary_cards(session, ctx),
        "sales_over_time": _sales_over_time(session, ctx),
        "payment_method_breakdown": _payment_method_breakdown(session, ctx),
        "discounts_tax_tips": _discounts_tax_tips(session, ctx),
        "top_selling_items": _item_rows(session, ctx, "quantity", limit=5),
        "top_revenue_items": _item_rows(session, ctx, "revenue", limit=5),
        "lowest_selling_active_items": _lowest_selling_active_items(session, ctx, limit=5),
        "staff_activity": _staff_activity(session, ctx),
    }

    if is_admin:
        data["refunds_and_cancellations"] = _refunds_and_cancellations(session, ctx)
        data["recent_price_changes"] = _recent_price_changes(session, ctx, limit=5)
    else:
        data["refunds_and_cancellations"] = None
        data["recent_price_changes"] = None

    data["max_sales"] = max((row["sales"] for row in data["sales_over_time"]), default=Decimal("0.00"))
    data["max_orders"] = max((row["orders"] for row in data["sales_over_time"]), default=0)
    return data
