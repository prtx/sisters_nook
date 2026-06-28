from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.schema import OrderStatus, PaymentMethod, PaymentStatus, User, UserRole
from sisters_nook.services import MenuService, OrderLineRequest, OrderService, PaymentService, RefundService
from sisters_nook.web.analysis import get_analysis_dashboard_data, resolve_date_range


@pytest.fixture
def analysis_setup():
    reset_database()
    session = SessionLocal()
    admin = User(
        first_name="Admin",
        last_name="Analysis",
        email="admin@sisters.local",
        password_hash="hash",
        role=UserRole.ADMIN,
    )
    employee = User(
        first_name="Employee",
        last_name="Analysis",
        email="employee@sisters.local",
        password_hash="hash",
        role=UserRole.EMPLOYEE,
    )
    session.add_all([admin, employee])
    session.flush()

    menu_service = MenuService(session)
    order_service = OrderService(session)
    payment_service = PaymentService(session)
    refund_service = RefundService(session)

    latte = menu_service.create_menu_item(admin, "Latte", Decimal("4.50"), "Milk", sort_order=1)
    muffin = menu_service.create_menu_item(admin, "Muffin", Decimal("3.00"), "Blueberry", sort_order=2)

    order = order_service.create_order(
        employee,
        [OrderLineRequest(latte.id, 2), OrderLineRequest(muffin.id, 1)],
        tax_total=Decimal("0.50"),
        discount_total=Decimal("1.00"),
        tip_total=Decimal("2.00"),
    )
    now = datetime.utcnow()
    order.status = OrderStatus.PAID
    order.paid_at = now
    session.add(order)
    session.flush()

    payment = payment_service.log_payment(
        employee,
        order.id,
        order.grand_total,
        PaymentMethod.CASH,
        status=PaymentStatus.PAID,
    )
    payment.paid_at = now
    session.add(payment)
    session.commit()

    yield {
        "session": session,
        "admin": admin,
        "employee": employee,
        "order": order,
        "payment": payment,
    }
    session.close()


@pytest.fixture
def analysis_setup_with_refund(analysis_setup):
    session = analysis_setup["session"]
    admin = analysis_setup["admin"]
    payment = analysis_setup["payment"]
    refund_service = RefundService(session)
    refund = refund_service.create_refund(admin, payment.id, Decimal("2.00"), "Wrong item")
    refund.created_at = datetime.utcnow()
    session.add(refund)
    session.commit()
    return analysis_setup


def test_analysis_summary_totals(analysis_setup):
    session = analysis_setup["session"]
    admin = analysis_setup["admin"]
    start, end = resolve_date_range("today")
    data = get_analysis_dashboard_data(session, admin, start, end, is_admin=True)

    summary = {card["key"]: card["value"] for card in data["summary_cards"]}
    assert summary["gross_sales"] == "NRs 13.50"
    assert summary["net_sales"] == "NRs 13.50"
    assert summary["orders_paid"] == "1"
    assert summary["refunds"] == "NRs 0.00"


def test_analysis_refunds_reduce_net_sales(analysis_setup_with_refund):
    session = analysis_setup_with_refund["session"]
    admin = analysis_setup_with_refund["admin"]
    start, end = resolve_date_range("today")
    data = get_analysis_dashboard_data(session, admin, start, end, is_admin=True)
    summary = {card["key"]: card["value"] for card in data["summary_cards"]}
    assert summary["net_sales"] == "NRs 11.50"
    assert summary["refunds"] == "NRs 2.00"


def test_analysis_uses_order_item_snapshots(analysis_setup):
    session = analysis_setup["session"]
    admin = analysis_setup["admin"]
    start, end = resolve_date_range("today")
    data = get_analysis_dashboard_data(session, admin, start, end, is_admin=True)

    top_item = data["top_selling_items"][0]
    assert top_item["item"] == "Latte"
    assert top_item["quantity"] == 2
    assert top_item["revenue_display"] == "NRs 9.00"


def test_analysis_payment_method_filter(analysis_setup):
    session = analysis_setup["session"]
    admin = analysis_setup["admin"]
    start, end = resolve_date_range("today")
    data = get_analysis_dashboard_data(
        session,
        admin,
        start,
        end,
        payment_method="card",
        is_admin=True,
    )
    cash = next(row for row in data["payment_method_breakdown"] if row["method"] == "cash")
    assert cash["count"] == 0


def test_analysis_sales_charts_include_three_views(analysis_setup):
    session = analysis_setup["session"]
    admin = analysis_setup["admin"]
    start, end = resolve_date_range("this_month")
    data = get_analysis_dashboard_data(session, admin, start, end, date_range="this_month", is_admin=True)

    charts = data["sales_charts"]
    assert len(charts["hourly"]["labels"]) == 24
    assert charts["weekday"]["labels"] == ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    assert "daily" in charts["trend"]
    assert "weekly" in charts["trend"]
    assert "monthly" in charts["trend"]
    assert len(charts["trend"]["daily"]["labels"]) >= 1


def test_analysis_empty_range_does_not_crash(analysis_setup):
    session = analysis_setup["session"]
    admin = analysis_setup["admin"]
    start = datetime.utcnow() + timedelta(days=10)
    end = start + timedelta(days=1)
    data = get_analysis_dashboard_data(session, admin, start, end, is_admin=True)
    assert data["summary_cards"][0]["value"] == "NRs 0.00"
    assert data["sales_charts"]["hourly"]["salesAmounts"] == [0.0] * 24


def test_analysis_date_range_excludes_old_orders(analysis_setup):
    session = analysis_setup["session"]
    admin = analysis_setup["admin"]
    order = analysis_setup["order"]
    order.paid_at = datetime.utcnow() - timedelta(days=30)
    session.add(order)
    session.commit()

    start, end = resolve_date_range("today")
    data = get_analysis_dashboard_data(session, admin, start, end, is_admin=True)
    assert data["summary_cards"][0]["value"] == "NRs 0.00"
