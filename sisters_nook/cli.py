from __future__ import annotations

import argparse
import csv
from decimal import Decimal
from pathlib import Path
from typing import List

from .db import get_session, reset_database
from .schema import MenuItem, Order, PaymentMethod, User, UserRole
from .services import (
    MenuService,
    OrderLineRequest,
    OrderService,
    PaymentService,
    RefundService,
    UserService,
)


def parse_items(raw_items: List[str]) -> List[tuple[str, int]]:
    parsed: List[tuple[str, int]] = []
    for raw in raw_items:
        if ":" not in raw:
            raise ValueError("Items must include quantity, e.g. Latte:2")
        name, qty = raw.split(":", 1)
        parsed.append((name.strip(), int(qty)))
    return parsed


from sisters_nook.web.auth_utils import hash_password


DEFAULT_PASSWORD = "changeme"
SEED_MENU_FILE = Path(__file__).resolve().parent.parent / "seed_menu.csv"


def load_seed_menu_rows(csv_path: Path) -> list[tuple[str, str | None, Decimal]]:
    if not csv_path.exists():
        raise FileNotFoundError(f"Seed file not found: {csv_path}")
    rows: list[tuple[str, str | None, Decimal]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            name = (row.get("Item") or "").strip()
            description = (row.get("Description") or "").strip() or None
            price_raw = (row.get("Price (INR)") or "").strip()
            if not name:
                continue
            if not price_raw:
                raise ValueError(f"Missing price for item: {name}")
            rows.append((name, description, Decimal(price_raw)))
    if not rows:
        raise ValueError(f"No menu rows found in {csv_path}")
    return rows


def seed_users_and_menu(session):
    menu_rows = load_seed_menu_rows(SEED_MENU_FILE)
    admin = session.query(User).filter_by(email="admin@sisters.local").one_or_none()
    employee = session.query(User).filter_by(email="employee@sisters.local").one_or_none()
    if admin is None:
        admin = User(
            first_name="Admin",
            last_name="User",
            email="admin@sisters.local",
            password_hash=hash_password(DEFAULT_PASSWORD),
            role=UserRole.ADMIN,
        )
        session.add(admin)
    if employee is None:
        employee = User(
            first_name="Employee",
            last_name="User",
            email="employee@sisters.local",
            password_hash=hash_password(DEFAULT_PASSWORD),
            role=UserRole.EMPLOYEE,
        )
        session.add(employee)
    session.flush()
    menu_service = MenuService(session)
    if not menu_service.list_active():
        for idx, (name, description, price) in enumerate(menu_rows, start=1):
            menu_service.create_menu_item(admin, name, price, description, sort_order=idx)
        session.flush()
    return admin, employee


def seed_data():
    reset_database()
    with get_session() as session:
        seed_users_and_menu(session)
        menu_count = session.query(MenuItem).count()
        print(f"Seeded admin, employee, and {menu_count} menu items from {SEED_MENU_FILE.name}.")
        print(f"  admin@sisters.local / {DEFAULT_PASSWORD}")
        print(f"  employee@sisters.local / {DEFAULT_PASSWORD}")


def mock_seed_data(args: argparse.Namespace):
    from .mock_seed import ensure_demo_users, populate_mock_sales

    if args.reset:
        reset_database()
    with get_session() as session:
        admin, employee = ensure_demo_users(session, seed_users_and_menu)
        stats = populate_mock_sales(
            session,
            admin,
            employee,
            days=args.days,
            seed=args.seed,
        )
    print("Mock sales data seeded for Analysis dashboard demo.")
    print(f"  Paid orders: {stats['paid_orders']}")
    print(f"  Open orders: {stats['open_orders']}")
    print(f"  Cancelled orders: {stats['cancelled_orders']}")
    print(f"  Refunds: {stats['refunds']}")
    print(f"  Price changes: {stats['price_changes']}")
    print(f"  Span: last {args.days} days (including busy hours today)")
    if not args.reset:
        print("  Tip: use mock-seed --reset for a clean demo database.")


def clean(args: argparse.Namespace):
    reset_database()
    print("Clean SQLite database and recreated schema.")


def create_order(args: argparse.Namespace):
    with get_session() as session:
        user_service = UserService(session)
        order_service = OrderService(session)
        menu_service = MenuService(session)
        actor = user_service.find_by_email(args.actor_email)
        if actor is None:
            raise ValueError("Actor not found.")
        items = parse_items(args.items)
        menu_lookup = {item.name: item for item in menu_service.list_all()}
        order_items = [
            OrderLineRequest(menu_item_id=menu_lookup[name].id, quantity=qty)
            for name, qty in items
        ]
        order = order_service.create_order(actor, order_items)
        print(f"Created order {order.order_number} for {actor.email}")


def log_payment(args: argparse.Namespace):
    with get_session() as session:
        user_service = UserService(session)
        order_service = OrderService(session)
        payment_service = PaymentService(session)
        actor = user_service.find_by_email(args.actor_email)
        if actor is None:
            raise ValueError("Actor not found.")
        order = session.query(Order).filter_by(order_number=args.order_number).one_or_none()
        if order is None:
            raise ValueError("Order not found.")
        method = PaymentMethod[args.method.upper()]
        note = args.note or None
        payment = payment_service.log_payment(actor, order.id, Decimal(args.amount), method, note=note)
        print(f"Logged payment {payment.id} for order {order.order_number}")


def create_refund(args: argparse.Namespace):
    with get_session() as session:
        user_service = UserService(session)
        refund_service = RefundService(session)
        actor = user_service.find_by_email(args.actor_email)
        if actor is None:
            raise ValueError("Actor not found.")
        refund = refund_service.create_refund(actor, args.payment_id, Decimal(args.amount), args.reason)
        print(f"Created refund {refund.id} for payment {refund.payment_id}")


def main():
    parser = argparse.ArgumentParser("Sisters Nook CLI")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("seed", help="Seed the database with default user accounts and menu.")
    subparsers.add_parser("reset-db", help="Drop and recreate the SQLite schema.")
    mock_parser = subparsers.add_parser(
        "mock-seed",
        help="Populate mock sales, payments, refunds, and price changes for Analysis demos.",
    )
    mock_parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset the database and seed users/menu before generating mock sales.",
    )
    mock_parser.add_argument("--days", type=int, default=10, help="Number of days of mock history.")
    mock_parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducible mock data.")

    order_parser = subparsers.add_parser("create-order", help="Create an order for actor.")
    order_parser.add_argument("--actor-email", required=True)
    order_parser.add_argument("--items", required=True, nargs="+", help="Format: ItemName:Qty")

    payment_parser = subparsers.add_parser("log-payment", help="Log payment for an order.")
    payment_parser.add_argument("--actor-email", required=True)
    payment_parser.add_argument("--order-number", required=True)
    payment_parser.add_argument("--amount", required=True)
    payment_parser.add_argument("--method", choices=[m.name.lower() for m in PaymentMethod], required=True)
    payment_parser.add_argument("--note", default=None)

    refund_parser = subparsers.add_parser("create-refund", help="Create refund for payment.")
    refund_parser.add_argument("--actor-email", required=True)
    refund_parser.add_argument("--payment-id", required=True)
    refund_parser.add_argument("--amount", required=True)
    refund_parser.add_argument("--reason", required=True)

    args = parser.parse_args()
    if args.command == "seed":
        seed_data()
    elif args.command == "reset-db":
        clean(args)
    elif args.command == "create-order":
        create_order(args)
    elif args.command == "log-payment":
        log_payment(args)
    elif args.command == "create-refund":
        create_refund(args)
    elif args.command == "mock-seed":
        mock_seed_data(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
