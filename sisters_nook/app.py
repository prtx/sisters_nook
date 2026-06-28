from __future__ import annotations

import os

from flask import Flask, session

from sisters_nook.db import get_session
from sisters_nook.rest import api
from sisters_nook.routes.analysis import analysis_bp
from sisters_nook.routes.audit import audit_bp
from sisters_nook.routes.auth import auth_bp
from sisters_nook.routes.dashboard import dashboard_bp
from sisters_nook.routes.menu import menu_bp
from sisters_nook.routes.orders import orders_bp
from sisters_nook.routes.payments import payments_bp
from sisters_nook.routes.refunds import refunds_bp
from sisters_nook.routes.users import users_bp
from sisters_nook.schema import UserRole
from sisters_nook.schema import PAYMENT_METHOD_LABELS
from sisters_nook.web.auth_utils import get_current_user


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

    app.register_blueprint(api)
    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(menu_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(refunds_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(audit_bp)

    @app.context_processor
    def inject_user():
        user_id = session.get("user_id")
        if not user_id:
            return {"current_user": None, "is_admin": False, "payment_method_labels": PAYMENT_METHOD_LABELS}
        with get_session() as db_session:
            user = get_current_user(db_session)
            if user is None:
                return {"current_user": None, "is_admin": False, "payment_method_labels": PAYMENT_METHOD_LABELS}
            return {"current_user": user, "is_admin": user.role == UserRole.ADMIN, "payment_method_labels": PAYMENT_METHOD_LABELS}

    return app


app = create_app()
