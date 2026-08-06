"""
Public API — exposed to the Vercel website (no CSRF, no session required).
Rate-limited by the platform security layer.
"""

import os
import logging
from flask import request, jsonify, make_response
from datetime import date as _date, datetime
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

# These three endpoints are unauthenticated, write to the database, and send
# WhatsApp messages — the whole reason they need a limit. Generous enough that
# no real client hits it: a household booking for several pets stays well under.
_LIMITS = {
    "book":      (20, 3600),    # 20 bookings/hour from one address
    "contact":   (10, 3600),
    "emergency": (10, 600),     # a real emergency justifies retrying quickly
    # Generous: a provider legitimately retries a callback it thinks was
    # missed, and throttling those would strand real payments as pending.
    "callback":  (300, 3600),
}


def _check_rate_limit(bucket: str = "public"):
    """Returns a 429 response if over the limit, else None.

    This used to call sec.is_rate_limited(ip), which counts rows only
    record_failed_login ever writes. Nothing here wrote to that table, so the
    counter this guard read stayed empty for public traffic and the limit could
    never fire, at any volume. sec.throttle() records the hit it is checking.
    """
    max_hits, window = _LIMITS.get(bucket, (30, 3600))
    ip = sec.get_real_ip(request)
    over, wait = sec.throttle(f"public_{bucket}", ip, max_hits, window)
    if over:
        resp = jsonify({"ok": False,
                        "error": "Too many requests. Please try again later."})
        resp.headers["Retry-After"] = str(max(wait, 1))
        return _cors(resp), 429
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
    rl = _check_rate_limit("book")
    if rl:
        return rl
    data = request.get_json(silent=True) or {}

    # This endpoint is the widest door in the building: no auth, no CSRF, no
    # API key, open to the whole internet. Whatever arrives here is stored and
    # later rendered on the reception screen and on the dashboard every staff
    # member lands on after login.
    #
    # The templates escape it now, which is the fix that actually holds. This
    # is the second layer: a name is a name, so markup and control characters
    # never enter the database in the first place, and a later screen that
    # forgets to escape has nothing dangerous to render.
    def _clean(value, limit=120):
        s = str(value or "").strip()[:limit]
        # Strip angle brackets and the JS template-literal characters rather
        # than rejecting: a real client called "O'Brien & Sons" must still be
        # able to book, and refusing their booking to stop an attack nobody has
        # attempted yet is the wrong trade for a clinic.
        return "".join(ch for ch in s if ch not in "<>`" and (ch >= " " or ch == "\n"))

    owner_name = _clean(data.get("ownerName"))
    mobile     = _clean(data.get("mobile"), 32)
    pet_name   = _clean(data.get("petName"))
    appt_date  = _clean(data.get("date"), 32)

    # Validation
    missing = [f for f, v in [("ownerName", owner_name), ("mobile", mobile),
                               ("petName", pet_name), ("date", appt_date)] if not v]
    if missing:
        return jsonify({"ok": False, "error": f"Missing required fields: {', '.join(missing)}"}), 400

    whatsapp    = _clean(data.get("whatsapp") or mobile, 32)
    email       = _clean(data.get("email"), 120)
    species     = _clean(data.get("species"), 40)
    breed       = _clean(data.get("breed"), 60)
    appt_time   = _clean(data.get("time"), 16)
    doctor      = _clean(data.get("doctor"))
    service     = _clean(data.get("service"))
    branch      = _clean(data.get("branch"))
    notes_raw   = _clean(data.get("notes"), 1000)
    reason      = _clean(data.get("reason"), 200)
    notes       = f"{reason}\n{notes_raw}".strip() if reason else notes_raw
    reminder    = _clean(data.get("reminder"), 40)
    wa_opt_in   = _clean(data.get("whatsappOptIn") or "No", 8)

    # Provenance and branch go into columns that EXIST. The previous version
    # wrote owners.source, pets.source, appointments.service_name and
    # appointments.branch — none of which are in the schema — so every booking
    # the website ever sent raised OperationalError and came back as the
    # generic "Booking failed" 500. Website leads have to land somewhere real:
    #   source  -> owners.created_by / appointments.channel
    #   service -> appointments.appointment_type
    #   branch  -> prefixed onto appointments.notes (branch_id is an integer id,
    #              and the website sends a branch NAME)
    if branch:
        notes = f"Branch: {branch}\n{notes}".strip()

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
                "INSERT INTO owners (full_name, phone, whatsapp_phone, email, created_by) "
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
                "INSERT INTO pets (owner_id, pet_name, species, breed) "
                "VALUES (?, ?, ?, ?)",
                (owner_id, pet_name, species, breed)
            )
            pet_id = cur.lastrowid

        # 3. Insert appointment
        cur = conn.execute(
            "INSERT INTO appointments "
            "(owner_id, pet_id, appt_date, appt_start, doctor_name, appointment_type, "
            " notes, status, channel, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (owner_id, pet_id, appt_date, appt_time, doctor,
             service or "Consultation", notes, "Pending", "Website", "website")
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
    rl = _check_rate_limit("contact")
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
    rl = _check_rate_limit("emergency")
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

    # appointments.pet_id is NOT NULL. A panicking caller who does not give a
    # pet name still has to be recorded, so an unnamed patient gets a real row
    # the clinic can rename — not a NULL that loses the whole emergency.
    pet_name = (data.get("petName") or "").strip() or "Unknown"
    branch   = (data.get("branch") or "").strip()
    today    = str(_date.today())
    # Same schema correction as /book — see the comment there.
    if branch:
        description = f"Branch: {branch}\n{description}".strip()

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
                "INSERT INTO owners (full_name, phone, whatsapp_phone, created_by) "
                "VALUES (?, ?, ?, ?)",
                (owner_name, mobile, mobile, "website")
            )
            owner_id = cur.lastrowid

        # Find or create pet
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
                    "INSERT INTO pets (owner_id, pet_name) VALUES (?, ?)",
                    (owner_id, pet_name)
                )
                pet_id = cur.lastrowid

        # Insert emergency appointment. appt_start is NOT NULL — an emergency
        # has no booked slot, so it is stamped with the time it came in.
        cur = conn.execute(
            "INSERT INTO appointments "
            "(owner_id, pet_id, appt_date, appt_start, notes, status, priority,"
            " channel, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (owner_id, pet_id, today, datetime.now().strftime("%H:%M"),
             description, "Emergency", "Urgent", "Website", "website")
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


# ── POST /api/public/payments/callback/<gateway> ─────────────────────────────
#
# Lives on the PUBLIC blueprint because the payment provider posts here, not a
# logged-in member of staff — behind @login_required it would redirect to the
# login page and every online payment would hang as "pending" forever.
#
# Unauthenticated does NOT mean untrusted: nothing is believed until
# gateway.verify_callback() has checked the signature. An unverified callback
# marking invoices paid is free treatment for anyone who finds this URL.

@public_api_bp.route("/payments/callback/<gateway>", methods=["POST", "GET"])
def payment_callback(gateway):
    from models import payments

    # Rate limited like everything else public. A provider retrying is normal;
    # someone hammering the endpoint hunting for a signature is not.
    rl = _check_rate_limit("callback")
    if rl:
        return rl

    payload = request.get_json(silent=True) or request.form.to_dict() or \
        request.args.to_dict()
    try:
        intent = payments.handle_callback(gateway, payload, dict(request.headers))
    except payments.PaymentError as exc:
        # 400, never 500: a 500 makes providers retry a callback that will never
        # be accepted. Details stay in the log, not in the response — telling a
        # caller WHY their signature failed helps them forge a better one.
        logger.warning("payment callback refused (%s): %s", gateway, exc)
        return jsonify({"ok": False, "error": "Callback rejected."}), 400
    except Exception:
        logger.exception("payment callback blew up (%s)", gateway)
        return jsonify({"ok": False, "error": "Callback could not be processed."}), 500

    logger.info("payment callback: intent=%s now %s", intent["id"], intent["status"])
    return jsonify({"ok": True, "status": intent["status"]})
