from __future__ import annotations

import random
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from sisters_nook.schema import MenuItemPriceHistory, Order, OrderStatus, Payment, PaymentMethod, PaymentStatus, User
from sisters_nook.services import (
    MenuService,
    OrderLineRequest,
    OrderService,
    PaymentService,
    RefundService,
    UserService,
)

ORDER_NAMES = [
    "Table 1",
    "Table 2",
    "Table 3",
    "Table 4",
    "Patio",
    "Takeaway",
    "Walk-in",
    "Corner booth",
]

REFUND_REASONS = [
    "Wrong item served",
    "Customer changed mind",
    "Duplicate charge",
    "Drink was cold",
    "Order cancelled late",
]

PAYMENT_METHOD_WEIGHTS = [
    (PaymentMethod.CASH, 35),
    (PaymentMethod.CARD, 25),
    (PaymentMethod.ONLINE, 15),
    (PaymentMethod.QR_CODE, 20),
    (PaymentMethod.OTHER, 5),
]


def _weighted_payment_method(rng: random.Random) -> PaymentMethod:
    methods, weights = zip(*PAYMENT_METHOD_WEIGHTS)
    return rng.choices(methods, weights=weights, k=1)[0]


def _orders_for_day(day_offset: int, rng: random.Random) -> int:
    if day_offset == 0:
        return rng.randint(22, 32)
    if day_offset < 7:
        return rng.randint(15, 22)
    if day_offset < 30:
        return rng.randint(5, 10)
    return rng.randint(2, 4)


def _random_event_time(day: datetime, rng: random.Random) -> datetime:
    hour_weights = [1, 1, 1, 1, 1, 2, 4, 6, 8, 9, 10, 10, 9, 8, 7, 6, 8, 9, 7, 5, 3, 2, 1, 1]
    hour = rng.choices(range(24), weights=hour_weights, k=1)[0]
    return day.replace(hour=hour, minute=rng.randint(0, 59), second=0, microsecond=0)


def _pick_line_items(menu_items: list, rng: random.Random) -> list[OrderLineRequest]:
    count = rng.randint(1, min(4, len(menu_items)))
    chosen = rng.sample(menu_items, k=count)
    return [OrderLineRequest(item.id, rng.randint(1, 3)) for item in chosen]


def _estimate_subtotal(session: Session, lines: list[OrderLineRequest]) -> Decimal:
    from sisters_nook.schema import MenuItem

    total = Decimal("0.00")
    for line in lines:
        item = session.get(MenuItem, line.menu_item_id)
        if item is None:
            continue
        total += item.current_price * Decimal(line.quantity)
    return total.quantize(Decimal("0.01"))


def _adjustments(subtotal: Decimal, rng: random.Random) -> tuple[Decimal, Decimal, Decimal]:
    tax = (subtotal * Decimal("0.05")).quantize(Decimal("0.01")) if rng.random() < 0.75 else Decimal("0.00")
    discount = Decimal("0.00")
    if rng.random() < 0.28:
        rate = Decimal(str(rng.uniform(0.05, 0.15))).quantize(Decimal("0.01"))
        discount = (subtotal * rate).quantize(Decimal("0.01"))
    tip = Decimal("0.00")
    if rng.random() < 0.42:
        rate = Decimal(str(rng.uniform(0.05, 0.12))).quantize(Decimal("0.01"))
        tip = (subtotal * rate).quantize(Decimal("0.01"))
    return tax, discount, tip


def _backdate_paid_order(
    session: Session,
    order: Order,
    payment: Payment | None,
    created_at: datetime,
    paid_at: datetime,
) -> None:
    order.created_at = created_at
    order.paid_at = paid_at
    order.status = OrderStatus.PAID
    session.add(order)
    for line in order.order_items:
        line.created_at = created_at
        session.add(line)
    if payment is not None:
        payment.created_at = paid_at
        payment.paid_at = paid_at
        session.add(payment)


def populate_mock_sales(
    session: Session,
    admin: User,
    employee: User,
    *,
    days: int = 10,
    seed: int = 42,
) -> dict[str, int]:
    rng = random.Random(seed)
    menu_service = MenuService(session)
    order_service = OrderService(session)
    payment_service = PaymentService(session)
    refund_service = RefundService(session)

    menu_items = menu_service.list_active()
    if not menu_items:
        raise ValueError("No active menu items found. Run seed first.")

    actors = [admin, employee]
    stats = {
        "paid_orders": 0,
        "open_orders": 0,
        "cancelled_orders": 0,
        "refunds": 0,
        "price_changes": 0,
    }
    refundable_payments: list[tuple[Payment, datetime, User]] = []

    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    for day_offset in range(days):
        day_start = today - timedelta(days=day_offset)
        for _ in range(_orders_for_day(day_offset, rng)):
            actor = rng.choice(actors)
            lines = _pick_line_items(menu_items, rng)
            subtotal = _estimate_subtotal(session, lines)
            tax, discount, tip = _adjustments(subtotal, rng)
            paid_at = _random_event_time(day_start, rng)
            created_at = paid_at - timedelta(minutes=rng.randint(4, 35))

            order = order_service.create_order(
                actor,
                lines,
                order_name=rng.choice(ORDER_NAMES),
                tax_total=tax,
                discount_total=discount,
                tip_total=tip,
                notes="Mock demo order" if rng.random() < 0.08 else None,
            )

            roll = rng.random()
            if roll < 0.04 and day_offset > 0:
                order.status = OrderStatus.CANCELLED
                order.cancelled_at = paid_at
                order.created_at = created_at
                session.add(order)
                stats["cancelled_orders"] += 1
                continue

            if roll < 0.03 and day_offset == 0:
                order.created_at = created_at
                session.add(order)
                stats["open_orders"] += 1
                continue

            method = _weighted_payment_method(rng)
            payment = payment_service.log_payment(
                actor,
                order.id,
                order.grand_total,
                method,
                note="Mock payment" if rng.random() < 0.1 else None,
                status=PaymentStatus.PAID,
            )
            _backdate_paid_order(session, order, payment, created_at, paid_at)
            stats["paid_orders"] += 1

            if rng.random() < 0.06:
                refundable_payments.append((payment, paid_at + timedelta(hours=rng.randint(1, 48)), actor))

    for payment, refund_at, actor in refundable_payments[: max(1, len(refundable_payments) // 3)]:
        amount = (payment.amount * Decimal(str(rng.uniform(0.25, 1.0)))).quantize(Decimal("0.01"))
        if amount <= Decimal("0.00"):
            continue
        refund = refund_service.create_refund(actor, payment.id, amount, rng.choice(REFUND_REASONS))
        refund.created_at = refund_at
        session.add(refund)
        stats["refunds"] += 1

    price_targets = rng.sample(menu_items, k=min(4, len(menu_items)))
    for idx, item in enumerate(price_targets):
        delta = Decimal(str(rng.choice([-20, -10, 10, 15, 25, 30])))
        new_price = max(Decimal("20.00"), item.current_price + delta)
        menu_service.change_price(admin, item.id, new_price)
        history = (
            session.query(MenuItemPriceHistory)
            .filter_by(menu_item_id=item.id)
            .order_by(MenuItemPriceHistory.changed_at.desc())
            .first()
        )
        if history is not None:
            history.changed_at = today - timedelta(days=rng.randint(2, 20), hours=idx * 3)
            session.add(history)
            stats["price_changes"] += 1

    return stats


def ensure_demo_users(session: Session, seed_users_and_menu) -> tuple[User, User]:
    user_service = UserService(session)
    admin = user_service.find_by_email("admin@sisters.local")
    employee = user_service.find_by_email("employee@sisters.local")
    menu_service = MenuService(session)
    if admin is None or employee is None or not menu_service.list_active():
        seed_users_and_menu(session)
        admin = user_service.find_by_email("admin@sisters.local")
        employee = user_service.find_by_email("employee@sisters.local")
    if admin is None or employee is None:
        raise ValueError("Failed to seed demo users.")
    return admin, employee
