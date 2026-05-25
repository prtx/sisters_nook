from __future__ import annotations

import argparse
from decimal import Decimal
from typing import List

from .db import get_session, reset_database
from .schema import Order, PaymentMethod, User, UserRole
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


def seed_data():
    with get_session() as session:
        session.query(User).delete()
        session.commit()
    with get_session() as session:
        admin = User(
            first_name="Admin",
            last_name="User",
            email="admin@sisters.local",
            password_hash="secure-hash",
            role=UserRole.ADMIN,
        )
        employee = User(
            first_name="Employee",
            last_name="User",
            email="employee@sisters.local",
            password_hash="secure-hash",
            role=UserRole.EMPLOYEE,
        )
        session.add_all([admin, employee])
        session.flush()
        menu_service = MenuService(session)
        menu_service.create_menu_item(admin, "Latte", Decimal("4.50"), "Milk and espresso", sort_order=1)
        menu_service.create_menu_item(admin, "Mocha", Decimal("5.00"), "Chocolate espresso", sort_order=2)
        menu_service.create_menu_item(admin, "Croissant", Decimal("3.25"), "Butter flake", sort_order=3)
        print("Seeded admin, employee, and default menu items.")


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
        payment = payment_service.log_payment(actor, order.id, Decimal(args.amount), method)
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

    order_parser = subparsers.add_parser("create-order", help="Create an order for actor.")
    order_parser.add_argument("--actor-email", required=True)
    order_parser.add_argument("--items", required=True, nargs="+", help="Format: ItemName:Qty")

    payment_parser = subparsers.add_parser("log-payment", help="Log payment for an order.")
    payment_parser.add_argument("--actor-email", required=True)
    payment_parser.add_argument("--order-number", required=True)
    payment_parser.add_argument("--amount", required=True)
    payment_parser.add_argument("--method", choices=[m.name.lower() for m in PaymentMethod], required=True)

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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
