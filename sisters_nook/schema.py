from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid4())


def current_time() -> datetime:
    return datetime.utcnow()


class UserRole(Enum):
    ADMIN = "admin"
    EMPLOYEE = "employee"


class OrderStatus(Enum):
    OPEN = "open"
    PAID = "paid"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"


class PaymentMethod(Enum):
    CASH = "cash"
    CARD = "card"
    ONLINE = "online"
    OTHER = "other"


class PaymentStatus(Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(SQLEnum(UserRole, name="user_role"), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=current_time, nullable=False)
    updated_at = Column(DateTime, default=current_time, onupdate=current_time, nullable=False)

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role.value})>"


class MenuItem(Base):
    __tablename__ = "menu_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)
    current_price = Column(Numeric(10, 2), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, nullable=True)
    created_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    updated_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=current_time, nullable=False)
    updated_at = Column(DateTime, default=current_time, onupdate=current_time, nullable=False)

    price_history = relationship("MenuItemPriceHistory", back_populates="menu_item", cascade="all, delete-orphan")
    order_items = relationship("OrderItem", back_populates="menu_item")

    def __repr__(self) -> str:
        return f"<MenuItem {self.name} (${self.current_price})>"


class MenuItemPriceHistory(Base):
    __tablename__ = "menu_item_price_history"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    menu_item_id = Column(String(36), ForeignKey("menu_items.id"), nullable=False)
    old_price = Column(Numeric(10, 2), nullable=True)
    new_price = Column(Numeric(10, 2), nullable=False)
    changed_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime, default=current_time, nullable=False)

    menu_item = relationship("MenuItem", back_populates="price_history")

    def __repr__(self) -> str:
        return f"<MenuItemPriceHistory {self.menu_item_id} {self.old_price}->{self.new_price}>"


class Order(Base):
    __tablename__ = "orders"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_number = Column(String, unique=True, nullable=False, index=True)
    created_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    status = Column(SQLEnum(OrderStatus, name="order_status"), default=OrderStatus.OPEN, nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)
    tax_total = Column(Numeric(10, 2), nullable=False)
    discount_total = Column(Numeric(10, 2), nullable=False)
    tip_total = Column(Numeric(10, 2), nullable=False)
    grand_total = Column(Numeric(10, 2), nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=current_time, nullable=False)
    paid_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    order_items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Order {self.order_number} ({self.status.value})>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False)
    menu_item_id = Column(String(36), ForeignKey("menu_items.id"), nullable=False)
    item_name_snapshot = Column(String, nullable=False)
    unit_price_snapshot = Column(Numeric(10, 2), nullable=False)
    quantity = Column(Integer, nullable=False)
    line_total = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime, default=current_time, nullable=False)

    order = relationship("Order", back_populates="order_items")
    menu_item = relationship("MenuItem", back_populates="order_items")

    def __repr__(self) -> str:
        return f"<OrderItem {self.item_name_snapshot} x{self.quantity}>"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    order_id = Column(String(36), ForeignKey("orders.id"), nullable=False)
    logged_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    payment_method = Column(SQLEnum(PaymentMethod, name="payment_method"), nullable=False)
    status = Column(SQLEnum(PaymentStatus, name="payment_status"), default=PaymentStatus.PAID, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    provider_reference = Column(String, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=current_time, nullable=False)

    refunds = relationship("Refund", back_populates="payment", cascade="all, delete-orphan")
    order = relationship("Order", back_populates="payments")

    def __repr__(self) -> str:
        return f"<Payment {self.id} ${self.amount}>"


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    payment_id = Column(String(36), ForeignKey("payments.id"), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    refunded_by_user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=current_time, nullable=False)

    payment = relationship("Payment", back_populates="refunds")

    def __repr__(self) -> str:
        return f"<Refund ${self.amount} for {self.payment_id}>"


