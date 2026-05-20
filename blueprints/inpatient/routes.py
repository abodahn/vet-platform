"""
Inpatient / Hospitalisation Blueprint
Premium Animal Hospital Platform

Handles pets admitted for in-clinic medical stays: ICU, post-op recovery,
IV therapy, isolation, etc.  Distinct from the boarding module (recreational
stays) — this tracks clinical rounds, medication administration records (MAR),
and generates a discharge summary automatically.
"""

from flask import render_template, request, redirect, url_for, flash, session, jsonify
from datetime import date, datetime
from . import inpatient_bp
import models.database as db
from blueprints.auth.routes import login_required, role_required

# ── Constants ──────────────────────────────────────────────────────────────────
WARDS   = ["General", "ICU", "Isolation", "Post-Op", "Neonatal", "Exotic"]
ROUTES  = ["PO", "IV", "IM", "SC", "Topical", "Nebulisation", "Intranasal"]
STATUSES = ["Admitted", "Critical", "Stable", "Ready for Discharge", "Discharged"]
STATUS_COLORS = {
    "Admitted":             "#2563eb",
    "Critical":             "#dc2626",
    "Stable":               "#16a34a",
    "Ready for Discharge":  "#d97706",
    "Discharged":           "#6b7280",
}


def _ensure_tables(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS inpatient_stays (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            pet_id          INTEGER NOT NULL,
            owner_id        INTEGER NOT NULL,
            visit_id        INTEGER,
            ward            TEXT DEFAULT 'General',
            cage_number     TEXT,
            admitted_by     INTEGER NOT NULL,
            reason          TEXT NOT NULL,
            diagnosis       TEXT,
            treatment_plan  TEXT,
            status          TEXT NOT NULL DEFAULT 'Admitted',
            admitted_at     TEXT DEFAULT (datetime('now')),
            expected_discharge DATE,
            discharged_at   TEXT,
            discharge_notes TEXT,
            daily_rate      NUMERIC(10,2) DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS inpatient_rounds (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            stay_id         INTEGER NOT NULL,
            recorded_by     INTEGER NOT NULL,
            round_time      TEXT DEFAULT (datetime('now')),
            temp_c          REAL,
            heart_rate      INTEGER,
            resp_rate       INTEGER,
            weight_kg       REAL,
            pain_score      INTEGER,
            food_intake     TEXT,
            fluid_input     REAL,
            fluid_output    REAL,
            observations    TEXT,
            treatment_given TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS inpatient_meds (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            stay_id     INTEGER NOT NULL,
            given_by    INTEGER,
            medication  TEXT NOT NULL,
            dose        TEXT,
            route       TEXT DEFAULT 'PO',
            given_at    TEXT DEFAULT (datetime('now')),
            notes       TEXT
        );
    """)
    conn.commit()


@inpatient_bp.before_request
def _init():
    conn = db.get_db()
    _ensure_tables(conn)
    conn.close()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_stay(stay_id: int):
    conn = db.get_db()
    row = conn.execute("""
        SELECT s.*,
               p.pet_name, p.species, p.breed, p.sex, p.dob, p.weight_kg,
               p.allergies, p.chronic_conditions,
               o.full_name  AS owner_name, o.phone AS owner_phone,
               u.full_name  AS admitted_by_name
        FROM inpatient_stays s
        JOIN pets   p ON p.id = s.pet_id
        JOIN owners o ON o.id = s.owner_id
        JOIN users  u ON u.id = s.admitted_by
        WHERE s.id = %s
    """, (stay_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def _nights(admitted_at: str, discharged_at: str = None) -> int:
    try:
        fmt = "%Y-%m-%d"
        start = datetime.fromisoformat(str(admitted_at)[:10])
        end   = datetime.fromisoformat(str(discharged_at)[:10]) if discharged_at \
                else datetime.today()
        return max(0, (end - start).days)
    except Exception:
        return 0


# ── List / Dashboard ───────────────────────────────────────────────────────────

@inpatient_bp.route("/")
@login_required
def dashboard():
    conn = db.get_db()
    status_f = request.args.get("status", "")

    where  = ["s.status != 'Discharged'"] if not status_f else ["s.status = %s"]
    params = [status_f] if status_f else []

    stays = conn.execute(f"""
        SELECT s.*,
               p.pet_name, p.species, p.breed,
               o.full_name AS owner_name, o.phone AS owner_phone,
               u.full_name AS admitted_by_name
        FROM inpatient_stays s
        JOIN pets   p ON p.id = s.pet_id
        JOIN owners o ON o.id = s.owner_id
        JOIN users  u ON u.id = s.admitted_by
        WHERE {' AND '.join(where)}
        ORDER BY
            CASE s.status WHEN 'Critical' THEN 1 WHEN 'Admitted' THEN 2
                          WHEN 'Stable' THEN 3 ELSE 4 END,
            s.admitted_at DESC
    """, params).fetchall()

    stats = conn.execute("""
        SELECT
            COUNT(*) FILTER (WHERE status != 'Discharged')       AS active,
            COUNT(*) FILTER (WHERE status = 'Critical')          AS critical,
            COUNT(*) FILTER (WHERE status = 'Ready for Discharge') AS ready,
            COUNT(*) FILTER (WHERE status = 'Discharged'
                             AND discharged_at::date = CURRENT_DATE) AS discharged_today
        FROM inpatient_stays
    """).fetchone()

    conn.close()
    return render_template("inpatient/dashboard.html",
        active="inpatient",
        stays=[dict(s) for s in stays],
        stats=dict(stats) if stats else {},
        status_f=status_f,
        statuses=STATUSES,
        status_colors=STATUS_COLORS,
    )


# ── Admit new patient ──────────────────────────────────────────────────────────

@inpatient_bp.route("/admit", methods=["GET", "POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "doctor", "nurse")
def admit():
    conn = db.get_db()
    if request.method == "POST":
        f = request.form
        pet_id   = int(f["pet_id"])
        owner_id = int(f["owner_id"])
        try:
            conn.execute("""
                INSERT INTO inpatient_stays
                  (pet_id, owner_id, visit_id, ward, cage_number, admitted_by,
                   reason, diagnosis, treatment_plan, status,
                   expected_discharge, daily_rate)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Admitted',%s,%s)
            """, (
                pet_id, owner_id,
                f.get("visit_id") or None,
                f.get("ward", "General"),
                f.get("cage_number", ""),
                session["user"]["id"],
                f["reason"],
                f.get("diagnosis", ""),
                f.get("treatment_plan", ""),
                f.get("expected_discharge") or None,
                float(f.get("daily_rate", 0)),
            ))
            conn.commit()
            flash("Patient admitted successfully.", "success")
            conn.close()
            return redirect(url_for("inpatient.dashboard"))
        except Exception as e:
            conn.rollback()
            flash(f"Error admitting patient: {e}", "danger")

    # GET — load owners/pets for form
    owners = conn.execute(
        "SELECT id, full_name, phone FROM owners ORDER BY full_name"
    ).fetchall()
    conn.close()
    return render_template("inpatient/admit.html",
        active="inpatient",
        owners=[dict(o) for o in owners],
        wards=WARDS,
        today=date.today().isoformat(),
    )


# ── Stay detail ────────────────────────────────────────────────────────────────

@inpatient_bp.route("/<int:stay_id>")
@login_required
def stay_detail(stay_id: int):
    stay = _get_stay(stay_id)
    if not stay:
        flash("Stay record not found.", "danger")
        return redirect(url_for("inpatient.dashboard"))

    conn = db.get_db()
    rounds = conn.execute("""
        SELECT r.*, u.full_name AS recorded_by_name
        FROM inpatient_rounds r
        JOIN users u ON u.id = r.recorded_by
        WHERE r.stay_id = %s
        ORDER BY r.round_time DESC
    """, (stay_id,)).fetchall()

    meds = conn.execute("""
        SELECT m.*, u.full_name AS given_by_name
        FROM inpatient_meds m
        LEFT JOIN users u ON u.id = m.given_by
        WHERE m.stay_id = %s
        ORDER BY m.given_at DESC
    """, (stay_id,)).fetchall()

    conn.close()

    nights = _nights(stay["admitted_at"], stay.get("discharged_at"))
    estimated_cost = nights * float(stay.get("daily_rate") or 0)

    return render_template("inpatient/stay_detail.html",
        active="inpatient",
        stay=stay,
        rounds=[dict(r) for r in rounds],
        meds=[dict(m) for m in meds],
        nights=nights,
        estimated_cost=estimated_cost,
        routes_list=ROUTES,
        statuses=STATUSES,
        status_colors=STATUS_COLORS,
    )


# ── Update status ──────────────────────────────────────────────────────────────

@inpatient_bp.route("/<int:stay_id>/status", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "doctor", "nurse")
def update_status(stay_id: int):
    new_status = request.form.get("status", "")
    if new_status not in STATUSES:
        flash("Invalid status.", "danger")
        return redirect(url_for("inpatient.stay_detail", stay_id=stay_id))

    conn = db.get_db()
    conn.execute(
        "UPDATE inpatient_stays SET status=%s, updated_at=NOW() WHERE id=%s",
        (new_status, stay_id)
    )
    conn.commit()
    conn.close()
    flash(f"Status updated to {new_status}.", "success")
    return redirect(url_for("inpatient.stay_detail", stay_id=stay_id))


# ── Add clinical round ─────────────────────────────────────────────────────────

@inpatient_bp.route("/<int:stay_id>/round", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "doctor", "nurse")
def add_round(stay_id: int):
    f = request.form
    conn = db.get_db()
    try:
        conn.execute("""
            INSERT INTO inpatient_rounds
              (stay_id, recorded_by, round_time, temp_c, heart_rate, resp_rate,
               weight_kg, pain_score, food_intake, fluid_input, fluid_output,
               observations, treatment_given)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            stay_id, session["user"]["id"],
            f.get("round_time") or datetime.now().isoformat(timespec="minutes"),
            f.get("temp_c") or None,
            f.get("heart_rate") or None,
            f.get("resp_rate") or None,
            f.get("weight_kg") or None,
            f.get("pain_score") or None,
            f.get("food_intake", ""),
            f.get("fluid_input") or None,
            f.get("fluid_output") or None,
            f.get("observations", ""),
            f.get("treatment_given", ""),
        ))
        conn.commit()
        flash("Round recorded.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}", "danger")
    conn.close()
    return redirect(url_for("inpatient.stay_detail", stay_id=stay_id))


# ── Add medication administration ──────────────────────────────────────────────

@inpatient_bp.route("/<int:stay_id>/med", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "doctor",
               "nurse", "pharmacist")
def add_med(stay_id: int):
    f = request.form
    conn = db.get_db()
    try:
        conn.execute("""
            INSERT INTO inpatient_meds
              (stay_id, given_by, medication, dose, route, given_at, notes)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
        """, (
            stay_id, session["user"]["id"],
            f["medication"],
            f.get("dose", ""),
            f.get("route", "PO"),
            f.get("given_at") or datetime.now().isoformat(timespec="minutes"),
            f.get("notes", ""),
        ))
        conn.commit()
        flash("Medication recorded.", "success")
    except Exception as e:
        conn.rollback()
        flash(f"Error: {e}", "danger")
    conn.close()
    return redirect(url_for("inpatient.stay_detail", stay_id=stay_id))


# ── Discharge ──────────────────────────────────────────────────────────────────

@inpatient_bp.route("/<int:stay_id>/discharge", methods=["POST"])
@role_required("super_admin", "clinic_owner", "branch_manager", "doctor")
def discharge(stay_id: int):
    notes = request.form.get("discharge_notes", "")
    conn  = db.get_db()
    conn.execute("""
        UPDATE inpatient_stays
        SET status='Discharged', discharged_at=NOW(),
            discharge_notes=%s, updated_at=NOW()
        WHERE id=%s AND status != 'Discharged'
    """, (notes, stay_id))
    conn.commit()
    conn.close()
    flash("Patient discharged successfully.", "success")
    return redirect(url_for("inpatient.stay_detail", stay_id=stay_id))


# ── API — pets for an owner (AJAX) ────────────────────────────────────────────

@inpatient_bp.route("/api/owner/<int:owner_id>/pets")
@login_required
def api_owner_pets(owner_id: int):
    conn = db.get_db()
    pets = conn.execute(
        "SELECT id, pet_name, species, breed FROM pets WHERE owner_id=%s ORDER BY pet_name",
        (owner_id,)
    ).fetchall()
    conn.close()
    return jsonify([dict(p) for p in pets])
