"""
Secure File Upload & Serving — Aleefy Platform
All files stored on filesystem, served only through authenticated routes.
"""
import os
import uuid
import mimetypes
import logging
from flask import (
    send_file, request, redirect, url_for, flash, session,
    jsonify, current_app, render_template, abort
)
from werkzeug.utils import secure_filename
from . import uploads_bp
from blueprints.auth.routes import login_required
from models.database import get_db, log_audit

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    "image": {"jpg", "jpeg", "png", "gif", "webp"},
    "document": {"pdf", "doc", "docx", "xls", "xlsx"},
    "all": {"jpg", "jpeg", "png", "gif", "webp", "pdf", "doc", "docx", "xls", "xlsx"},
}

# Allowed entity_type values — validated against this whitelist to prevent path traversal
ALLOWED_ENTITY_TYPES = frozenset(["pet", "visit", "staff", "supplier", "invoice", "lab"])

# ext -> the MIME its magic bytes must agree with. Module scope so both the
# route and save_attachment() check against the same table.
_EXT_MIME_MAP = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "png": "image/png", "gif": "image/gif", "webp": "image/webp",
    # TIFF and BMP added for the imaging module, which accepts both. Without an
    # entry here expected_mime is None and the content check is skipped
    # entirely, so ".tif" was the way past it.
    "tif": "image/tiff", "tiff": "image/tiff", "bmp": "image/bmp",
    "pdf": "application/pdf",
    # Office docs are zip-based (PK header)
    "docx": "application/zip", "xlsx": "application/zip",
    "doc": None, "xls": None,  # legacy binary — no reliable magic-byte check
}

# Magic-byte signatures for MIME validation (no python-magic required)
_MAGIC = {
    b"\xff\xd8\xff":       "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a":             "image/gif",
    b"GIF89a":             "image/gif",
    b"RIFF":               "image/webp",    # partial — webp has RIFF....WEBP
    b"II\x2a\x00":        "image/tiff",     # little-endian (Intel)
    b"MM\x00\x2a":        "image/tiff",     # big-endian (Motorola)
    b"BM":                 "image/bmp",
    b"%PDF":               "application/pdf",
    b"PK\x03\x04":        "application/zip",  # docx/xlsx are zip-based
}

def _validate_mime_from_bytes(file_obj) -> str | None:
    """Read first 16 bytes and return detected MIME type, or None if unrecognised."""
    header = file_obj.read(16)
    file_obj.seek(0)  # rewind for actual save
    for sig, mime in _MAGIC.items():
        if header[:len(sig)] == sig:
            # Extra check: WEBP has 'WEBP' at offset 8
            if sig == b"RIFF":
                if header[8:12] != b"WEBP":
                    return None  # Not a WEBP — skip
            return mime
    return None

# Entity → which roles can access
_ACCESS = {
    "pet":      ("super_admin","clinic_owner","branch_manager","doctor","nurse","reception"),
    "visit":    ("super_admin","clinic_owner","branch_manager","doctor","nurse"),
    "staff":    ("super_admin","clinic_owner","branch_manager","hr"),
    "supplier": ("super_admin","clinic_owner","branch_manager","inventory_mgr","finance"),
    "invoice":  ("super_admin","clinic_owner","branch_manager","finance","reception"),
    "lab":      ("super_admin","clinic_owner","branch_manager","doctor","nurse"),
}


def _allowed_file(filename: str, ftype: str = "all") -> bool:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in ALLOWED_EXTENSIONS.get(ftype, ALLOWED_EXTENSIONS["all"])


def _upload_path() -> str:
    return current_app.config.get("UPLOADS_PATH", "data/uploads")


def _can_access(entity_type: str) -> bool:
    role = session.get("user", {}).get("role", "")
    allowed = _ACCESS.get(entity_type, ())
    return role in allowed or role == "super_admin"


# ── the one place a file is validated and stored ─────────────────────────
# Extracted so callers OUTSIDE this blueprint (the exam screen attaches a photo
# as part of saving a visit) go through the same magic-byte check, the same
# extension whitelist and the same UUID naming. A second copy of a security
# control is a second copy to forget to fix.

def save_attachment(f, entity_type, entity_id, category="general", caption="",
                    username=""):
    """Validate and store one uploaded file. Returns {'ok':bool,'error':str,'id':int}."""
    if entity_type not in ALLOWED_ENTITY_TYPES:
        return {"ok": False, "error": "Invalid entity type"}
    if not f or not getattr(f, "filename", ""):
        return {"ok": False, "error": "No file selected"}
    if not _allowed_file(f.filename):
        return {"ok": False, "error": "File type not allowed"}

    detected_mime = _validate_mime_from_bytes(f.stream)
    ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
    expected_mime = _EXT_MIME_MAP.get(ext)
    # The content must MATCH what the extension claims — not merely fail to
    # contradict it. _validate_mime_from_bytes returns None for anything it
    # does not recognise, and the old guard required a truthy detected_mime
    # before comparing, so every unrecognised file passed: a .png containing
    # "<?php ... ?>" was accepted and stored. Only doc/xls map to None here,
    # because legacy binary Office files have no reliable magic bytes.
    if expected_mime and detected_mime != expected_mime:
        logger.warning("Upload rejected: ext=%s expected=%s detected=%s user=%s",
                       ext, expected_mime, detected_mime, username)
        return {"ok": False,
                "error": "File content does not match its extension"}

    stored_name = "%s.%s" % (uuid.uuid4().hex, ext)
    if os.sep in stored_name or "/" in stored_name or "\\" in stored_name:
        return {"ok": False, "error": "Invalid filename generated"}

    folder = os.path.join(_upload_path(), entity_type)
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, stored_name)
    f.save(filepath)
    size = os.path.getsize(filepath)

    final_mime = (detected_mime or mimetypes.guess_type(f.filename)[0]
                  or "application/octet-stream")
    conn = get_db()
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO attachments(entity_type,entity_id,filename,original_name,
                   mime_type,size_bytes,category,caption,uploaded_by)
                   VALUES(?,?,?,?,?,?,?,?,?)""",
                (entity_type, entity_id, stored_name, secure_filename(f.filename),
                 final_mime, size, category, caption, username))
            att_id = cur.lastrowid
    finally:
        conn.close()

    log_audit(username=username, role="", action="file_upload", module="uploads",
              entity_type=entity_type, entity_id=str(att_id),
              details="Uploaded %s for %s:%s" % (f.filename, entity_type, entity_id))
    return {"ok": True, "error": "", "id": att_id}


@uploads_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    entity_type = request.form.get("entity_type", "")
    entity_id   = request.form.get("entity_id", "")

    if entity_type not in ALLOWED_ENTITY_TYPES:
        logger.warning("Upload blocked: invalid entity_type=%r from user=%s",
                       entity_type, session.get("user", {}).get("username"))
        return jsonify({"error": "Invalid entity type"}), 400
    if not _can_access(entity_type):
        return jsonify({"error": "Access denied"}), 403

    result = save_attachment(
        request.files.get("file"), entity_type, entity_id,
        category=request.form.get("category", "general"),
        caption=request.form.get("caption", ""),
        username=session["user"]["username"])
    if not result["ok"]:
        flash(result["error"] + ".", "error")
    return redirect(request.referrer or "/")


def _safe_attachment_path(att) -> str | None:
    """Validate DB-stored entity_type and filename before building a filesystem path.
    Returns the absolute path, or None if validation fails.
    """
    entity_type = att["entity_type"]
    filename    = att["filename"]
    # entity_type must be in the known whitelist
    if entity_type not in ALLOWED_ENTITY_TYPES:
        logger.warning(f"serve: entity_type not in whitelist: {entity_type!r}")
        return None
    # filename must not contain path separators or parent-dir traversal
    if os.sep in filename or "/" in filename or "\\" in filename or ".." in filename:
        logger.warning(f"serve: unsafe filename in DB: {filename!r}")
        return None
    return os.path.join(_upload_path(), entity_type, filename)


@uploads_bp.route("/file/<int:att_id>")
@login_required
def serve(att_id):
    conn = get_db()
    att = conn.execute("SELECT * FROM attachments WHERE id=?", (att_id,)).fetchone()
    conn.close()
    if not att:
        abort(404)
    if not _can_access(att["entity_type"]):
        abort(403)

    filepath = _safe_attachment_path(att)
    if not filepath:
        abort(400)
    if not os.path.exists(filepath):
        abort(404)
    return send_file(filepath,
                     mimetype=att["mime_type"] or "application/octet-stream",
                     download_name=att["original_name"] or att["filename"])


@uploads_bp.route("/delete/<int:att_id>", methods=["POST"])
@login_required
def delete(att_id):
    conn = get_db()
    att = conn.execute("SELECT * FROM attachments WHERE id=?", (att_id,)).fetchone()
    if att and _can_access(att["entity_type"]):
        filepath = _safe_attachment_path(att)
        if filepath and os.path.exists(filepath):
            os.remove(filepath)
        with conn:
            conn.execute("DELETE FROM attachments WHERE id=?", (att_id,))
        log_audit(username=session["user"]["username"], role=session["user"]["role"],
                  action="file_delete", module="uploads", entity_id=str(att_id))
        flash("File deleted.", "success")
    conn.close()
    return redirect(request.referrer or "/")


@uploads_bp.route("/list/<entity_type>/<int:entity_id>")
@login_required
def list_attachments(entity_type, entity_id):
    if entity_type not in ALLOWED_ENTITY_TYPES or not _can_access(entity_type):
        return jsonify([])
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM attachments WHERE entity_type=? AND entity_id=? ORDER BY uploaded_at DESC",
        (entity_type, str(entity_id))).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
