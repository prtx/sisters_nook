from __future__ import annotations

from decimal import Decimal
from functools import wraps

from flask import Blueprint, jsonify, request

from .db import get_session
from .schema import (
    Order,
    PaymentMethod,
    PaymentStatus,
    User,
    UserRole,
)
from .services import (
    MenuService,
    OrderLineRequest,
    OrderService,
    PaymentService,
    RefundService,
    UserService,
)

api = Blueprint("api", __name__, url_prefix="/api")


@api.errorhandler(PermissionError)
def handle_permission_error(error):
    return jsonify({"error": str(error)}), 403


@api.errorhandler(ValueError)
def handle_value_error(error):
    return jsonify({"error": str(error)}), 400


def get_role() -> str | None:
    return request.headers.get("X-User-Role")


def get_actor(session) -> User | None:
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        return None

    return session.get(User, user_id)


def require_roles(*roles: UserRole):
    allowed_roles = {role.value for role in roles}

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if get_role() not in allowed_roles:
                return jsonify({"error": "insufficient role"}), 403

            return func(*args, **kwargs)

        return wrapper

    return decorator


@api.route("/menu", methods=["GET"])
@require_roles(UserRole.ADMIN, UserRole.EMPLOYEE)
def list_menu():
    with get_session() as session:
        service = MenuService(session)
        items = service.list_all()

        return jsonify(
            [
                {
                    "id": item.id,
                    "name": item.name,
                    "price": str(item.current_price),
                    "active": item.is_active,
                }
                for item in items
            ]
        )


@api.route("/menu", methods=["POST"])
@require_roles(UserRole.ADMIN)
def create_menu():
    payload = request.get_json() or {}

    with get_session() as session:
        actor = get_actor(session)
        if actor is None:
            return jsonify({"error": "actor header missing"}), 400

        service = MenuService(session)
        item = service.create_menu_item(
            actor,
            payload["name"],
            Decimal(payload["price"]),
            payload.get("description"),
            payload.get("sort_order"),
        )

        return jsonify({"id": item.id}), 201


@api.route("/menu/<item_id>", methods=["PUT"])
@require_roles(UserRole.ADMIN)
def update_menu(item_id):
    payload = request.get_json() or {}

    with get_session() as session:
        actor = get_actor(session)
        if actor is None:
            return jsonify({"error": "actor header missing"}), 400

        service = MenuService(session)
        item = service.update_menu_item(
            actor,
            item_id,
            name=payload.get("name"),
            description=payload.get("description"),
            sort_order=payload.get("sort_order"),
        )

        if "price" in payload:
            service.change_price(actor, item_id, Decimal(payload["price"]))

        return jsonify({"id": item.id})


@api.route("/menu/<item_id>", methods=["DELETE"])
@require_roles(UserRole.ADMIN)
def deactivate_menu(item_id):
    with get_session() as session:
        actor = get_actor(session)
        if actor is None:
            return jsonify({"error": "actor header missing"}), 400

        service = MenuService(session)
        service.deactivate_menu_item(actor, item_id)

        return jsonify({"id": item_id})


@api.route("/users", methods=["GET"])
@require_roles(UserRole.ADMIN)
def list_users():
    with get_session() as session:
        users = session.query(User).all()

        return jsonify(
            [
                {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role.value,
                    "active": user.is_active,
                }
                for user in users
            ]
        )


@api.route("/users", methods=["POST"])
@require_roles(UserRole.ADMIN)
def create_user():
    payload = request.get_json() or {}

    with get_session() as session:
        actor = get_actor(session)
        if actor is None:
            return jsonify({"error": "actor header missing"}), 400

        service = UserService(session)
        user = service.create_user(
            actor,
            payload["first_name"],
            payload["last_name"],
            payload["email"],
            payload["password_hash"],
            UserRole(payload["role"]),
        )

        return jsonify({"id": user.id}), 201


@api.route("/users/<user_id>", methods=["PUT"])
@require_roles(UserRole.ADMIN)
def update_user(user_id):
    payload = request.get_json() or {}

    with get_session() as session:
        actor = get_actor(session)
        if actor is None:
            return jsonify({"error": "actor header missing"}), 400

        service = UserService(session)
        user = service.update_user(
            actor,
            user_id,
            first_name=payload.get("first_name"),
            last_name=payload.get("last_name"),
            email=payload.get("email"),
            role=UserRole(payload["role"]) if payload.get("role") else None,
        )

        return jsonify({"id": user.id})


@api.route("/users/<user_id>/deactivate", methods=["POST"])
@require_roles(UserRole.ADMIN)
def deactivate_user(user_id):
    with get_session() as session:
        actor = get_actor(session)
        if actor is None:
            return jsonify({"error": "actor header missing"}), 400

        service = UserService(session)
        service.deactivate_user(actor, user_id)

        return jsonify({"id": user_id})


@api.route("/users/<user_id>/reactivate", methods=["POST"])
@require_roles(UserRole.ADMIN)
def reactivate_user(user_id):
    with get_session() as session:
        actor = get_actor(session)
        if actor is None:
            return jsonify({"error": "actor header missing"}), 400

        service = UserService(session)
        service.reactivate_user(actor, user_id)

        return jsonify({"id": user_id})



@api.route("/users/<user_id>/record-login", methods=["POST"])
@require_roles(UserRole.ADMIN, UserRole.EMPLOYEE)
def record_login(user_id):
    with get_session() as session:
        actor = get_actor(session)
        if actor is None:
            return jsonify({"error": "actor header missing"}), 400

        service = UserService(session)
        service.record_login(user_id)

        return jsonify({"id": user_id})


@api.route("/orders", methods=["GET"])
@require_roles(UserRole.ADMIN, UserRole.EMPLOYEE)
def list_orders():
    with get_session() as session:
        orders = session.query(Order).all()

        return jsonify(
            [
                {
                    "id": order.id,
                    "status": order.status.value,
                    "total": str(order.grand_total),
                }
                for order in orders
            ]
        )


@api.route("/orders", methods=["POST"])
@require_roles(UserRole.ADMIN, UserRole.EMPLOYEE)
def create_order():
    payload = request.get_json() or {}
    items = [
        OrderLineRequest(item["menu_item_id"], item["quantity"])
        for item in payload["items"]
    ]

    with get_session() as session:
        actor = get_actor(session)
        if actor is None:
            return jsonify({"error": "actor header missing"}), 400

        service = OrderService(session)
        order = service.create_order(actor, items)

        return jsonify({"id": order.id}), 201


@api.route("/orders/<order_id>/cancel", methods=["POST"])
@require_roles(UserRole.ADMIN)
def cancel_order(order_id):
    with get_session() as session:
        actor = get_actor(session)
        if actor is None:
            return jsonify({"error": "actor header missing"}), 400

        service = OrderService(session)
        service.cancel_order(actor, order_id)

        return jsonify({"id": order_id})


@api.route("/payments", methods=["POST"])
@require_roles(UserRole.ADMIN, UserRole.EMPLOYEE)
def log_payment():
    payload = request.get_json() or {}

    with get_session() as session:
        actor = get_actor(session)
        if actor is None:
            return jsonify({"error": "actor header missing"}), 400

        service = PaymentService(session)
        payment = service.log_payment(
            actor,
            payload["order_id"],
            Decimal(payload["amount"]),
            PaymentMethod(payload["method"]),
            note=payload.get("note"),
            status=PaymentStatus(payload.get("status", PaymentStatus.PAID.value)),
        )

        return jsonify({"id": payment.id}), 201


@api.route("/refunds", methods=["POST"])
@require_roles(UserRole.ADMIN, UserRole.EMPLOYEE)
def refund_payment():
    payload = request.get_json() or {}

    with get_session() as session:
        actor = get_actor(session)
        if actor is None:
            return jsonify({"error": "actor header missing"}), 400

        service = RefundService(session)
        refund = service.create_refund(
            actor,
            payload["payment_id"],
            Decimal(payload["amount"]),
            payload["reason"],
        )

        return jsonify({"id": refund.id}), 201
