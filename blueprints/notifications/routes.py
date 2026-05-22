"""In-App Notification Center — Aleefy Platform"""
from flask import render_template, request, redirect, url_for, session, jsonify
from . import notifications_bp
from blueprints.auth.routes import login_required
import models.database as db


@notifications_bp.route("/")
@login_required
def index():
    user = session["user"]
    notifs = db.get_user_notifications(user["id"], limit=50)
    return render_template(
        "notifications/index.html",
        active="notifications",
        notifications=notifs,
    )


@notifications_bp.route("/mark-read/<int:notif_id>", methods=["POST"])
@login_required
def mark_read(notif_id):
    db.mark_notifications_read(session["user"]["id"], notif_id)
    return jsonify({"ok": True})


@notifications_bp.route("/mark-all-read", methods=["POST"])
@login_required
def mark_all_read():
    db.mark_notifications_read(session["user"]["id"])
    return redirect(request.referrer or url_for("notifications.index"))


@notifications_bp.route("/api/unread")
@login_required
def api_unread():
    user = session["user"]
    notifs = db.get_user_notifications(user["id"], limit=10)
    count  = db.count_unread_notifications(user["id"])
    return jsonify({"count": count, "items": notifs})
