"""Service / Price Catalog — Aleefy Platform"""
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from . import catalog_bp
from blueprints.auth.routes import login_required
import models.database as db

_MANAGER_ROLES = ("super_admin", "clinic_owner", "branch_manager", "finance")

def _is_manager():
    return session.get("user", {}).get("role") in _MANAGER_ROLES


@catalog_bp.route("/")
@login_required
def index():
    category = request.args.get("category", "")
    search   = request.args.get("q", "")
    show_all = request.args.get("all", "0") == "1"

    services  = db.list_services(category=category, active_only=not show_all)
    if search:
        q = search.lower()
        services = [s for s in services if q in s["name"].lower() or q in (s.get("code") or "").lower()]

    categories = db.service_categories() or [
        "Consultation","Vaccination","Laboratory","Surgery",
        "Grooming","Boarding","Treatment","Hospitalization"
    ]
    return render_template(
        "catalog/index.html",
        active="catalog",
        services=services,
        categories=categories,
        selected_cat=category,
        search=search,
        show_all=show_all,
        is_manager=_is_manager(),
    )


@catalog_bp.route("/save", methods=["POST"])
@login_required
def save():
    if not _is_manager():
        flash("Access denied.", "error")
        return redirect(url_for("catalog.index"))

    data = {
        "id":             request.form.get("svc_id") or None,
        "code":           request.form.get("code", "").strip().upper() or None,  # NULL not "" to allow multiple codeless services
        "name":           request.form.get("name", "").strip(),
        "name_ar":        request.form.get("name_ar", "").strip(),
        "category":       request.form.get("category", "Consultation"),
        "description":    request.form.get("description", "").strip(),
        "standard_price": request.form.get("standard_price", 0),
        "tax_rate":       request.form.get("tax_rate", 0),
        "duration_min":   request.form.get("duration_min", 0),
        "species":        request.form.get("species", "All"),
        "is_active":      1 if request.form.get("is_active") else 0,
        "sort_order":     request.form.get("sort_order", 0),
    }
    if not data["name"]:
        flash("Service name is required.", "error")
        return redirect(url_for("catalog.index"))

    try:
        svc_id = db.upsert_service(data)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("upsert_service failed: %s", e)
        msg = str(e)
        if "unique" in msg.lower() or "duplicate" in msg.lower():
            flash(f"A service with code '{data['code']}' already exists. Use a different code or leave it blank.", "error")
        else:
            flash(f"Could not save service: {msg}", "error")
        return redirect(url_for("catalog.index"))
    action = "updated" if data["id"] else "created"
    db.log_audit(
        username=session["user"]["username"],
        role=session["user"]["role"],
        action=f"service_{action}",
        module="catalog",
        entity_type="service_catalog",
        entity_id=str(svc_id),
        details=data["name"],
    )
    flash(f"Service '{data['name']}' {action} successfully.", "success")
    return redirect(url_for("catalog.index", category=data["category"]))


@catalog_bp.route("/<int:svc_id>/toggle", methods=["POST"])
@login_required
def toggle(svc_id):
    if not _is_manager():
        flash("Access denied.", "error")
        return redirect(url_for("catalog.index"))
    svc = db.get_service(svc_id)
    if svc:
        db.upsert_service({**svc, "id": svc_id, "is_active": 0 if svc["is_active"] else 1})
        flash(f"Service {'deactivated' if svc['is_active'] else 'activated'}.", "success")
    return redirect(url_for("catalog.index"))


@catalog_bp.route("/api/list")
@login_required
def api_list():
    """JSON endpoint used by invoice form to load services."""
    category = request.args.get("category", "")
    services = db.list_services(category=category, active_only=True)
    return jsonify(services)


@catalog_bp.route("/api/get/<int:svc_id>")
@login_required
def api_get(svc_id):
    svc = db.get_service(svc_id)
    if not svc:
        return jsonify({"error": "Not found"}), 404
    return jsonify(svc)
