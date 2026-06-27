from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from .schema import (
    MenuItem,
    MenuItemPriceHistory,
    Order,
    OrderItem,
    Payment,
    PaymentMethod,
    PaymentStatus,
    Refund,
    OrderStatus,
    User,
    UserRole,
)

TWO_PLACES = Decimal("0.01")


def _now() -> datetime:
    return datetime.utcnow()


def _normalize(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _order_number() -> str:
    return f"SNO-{uuid4().hex[:8].upper()}"


def _ensure_admin(actor: User) -> None:
    if actor.role != UserRole.ADMIN:
        raise PermissionError("Only admins may perform this action.")


def _ensure_active(actor: User) -> None:
    if not actor.is_active:
        raise PermissionError("Inactive users cannot perform this action.")


@dataclass
class OrderLineRequest:
    menu_item_id: str
    quantity: int


class BaseService:
    def __init__(self, session: Session):
        self.session = session


class UserService(BaseService):
    def create_user(
        self,
        actor: User,
        first_name: str,
        last_name: str,
        email: str,
        password_hash: str,
        role: UserRole,
    ) -> User:
        _ensure_admin(actor)
        user = User(
            first_name=first_name,
            last_name=last_name,
            email=email,
            password_hash=password_hash,
            role=role,
        )
        self.session.add(user)
        self.session.flush()
        return user

    def update_user(
        self,
        actor: User,
        user_id: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        role: Optional[UserRole] = None,
    ) -> User:
        _ensure_admin(actor)
        user = self.session.get(User, user_id)
        if user is None:
            raise ValueError("User not found.")
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        if email:
            user.email = email
        if role:
            user.role = role
        user.updated_at = _now()
        self.session.add(user)
        self.session.flush()
        return user

    def deactivate_user(self, actor: User, user_id: str) -> User:
        _ensure_admin(actor)
        user = self.session.get(User, user_id)
        if user is None:
            raise ValueError("User not found.")
        user.is_active = False
        user.updated_at = _now()
        self.session.add(user)
        self.session.flush()
        return user

    def reactivate_user(self, actor: User, user_id: str) -> User:
        _ensure_admin(actor)
        user = self.session.get(User, user_id)
        if user is None:
            raise ValueError("User not found.")
        user.is_active = True
        user.updated_at = _now()
        self.session.add(user)
        self.session.flush()
        return user

    def record_login(self, user_id: str) -> None:
        user = self.session.get(User, user_id)
        if user is None:
            raise ValueError("User not found.")
        user.last_login_at = _now()
        user.updated_at = _now()
        self.session.add(user)

    def find_by_email(self, email: str) -> Optional[User]:
        return self.session.query(User).filter_by(email=email).one_or_none()


class MenuService(BaseService):
    def create_menu_item(
        self,
        actor: User,
        name: str,
        price: Decimal,
        description: Optional[str] = None,
        sort_order: Optional[int] = None,
    ) -> MenuItem:
        _ensure_admin(actor)
        if price < Decimal("0.00"):
            raise ValueError("Price cannot be negative.")
        menu_item = MenuItem(
            name=name,
            description=description,
            current_price=_normalize(price),
            is_active=True,
            sort_order=sort_order,
            created_by_user_id=actor.id,
            updated_by_user_id=actor.id,
        )
        self.session.add(menu_item)
        self.session.flush()
        return menu_item

    def update_menu_item(
        self,
        actor: User,
        item_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        sort_order: Optional[int] = None,
    ) -> MenuItem:
        _ensure_admin(actor)
        item = self.session.get(MenuItem, item_id)
        if item is None:
            raise ValueError("Menu item not found.")
        if name:
            item.name = name
        if description is not None:
            item.description = description
        if sort_order is not None:
            item.sort_order = sort_order
        item.updated_by_user_id = actor.id
        item.updated_at = _now()
        self.session.add(item)
        self.session.flush()
        return item

    def change_price(self, actor: User, item_id: str, new_price: Decimal) -> MenuItem:
        _ensure_admin(actor)
        if new_price < Decimal("0.00"):
            raise ValueError("Price cannot be negative.")
        item = self.session.get(MenuItem, item_id)
        if item is None:
            raise ValueError("Menu item not found.")
        old_price = item.current_price
        item.current_price = _normalize(new_price)
        item.updated_by_user_id = actor.id
        item.updated_at = _now()
        self.session.add(item)
        self.session.add(
            MenuItemPriceHistory(
                menu_item_id=item.id,
                old_price=old_price,
                new_price=item.current_price,
                changed_by_user_id=actor.id,
                changed_at=_now(),
            )
        )
        self.session.flush()
        return item

    def deactivate_menu_item(self, actor: User, item_id: str) -> MenuItem:
        _ensure_admin(actor)
        item = self.session.get(MenuItem, item_id)
        if item is None:
            raise ValueError("Menu item not found.")
        item.is_active = False
        item.updated_by_user_id = actor.id
        item.updated_at = _now()
        self.session.add(item)
        self.session.flush()
        return item

    def reactivate_menu_item(self, actor: User, item_id: str) -> MenuItem:
        _ensure_admin(actor)
        item = self.session.get(MenuItem, item_id)
        if item is None:
            raise ValueError("Menu item not found.")
        item.is_active = True
        item.updated_by_user_id = actor.id
        item.updated_at = _now()
        self.session.add(item)
        self.session.flush()
        return item

    def list_active(self) -> list[MenuItem]:
        return self.session.query(MenuItem).filter_by(is_active=True).order_by(MenuItem.sort_order).all()

    def list_all(self) -> list[MenuItem]:
        return self.session.query(MenuItem).order_by(MenuItem.sort_order).all()

    def get_by_name(self, name: str) -> MenuItem:
        return self.session.query(MenuItem).filter_by(name=name).one()


class OrderService(BaseService):
    def create_order(
        self,
        actor: User,
        line_items: Iterable[OrderLineRequest],
        order_name: Optional[str] = None,
        tax_total: Decimal = Decimal("0.00"),
        discount_total: Decimal = Decimal("0.00"),
        tip_total: Decimal = Decimal("0.00"),
        notes: Optional[str] = None,
    ) -> Order:
        _ensure_active(actor)
        requested = list(line_items)
        if not requested:
            raise ValueError("Orders must contain at least one item.")
        menu_item_ids = [line.menu_item_id for line in requested]
        menu_items = (
            self.session.query(MenuItem)
            .filter(MenuItem.id.in_(menu_item_ids))
            .all()
        )
        menu_index = {item.id: item for item in menu_items}
        subtotal = Decimal("0.00")
        order_items: List[OrderItem] = []
        now = _now()
        for line in requested:
            menu_item = menu_index.get(line.menu_item_id)
            if menu_item is None:
                raise ValueError("Menu item not found.")
            if not menu_item.is_active:
                raise ValueError("Inactive items cannot be added to orders.")
            if line.quantity <= 0:
                raise ValueError("Quantity must be positive.")
            unit_price = _normalize(menu_item.current_price)
            line_total = _normalize(unit_price * Decimal(line.quantity))
            subtotal += line_total
            order_items.append(
                OrderItem(
                    menu_item_id=menu_item.id,
                    item_name_snapshot=menu_item.name,
                    unit_price_snapshot=unit_price,
                    quantity=line.quantity,
                    line_total=line_total,
                    created_at=now,
                )
            )
        if any(val < Decimal("0.00") for val in (tax_total, discount_total, tip_total)):
            raise ValueError("Taxes, discounts, and tips must be non-negative.")
        tax_total = _normalize(tax_total)
        discount_total = _normalize(discount_total)
        tip_total = _normalize(tip_total)
        if discount_total > subtotal:
            raise ValueError("Discount cannot exceed the subtotal.")
        grand_total = _normalize(subtotal + tax_total + tip_total - discount_total)
        order = Order(
            order_number=_order_number(),
            order_name=order_name.strip() if order_name else None,
            created_by_user_id=actor.id,
            subtotal=subtotal,
            tax_total=tax_total,
            discount_total=discount_total,
            tip_total=tip_total,
            grand_total=grand_total,
            notes=notes,
            created_at=now,
        )
        self.session.add(order)
        self.session.flush()
        for item in order_items:
            item.order_id = order.id
            self.session.add(item)
        self.session.flush()
        return order

    def cancel_order(self, actor: User, order_id: str) -> Order:
        order = self.session.get(Order, order_id)
        if order is None:
            raise ValueError("Order not found.")
        _ensure_admin(actor)
        now = _now()
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = now
        self.session.add(order)
        self.session.flush()
        return order

    def find_order(self, order_id: str) -> Optional[Order]:
        return self.session.get(Order, order_id)


class PaymentService(BaseService):
    def log_payment(
        self,
        actor: User,
        order_id: str,
        amount: Decimal,
        method: PaymentMethod,
        provider_reference: Optional[str] = None,
        note: Optional[str] = None,
        status: PaymentStatus = PaymentStatus.PAID,
    ) -> Payment:
        _ensure_active(actor)
        order = self.session.get(Order, order_id)
        if order is None:
            raise ValueError("Order not found.")
        amount = _normalize(amount)
        if amount <= Decimal("0.00"):
            raise ValueError("Payment amount must be positive.")
        if amount > order.grand_total:
            raise ValueError("Payments cannot exceed the order grand total.")
        payment = Payment(
            order_id=order.id,
            logged_by_user_id=actor.id,
            payment_method=method,
            amount=amount,
            provider_reference=provider_reference,
            note=note,
            status=status,
            paid_at=_now() if status == PaymentStatus.PAID else None,
            created_at=_now(),
        )
        self.session.add(payment)
        if status == PaymentStatus.PAID:
            order.status = OrderStatus.PAID
            order.paid_at = _now()
            self.session.add(order)
        self.session.flush()
        return payment


class RefundService(BaseService):
    def create_refund(self, actor: User, payment_id: str, amount: Decimal, reason: str) -> Refund:
        _ensure_active(actor)
        payment = self.session.get(Payment, payment_id)
        if payment is None:
            raise ValueError("Payment not found.")
        amount = _normalize(amount)
        if amount <= Decimal("0.00") or amount > payment.amount:
            raise ValueError("Refund amount must be positive and not greater than payment.")
        if not reason:
            raise ValueError("Refund reason is required.")
        refund = Refund(
            payment_id=payment.id,
            amount=amount,
            refunded_by_user_id=actor.id,
            reason=reason,
        )
        payment.status = PaymentStatus.REFUNDED
        payment.paid_at = _now()
        self.session.add(payment)
        self.session.add(refund)
        order = payment.order
        if order:
            order.status = OrderStatus.REFUNDED
            self.session.add(order)
        self.session.flush()
        return refund
