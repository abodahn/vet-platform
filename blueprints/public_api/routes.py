"""
Public API — exposed to the Vercel website (no CSRF, no session required).
Rate-limited by the platform security layer.
"""

import os
import logging
from flask import request, jsonify, make_response
from datetime import date as _date
import models.database as db
import models.security as sec
from . import public_api_bp

logger = logging.getLogger(__name__)

# Allowed CORS origin — restrict to your website domain in production.
# Set CORS_ALLOWED_ORIGIN env var to your Vercel/website URL.
# Default "*" works for local dev but MUST be restricted in production.
_CORS_ORIGIN = os.environ.get("CORS_ALLOWED_ORIGIN", "*")

# Emergency contact — set EMERGENCY_PHONE env var in production
_EMERGENCY_PHONE = os.environ.get("EMERGENCY_PHONE", "")


# ── CORS helper ─────────────────────────────────────────────────────────────

def _cors(response):
    response.headers["Access-Control-Allow-Origin"] = _CORS_ORIGIN
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Api-Key"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    if _CORS_ORIGIN != "*":
        response.headers["Vary"] = "Origin"
    return response


@public_api_bp.after_request
def _apply_cors(response):
    return _cors(response)


# Preflight handler for every sub-path
@public_api_bp.route("/<path:p>", methods=["OPTIONS"])
def options_handler(p):
    return _cors(make_response("", 204))


# ── Rate limit helper for public endpoints ───────────────────────────────────

def _check_rate_limit():
    """Returns a 429 response if rate limited, else None."""
    ip = sec.get_real_ip(request)
    limited, wait = sec.is_rate_limited(ip)
    if limited:
        return jsonify({"ok": False, "error": "Too many requests. Please try again later."}), 429
    return None


# ── GET /api/public/health ───────────────────────────────────────────────────

@public_api_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "service": "Aleefy API"})


# ── GET /api/public/services ─────────────────────────────────────────────────

@public_api_bp.route("/services", methods=["GET"])
def services():
    conn = db.get_db()
    try:
        cur = conn.execute(
            "SELECT id, name, standard_price, category FROM service_catalog ORDER BY category, name"
        )
        rows = cur.fetchall()
        result = [
            {
                "id": row["id"],
                "name": row["name"],
                "standard_price": row["standard_price"],
                "category": row["category"],
            }
            for row in rows
        ]
        return jsonify(result)
    except Exception as exc:
        logger.error(f"Public API /services error: {exc}", exc_info=True)
        return jsonify({"ok": False, "error": "Service temporarily unavailable."}), 500
    finally:
        conn.close()


# ── POST /api/public/book ────────────────────────────────────────────────────

@public_api_bp.route("/book", methods=["POST"])
def book():
    rl = _check_rate_limit()
    if rl:
        return rl
    data = request.get_json(silent=True) or {}

    owner_name = (data.get("ownerName") or "").strip()
    mobile     = (data.get("mobile") or "").strip()
    pet_name   = (data.get("petName") or "").strip()
    appt_date  = (data.get("date") or "").strip()

    # Validation
    missing = [f for f, v in [("ownerName", owner_name), ("mobile", mobile),
                               ("petName", pet_name), ("date", appt_date)] if not v]
    if missing:
        return jsonify({"ok": False, "error": f"Missing required fields: {', '.join(missing)}"}), 400

    whatsapp    = (data.get("whatsapp") or mobile).strip()
    email       = (data.get("email") or "").strip()
    species     = (data.get("species") or "").strip()
    breed       = (data.get("breed") or "").strip()
    appt_time   = (data.get("time") or "").strip()
    doctor      = (data.get("doctor") or "").strip()
    service     = (data.get("service") or "").strip()
    branch      = (data.get("branch") or "").strip()
    notes_raw   = (data.get("notes") or "").strip()
    reason      = (data.get("reason") or "").strip()
    notes       = f"{reason}\n{notes_raw}".strip() if reason else notes_raw
    reminder    = (data.get("reminder") or "").strip()
    wa_opt_in   = (data.get("whatsappOptIn") or "No").strip()

    conn = db.get_db()
    try:
        # 1. Find or create owner
        cur = conn.execute(
            "SELECT id FROM owners WHERE phone=? OR whatsapp_phone=? LIMIT 1",
            (mobile, whatsapp)
        )
        row = cur.fetchone()
        if row:
            owner_id = row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO owners (full_name, phone, whatsapp_phone, email, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (owner_name, mobile, whatsapp, email, "website")
            )
            owner_id = cur.lastrowid

        # 2. Find or create pet
        cur = conn.execute(
            "SELECT id FROM pets WHERE owner_id=? AND pet_name=? LIMIT 1",
            (owner_id, pet_name)
        )
        row = cur.fetchone()
        if row:
            pet_id = row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO pets (owner_id, pet_name, species, breed, source) "
                "VALUES (?, ?, ?, ?, ?)",
                (owner_id, pet_name, species, breed, "website")
            )
            pet_id = cur.lastrowid

        # 3. Insert appointment
        cur = conn.execute(
            "INSERT INTO appointments "
            "(owner_id, pet_id, appt_date, appt_start, doctor_name, service_name, "
            " branch, notes, status, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (owner_id, pet_id, appt_date, appt_time, doctor, service,
             branch, notes, "Pending", "website")
        )
        appointment_id = cur.lastrowid

        # 4. WhatsApp reminder
        if reminder == "WhatsApp reminder" and wa_opt_in == "Yes":
            scheduled_for = f"{appt_date} 09:00:00"
            message = (
                f"Dear {owner_name}, {pet_name} has an appointment on "
                f"{appt_date} at {appt_time}."
            )
            conn.execute(
                "INSERT INTO reminders "
                "(owner_id, pet_id, appointment_id, reminder_type, scheduled_for, message, status) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (owner_id, pet_id, appointment_id, "appointment",
                 scheduled_for, message, "Pending")
            )

        conn.commit()
        return jsonify({
            "ok": True,
            "booking_id": appointment_id,
            "message": "Booking received. We will confirm shortly.",
        })

    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"Public API /book error: {exc}", exc_info=True)
        return jsonify({"ok": False, "error": "Booking failed. Please try again or call us directly."}), 500
    finally:
        conn.close()


# ── POST /api/public/contact ─────────────────────────────────────────────────

@public_api_bp.route("/contact", methods=["POST"])
def contact():
    rl = _check_rate_limit()
    if rl:
        return rl
    data = request.get_json(silent=True) or {}

    name    = (data.get("name") or "").strip()
    mobile  = (data.get("mobile") or "").strip()
    message = (data.get("message") or "").strip()

    missing = [f for f, v in [("name", name), ("mobile", mobile), ("message", message)] if not v]
    if missing:
        return jsonify({"ok": False, "error": f"Missing required fields: {', '.join(missing)}"}), 400

    email   = (data.get("email") or "").strip()
    pet_name = (data.get("petName") or "").strip()
    branch  = (data.get("branch") or "").strip()
    method  = (data.get("method") or "").strip()

    conn = db.get_db()
    try:
        # Ensure table exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contact_messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT,
                mobile          TEXT,
                email           TEXT,
                pet_name        TEXT,
                branch          TEXT,
                contact_method  TEXT,
                message         TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                handled         BOOLEAN DEFAULT FALSE
            )
        """)

        conn.execute(
            "INSERT INTO contact_messages "
            "(name, mobile, email, pet_name, branch, contact_method, message) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (name, mobile, email, pet_name, branch, method, message)
        )
        conn.commit()
        return jsonify({"ok": True, "message": "Thank you. We will contact you shortly."})

    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"Public API /contact error: {exc}", exc_info=True)
        return jsonify({"ok": False, "error": "Message could not be saved. Please call us directly."}), 500
    finally:
        conn.close()


# ── POST /api/public/emergency ───────────────────────────────────────────────

@public_api_bp.route("/emergency", methods=["POST"])
def emergency():
    rl = _check_rate_limit()
    if rl:
        return rl
    data = request.get_json(silent=True) or {}

    owner_name  = (data.get("ownerName") or "").strip()
    mobile      = (data.get("mobile") or "").strip()
    description = (data.get("description") or "").strip()

    missing = [f for f, v in [("ownerName", owner_name), ("mobile", mobile),
                               ("description", description)] if not v]
    if missing:
        return jsonify({"ok": False, "error": f"Missing required fields: {', '.join(missing)}"}), 400

    pet_name = (data.get("petName") or "").strip()
    branch   = (data.get("branch") or "").strip()
    today    = str(_date.today())

    conn = db.get_db()
    try:
        # Find or create owner
        cur = conn.execute(
            "SELECT id FROM owners WHERE phone=? LIMIT 1",
            (mobile,)
        )
        row = cur.fetchone()
        if row:
            owner_id = row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO owners (full_name, phone, whatsapp_phone, source) "
                "VALUES (?, ?, ?, ?)",
                (owner_name, mobile, mobile, "website")
            )
            owner_id = cur.lastrowid

        # Find or create pet (if provided)
        pet_id = None
        if pet_name and owner_id:
            cur = conn.execute(
                "SELECT id FROM pets WHERE owner_id=? AND pet_name=? LIMIT 1",
                (owner_id, pet_name)
            )
            row = cur.fetchone()
            if row:
                pet_id = row["id"]
            else:
                cur = conn.execute(
                    "INSERT INTO pets (owner_id, pet_name, source) VALUES (?, ?, ?)",
                    (owner_id, pet_name, "website")
                )
                pet_id = cur.lastrowid

        # Insert emergency appointment
        cur = conn.execute(
            "INSERT INTO appointments "
            "(owner_id, pet_id, appt_date, branch, notes, status, source) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (owner_id, pet_id, today, branch, description, "Emergency", "website")
        )
        appointment_id = cur.lastrowid

        conn.commit()
        # Phone number comes from env var — never hardcoded
        phone_msg = f" Please call {_EMERGENCY_PHONE} immediately." if _EMERGENCY_PHONE else ""
        return jsonify({
            "ok": True,
            "message": f"Emergency received. Our team will contact you shortly.{phone_msg}",
        })

    except Exception as exc:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.error(f"Public API /emergency error: {exc}", exc_info=True)
        return jsonify({"ok": False, "error": "Emergency registration failed. Please call us directly."}), 500
    finally:
        conn.close()
