"""
Legacy XLSX → Platform SQLite Migration
Reads Excel files from C:\vet\ppc_diagnostics_work\data\
and safely imports them into the platform database.
"""
import os, uuid, traceback
from datetime import datetime
from flask import render_template, request, redirect, url_for, session, flash, current_app
from . import migration_bp
from blueprints.auth.routes import role_required
import models.database as db

LEGACY_DATA_DIR = r"C:\vet\ppc_diagnostics_work\data"

# ── helpers ──────────────────────────────────────────────────────────────────

def _xlsx_rows(filename):
    """Read an xlsx file and return list of dicts keyed by header row."""
    path = os.path.join(LEGACY_DATA_DIR, filename)
    if not os.path.exists(path):
        return None, f"File not found: {path}"
    try:
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return [], None
        headers = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
        result = []
        for row in rows[1:]:
            if all(v is None for v in row):
                continue
            result.append(dict(zip(headers, row)))
        wb.close()
        return result, None
    except Exception as e:
        return None, str(e)


def _safe_str(v, default=""):
    if v is None:
        return default
    return str(v).strip()


def _safe_float(v, default=0.0):
    try:
        return float(v) if v is not None else default
    except Exception:
        return default


def _now():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def _log_audit(action, entity_type, entity_id, details):
    try:
        user = session.get("user", {})
        db.log_audit(
            username=user.get("username", "migration"),
            role=user.get("role", "system"),
            action=action,
            module="migration",
            entity_type=entity_type,
            entity_id=str(entity_id),
            details=details,
        )
    except Exception:
        pass


# ── MAIN VIEW ─────────────────────────────────────────────────────────────────

@migration_bp.route("/")
@role_required("super_admin", "clinic_owner", "support_admin")
def index():
    legacy_exists = os.path.isdir(LEGACY_DATA_DIR)
    files_found = {}
    if legacy_exists:
        for fname in ["owners.xlsx", "pets.xlsx", "bookings.xlsx", "services.xlsx", "users.xlsx"]:
            files_found[fname] = os.path.exists(os.path.join(LEGACY_DATA_DIR, fname))

    # Count existing platform records for comparison
    conn = db.get_db()
    counts = {}
    for tbl in ["owners", "pets", "visits", "appointments"]:
        try:
            counts[tbl] = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
        except Exception:
            counts[tbl] = "N/A"
    conn.close()

    # Migration history from audit log
    conn = db.get_db()
    history = conn.execute(
        "SELECT * FROM audit_log WHERE module='migration' ORDER BY timestamp DESC LIMIT 50"
    ).fetchall()
    conn.close()

    return render_template(
        "migration/index.html",
        legacy_exists=legacy_exists,
        legacy_dir=LEGACY_DATA_DIR,
        files_found=files_found,
        platform_counts=counts,
        history=[dict(h) for h in history],
        active="migration",
    )


# ── RUN MIGRATION ─────────────────────────────────────────────────────────────

@migration_bp.route("/run", methods=["POST"])
@role_required("super_admin", "clinic_owner")
def run_migration():
    dry_run = request.form.get("dry_run") == "1"
    report = {
        "owners":  {"imported": 0, "skipped": 0, "duplicate": 0, "failed": 0, "errors": []},
        "pets":    {"imported": 0, "skipped": 0, "duplicate": 0, "failed": 0, "errors": []},
        "bookings":{"imported": 0, "skipped": 0, "duplicate": 0, "failed": 0, "errors": []},
        "services":{"imported": 0, "skipped": 0, "duplicate": 0, "failed": 0, "errors": []},
        "dry_run": dry_run,
        "started_at": _now(),
        "completed_at": None,
    }

    # Auto-backup before migration
    if not dry_run:
        try:
            import models.backup as bk
            bk.run_backup(current_app.config.get("DATABASE_PATH", ""))
        except Exception as e:
            report["backup_error"] = str(e)

    # ── 1. OWNERS ──────────────────────────────────────────────────────────────
    owner_id_map = {}   # legacy_id → platform_id

    rows, err = _xlsx_rows("owners.xlsx")
    if err:
        report["owners"]["errors"].append(f"Cannot read owners.xlsx: {err}")
    elif rows is not None:
        conn = db.get_db()
        for row in rows:
            legacy_id   = _safe_str(row.get("id"))
            owner_name  = _safe_str(row.get("owner_name"))
            phone       = _safe_str(row.get("phone"))
            email       = _safe_str(row.get("email"))
            address     = _safe_str(row.get("address"))
            notes       = _safe_str(row.get("notes"))
            created_at  = _safe_str(row.get("created_at")) or _now()

            if not owner_name:
                report["owners"]["skipped"] += 1
                continue

            # Dedup: match by phone (primary) or name
            existing = None
            if phone:
                existing = conn.execute(
                    "SELECT id FROM owners WHERE phone=? OR whatsapp_phone=?", (phone, phone)
                ).fetchone()
            if not existing:
                existing = conn.execute(
                    "SELECT id FROM owners WHERE full_name=?", (owner_name,)
                ).fetchone()

            if existing:
                owner_id_map[legacy_id] = existing["id"]
                report["owners"]["duplicate"] += 1
                continue

            if dry_run:
                report["owners"]["imported"] += 1
                owner_id_map[legacy_id] = f"(dry-run-{legacy_id})"
                continue

            try:
                with conn:
                    cur = conn.execute(
                        """INSERT INTO owners(full_name, phone, whatsapp_phone, email, address,
                                            preferred_contact, notes, created_by, created_at, updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?)""",
                        (owner_name, phone, phone, email, address,
                         _safe_str(row.get("preferred_contact"), "WhatsApp"),
                         notes, "migration", created_at, created_at)
                    )
                    new_id = cur.lastrowid
                owner_id_map[legacy_id] = new_id
                report["owners"]["imported"] += 1
                _log_audit("legacy_migrated", "owner", new_id,
                           f"Migrated from legacy id={legacy_id}, name={owner_name}")
            except Exception as e:
                report["owners"]["failed"] += 1
                report["owners"]["errors"].append(f"Owner '{owner_name}': {e}")
        conn.close()

    # ── 2. PETS ────────────────────────────────────────────────────────────────
    pet_id_map = {}   # legacy_id → platform_id

    rows, err = _xlsx_rows("pets.xlsx")
    if err:
        report["pets"]["errors"].append(f"Cannot read pets.xlsx: {err}")
    elif rows is not None:
        conn = db.get_db()
        for row in rows:
            legacy_id   = _safe_str(row.get("id"))
            pet_name    = _safe_str(row.get("pet_name"))
            legacy_oid  = _safe_str(row.get("owner_id"))
            platform_oid = owner_id_map.get(legacy_oid)

            if not pet_name:
                report["pets"]["skipped"] += 1
                continue

            # Dedup: same pet_name + owner_id
            existing = None
            if platform_oid and str(platform_oid).isdigit():
                existing = conn.execute(
                    "SELECT id FROM pets WHERE pet_name=? AND owner_id=?",
                    (pet_name, platform_oid)
                ).fetchone()
            if existing:
                pet_id_map[legacy_id] = existing["id"]
                report["pets"]["duplicate"] += 1
                continue

            if dry_run:
                report["pets"]["imported"] += 1
                pet_id_map[legacy_id] = f"(dry-run-{legacy_id})"
                continue

            try:
                owner_id_val = int(platform_oid) if platform_oid and str(platform_oid).isdigit() else None
                created_at   = _safe_str(row.get("created_at")) or _now()
                dob_raw      = _safe_str(row.get("dob"))
                # Normalise dob to YYYY-MM-DD
                dob = None
                if dob_raw:
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                        try:
                            dob = datetime.strptime(dob_raw[:10], fmt).strftime("%Y-%m-%d")
                            break
                        except Exception:
                            pass

                with conn:
                    cur = conn.execute(
                        """INSERT INTO pets(owner_id, pet_name, species, breed, sex, dob,
                                           weight_kg, color, microchip_id, neutered,
                                           allergies, chronic_conditions, notes,
                                           is_active, created_at, updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                        (owner_id_val, pet_name,
                         _safe_str(row.get("species"), "Unknown"),
                         _safe_str(row.get("breed")),
                         _safe_str(row.get("sex")),
                         dob,
                         _safe_float(row.get("weight_kg")),
                         _safe_str(row.get("color")),
                         _safe_str(row.get("microchip_id")),
                         1 if _safe_str(row.get("spayed_neutered","")).lower() in ("yes","true","1") else 0,
                         _safe_str(row.get("allergies")),
                         _safe_str(row.get("chronic_conditions")),
                         _safe_str(row.get("notes")),
                         created_at, created_at)
                    )
                    new_id = cur.lastrowid
                pet_id_map[legacy_id] = new_id
                report["pets"]["imported"] += 1
                _log_audit("legacy_migrated", "pet", new_id,
                           f"Migrated from legacy id={legacy_id}, name={pet_name}")
            except Exception as e:
                report["pets"]["failed"] += 1
                report["pets"]["errors"].append(f"Pet '{pet_name}': {e}")
        conn.close()

    # ── 3. BOOKINGS → VISITS ──────────────────────────────────────────────────
    rows, err = _xlsx_rows("bookings.xlsx")
    if err:
        report["bookings"]["errors"].append(f"Cannot read bookings.xlsx: {err}")
    elif rows is not None:
        conn = db.get_db()

        # Get list of already-migrated visit legacy refs from audit log
        already_migrated = set(
            r[0] for r in conn.execute(
                "SELECT entity_id FROM audit_log WHERE module='migration' AND entity_type='visit'"
            ).fetchall()
        )

        for row in rows:
            legacy_id  = _safe_str(row.get("id"))
            if legacy_id in already_migrated:
                report["bookings"]["duplicate"] += 1
                continue

            legacy_oid = _safe_str(row.get("owner_id"))
            legacy_pid = _safe_str(row.get("pet_id"))
            platform_oid = owner_id_map.get(legacy_oid)
            platform_pid = pet_id_map.get(legacy_pid)

            appt_start = _safe_str(row.get("appointment_start"))
            status_raw = _safe_str(row.get("status"), "Completed")
            # Map legacy statuses → platform visit status
            visit_status = "Completed" if status_raw in ("Completed","completed") else "Open"

            visit_type_raw = _safe_str(row.get("appointment_type"), "Consultation")
            # Normalise to platform allowed types
            type_map = {
                "Consultation": "Consultation", "consultation": "Consultation",
                "Vaccination": "Vaccination",   "vaccination": "Vaccination",
                "Surgery": "Surgery",           "surgery": "Surgery",
                "Grooming": "Wellness",         "grooming": "Wellness",
                "Lab Test": "Wellness",         "lab test": "Wellness",
                "Follow-up": "Follow-up",       "follow-up": "Follow-up",
                "Emergency": "Emergency",       "emergency": "Emergency",
            }
            visit_type = type_map.get(visit_type_raw, "Consultation")

            if dry_run:
                report["bookings"]["imported"] += 1
                continue

            try:
                owner_id_val = int(platform_oid) if platform_oid and str(platform_oid).isdigit() else None
                pet_id_val   = int(platform_pid)  if platform_pid  and str(platform_pid).isdigit()  else None
                created_at   = _safe_str(row.get("created_at")) or _now()
                visit_date   = appt_start[:10] if appt_start else created_at[:10]

                with conn:
                    cur = conn.execute(
                        """INSERT INTO visits(
                              owner_id, pet_id, doctor_name, room,
                              visit_date, visit_type, status,
                              chief_complaint, symptoms, notes,
                              weight_kg, temp_c,
                              soap_subjective, soap_objective, soap_assessment, soap_plan,
                              created_by, created_at, updated_at
                           ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (owner_id_val, pet_id_val,
                         _safe_str(row.get("vet_name")),
                         _safe_str(row.get("room")),
                         visit_date, visit_type, visit_status,
                         _safe_str(row.get("reason")),
                         _safe_str(row.get("symptoms")),
                         _safe_str(row.get("notes")),
                         _safe_float(row.get("visit_weight_kg")),
                         _safe_float(row.get("visit_temp_c")),
                         _safe_str(row.get("symptoms")),       # subjective
                         "",                                   # objective (vitals captured separately)
                         _safe_str(row.get("diagnosis")),      # assessment
                         _safe_str(row.get("treatment_plan")), # plan
                         "migration", created_at, created_at)
                    )
                    visit_id = cur.lastrowid

                # Add diagnosis record if present
                diag_text = _safe_str(row.get("diagnosis"))
                if diag_text and visit_id:
                    try:
                        with conn:
                            conn.execute(
                                """INSERT INTO diagnoses(visit_id, pet_id, diagnosis, severity, created_by, created_at)
                                   VALUES(?,?,?,?,?,?)""",
                                (visit_id, pet_id_val, diag_text, "Moderate", "migration", created_at)
                            )
                    except Exception:
                        pass

                # Add prescription record if present
                rx_text = _safe_str(row.get("prescription"))
                if rx_text and visit_id:
                    try:
                        with conn:
                            prx_cur = conn.execute(
                                """INSERT INTO prescriptions(visit_id, pet_id, owner_id, prescribed_by, status, notes, created_at)
                                   VALUES(?,?,?,?,?,?,?)""",
                                (visit_id, pet_id_val, owner_id_val, _safe_str(row.get("vet_name"), "migration"),
                                 "Active", rx_text, created_at)
                            )
                            prx_id = prx_cur.lastrowid
                            # Single item containing the full rx text
                            conn.execute(
                                """INSERT INTO prescription_items(prescription_id, medication_name, dosage,
                                      frequency, route, quantity, unit, instructions)
                                   VALUES(?,?,?,?,?,?,?,?)""",
                                (prx_id, "Legacy Prescription", "As prescribed",
                                 "As directed", "Oral", 1, "unit", rx_text)
                            )
                    except Exception:
                        pass

                report["bookings"]["imported"] += 1
                _log_audit("legacy_migrated", "visit", legacy_id,
                           f"Migrated booking id={legacy_id}, type={visit_type}, date={visit_date}")

            except Exception as e:
                report["bookings"]["failed"] += 1
                report["bookings"]["errors"].append(f"Booking '{legacy_id}': {e}")
        conn.close()

    # ── 4. SERVICES → service_catalog ─────────────────────────────────────────
    rows, err = _xlsx_rows("services.xlsx")
    if err:
        report["services"]["errors"].append(f"Cannot read services.xlsx: {err}")
    elif rows is not None and not dry_run:
        conn = db.get_db()
        for row in rows:
            name = _safe_str(row.get("name"))
            if not name:
                report["services"]["skipped"] += 1
                continue
            existing = conn.execute("SELECT id FROM service_catalog WHERE name=?", (name,)).fetchone()
            if existing:
                report["services"]["duplicate"] += 1
                continue
            try:
                with conn:
                    conn.execute(
                        """INSERT INTO service_catalog(name, base_price, is_active, created_at)
                           VALUES(?,?,1,?)""",
                        (name, _safe_float(row.get("fee")), _now())
                    )
                report["services"]["imported"] += 1
            except Exception as e:
                report["services"]["failed"] += 1
                report["services"]["errors"].append(f"Service '{name}': {e}")
        conn.close()

    report["completed_at"] = _now()

    # Store summary in audit log
    if not dry_run:
        summary = (f"Migration complete: owners={report['owners']['imported']} imported, "
                   f"pets={report['pets']['imported']} imported, "
                   f"bookings={report['bookings']['imported']} imported")
        _log_audit("migration_complete", "migration", "full", summary)

    return render_template(
        "migration/report.html",
        report=report,
        active="migration",
    )
