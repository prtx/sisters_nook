from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID


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


@dataclass
class User:
    id: UUID
    first_name: str
    last_name: str
    email: str
    password_hash: str
    role: UserRole
    is_active: bool = True
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


@dataclass
class MenuItem:
    id: UUID
    name: str
    current_price: Decimal
    created_by_user_id: UUID
    updated_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None
    is_active: bool = True
    sort_order: Optional[int] = None


@dataclass
class MenuItemPriceHistory:
    id: UUID
    menu_item_id: UUID
    new_price: Decimal
    changed_by_user_id: UUID
    changed_at: datetime
    old_price: Optional[Decimal] = None


@dataclass
class Order:
    id: UUID
    order_number: str
    created_by_user_id: UUID
    subtotal: Decimal
    grand_total: Decimal
    created_at: datetime
    status: OrderStatus = OrderStatus.OPEN
    tax_total: Decimal = Decimal("0.00")
    discount_total: Decimal = Decimal("0.00")
    tip_total: Decimal = Decimal("0.00")
    notes: Optional[str] = None
    paid_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None


@dataclass
class OrderItem:
    id: UUID
    order_id: UUID
    menu_item_id: UUID
    item_name_snapshot: str
    unit_price_snapshot: Decimal
    quantity: int
    line_total: Decimal
    created_at: datetime


@dataclass
class Payment:
    id: UUID
    order_id: UUID
    logged_by_user_id: UUID
    payment_method: PaymentMethod
    amount: Decimal
    created_at: datetime
    status: PaymentStatus = PaymentStatus.PENDING
    provider_reference: Optional[str] = None
    paid_at: Optional[datetime] = None


@dataclass
class Refund:
    id: UUID
    payment_id: UUID
    amount: Decimal
    refunded_by_user_id: UUID
    created_at: datetime
    reason: Optional[str] = None
