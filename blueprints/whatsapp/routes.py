"""
WhatsApp Control Center — full Wapilot v2 integration.
All API calls proxy through the backend so the token stays server-side.
"""
import json
from datetime import datetime
from flask import (
    render_template, request, redirect, url_for,
    session, flash, jsonify, Response,
)
from . import whatsapp_bp
from .wapilot import WapilotClient
from blueprints.auth.routes import login_required, role_required
import models.database as db


# ── Wapilot client factory ────────────────────────────────────────

def _client() -> WapilotClient:
    """Build a WapilotClient using credentials from the settings table."""
    conn = db.get_db()
    rows = {r["key"]: r["value"] for r in conn.execute(
        "SELECT key, value FROM settings WHERE category='wapilot'"
    ).fetchall()}
    conn.close()
    token = rows.get("wapilot_token", "iWmctH6vcBx1RIItK9ucdO94Kv4vHfu6NYTz651yXR")
    iid   = rows.get("wapilot_instance_id", "instance4042")
    return WapilotClient(token=token, instance_id=iid)


def _send_and_log(phone: str, message: str,
                  owner_id=None, template_name: str = "") -> str:
    """Send a WhatsApp message and log the result."""
    cli = _client()
    # Format phone as chat_id (phone@c.us if not already)
    chat_id = phone if "@" in phone else f"{phone.lstrip('+')}@c.us"
    data, err = cli.send_message(chat_id, message)
    status     = "Failed" if err else "Sent"
    http_st    = data.get("status", 0) if isinstance(data, dict) else 0
    response   = json.dumps(data)[:500]
    conn = db.get_db()
    conn.execute(
        """INSERT INTO whatsapp_log
           (owner_id, phone, message, template_name, status, http_status,
            response, error, sent_at)
           VALUES (?,?,?,?,?,?,?,?,NOW())""",
        (owner_id, phone, message[:500], template_name,
         status, http_st, response, err[:300] if err else "")
    )
    conn.commit()
    conn.close()
    return status


# ═══════════════════════════════════════════════════════════════════
# MAIN CONTROL CENTER
# ═══════════════════════════════════════════════════════════════════

@whatsapp_bp.route("/")
@login_required
def index():
    return redirect(url_for("whatsapp.control_center"))


@whatsapp_bp.route("/control")
@login_required
def control_center():
    """Main WhatsApp Control Center dashboard."""
    cli  = _client()
    # Fetch instance status — show error gracefully if API unreachable
    status_data, err = cli.instance_status()
    if err:
        status_data = {"status": "unknown", "error": err}

    # Recent log (last 10)
    conn = db.get_db()
    recent_log = [dict(r) for r in conn.execute(
        """SELECT wl.*, o.full_name as owner_name
           FROM whatsapp_log wl
           LEFT JOIN owners o ON wl.owner_id = o.id
           ORDER BY wl.sent_at DESC LIMIT 10"""
    ).fetchall()]
    template_count = conn.execute(
        "SELECT COUNT(*) FROM whatsapp_templates WHERE is_active=1"
    ).fetchone()[0]
    reminder_count = conn.execute(
        "SELECT COUNT(*) FROM reminders WHERE status='Pending'"
    ).fetchone()[0]
    conn.close()

    return render_template(
        "whatsapp/control_center.html",
        status_data=status_data,
        recent_log=recent_log,
        template_count=template_count,
        reminder_count=reminder_count,
        instance_id=cli.instance_id,
        active="whatsapp",
    )


# ═══════════════════════════════════════════════════════════════════
# INSTANCE API  (JSON — called by frontend JS)
# ═══════════════════════════════════════════════════════════════════

@whatsapp_bp.route("/api/instance/status")
@login_required
def api_instance_status():
    data, err = _client().instance_status()
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/instance/details")
@login_required
def api_instance_details():
    data, err = _client().instance_details()
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/instance/qr")
@login_required
def api_qr_code():
    data, err = _client().get_qr()
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/instance/screenshot")
@login_required
def api_screenshot():
    data, err = _client().get_screenshot()
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/instance/start", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def api_start():
    data, err = _client().start_instance()
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/instance/restart", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def api_restart():
    data, err = _client().restart_instance()
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/instance/logout", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def api_logout():
    data, err = _client().logout_instance()
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/instance/troubleshoot", methods=["POST"])
@role_required("super_admin", "clinic_owner")
def api_troubleshoot():
    data, err = _client().troubleshoot_instance()
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/instance/queue-settings", methods=["GET", "PUT"])
@login_required
def api_queue_settings():
    cli = _client()
    if request.method == "GET":
        data, err = cli.get_queue_settings()
        return jsonify({"ok": not err, "data": data, "error": err})
    body = request.get_json(force=True) or {}
    data, err = cli.update_queue_settings(body)
    return jsonify({"ok": not err, "data": data, "error": err})


# ═══════════════════════════════════════════════════════════════════
# MESSAGES API  (JSON)
# ═══════════════════════════════════════════════════════════════════

@whatsapp_bp.route("/api/messages")
@login_required
def api_list_messages():
    filters = {k: v for k, v in request.args.items()}
    data, err = _client().list_messages(**filters)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/messages/<msg_id>")
@login_required
def api_message_detail(msg_id):
    data, err = _client().message_details(msg_id)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/messages/<msg_id>/retry", methods=["POST"])
@login_required
def api_retry_message(msg_id):
    data, err = _client().retry_message(msg_id)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/messages/retry-all", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager")
def api_retry_all():
    body = request.get_json(force=True) or {}
    data, err = _client().retry_all_messages(body)
    return jsonify({"ok": not err, "data": data, "error": err})


# ═══════════════════════════════════════════════════════════════════
# SEND  (HTML + JSON)
# ═══════════════════════════════════════════════════════════════════

@whatsapp_bp.route("/send-center")
@login_required
def send_center():
    conn = db.get_db()
    templates = [dict(r) for r in conn.execute(
        "SELECT id, name, template_text FROM whatsapp_templates WHERE is_active=1 ORDER BY name"
    ).fetchall()]
    conn.close()
    return render_template("whatsapp/send_center.html",
                           templates=templates, active="whatsapp")


@whatsapp_bp.route("/api/send/text", methods=["POST"])
@login_required
def api_send_text():
    body    = request.get_json(force=True) or {}
    phone   = body.get("phone", "").strip()
    text    = body.get("text", "").strip()
    chat_id = phone if "@" in phone else f"{phone.lstrip('+')}@c.us"
    if not phone or not text:
        return jsonify({"ok": False, "error": "phone and text required"}), 400
    data, err = _client().send_message(chat_id, text)
    # Log to DB
    owner_id = body.get("owner_id")
    status   = "Failed" if err else "Sent"
    conn = db.get_db()
    conn.execute(
        """INSERT INTO whatsapp_log
           (owner_id, phone, message, template_name, status, response, error, sent_at)
           VALUES (?,?,?,?,?,?,?,NOW())""",
        (owner_id, phone, text[:500], body.get("template_name",""),
         status, json.dumps(data)[:500], err or "")
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/send/image", methods=["POST"])
@login_required
def api_send_image():
    phone   = request.form.get("phone", "").strip()
    caption = request.form.get("caption", "")
    chat_id = phone if "@" in phone else f"{phone.lstrip('+')}@c.us"
    file    = request.files.get("media")
    if not phone or not file:
        return jsonify({"ok": False, "error": "phone and media required"}), 400
    data, err = _client().send_image(chat_id, file.read(), file.filename, caption)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/send/file", methods=["POST"])
@login_required
def api_send_file():
    phone   = request.form.get("phone", "").strip()
    caption = request.form.get("caption", "")
    chat_id = phone if "@" in phone else f"{phone.lstrip('+')}@c.us"
    file    = request.files.get("media")
    if not phone or not file:
        return jsonify({"ok": False, "error": "phone and media required"}), 400
    data, err = _client().send_file(chat_id, file.read(), file.filename, caption)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/send/video", methods=["POST"])
@login_required
def api_send_video():
    phone   = request.form.get("phone", "").strip()
    caption = request.form.get("caption", "")
    chat_id = phone if "@" in phone else f"{phone.lstrip('+')}@c.us"
    file    = request.files.get("media")
    if not phone or not file:
        return jsonify({"ok": False, "error": "phone and media required"}), 400
    data, err = _client().send_video(chat_id, file.read(), file.filename, caption)
    return jsonify({"ok": not err, "data": data, "error": err})


# ═══════════════════════════════════════════════════════════════════
# CAMPAIGNS
# ═══════════════════════════════════════════════════════════════════

@whatsapp_bp.route("/campaigns")
@login_required
def campaigns_list():
    data, err = _client().list_campaigns()
    campaigns = []
    if isinstance(data, dict):
        campaigns = data.get("data", data.get("campaigns", []))
    elif isinstance(data, list):
        campaigns = data
    return render_template("whatsapp/campaigns_list.html",
                           campaigns=campaigns, error=err, active="whatsapp")


@whatsapp_bp.route("/campaigns/new", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def campaign_new():
    cli = _client()
    if request.method == "POST":
        f               = request.form
        default_msg     = f.get("default_message", "").strip()
        instance_uns    = [cli.instance_id]
        data, err = cli.create_campaign(instance_uns, default_msg)
        if err:
            flash(f"Failed to create campaign: {err}", "danger")
            return render_template("whatsapp/campaign_form.html",
                                   form=f, active="whatsapp")
        # campaign id
        cid = (data.get("data", {}) or {}).get("id", "") if isinstance(data, dict) else ""
        db.log_audit(
            username=session["user"]["username"],
            role=session["user"]["role"],
            action="create", module="whatsapp",
            entity_type="campaign",
            details=f"Created campaign {cid}: {default_msg[:60]}",
            ip=request.remote_addr,
        )
        flash("Campaign created.", "success")
        if cid:
            return redirect(url_for("whatsapp.campaign_detail", campaign_id=cid))
        return redirect(url_for("whatsapp.campaigns_list"))
    return render_template("whatsapp/campaign_form.html", form={}, active="whatsapp")


@whatsapp_bp.route("/campaigns/<campaign_id>")
@login_required
def campaign_detail(campaign_id):
    cli  = _client()
    data, _   = cli.campaign_messages(campaign_id)
    stats, _  = cli.campaign_stats(campaign_id)
    delay, _  = cli.get_delay(campaign_id)
    messages  = []
    if isinstance(data, dict):
        messages = data.get("data", data.get("messages", []))
    elif isinstance(data, list):
        messages = data
    stats_d = stats.get("data", stats) if isinstance(stats, dict) else {}
    delay_d = delay.get("data", delay) if isinstance(delay, dict) else {}
    return render_template(
        "whatsapp/campaign_detail.html",
        campaign_id=campaign_id,
        messages=messages,
        stats=stats_d,
        delay=delay_d,
        active="whatsapp",
    )


# ── Campaign action API endpoints (JSON) ─────────────────────────

@whatsapp_bp.route("/api/campaigns")
@login_required
def api_campaigns():
    data, err = _client().list_campaigns()
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/campaigns", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager")
def api_create_campaign():
    body = request.get_json(force=True) or {}
    cli  = _client()
    instance_uns = body.get("instance_uns", [cli.instance_id])
    default_msg  = body.get("default_message", "")
    data, err = cli.create_campaign(instance_uns, default_msg)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/campaigns/<cid>/start", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def api_campaign_start(cid):
    data, err = _client().start_campaign(cid)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/campaigns/<cid>/pause", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def api_campaign_pause(cid):
    data, err = _client().pause_campaign(cid)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/campaigns/<cid>/finish", methods=["PATCH"])
@role_required("super_admin", "clinic_owner", "branch_manager")
def api_campaign_finish(cid):
    data, err = _client().finish_campaign(cid)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/campaigns/<cid>/copy", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager")
def api_campaign_copy(cid):
    data, err = _client().copy_campaign(cid)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/campaigns/<cid>/reset-failed", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager")
def api_campaign_reset_failed(cid):
    data, err = _client().reset_failed(cid)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/campaigns/<cid>/schedule", methods=["POST", "DELETE"])
@role_required("super_admin", "clinic_owner", "branch_manager")
def api_campaign_schedule(cid):
    if request.method == "DELETE":
        data, err = _client().unschedule_campaign(cid)
    else:
        body = request.get_json(force=True) or {}
        data, err = _client().schedule_campaign(cid, body.get("schedule_date", ""))
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/campaigns/<cid>/delay", methods=["GET", "PATCH"])
@login_required
def api_campaign_delay(cid):
    if request.method == "GET":
        data, err = _client().get_delay(cid)
    else:
        body = request.get_json(force=True) or {}
        data, err = _client().update_delay(cid, body)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/campaigns/<cid>/messages", methods=["GET", "POST", "DELETE"])
@login_required
def api_campaign_messages(cid):
    cli = _client()
    if request.method == "GET":
        data, err = cli.campaign_messages(cid)
    elif request.method == "POST":
        body = request.get_json(force=True) or {}
        data, err = cli.bulk_add_messages(cid, body.get("messages", []))
    else:
        body = request.get_json(force=True) or {}
        data, err = cli.bulk_delete_messages(cid, body.get("ids", []))
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/campaigns/<cid>/stats")
@login_required
def api_campaign_stats(cid):
    data, err = _client().campaign_stats(cid)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/campaigns/<cid>/queue")
@login_required
def api_campaign_queue(cid):
    data, err = _client().campaign_queue(cid)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/campaigns/<cid>/done")
@login_required
def api_campaign_done(cid):
    data, err = _client().campaign_done(cid)
    return jsonify({"ok": not err, "data": data, "error": err})


# ═══════════════════════════════════════════════════════════════════
# TEMPLATES  (DB-backed)
# ═══════════════════════════════════════════════════════════════════

@whatsapp_bp.route("/templates")
@login_required
def templates_list():
    conn = db.get_db()
    templates = [dict(r) for r in conn.execute(
        "SELECT * FROM whatsapp_templates ORDER BY name"
    ).fetchall()]
    conn.close()
    return render_template("whatsapp/templates_list.html",
                           templates=templates, active="whatsapp")


@whatsapp_bp.route("/templates/new", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "reception")
def template_new():
    if request.method == "POST":
        f    = request.form
        name = f.get("name", "").strip()
        if not name:
            flash("Template name is required.", "danger")
            return render_template("whatsapp/template_form.html",
                                   form=f, action="new", active="whatsapp")
        try:
            conn = db.get_db()
            conn.execute(
                """INSERT INTO whatsapp_templates
                   (name, scenario, language, template_text, variables_json, is_active, is_default)
                   VALUES (?,?,?,?,?,?,?)""",
                (name, f.get("scenario",""), f.get("language","en"),
                 f.get("template_text",""), f.get("variables_json","[]"),
                 1 if f.get("is_active") else 0,
                 1 if f.get("is_default") else 0)
            )
            conn.commit()
            conn.close()
            db.log_audit(
                username=session["user"]["username"],
                role=session["user"]["role"],
                action="create", module="whatsapp",
                entity_type="template",
                details=f"Created template: {name}",
                ip=request.remote_addr,
            )
            flash(f"Template '{name}' created.", "success")
            return redirect(url_for("whatsapp.templates_list"))
        except Exception as e:
            flash(f"Error: {e}", "danger")
    return render_template("whatsapp/template_form.html",
                           form={}, action="new", active="whatsapp")


@whatsapp_bp.route("/templates/<int:tid>/edit", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin", "reception")
def template_edit(tid):
    conn = db.get_db()
    tmpl = conn.execute("SELECT * FROM whatsapp_templates WHERE id=?", (tid,)).fetchone()
    if not tmpl:
        conn.close()
        flash("Template not found.", "danger")
        return redirect(url_for("whatsapp.templates_list"))
    if request.method == "POST":
        f = request.form
        conn.execute(
            """UPDATE whatsapp_templates
               SET name=?, scenario=?, language=?, template_text=?,
                   variables_json=?, is_active=?, is_default=?
               WHERE id=?""",
            (f.get("name",""), f.get("scenario",""), f.get("language","en"),
             f.get("template_text",""), f.get("variables_json","[]"),
             1 if f.get("is_active") else 0,
             1 if f.get("is_default") else 0, tid)
        )
        conn.commit()
        conn.close()
        db.log_audit(
            username=session["user"]["username"],
            role=session["user"]["role"],
            action="update", module="whatsapp",
            entity_type="template", entity_id=tid,
            details=f"Updated template: {f.get('name','')}",
            ip=request.remote_addr,
        )
        flash("Template updated.", "success")
        return redirect(url_for("whatsapp.templates_list"))
    form = dict(tmpl)
    conn.close()
    return render_template("whatsapp/template_form.html",
                           form=form, action="edit", active="whatsapp")


@whatsapp_bp.route("/templates/<int:tid>/delete", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager")
def template_delete(tid):
    conn = db.get_db()
    conn.execute("DELETE FROM whatsapp_templates WHERE id=?", (tid,))
    conn.commit()
    conn.close()
    flash("Template deleted.", "success")
    return redirect(url_for("whatsapp.templates_list"))


@whatsapp_bp.route("/api/templates")
@login_required
def api_templates():
    """JSON list of active templates (used by send modals)."""
    conn = db.get_db()
    templates = [dict(r) for r in conn.execute(
        "SELECT id, name, scenario, template_text FROM whatsapp_templates WHERE is_active=1 ORDER BY name"
    ).fetchall()]
    conn.close()
    return jsonify(templates)


# ═══════════════════════════════════════════════════════════════════
# REMINDERS
# ═══════════════════════════════════════════════════════════════════

@whatsapp_bp.route("/reminders")
@login_required
def reminders():
    conn = db.get_db()
    pending = [dict(r) for r in conn.execute(
        """SELECT r.*, o.full_name as owner_name, o.whatsapp_phone,
                  p.pet_name
           FROM reminders r
           LEFT JOIN owners o ON r.owner_id = o.id
           LEFT JOIN pets   p ON r.pet_id   = p.id
           WHERE r.status = 'Pending'
           ORDER BY r.scheduled_for"""
    ).fetchall()]
    conn.close()
    return render_template("whatsapp/reminders.html",
                           reminders=pending, active="whatsapp")


@whatsapp_bp.route("/reminders/<int:rid>/send", methods=["POST"])
@login_required
def reminder_send(rid):
    conn = db.get_db()
    r = conn.execute(
        """SELECT r.*, o.whatsapp_phone, o.phone, o.full_name, p.pet_name
           FROM reminders r
           LEFT JOIN owners o ON r.owner_id = o.id
           LEFT JOIN pets   p ON r.pet_id   = p.id
           WHERE r.id=?""", (rid,)
    ).fetchone()
    conn.close()
    if not r:
        return jsonify({"ok": False, "error": "Reminder not found"}), 404
    phone   = r["whatsapp_phone"] or r["phone"] or ""
    message = r["message"] or ""
    if not phone:
        return jsonify({"ok": False, "error": "No phone number"})
    status = _send_and_log(phone, message, owner_id=r["owner_id"])
    if status == "Sent":
        conn = db.get_db()
        conn.execute(
            "UPDATE reminders SET status='Sent', sent_at=NOW() WHERE id=?", (rid,)
        )
        conn.commit()
        conn.close()
    return jsonify({"ok": status == "Sent", "status": status})


@whatsapp_bp.route("/reminders/<int:rid>/mark-sent", methods=["POST"])
@login_required
def mark_reminder_sent(rid):
    conn = db.get_db()
    conn.execute(
        "UPDATE reminders SET status='Sent', sent_at=NOW() WHERE id=?", (rid,)
    )
    conn.commit()
    conn.close()
    flash("Reminder marked as sent.", "success")
    return redirect(url_for("whatsapp.reminders"))


# ═══════════════════════════════════════════════════════════════════
# MESSAGE LOG
# ═══════════════════════════════════════════════════════════════════

@whatsapp_bp.route("/log")
@login_required
def message_log():
    conn = db.get_db()
    logs = [dict(r) for r in conn.execute(
        """SELECT wl.*, o.full_name as owner_name
           FROM whatsapp_log wl
           LEFT JOIN owners o ON wl.owner_id = o.id
           ORDER BY wl.sent_at DESC LIMIT 200"""
    ).fetchall()]
    conn.close()
    return render_template("whatsapp/message_log.html",
                           logs=logs, active="whatsapp")


# ═══════════════════════════════════════════════════════════════════
# SETTINGS
# ═══════════════════════════════════════════════════════════════════

@whatsapp_bp.route("/settings", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def wa_settings():
    WAPILOT_KEYS = [
        ("wapilot_token",       "API Token",       "API token from wapilot.net"),
        ("wapilot_instance_id", "Instance ID",     "Your WhatsApp instance unique name"),
    ]
    REMINDER_KEYS = [
        ("reminder_appt_enabled",    "1",   "Appointment Reminders",  "Send reminders 24h before appointment"),
        ("reminder_vaccine_enabled", "1",   "Vaccine Due Reminders",  "Remind owners of upcoming vaccines"),
        ("reminder_invoice_enabled", "1",   "Invoice Overdue Alerts", "Alert owners on unpaid invoices"),
        ("reminder_appt_msg",
         "Dear {owner}, {pet} has an appointment tomorrow ({date} at {time}).",
         "Appointment Message", ""),
        ("reminder_vaccine_msg",
         "Dear {owner}, {pet} is due for the {vaccine} vaccine (due: {date}).",
         "Vaccine Message", ""),
        ("reminder_invoice_msg",
         "Dear {owner}, Invoice #{invoice} ({amount}) was due on {date} and remains unpaid.",
         "Invoice Message", ""),
    ]

    if request.method == "POST":
        conn = db.get_db()
        for key, _lbl, _desc in WAPILOT_KEYS:
            val = request.form.get(key, "").strip()
            if val:
                conn.execute(
                    """INSERT INTO settings(key,value,category,updated_at,updated_by)
                       VALUES(?,?,'wapilot',NOW(),?)
                       ON CONFLICT(key) DO UPDATE
                       SET value=excluded.value, updated_at=excluded.updated_at,
                           updated_by=excluded.updated_by""",
                    (key, val, session["user"]["username"])
                )
        for key, _default, _lbl, _desc in REMINDER_KEYS:
            val = request.form.get(key, "0" if key.endswith("_enabled") else "")
            conn.execute(
                """INSERT INTO settings(key,value,category,updated_at,updated_by)
                   VALUES(?,?,'whatsapp',NOW(),?)
                   ON CONFLICT(key) DO UPDATE
                   SET value=excluded.value, updated_at=excluded.updated_at,
                       updated_by=excluded.updated_by""",
                (key, val, session["user"]["username"])
            )
        conn.commit()
        conn.close()
        db.log_audit(
            username=session["user"]["username"],
            role=session["user"]["role"],
            action="update", module="whatsapp",
            entity_type="settings",
            details="Updated WhatsApp / Wapilot settings",
        )
        flash("Settings saved.", "success")
        return redirect(url_for("whatsapp.wa_settings"))

    conn = db.get_db()
    rows = {r["key"]: r["value"] for r in conn.execute(
        "SELECT key, value FROM settings WHERE category IN ('whatsapp','wapilot')"
    ).fetchall()}
    conn.close()
    # Inject defaults
    defaults = {"wapilot_token": "iWmctH6vcBx1RIItK9ucdO94Kv4vHfu6NYTz651yXR",
                "wapilot_instance_id": "instance4042"}
    for k, v in defaults.items():
        rows.setdefault(k, v)
    for key, default, _lbl, _desc in REMINDER_KEYS:
        rows.setdefault(key, default)

    return render_template(
        "whatsapp/wa_settings.html",
        settings=rows,
        wapilot_keys=WAPILOT_KEYS,
        reminder_keys=REMINDER_KEYS,
        active="whatsapp",
    )


# ── Alias for old route ───────────────────────────────────────────
@whatsapp_bp.route("/reminder-settings", methods=["GET"])
@login_required
def reminder_settings():
    return redirect(url_for("whatsapp.wa_settings"))


# ═══════════════════════════════════════════════════════════════════
# CHAT ID LOOKUP
# ═══════════════════════════════════════════════════════════════════

@whatsapp_bp.route("/api/lookup/lid/<lid>")
@login_required
def api_lookup_lid(lid):
    data, err = _client().get_chat_id_by_lid(lid)
    return jsonify({"ok": not err, "data": data, "error": err})


@whatsapp_bp.route("/api/lookup/phone/<phone>")
@login_required
def api_lookup_phone(phone):
    data, err = _client().get_lid_by_phone(phone)
    return jsonify({"ok": not err, "data": data, "error": err})


# ── Existing send shortcut (keep for CRM compatibility) ──────────

# ═══════════════════════════════════════════════════════════════════
# REMINDER ADMIN UI
# ═══════════════════════════════════════════════════════════════════

@whatsapp_bp.route("/reminder-admin")
@login_required
def reminder_admin():
    """Admin UI for viewing, configuring, and triggering reminders."""
    conn = db.get_db()
    # Stats
    pending_count = conn.execute(
        "SELECT COUNT(*) FROM reminders WHERE status='Pending'"
    ).fetchone()[0]
    sent_count = conn.execute(
        "SELECT COUNT(*) FROM reminders WHERE status='Sent'"
    ).fetchone()[0]
    failed_count = conn.execute(
        "SELECT COUNT(*) FROM reminders WHERE status='Failed'"
    ).fetchone()[0]

    # Upcoming reminders (next 7 days)
    upcoming = [dict(r) for r in conn.execute(
        """SELECT r.*, o.full_name as owner_name, o.whatsapp_phone,
                  p.pet_name
           FROM reminders r
           LEFT JOIN owners o ON r.owner_id = o.id
           LEFT JOIN pets   p ON r.pet_id   = p.id
           WHERE r.status='Pending'
           AND r.scheduled_for >= NOW()
           ORDER BY r.scheduled_for
           LIMIT 50"""
    ).fetchall()]

    # Overdue reminders
    overdue = [dict(r) for r in conn.execute(
        """SELECT r.*, o.full_name as owner_name, o.whatsapp_phone,
                  p.pet_name
           FROM reminders r
           LEFT JOIN owners o ON r.owner_id = o.id
           LEFT JOIN pets   p ON r.pet_id   = p.id
           WHERE r.status='Pending'
           AND r.scheduled_for < NOW()
           ORDER BY r.scheduled_for
           LIMIT 50"""
    ).fetchall()]

    # Recent run log
    run_log = []
    try:
        run_log = [dict(r) for r in conn.execute(
            "SELECT * FROM reminder_runs ORDER BY run_at DESC LIMIT 20"
        ).fetchall()]
    except Exception:
        pass

    # Settings
    settings_rows = {r["key"]: r["value"] for r in conn.execute(
        "SELECT key, value FROM settings WHERE category IN ('whatsapp','wapilot')"
    ).fetchall()}
    conn.close()

    return render_template(
        "whatsapp/reminder_admin.html",
        active="whatsapp",
        pending_count=pending_count,
        sent_count=sent_count,
        failed_count=failed_count,
        upcoming=upcoming,
        overdue=overdue,
        run_log=run_log,
        settings=settings_rows,
    )


@whatsapp_bp.route("/reminder-admin/trigger", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "support_admin")
def reminder_trigger():
    """Manually trigger the reminder job."""
    try:
        from blueprints.whatsapp.scheduler import run_reminder_jobs
        run_reminder_jobs()
        flash("Reminder job triggered successfully. Check the run log.", "success")
    except Exception as e:
        flash(f"Reminder job failed: {e}", "danger")
    return redirect(url_for("whatsapp.reminder_admin"))


@whatsapp_bp.route("/reminder-admin/reminders/new", methods=["POST"])
@login_required
def reminder_create():
    """Create a manual reminder."""
    f = request.form
    owner_id   = f.get("owner_id", type=int)
    pet_id     = f.get("pet_id", type=int)
    rtype      = f.get("reminder_type", "custom")
    sched      = f.get("scheduled_for", "")
    message    = f.get("message", "").strip()
    if not owner_id or not message or not sched:
        flash("Owner, scheduled date, and message are required.", "danger")
        return redirect(url_for("whatsapp.reminder_admin"))
    conn = db.get_db()
    conn.execute(
        """INSERT INTO reminders
           (owner_id, pet_id, reminder_type, scheduled_for, message, status)
           VALUES (?,?,?,?,?,'Pending')""",
        (owner_id, pet_id, rtype, sched, message)
    )
    conn.commit()
    conn.close()
    flash("Reminder created.", "success")
    return redirect(url_for("whatsapp.reminder_admin"))


@whatsapp_bp.route("/reminder-admin/reminders/<int:rid>/cancel", methods=["POST"])
@login_required
def reminder_cancel(rid):
    conn = db.get_db()
    conn.execute("UPDATE reminders SET status='Cancelled' WHERE id=? AND status='Pending'", (rid,))
    conn.commit()
    conn.close()
    flash("Reminder cancelled.", "success")
    return redirect(url_for("whatsapp.reminder_admin"))


@whatsapp_bp.route("/reminder-admin/reminders/<int:rid>/send-now", methods=["POST"])
@login_required
def reminder_send_now(rid):
    """Send a specific reminder immediately."""
    conn = db.get_db()
    r = conn.execute(
        """SELECT r.*, o.whatsapp_phone, o.phone
           FROM reminders r
           LEFT JOIN owners o ON r.owner_id = o.id
           WHERE r.id=?""", (rid,)
    ).fetchone()
    conn.close()
    if not r:
        flash("Reminder not found.", "danger")
        return redirect(url_for("whatsapp.reminder_admin"))
    phone = r["whatsapp_phone"] or r["phone"] or ""
    if not phone:
        flash("Owner has no phone number.", "warning")
        return redirect(url_for("whatsapp.reminder_admin"))
    status = _send_and_log(phone, r["message"], owner_id=r["owner_id"])
    if status == "Sent":
        conn = db.get_db()
        conn.execute("UPDATE reminders SET status='Sent', sent_at=NOW() WHERE id=?", (rid,))
        conn.commit()
        conn.close()
        flash("Reminder sent successfully.", "success")
    else:
        flash("Send failed — check message log.", "warning")
    return redirect(url_for("whatsapp.reminder_admin"))


# ── Existing send shortcut (keep for CRM compatibility) ──────────

@whatsapp_bp.route("/send", methods=["POST"])
@login_required
def send_message():
    phone        = request.form.get("phone", "").strip()
    message      = request.form.get("custom_message", "").strip()
    owner_id     = request.form.get("owner_id") or None
    template_id  = request.form.get("template_id") or None
    template_name = ""
    if not phone:
        flash("Phone number is required.", "danger")
        return redirect(request.referrer or url_for("whatsapp.reminders"))
    if template_id and not message:
        conn = db.get_db()
        tmpl = conn.execute(
            "SELECT * FROM whatsapp_templates WHERE id=?", (template_id,)
        ).fetchone()
        conn.close()
        if tmpl:
            message       = tmpl["template_text"]
            template_name = tmpl["name"]
    if not message:
        flash("Message content is required.", "danger")
        return redirect(request.referrer or url_for("whatsapp.reminders"))
    status = _send_and_log(phone, message, owner_id=owner_id,
                           template_name=template_name)
    if status == "Sent":
        flash(f"Message sent to {phone}.", "success")
    else:
        flash("Message queued / failed — check log.", "warning")
    return redirect(request.referrer or url_for("whatsapp.message_log"))



# ═══════════════════════════════════════════════════════════════════
# SCHEDULER ADMIN UI
# ═══════════════════════════════════════════════════════════════════

@whatsapp_bp.route("/scheduler")
@login_required
def scheduler():
    conn = db.get_db()
    # Recent reminder history (last 200 runs)
    history = []
    try:
        history = [dict(r) for r in conn.execute(
            """SELECT rr.*, wl.status AS wa_status, wl.error AS wa_error
               FROM reminder_runs rr
               LEFT JOIN whatsapp_log wl ON wl.id = (
                   SELECT id FROM whatsapp_log
                   WHERE template_name = rr.run_type
                     AND sent_at >= rr.run_at
                   ORDER BY sent_at LIMIT 1
               )
               ORDER BY rr.run_at DESC LIMIT 200""",
        ).fetchall()]
    except Exception:
        try:
            history = [dict(r) for r in conn.execute(
                "SELECT * FROM reminder_runs ORDER BY run_at DESC LIMIT 200"
            ).fetchall()]
        except Exception:
            history = []

    # Stats by type
    stats = {}
    for row in history:
        t = row.get("run_type", "?")
        stats[t] = stats.get(t, 0) + 1

    # Upcoming: appointments tomorrow
    from datetime import date, timedelta
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    try:
        upcoming_appts = conn.execute(
            """SELECT COUNT(*) FROM appointments a
               JOIN owners o ON o.id=a.owner_id
               WHERE a.appt_date=? AND a.status IN ('Scheduled','Confirmed')
                 AND o.whatsapp_phone IS NOT NULL AND o.whatsapp_phone != ''""",
            (tomorrow,)
        ).fetchone()[0]
    except Exception:
        upcoming_appts = 0

    try:
        overdue_vaccines = conn.execute(
            """SELECT COUNT(*) FROM vaccinations v
               JOIN pets p ON p.id=v.pet_id
               JOIN owners o ON o.id=p.owner_id
               WHERE v.next_due_at <= ? AND o.whatsapp_phone IS NOT NULL""",
            (date.today().isoformat(),)
        ).fetchone()[0]
    except Exception:
        overdue_vaccines = 0

    try:
        overdue_invoices = conn.execute(
            """SELECT COUNT(*) FROM invoices i
               JOIN owners o ON o.id=i.owner_id
               WHERE i.status IN ('Unpaid','Partial')
                 AND o.whatsapp_phone IS NOT NULL""",
        ).fetchone()[0]
    except Exception:
        overdue_invoices = 0

    conn.close()
    return render_template(
        "whatsapp/scheduler.html",
        history=history,
        stats=stats,
        upcoming_appts=upcoming_appts,
        overdue_vaccines=overdue_vaccines,
        overdue_invoices=overdue_invoices,
        active="whatsapp",
    )


@whatsapp_bp.route("/scheduler/run", methods=["POST"])
@login_required
def scheduler_run():
    """Manually trigger all reminder jobs right now."""
    run_type = request.form.get("type", "all")   # all | appt | vaccine | invoice
    from blueprints.whatsapp.scheduler import (
        run_reminder_jobs, _appointment_reminders,
        _vaccine_reminders, _invoice_reminders,
    )
    conn = db.get_db()
    try:
        if run_type == "all":
            run_reminder_jobs()
            flash("All reminder jobs triggered successfully.", "success")
        elif run_type == "appt":
            n = _appointment_reminders(conn)
            conn.commit()
            flash(f"Appointment reminders sent: {n}.", "success")
        elif run_type == "vaccine":
            n = _vaccine_reminders(conn)
            conn.commit()
            flash(f"Vaccine reminders sent: {n}.", "success")
        elif run_type == "invoice":
            n = _invoice_reminders(conn)
            conn.commit()
            flash(f"Invoice reminders sent: {n}.", "success")
        else:
            flash("Unknown job type.", "warning")
    except Exception as e:
        flash(f"Scheduler error: {e}", "danger")
    finally:
        conn.close()
    return redirect(url_for("whatsapp.scheduler"))


@whatsapp_bp.route("/scheduler/clear-history", methods=["POST"])
@login_required
def scheduler_clear_history():
    """Clear reminder_runs history older than 30 days."""
    conn = db.get_db()
    try:
        conn.execute(
            "DELETE FROM reminder_runs WHERE run_at < NOW() - INTERVAL '30 days'"
        )
        conn.commit()
        flash("History cleared (entries older than 30 days removed).", "success")
    except Exception:
        try:
            conn.execute(
                "DELETE FROM reminder_runs WHERE run_at < datetime('now', '-30 days')"
            )
            conn.commit()
            flash("History cleared.", "success")
        except Exception as e:
            flash(f"Could not clear history: {e}", "warning")
    finally:
        conn.close()
    return redirect(url_for("whatsapp.scheduler"))
