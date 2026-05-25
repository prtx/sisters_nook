from __future__ import annotations

from hashlib import sha256
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from sisters_nook.db import get_session, reset_database
from sisters_nook.rest import api
from sisters_nook.schema import Order, User, UserRole
from sisters_nook.services import MenuService, OrderLineRequest, OrderService, UserService

app = Flask(__name__)
app.secret_key = "change-me-in-production"
app.register_blueprint(api)


def current_user() -> str | None:
    return session.get("user_id")


def login_required(role: UserRole):
    def decorator(func):
        def wrapper(*args, **kwargs):
            user_id = current_user()
            if not user_id:
                flash("Login required", "warning")
                return redirect(url_for("login"))
            with get_session() as db_session:
                user = db_session.get(User, user_id)
                if user and user.role != role:
                    flash("Unauthorized", "danger")
                    return redirect(url_for("dashboard"))
            return func(*args, **kwargs)
        return wrapper
    return decorator


@app.route("/reset-db")
def reset():
    reset_database()
    flash("Database reset", "success")
    return redirect(url_for("dashboard"))


def hash_password(value: str) -> str:
    return sha256(value.encode()).hexdigest()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        with get_session() as db_session:
            user_service = UserService(db_session)
            user = user_service.find_by_email(email)
            if user and user.is_active and user.password_hash == hash_password(password):
                session["user_id"] = user.id
                session["user_role"] = user.role.value
                flash("Successfully signed in.", "success")
                return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "danger")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("user_role", None)
    flash("Logged out.", "info")
    return redirect(url_for("dashboard"))


@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/menu")
def menu():
    with get_session() as db_session:
        menu_service = MenuService(db_session)
        items = menu_service.list_all()
    return render_template("menu.html", menu_items=items)


def parse_order_items(raw_text: str, menu_lookup: dict[str, object]) -> list[OrderLineRequest]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Orders must contain at least one item.")
    parsed: list[OrderLineRequest] = []
    for raw in lines:
        if ":" not in raw:
            raise ValueError("Items must be in the format Name:Qty")
        name, qty = raw.split(":", 1)
        item_name = name.strip().lower()
        if not qty.strip().isdigit():
            raise ValueError("Quantities must be numbers.")
        item_qty = int(qty.strip())
        if item_qty <= 0:
            raise ValueError("Quantity must be positive.")
        menu_item = menu_lookup.get(item_name)
        if menu_item is None:
            raise ValueError(f"Unknown menu item: {name.strip()}")
        parsed.append(OrderLineRequest(menu_item_id=menu_item.id, quantity=item_qty))
    return parsed


@app.route("/orders", methods=["GET", "POST"])
def orders():
    user_id = session.get("user_id")
    if not user_id:
        flash("Sign in to manage orders.", "warning")
        return redirect(url_for("login"))

    with get_session() as db_session:
        current = db_session.get(User, user_id)
        if current is None or not current.is_active:
            flash("Account disabled.", "danger")
            return redirect(url_for("dashboard"))
        menu_items = MenuService(db_session).list_active()
        menu_lookup = {item.name.lower(): item for item in menu_items}
        order_service = OrderService(db_session)
        if request.method == "POST":
            raw_items = request.form.get("items", "")
            notes = request.form.get("notes")
            try:
                parsed = parse_order_items(raw_items, menu_lookup)
                order = order_service.create_order(current, parsed, notes=notes)
                flash(f"Order {order.order_number} created.", "success")
            except Exception as exc:
                flash(str(exc), "danger")
        orders = (
            db_session.query(Order)
            .order_by(Order.created_at.desc())
            .all()
        )
        is_admin = current.role == UserRole.ADMIN
    return render_template(
        "orders.html",
        menu_items=menu_items,
        orders=orders,
        current_user=current,
        is_admin=is_admin,
    )


@app.route("/orders/<order_id>/cancel", methods=["POST"])
def cancel_order(order_id: str):
    user_id = session.get("user_id")
    if not user_id:
        flash("Sign in to manage orders.", "warning")
        return redirect(url_for("login"))

    with get_session() as db_session:
        current = db_session.get(User, user_id)
        if current is None or not current.is_active:
            flash("Account disabled.", "danger")
            return redirect(url_for("dashboard"))
        order_service = OrderService(db_session)
        try:
            order_service.cancel_order(current, order_id)
            flash("Order cancelled.", "success")
        except Exception as exc:
            flash(str(exc), "danger")
    return redirect(url_for("orders"))


@app.route("/orders")
def orders():
    return render_template("placeholder.html", title="Orders", message="Order creation coming soon.")


@app.route("/payments")
def payments():
    return render_template("placeholder.html", title="Payments", message="Payment logging coming soon.")


@app.route("/refunds")
def refunds():
    return render_template("placeholder.html", title="Refunds", message="Refund workflow coming soon.")
