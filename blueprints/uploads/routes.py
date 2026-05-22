"""
Secure File Upload & Serving — Aleefy Platform
All files stored on filesystem, served only through authenticated routes.
"""
import os
import uuid
import mimetypes
from flask import (
    send_file, request, redirect, url_for, flash, session,
    jsonify, current_app, render_template, abort
)
from werkzeug.utils import secure_filename
from . import uploads_bp
from blueprints.auth.routes import login_required
from models.database import get_db, log_audit

ALLOWED_EXTENSIONS = {
    "image": {"jpg", "jpeg", "png", "gif", "webp"},
    "document": {"pdf", "doc", "docx", "xls", "xlsx"},
    "all": {"jpg", "jpeg", "png", "gif", "webp", "pdf", "doc", "docx", "xls", "xlsx"},
}

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


@uploads_bp.route("/upload", methods=["POST"])
@login_required
def upload():
    entity_type = request.form.get("entity_type", "")
    entity_id   = request.form.get("entity_id", "")
    category    = request.form.get("category", "general")
    caption     = request.form.get("caption", "")

    if not _can_access(entity_type):
        return jsonify({"error": "Access denied"}), 403

    if "file" not in request.files:
        flash("No file selected.", "error")
        return redirect(request.referrer or "/")

    f = request.files["file"]
    if not f.filename:
        flash("No file selected.", "error")
        return redirect(request.referrer or "/")

    if not _allowed_file(f.filename):
        flash("File type not allowed.", "error")
        return redirect(request.referrer or "/")

    # Store file
    ext = f.filename.rsplit(".", 1)[-1].lower()
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    folder = os.path.join(_upload_path(), entity_type)
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, stored_name)
    f.save(filepath)
    size = os.path.getsize(filepath)

    # Record in DB
    conn = get_db()
    with conn:
        conn.execute(
            """INSERT INTO attachments(entity_type,entity_id,filename,original_name,
               mime_type,size_bytes,category,caption,uploaded_by)
               VALUES(?,?,?,?,?,?,?,?,?)""",
            (entity_type, entity_id, stored_name,
             secure_filename(f.filename),
             f.content_type or mimetypes.guess_type(f.filename)[0] or "application/octet-stream",
             size, category, caption, session["user"]["username"]))
        att_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.close()

    log_audit(username=session["user"]["username"], role=session["user"]["role"],
              action="file_upload", module="uploads",
              entity_type=entity_type, entity_id=str(att_id),
              details=f"Uploaded {f.filename} for {entity_type}:{entity_id}")

    return redirect(request.referrer or "/")


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

    filepath = os.path.join(_upload_path(), att["entity_type"], att["filename"])
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
        filepath = os.path.join(_upload_path(), att["entity_type"], att["filename"])
        if os.path.exists(filepath):
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
    if not _can_access(entity_type):
        return jsonify([])
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM attachments WHERE entity_type=? AND entity_id=? ORDER BY uploaded_at DESC",
        (entity_type, str(entity_id))).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])
