import pytest

from sisters_nook.app import app
from sisters_nook.db import SessionLocal, reset_database
from sisters_nook.schema import Payment, PaymentMethod, PaymentStatus, User, UserRole
from sisters_nook.services import MenuService, OrderLineRequest, OrderService, PaymentService
from sisters_nook.web.auth_utils import hash_password
from decimal import Decimal


@pytest.fixture
def client():
    reset_database()
    session = SessionLocal()
    admin = User(
        first_name="Admin",
        last_name="UI",
        email="admin@sisters.local",
        password_hash=hash_password("changeme"),
        role=UserRole.ADMIN,
    )
    employee = User(
        first_name="Employee",
        last_name="UI",
        email="employee@sisters.local",
        password_hash=hash_password("changeme"),
        role=UserRole.EMPLOYEE,
    )
    session.add_all([admin, employee])
    session.flush()
    latte = MenuService(session).create_menu_item(admin, "Latte", Decimal("4.50"), "Milk", sort_order=1)
    order = OrderService(session).create_order(
        employee,
        [OrderLineRequest(menu_item_id=latte.id, quantity=1)],
        tax_total=Decimal("0.00"),
        discount_total=Decimal("0.00"),
        tip_total=Decimal("0.00"),
    )
    PaymentService(session).log_payment(
        employee,
        order.id,
        Decimal("4.50"),
        PaymentMethod.CARD,
        status=PaymentStatus.PAID,
    )
    session.commit()
    session.close()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_login_and_dashboard(client):
    resp = client.post("/login", data={"email": "admin@sisters.local", "password": "changeme"}, follow_redirects=True)
    assert resp.status_code == 200
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Dashboard" in resp.data
    assert b"Today sales" in resp.data


def test_employee_can_create_order(client):
    client.post("/login", data={"email": "employee@sisters.local", "password": "changeme"})
    menu_page = client.get("/menu")
    assert menu_page.status_code == 200
    resp = client.get("/orders/new")
    assert resp.status_code == 200
    assert b"Create Order" in resp.data
    assert b"Latte" in resp.data


def test_admin_menu_management(client):
    client.post("/login", data={"email": "admin@sisters.local", "password": "changeme"})
    resp = client.get("/menu/new")
    assert resp.status_code == 200
    resp = client.get("/users")
    assert resp.status_code == 200
    resp = client.get("/audit")
    assert resp.status_code == 200
    resp = client.get("/refunds")
    assert resp.status_code == 200


def test_employee_blocked_from_users(client):
    client.post("/login", data={"email": "employee@sisters.local", "password": "changeme"})
    resp = client.get("/users", follow_redirects=True)
    assert b"Admin access required" in resp.data


def test_employee_can_open_refund_form(client):
    client.post("/login", data={"email": "employee@sisters.local", "password": "changeme"})
    session = SessionLocal()
    payment = session.query(Payment).first()
    session.close()
    assert payment is not None
    resp = client.get(f"/payments/{payment.id}/refund")
    assert resp.status_code == 200
    assert b"Refund amount" in resp.data


def test_employee_can_create_refund(client):
    client.post("/login", data={"email": "employee@sisters.local", "password": "changeme"})
    session = SessionLocal()
    payment = session.query(Payment).first()
    session.close()
    assert payment is not None
    resp = client.post(
        f"/payments/{payment.id}/refund",
        data={"amount": "4.50", "reason": "Wrong item"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Refund created" in resp.data
    assert b"Admin access required" not in resp.data
