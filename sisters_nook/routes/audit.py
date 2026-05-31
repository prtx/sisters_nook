from __future__ import annotations

from flask import Blueprint, render_template

from sisters_nook.db import get_session
from sisters_nook.web import queries
from sisters_nook.web.auth_utils import admin_required

audit_bp = Blueprint("audit", __name__)


@audit_bp.route("/audit")
@admin_required
def list_audit():
    with get_session() as db_session:
        events = sorted(
            queries.audit_events(db_session),
            key=lambda event: event.timestamp,
            reverse=True,
        )
    return render_template("audit/list.html", events=events)
