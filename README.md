# Sisters Nook CMS

This repository implements the Sisters Nook cafe CMS described in [`requirements.md`](requirements.md). SQLAlchemy models cover every table (`users`, `menu_items`, `menu_item_price_history`, `orders`, `order_items`, `payments`, `refunds`) while the services enforce the RBAC/business rules (no hard deletes, price history snapshots, order totals, role boundaries, etc.).

## Architecture Overview

- **SQLAlchemy schema**: [`sisters_nook/schema.py`](sisters_nook/schema.py) defines `Base` models plus enums (statuses, payment methods, roles). Relationships make it easy to track price history and order snapshots.
- **Database helper**: [`sisters_nook/db.py`](sisters_nook/db.py) exposes `engine`, `SessionLocal`, `reset_database`, and a `get_session` context manager for transactional work on `sqlite:///sisters_nook.db`.
- **Service layer**: [`sisters_nook/services.py`](sisters_nook/services.py) rewrites the user, menu, order, payment, and refund flows on top of SQLAlchemy. Each method checks permissions, enforces rules like `PRICE-*`, `ORDER-*`, `PAY-*`, `REFUND-*`, and manipulates history/status fields.
- **CLI helper**: [`sisters_nook/cli.py`](sisters_nook/cli.py) wraps the services to seed data, reset the database, create orders, log payments, and issue refunds from the command line.

## Getting Started

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Reset the SQLite file:
   ```bash
   python -m sisters_nook.cli reset-db
   ```
3. Seed baseline users and menu items:
   ```bash
   python -m sisters_nook.cli seed
   ```
4. Use the CLI to exercise requirements:
   - Create an order:
     ```bash
     python -m sisters_nook.cli create-order --actor-email employee@sisters.local --items Latte:2 Mocha:1
     ```
   - Log payment (ensure `order-number` matches the CLI output):
     ```bash
     python -m sisters_nook.cli log-payment --actor-email employee@sisters.local --order-number SNO-XXXX --amount 15.75 --method cash
     ```
   - Create a refund as admin:
     ```bash
     python -m sisters_nook.cli create-refund --actor-email admin@sisters.local --payment-id <PAYMENT_ID> --amount 5.00 --reason "Customer cold"
     ```

   The CLI uses the SQLAlchemy services, so all business rules still apply (role checks, price history, snapshotting, etc.).

## Flask UI

1. Reset and seed the database (creates users and sample menu):
   ```bash
   python -m sisters_nook.cli reset-db
   python -m sisters_nook.cli seed
   ```
2. Run the app:
   ```bash
   export FLASK_APP=sisters_nook.app
   flask run
   ```
3. Sign in at `/login`:
   - **Admin:** `admin@sisters.local` / `changeme`
   - **Employee:** `employee@sisters.local` / `changeme`

The UI includes role-specific dashboards, order creation/payment, menu management (admin), user management (admin), refunds (admin), and an audit log. See [`flask.md`](flask.md) for the full route list.

## Tests

Run the full suite:

```bash
PYTHONPATH=. pytest
```

## References

- Functional requirements: [`requirements.md`](requirements.md)
