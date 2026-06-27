from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, flash, redirect, render_template, request, url_for

from sisters_nook.db import get_session
from sisters_nook.schema import MenuItem, MenuItemPriceHistory, User, UserRole
from sisters_nook.services import MenuService
from sisters_nook.web.auth_utils import admin_required, get_current_user, login_required

menu_bp = Blueprint("menu", __name__)


@menu_bp.route("/menu")
@login_required
def list_menu():
    active_only = request.args.get("active_only") in {"1", "true", "yes"}
    with get_session() as db_session:
        user = get_current_user(db_session)
        menu_service = MenuService(db_session)
        is_admin = user.role == UserRole.ADMIN
        if is_admin:
            items = menu_service.list_active() if active_only else menu_service.list_all()
        else:
            items = menu_service.list_active()
            active_only = True
    return render_template("menu/list.html", menu_items=items, is_admin=is_admin, active_only=active_only)


@menu_bp.route("/menu/new", methods=["GET", "POST"])
@admin_required
def create_menu():
    if request.method == "POST":
        with get_session() as db_session:
            user = get_current_user(db_session)
            menu_service = MenuService(db_session)
            try:
                price = Decimal(request.form.get("price", "0"))
                sort_order = request.form.get("sort_order")
                item = menu_service.create_menu_item(
                    user,
                    request.form.get("name", "").strip(),
                    price,
                    request.form.get("description") or None,
                    int(sort_order) if sort_order else None,
                )
                flash(f"Created {item.name}.", "success")
                return redirect(url_for("menu.list_menu"))
            except Exception as exc:
                flash(str(exc), "danger")
    return render_template("menu/create.html")


@menu_bp.route("/menu/<item_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_menu(item_id: str):
    with get_session() as db_session:
        user = get_current_user(db_session)
        menu_service = MenuService(db_session)
        item = db_session.get(MenuItem, item_id)
        if item is None:
            flash("Menu item not found.", "danger")
            return redirect(url_for("menu.list_menu"))
        if request.method == "POST":
            try:
                menu_service.update_menu_item(
                    user,
                    item_id,
                    name=request.form.get("name") or None,
                    description=request.form.get("description"),
                    sort_order=int(request.form["sort_order"]) if request.form.get("sort_order") else None,
                )
                new_price = request.form.get("new_price")
                if new_price:
                    menu_service.change_price(user, item_id, Decimal(new_price))
                flash("Menu item updated.", "success")
                return redirect(url_for("menu.list_menu"))
            except Exception as exc:
                flash(str(exc), "danger")
        db_session.expire(item)
        item = db_session.get(MenuItem, item_id)
    return render_template("menu/edit.html", item=item)


@menu_bp.route("/menu/<item_id>/price-history")
@admin_required
def price_history(item_id: str):
    with get_session() as db_session:
        item = db_session.get(MenuItem, item_id)
        if item is None:
            flash("Menu item not found.", "danger")
            return redirect(url_for("menu.list_menu"))
        history = (
            db_session.query(MenuItemPriceHistory)
            .filter_by(menu_item_id=item_id)
            .order_by(MenuItemPriceHistory.changed_at.desc())
            .all()
        )
        user_emails = {}
        for record in history:
            if record.changed_by_user_id not in user_emails:
                u = db_session.get(User, record.changed_by_user_id)
                user_emails[record.changed_by_user_id] = u.email if u else "unknown"
    return render_template("menu/price_history.html", item=item, history=history, user_emails=user_emails)


@menu_bp.route("/menu/<item_id>/deactivate", methods=["POST"])
@admin_required
def deactivate(item_id: str):
    with get_session() as db_session:
        user = get_current_user(db_session)
        MenuService(db_session).deactivate_menu_item(user, item_id)
        flash("Menu item deactivated.", "success")
    return redirect(url_for("menu.list_menu"))


@menu_bp.route("/menu/<item_id>/reactivate", methods=["POST"])
@admin_required
def reactivate(item_id: str):
    with get_session() as db_session:
        user = get_current_user(db_session)
        MenuService(db_session).reactivate_menu_item(user, item_id)
        flash("Menu item reactivated.", "success")
    return redirect(url_for("menu.list_menu"))
