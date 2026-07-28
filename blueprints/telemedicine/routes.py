"""
Telemedicine — Video Consultations via Jitsi Meet (no API key required).
Each session gets a unique Jitsi room: meet.jit.si/PAH-<clinic_slug>-<token>
"""
import logging
import secrets
import string
from datetime import date, datetime
from flask import (render_template, request, redirect, url_for,
                   flash, session, jsonify, abort)
from . import telemedicine_bp
from blueprints.auth.routes import login_required
from models.database import get_db
import models.database as db

logger = logging.getLogger(__name__)

TELEMEDICINE_FALLBACK_PRICE = 0.0


# ── Table init ────────────────────────────────────────────────────────────────

def _ensure_tables():
    """Create telemedicine_sessions if it does not exist.

    ONE portable definition, written SQLite-flavoured. `_fix_sql` translates
    it for PostgreSQL (INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL,
    datetime('now') -> NOW()), so both engines get correct DDL from the same
    source.

    It previously carried two full copies — a PostgreSQL one that raised on
    SQLite, caught by a bare except, and a SQLite one in the handler. Two
    definitions of the same table drift, and the swallowed exception meant a
    genuine DDL failure looked identical to the normal path.
    """
    conn = get_db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemedicine_sessions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id        INTEGER NOT NULL,
                pet_id          INTEGER,
                doctor_name     TEXT,
                scheduled_at    TEXT NOT NULL,
                duration_min    INTEGER DEFAULT 30,
                room_token      TEXT NOT NULL UNIQUE,
                room_url        TEXT NOT NULL,
                status          TEXT DEFAULT 'Scheduled',
                chief_complaint TEXT,
                notes           TEXT,
                prescription_id INTEGER,
                invoice_id      INTEGER,
                created_by      TEXT,
                created_at      TEXT DEFAULT (datetime('now')),
                started_at      TEXT,
                ended_at        TEXT
            )
        """)
        conn.commit()
    except Exception:
        # A real DDL failure now surfaces instead of being swallowed by a
        # second attempt. The route still renders — a broken telemedicine
        # table must not take down the app — but the reason is in the log
        # rather than invisible.
        logger.exception(
            "Could not create telemedicine_sessions — the telemedicine module "
            "will not work until this is resolved")
    finally:
        conn.close()


def _make_room_url(token: str) -> str:
    """Generate a Jitsi Meet URL from a token."""
    return f"https://meet.jit.si/PAH-{token}"


def _random_token(n=12) -> str:
    chars = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(n))


# ── Dashboard ─────────────────────────────────────────────────────────────────

@telemedicine_bp.route("/")
@login_required
def dashboard():
    _ensure_tables()
    conn = get_db()
    today = date.today().isoformat()

    upcoming = conn.execute("""
        SELECT ts.*, o.full_name owner_name, o.phone, o.whatsapp_phone,
               p.pet_name, p.species
        FROM telemedicine_sessions ts
        JOIN owners o ON o.id = ts.owner_id
        LEFT JOIN pets p ON p.id = ts.pet_id
        WHERE ts.status IN ('Scheduled','In Progress')
        ORDER BY ts.scheduled_at
        LIMIT 50
    """).fetchall()

    past = conn.execute("""
        SELECT ts.*, o.full_name owner_name, p.pet_name
        FROM telemedicine_sessions ts
        JOIN owners o ON o.id = ts.owner_id
        LEFT JOIN pets p ON p.id = ts.pet_id
        WHERE ts.status IN ('Completed','Cancelled')
        ORDER BY ts.scheduled_at DESC
        LIMIT 30
    """).fetchall()

    stats = {
        "total":      conn.execute("SELECT COUNT(*) FROM telemedicine_sessions").fetchone()[0],
        "scheduled":  conn.execute("SELECT COUNT(*) FROM telemedicine_sessions WHERE status='Scheduled'").fetchone()[0],
        "completed":  conn.execute("SELECT COUNT(*) FROM telemedicine_sessions WHERE status='Completed'").fetchone()[0],
        "today":      conn.execute(
            "SELECT COUNT(*) FROM telemedicine_sessions WHERE SUBSTRING(scheduled_at::text,1,10)=?", (today,)
        ).fetchone()[0],
    }

    conn.close()
    return render_template("telemedicine/dashboard.html",
                           upcoming=upcoming, past=past, stats=stats, active="telemedicine")


# ── New Session ───────────────────────────────────────────────────────────────

@telemedicine_bp.route("/new", methods=["GET", "POST"])
@login_required
def new_session():
    _ensure_tables()
    conn = get_db()

    if request.method == "POST":
        owner_id        = request.form.get("owner_id")
        pet_id          = request.form.get("pet_id") or None
        doctor_name     = request.form.get("doctor_name", "").strip()
        scheduled_at    = request.form.get("scheduled_at", "")
        duration_min    = int(request.form.get("duration_min") or 30)
        chief_complaint = request.form.get("chief_complaint", "")

        if not owner_id or not scheduled_at:
            flash("Owner and scheduled time are required.", "error")
            conn.close()
            return redirect(url_for("telemedicine.new_session"))

        token    = _random_token(12)
        room_url = _make_room_url(token)

        cur = conn.execute("""
            INSERT INTO telemedicine_sessions
                (owner_id, pet_id, doctor_name, scheduled_at, duration_min,
                 room_token, room_url, status, chief_complaint, created_by)
            VALUES (?,?,?,?,?,?,?,'Scheduled',?,?)
        """, (owner_id, pet_id, doctor_name, scheduled_at, duration_min,
              token, room_url, chief_complaint,
              session.get("user", {}).get("username", "")))
        conn.commit()
        sid = cur.lastrowid
        conn.close()

        flash("Telemedicine session created. Share the room link with the owner.", "success")
        return redirect(url_for("telemedicine.session_detail", sid=sid))

    owners = conn.execute(
        "SELECT id, full_name, phone FROM owners ORDER BY full_name LIMIT 500"
    ).fetchall()
    # Default doctor name from logged-in user
    default_doctor = session.get("user", {}).get("full_name") or session.get("user", {}).get("username", "")
    conn.close()
    return render_template("telemedicine/new_session.html",
                           owners=owners, default_doctor=default_doctor, active="telemedicine")


# ── Session Detail ────────────────────────────────────────────────────────────

@telemedicine_bp.route("/<int:sid>")
@login_required
def session_detail(sid):
    _ensure_tables()
    conn = get_db()
    ts = conn.execute("""
        SELECT ts.*, o.full_name owner_name, o.phone, o.whatsapp_phone,
               o.email, p.pet_name, p.species, p.breed
        FROM telemedicine_sessions ts
        JOIN owners o ON o.id = ts.owner_id
        LEFT JOIN pets p ON p.id = ts.pet_id
        WHERE ts.id = ?
    """, (sid,)).fetchone()
    conn.close()

    if not ts:
        abort(404)

    return render_template("telemedicine/session_detail.html",
                           ts=dict(ts), active="telemedicine")


# ── Start Session ─────────────────────────────────────────────────────────────

@telemedicine_bp.route("/<int:sid>/start", methods=["POST"])
@login_required
def start_session(sid):
    _ensure_tables()
    conn = get_db()
    now = datetime.utcnow().isoformat(timespec='seconds')
    conn.execute("""
        UPDATE telemedicine_sessions
        SET status='In Progress', started_at=?
        WHERE id=?
    """, (now, sid,))
    conn.commit()
    conn.close()
    flash("Session started. Click the room link to open the video call.", "success")
    return redirect(url_for("telemedicine.session_detail", sid=sid))


# ── Pricing ───────────────────────────────────────────────────────────────────

def _telemedicine_price(conn) -> float:
    """Configured telemedicine price from service_catalog, else the fallback.

    The LIKE pattern MUST be a bound parameter. Inlining '%tele%' makes
    psycopg2 read '%t' as a format placeholder and raise — which is exactly
    how this lookup silently returned the fallback price since day one.
    The column is `standard_price`; `price` does not exist on this table.
    """
    try:
        row = conn.execute(
            "SELECT standard_price FROM service_catalog "
            "WHERE LOWER(name) LIKE ? AND is_active=1 "
            "ORDER BY sort_order, id LIMIT 1",
            ("%tele%",),
        ).fetchone()
    except Exception:
        logger.exception("service_catalog telemedicine price lookup failed")
        return TELEMEDICINE_FALLBACK_PRICE
    if not row or row["standard_price"] is None:
        logger.warning("No active service_catalog entry matching '%%tele%%'; "
                       "using fallback price %s", TELEMEDICINE_FALLBACK_PRICE)
        return TELEMEDICINE_FALLBACK_PRICE
    return float(row["standard_price"])


# ── Complete Session ──────────────────────────────────────────────────────────

@telemedicine_bp.route("/<int:sid>/complete", methods=["POST"])
@login_required
def complete_session(sid):
    _ensure_tables()
    conn = get_db()
    notes = request.form.get("notes", "")

    ts = conn.execute("SELECT * FROM telemedicine_sessions WHERE id=?", (sid,)).fetchone()
    if not ts:
        conn.close()
        flash("Session not found.", "error")
        return redirect(url_for("telemedicine.dashboard"))

    now = datetime.utcnow().isoformat(timespec='seconds')
    conn.execute("""
        UPDATE telemedicine_sessions
        SET status='Completed', ended_at=?, notes=?
        WHERE id=?
    """, (now, notes, sid))
    conn.commit()

    # Auto-create invoice if duration > 0 and owner set
    inv_id = None
    try:
        duration = int(ts["duration_min"] or 30)
        price = _telemedicine_price(conn)

        if ts["owner_id"] and price > 0:
            inv_data = {
                "owner_id":   ts["owner_id"],
                "pet_id":     ts["pet_id"],
                "issue_date": date.today().isoformat(),
                "doctor_name": ts["doctor_name"] or "",
                "notes":      f"Telemedicine consultation ({duration} min)",
                "created_by": session.get("user", {}).get("username", ""),
            }
            lines = [{
                "description": f"Video Consultation — {ts['doctor_name'] or 'Doctor'} ({duration} min)",
                "quantity":    1,
                "unit_price":  price,
                "total":       price,
                "line_type":   "service",
            }]
            inv_id = db.create_invoice(inv_data, lines)
            conn.execute("UPDATE telemedicine_sessions SET invoice_id=? WHERE id=?", (inv_id, sid))
            conn.commit()
    except Exception:
        # Session IS completed at this point; only the invoice failed.
        # Log it loudly instead of swallowing — this hid a broken query for months.
        logger.exception("Telemedicine auto-invoice failed for session %s", sid)
        flash("Session completed, but the invoice could not be generated. "
              "Please create it manually.", "warning")

    conn.close()

    if inv_id:
        flash(f"Session completed. Invoice #{inv_id} generated.", "success")
        return redirect(url_for("finance.invoice_detail", inv_id=inv_id))
    flash("Session completed successfully.", "success")
    return redirect(url_for("telemedicine.session_detail", sid=sid))


# ── Cancel Session ────────────────────────────────────────────────────────────

@telemedicine_bp.route("/<int:sid>/cancel", methods=["POST"])
@login_required
def cancel_session(sid):
    _ensure_tables()
    conn = get_db()
    conn.execute(
        "UPDATE telemedicine_sessions SET status='Cancelled' WHERE id=?", (sid,)
    )
    conn.commit()
    conn.close()
    flash("Session cancelled.", "success")
    return redirect(url_for("telemedicine.dashboard"))


# ── Share Link (JSON) ─────────────────────────────────────────────────────────

@telemedicine_bp.route("/<int:sid>/share", methods=["POST"])
@login_required
def share_link(sid):
    """Send the room URL to the owner via WhatsApp."""
    conn = get_db()
    ts = conn.execute("""
        SELECT ts.*, o.full_name owner_name, o.whatsapp_phone
        FROM telemedicine_sessions ts
        JOIN owners o ON o.id = ts.owner_id
        WHERE ts.id = ?
    """, (sid,)).fetchone()
    conn.close()

    if not ts or not ts["whatsapp_phone"]:
        flash("Owner has no WhatsApp number registered.", "warning")
        return redirect(url_for("telemedicine.session_detail", sid=sid))

    try:
        from blueprints.whatsapp.routes import _send_and_log
        msg = (
            f"Dear {ts['owner_name']},\n"
            f"Your video consultation is scheduled for {str(ts['scheduled_at'])[:16]}.\n\n"
            f"Join here:\n{ts['room_url']}\n\n"
            f"No app download needed — works in any browser.\n"
            f"Aleefy"
        )
        _send_and_log(ts["whatsapp_phone"], msg,
                      owner_id=ts["owner_id"],
                      template_name="telemedicine_invite")
        flash(f"Room link sent to {ts['whatsapp_phone']} via WhatsApp.", "success")
    except Exception as e:
        flash(f"Could not send WhatsApp: {e}", "warning")

    return redirect(url_for("telemedicine.session_detail", sid=sid))


# ── Pets JSON (for owner select) ──────────────────────────────────────────────

@telemedicine_bp.route("/api/pets/<int:owner_id>")
@login_required
def api_pets(owner_id):
    conn = get_db()
    pets = conn.execute(
        "SELECT id, pet_name, species FROM pets WHERE owner_id=? ORDER BY pet_name", (owner_id,)
    ).fetchall()
    conn.close()
    return jsonify({"pets": [dict(p) for p in pets]})
