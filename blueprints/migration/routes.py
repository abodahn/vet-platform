"""
Data Import — bring a clinic's existing Excel/CSV records into the platform.

Four steps, each one reversible until the last:
    1. upload    the owner picks their own file from their own computer
    2. map       they confirm which column is which (we pre-select a guess)
    3. preview   a dry run that writes nothing and shows exactly what will happen
    4. import    a verified backup, then one transaction

The previous version of this file read fixed filenames out of a hardcoded
developer path and had no preview, so it could not be handed to a customer.
"""
import json
import logging
import os
import time
import uuid

from flask import (
    Response, current_app, flash, redirect, render_template, request,
    session, url_for,
)
from werkzeug.exceptions import RequestEntityTooLarge

from . import migration_bp
from blueprints.auth.routes import role_required
import models.backup as bk
import models.database as db
from migrations import excel_import as xi

logger = logging.getLogger(__name__)

STAGING_SUBDIR = "import_staging"
STAGING_MAX_AGE = 24 * 3600          # uploads left behind by an abandoned wizard
SESSION_KEY = "import_file"
MAPPING_SETTING_PREFIX = "import_map_"

READ_ROLES = ("super_admin", "clinic_owner", "support_admin")
WRITE_ROLES = ("super_admin", "clinic_owner")


# ── staging area ─────────────────────────────────────────────────────────

def _staging_dir() -> str:
    base = current_app.config.get("UPLOADS_PATH") or os.path.join(
        os.path.dirname(current_app.config.get("DATABASE_PATH", "data/x")), "uploads"
    )
    path = os.path.join(base, STAGING_SUBDIR)
    os.makedirs(path, exist_ok=True)
    return path


def _purge_stale_uploads() -> None:
    """Drop staged files older than a day.

    ponytail: swept on upload rather than on a schedule. Ceiling — a site that
    never imports again keeps its last file for good; move this to the
    APScheduler job in app.py if that ever matters.
    """
    cutoff = time.time() - STAGING_MAX_AGE
    try:
        entries = os.listdir(_staging_dir())
    except OSError:
        logger.warning("import staging directory unreadable", exc_info=True)
        return
    for name in entries:
        path = os.path.join(_staging_dir(), name)
        try:
            if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            logger.warning("could not remove stale import file %s", name, exc_info=True)


def _staged_path(token: str, suffix: str = "") -> str | None:
    """Absolute path for a staged file. None if the token is not a plain hex id."""
    if not token or not all(c in "0123456789abcdef" for c in token):
        return None
    return os.path.join(_staging_dir(), f"{token}{suffix}")


def _load_staged():
    """(headers, rows, original filename) for the file in this session.

    Returns (None, None, None) when there is nothing staged — the caller sends
    the user back to step 1 with an explanation.
    """
    info = session.get(SESSION_KEY) or {}
    path = _staged_path(info.get("token", ""), info.get("ext", ""))
    if not path or not os.path.exists(path):
        return None, None, None
    with open(path, "rb") as fh:
        data = fh.read()
    headers, rows = xi.read_table(data, info.get("name", "upload.xlsx"))
    return headers, rows, info.get("name", "")


def _no_file_redirect():
    flash("Your uploaded file is no longer available. Please upload it again. | "
          "لم يعد الملف الذي رفعته متاحاً. من فضلك ارفعه مرة أخرى.", "warning")
    return redirect(url_for("migration.index"))


def _remembered_mapping(headers):
    raw = db.get_setting(MAPPING_SETTING_PREFIX + xi.mapping_signature(headers), "")
    if not raw:
        return None
    try:
        stored = json.loads(raw)
    except ValueError:
        logger.warning("stored import mapping was not valid JSON; ignoring it")
        return None
    return xi.clean_mapping(stored, headers) or None


def _remember_mapping(headers, mapping):
    db.set_setting(
        MAPPING_SETTING_PREFIX + xi.mapping_signature(headers),
        json.dumps({str(k): v for k, v in mapping.items()}),
        category="migration",
        updated_by=session.get("user", {}).get("username", "system"),
    )


def _write_failed_csv(token, failed_rows) -> bool:
    path = _staged_path(token, ".failed.csv")
    if not path:
        return False
    if not failed_rows:
        if os.path.exists(path):
            os.remove(path)
        return False
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        fh.write(xi.failed_rows_csv(failed_rows))
    return True


# ── step 1: choose a file ────────────────────────────────────────────────

@migration_bp.route("/")
@role_required(*READ_ROLES)
def index():
    conn = db.get_db()
    try:
        counts = {}
        for table in ("owners", "pets", "visits"):
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        history = [dict(r) for r in conn.execute(
            "SELECT * FROM audit_log WHERE module='migration' ORDER BY timestamp DESC LIMIT 20"
        ).fetchall()]
    finally:
        conn.close()

    # This page's whole job is to tell you whether it is safe to run a
    # destructive import. Unscoped it read the deployment's archives, so a
    # clinic could be shown a reassuring "last backup 4 hours ago" that
    # belonged to a different database entirely.
    with bk.for_current_clinic():
        latest_backup = bk.get_latest_backup()

    return render_template(
        "migration/index.html",
        platform_counts=counts,
        history=history,
        latest_backup=latest_backup,
        max_mb=int(current_app.config.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024) / 1024 / 1024),
        active="migration",
    )


@migration_bp.route("/upload", methods=["POST"])
@role_required(*READ_ROLES)
def upload():
    max_mb = int(current_app.config.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024) / 1024 / 1024)
    try:
        uploaded = request.files.get("file")
    except RequestEntityTooLarge:
        # This Flask version rejects an over-sized body before the view runs, so
        # the generic 413 page wins and this branch does not fire. Left in place
        # because it is the correct handling if form parsing ever goes lazy
        # again; the friendly message for the common case has to live in a
        # 413 handler in app.py, which this blueprint does not own.
        flash(f"That file is larger than {max_mb} MB. Split it into smaller files and "
              f"import them one at a time. | حجم الملف أكبر من {max_mb} ميجابايت. "
              "قسّمه إلى ملفات أصغر واستوردها واحداً تلو الآخر.", "danger")
        return redirect(url_for("migration.index"))

    if uploaded is None or not uploaded.filename:
        flash("No file was chosen. Click Choose file and pick your Excel or CSV file. | "
              "لم يتم اختيار أي ملف. اضغط «اختيار ملف» واختر ملف إكسل أو ‎CSV.", "warning")
        return redirect(url_for("migration.index"))

    data = uploaded.read()
    filename = os.path.basename(uploaded.filename)

    try:
        headers, rows = xi.read_table(data, filename)
    except xi.SpreadsheetError as exc:
        flash(f"{exc.en} | {exc.ar}", "danger")
        return redirect(url_for("migration.index"))

    _purge_stale_uploads()
    token = uuid.uuid4().hex
    ext = ".xlsx" if filename.lower().endswith(".xlsx") else ".csv"
    path = _staged_path(token, ext)
    with open(path, "wb") as fh:
        fh.write(data)
    session[SESSION_KEY] = {"token": token, "name": filename, "ext": ext}

    remembered = _remembered_mapping(headers)
    mapping = remembered or xi.guess_mapping(headers)

    return render_template(
        "migration/map.html",
        filename=filename,
        headers=headers,
        sample=rows[:3],
        row_count=len(rows),
        mapping=mapping,
        remembered=bool(remembered),
        target_fields=xi.TARGET_FIELDS,
        group_labels=xi.GROUP_LABELS,
        active="migration",
    )


# ── step 3: dry run ──────────────────────────────────────────────────────

@migration_bp.route("/preview", methods=["POST"])
@role_required(*READ_ROLES)
def preview():
    try:
        headers, rows, filename = _load_staged()
    except xi.SpreadsheetError as exc:
        flash(f"{exc.en} | {exc.ar}", "danger")
        return redirect(url_for("migration.index"))
    if headers is None:
        return _no_file_redirect()

    mapping = xi.clean_mapping(
        {k[4:]: v for k, v in request.form.items() if k.startswith("col_")}, headers
    )
    strategy = request.form.get("strategy", "skip")

    if "owner_name" not in mapping.values() and "owner_phone" not in mapping.values():
        flash("Choose which column holds the owner's name or phone number — "
              "records cannot be imported without one of them. | "
              "اختر العمود الذي يحتوي على اسم العميل أو رقم هاتفه؛ "
              "لا يمكن استيراد السجلات بدون أحدهما.", "warning")
        return render_template(
            "migration/map.html", filename=filename, headers=headers,
            sample=rows[:3], row_count=len(rows), mapping=mapping, remembered=False,
            target_fields=xi.TARGET_FIELDS, group_labels=xi.GROUP_LABELS,
            active="migration",
        )

    conn = db.get_db()
    try:
        report = xi.run_import(conn, headers, rows, mapping,
                               strategy=strategy, dry_run=True)
    finally:
        conn.close()

    _remember_mapping(headers, mapping)
    has_failed_csv = _write_failed_csv((session.get(SESSION_KEY) or {}).get("token", ""),
                                       report["failed_rows"])

    return render_template(
        "migration/preview.html",
        filename=filename,
        report=report,
        mapping=mapping,
        headers=headers,
        strategy=strategy,
        has_failed_csv=has_failed_csv,
        field_labels={f[0]: (f[1], f[2]) for f in xi.TARGET_FIELDS},
        active="migration",
    )


# ── step 4: for real ─────────────────────────────────────────────────────

@migration_bp.route("/commit", methods=["POST"])
@role_required(*WRITE_ROLES)
def commit():
    try:
        headers, rows, filename = _load_staged()
    except xi.SpreadsheetError as exc:
        flash(f"{exc.en} | {exc.ar}", "danger")
        return redirect(url_for("migration.index"))
    if headers is None:
        return _no_file_redirect()

    mapping = xi.clean_mapping(
        {k[4:]: v for k, v in request.form.items() if k.startswith("col_")}, headers
    )
    strategy = request.form.get("strategy", "skip")

    # ── the backup gate ──────────────────────────────────────────────────
    # A failed backup stops the import. It used to be a bare call whose
    # TypeError was swallowed into the results page, so every destructive
    # import ran with no backup at all and nobody could tell.
    backup = bk.run_backup()
    if not backup.get("success"):
        reason = backup.get("error") or "unknown error"
        logger.error("import refused: backup failed (%s)", reason)
        flash("Nothing was imported. The safety backup could not be created, so we "
              "stopped before changing any of your data. Ask your administrator to "
              f"check the Backup Manager. Reason: {reason} | "
              "لم يتم استيراد أي شيء. تعذّر إنشاء النسخة الاحتياطية، لذلك توقّفنا قبل "
              "تغيير أي من بياناتك. اطلب من مسؤول النظام مراجعة مدير النسخ الاحتياطي. "
              f"السبب: {reason}", "danger")
        return redirect(url_for("migration.index"))

    username = session.get("user", {}).get("username", "import")

    # One transaction: a failure half way through a file leaves nothing behind.
    conn = db.get_db()
    try:
        with conn:
            report = xi.run_import(conn, headers, rows, mapping,
                                   strategy=strategy, dry_run=False,
                                   created_by=f"import:{username}")
    except Exception as exc:
        logger.exception("import failed and was rolled back")
        flash("The import stopped and every change was undone — your data is exactly "
              "as it was before. Please send this message to support so they can help: "
              f"{exc} | "
              "توقّف الاستيراد وتم التراجع عن كل التغييرات، وبياناتك كما كانت تماماً. "
              f"من فضلك أرسل هذه الرسالة للدعم الفني: {exc}", "danger")
        return redirect(url_for("migration.index"))
    finally:
        conn.close()

    report["backup"] = backup
    counts = report["counts"]
    db.log_audit(
        username=username,
        role=session.get("user", {}).get("role", ""),
        action="data_import",
        module="migration",
        entity_type="import",
        entity_id=(session.get(SESSION_KEY) or {}).get("token", ""),
        details=(f"Imported {filename}: owners +{counts['owners']['created']}/"
                 f"~{counts['owners']['updated']}, pets +{counts['pets']['created']}/"
                 f"~{counts['pets']['updated']}, visits +{counts['visits']['created']}; "
                 f"{report['rows_failed']} rows failed; backup={backup.get('filename')}"),
    )

    has_failed_csv = _write_failed_csv((session.get(SESSION_KEY) or {}).get("token", ""),
                                       report["failed_rows"])

    return render_template(
        "migration/result.html",
        filename=filename,
        report=report,
        backup=backup,
        has_failed_csv=has_failed_csv,
        active="migration",
    )


@migration_bp.route("/failed-rows.csv")
@role_required(*READ_ROLES)
def failed_rows():
    """The rows that did not import, so the owner can fix them and re-run."""
    path = _staged_path((session.get(SESSION_KEY) or {}).get("token", ""), ".failed.csv")
    if not path or not os.path.exists(path):
        return _no_file_redirect()
    with open(path, "r", encoding="utf-8-sig") as fh:
        body = fh.read()
    # utf-8-sig so Excel opens the Arabic columns correctly instead of as mojibake.
    return Response(
        body.encode("utf-8-sig"),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="rows_to_fix.csv"'},
    )
