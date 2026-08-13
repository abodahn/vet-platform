"""Service / Price Catalog — Aleefy Platform"""
import csv
import io
import logging

from flask import (
    render_template, request, redirect, url_for, flash, session, jsonify,
    Response,
)
from . import catalog_bp
from blueprints.auth.routes import login_required
import models.database as db
import models.money as money

logger = logging.getLogger(__name__)

# The columns of the round-trip file. Export writes these, import reads them,
# so a clinic can download what it has, edit the prices in Excel, and put it
# back.
_CSV_COLUMNS = ["code", "name", "name_ar", "category", "standard_price",
                "tax_rate", "duration_min", "species", "description",
                "is_active"]

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

    # Where each service is actually used: invoice lines carry the service NAME,
    # not its id — service_catalog has no foreign key pointing at it from
    # anywhere. Match on description, which is exactly what create_invoice
    # writes. One grouped query, not one per row.
    # ponytail: MAX(invoice_id) stands in for "latest" — ids are monotonic here.
    #           Needs an ORDER BY issue_date join only if invoices ever backfill.
    conn = db.get_db()
    usage = {
        r["description"]: (r["uses"], r["last_invoice_id"])
        for r in conn.execute(
            "SELECT description, COUNT(*) AS uses, MAX(invoice_id) AS last_invoice_id "
            "FROM invoice_lines GROUP BY description"
        ).fetchall()
    }
    conn.close()

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
        usage=usage,
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


# ─────────────────────────────────────────────
# THE CLINIC'S OWN PRICE LIST
#
# Until now a clinic could only add services one form at a time, and the ~23
# services a fresh database seeds itself with are OUR prices, not theirs. A
# practice with 200 services was looking at 200 forms before it could quote a
# single correct figure — which is why the demo screenshots show Biochemistry
# Panel at 750 rather than anything the clinic charges.
# ─────────────────────────────────────────────

@catalog_bp.route("/export.csv")
@login_required
def export_csv():
    """The current catalog, in the shape import expects.

    Export before import on purpose: the reliable way to bulk-EDIT prices is to
    download what is there, change the numbers in Excel, and put the file back.
    Without this, import can only ever add.
    """
    services = db.list_services(active_only=False)
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=_CSV_COLUMNS, extrasaction="ignore")
    w.writeheader()
    for s in services:
        row = {k: (s.get(k) if s.get(k) is not None else "") for k in _CSV_COLUMNS}
        w.writerow(row)

    # utf-8-sig: Excel on a Windows machine in Cairo opens a plain UTF-8 CSV
    # and renders every Arabic name as mojibake. The BOM is what makes it
    # readable, and this file exists to be opened in Excel.
    data = buf.getvalue().encode("utf-8-sig")
    return Response(data, mimetype="text/csv; charset=utf-8", headers={
        "Content-Disposition": 'attachment; filename="aleefy-price-list.csv"',
    })


def _decode_upload(raw: bytes) -> str:
    """Whatever Excel produced. Never raises."""
    for enc in ("utf-8-sig", "utf-8", "cp1256", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


@catalog_bp.route("/import", methods=["POST"])
@login_required
def import_csv():
    if not _is_manager():
        flash("Access denied.", "error")
        return redirect(url_for("catalog.index"))

    up = request.files.get("file")
    if not up or not up.filename:
        flash("Choose a CSV file first.", "error")
        return redirect(url_for("catalog.index"))

    text = _decode_upload(up.read())
    try:
        # Sniff the delimiter: an Arabic Windows Excel writes semicolons, an
        # English one writes commas, and picking wrong turns every row into a
        # single column named "code".
        sample = text[:4096]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        fields = [(f or "").strip().lower() for f in (reader.fieldnames or [])]
    except Exception:
        logger.exception("price list could not be parsed")
        flash("That file could not be read as a CSV.", "error")
        return redirect(url_for("catalog.index"))

    if "name" not in fields:
        flash("The file needs a 'name' column. Export the current list to see "
              "the expected columns.", "error")
        return redirect(url_for("catalog.index"))

    # Existing services, so a re-import UPDATES rather than duplicating. Code
    # wins when present because it is the clinic's own identifier; otherwise
    # the name, compared case- and space-insensitively.
    existing = db.list_services(active_only=False)
    by_code = {(s.get("code") or "").strip().upper(): s
               for s in existing if (s.get("code") or "").strip()}
    by_name = {" ".join((s.get("name") or "").lower().split()): s for s in existing}

    created = updated = 0
    problems = []

    for n, raw_row in enumerate(reader, start=2):   # row 1 is the header
        row = {(k or "").strip().lower(): (v or "").strip()
               for k, v in raw_row.items() if k is not None}
        name = row.get("name", "")
        if not name:
            continue                                 # blank line at the end

        price, price_err = money.form_amount(row.get("standard_price"), "price")
        if price_err:
            problems.append("Row %d (%s): %s" % (n, name, price_err))
            continue
        tax, tax_err = money.form_amount(row.get("tax_rate"), "tax rate")
        if tax_err:
            problems.append("Row %d (%s): %s" % (n, name, tax_err))
            continue

        code = row.get("code", "").upper()
        match = by_code.get(code) if code else None
        if match is None:
            match = by_name.get(" ".join(name.lower().split()))

        try:
            duration = int(float(row.get("duration_min") or 0))
        except ValueError:
            duration = 0

        active = row.get("is_active", "1").strip().lower()
        payload = {
            "id": match["id"] if match else None,
            "code": code or None,
            "name": name,
            "name_ar": row.get("name_ar", ""),
            "category": row.get("category") or "Consultation",
            "description": row.get("description", ""),
            "standard_price": price,
            "tax_rate": tax,
            "duration_min": duration,
            "species": row.get("species") or "All",
            "is_active": 0 if active in ("0", "no", "false", "inactive", "لا") else 1,
            "sort_order": 0,
        }
        try:
            svc_id = db.upsert_service(payload)
        except Exception as exc:
            # One bad row must not abandon the other 199.
            logger.warning("price list row %d rejected: %s", n, exc)
            problems.append("Row %d (%s): %s" % (n, name, exc))
            continue

        if match:
            updated += 1
        else:
            created += 1
            # Register it, so a file that lists the same service twice updates
            # the first row instead of leaving the clinic with a duplicate pair
            # and two different prices for one thing.
            by_name[" ".join(name.lower().split())] = {"id": svc_id}
            if code:
                by_code[code] = {"id": svc_id}

    db.log_audit(
        username=session["user"]["username"],
        role=session["user"]["role"],
        action="price_list_imported",
        module="catalog",
        entity_type="service_catalog",
        entity_id="",
        details="%s: +%d new, %d updated, %d rejected"
                % (up.filename, created, updated, len(problems)),
    )

    if created or updated:
        flash("Price list loaded: %d new, %d updated." % (created, updated), "success")
    if problems:
        # Named rows, not a count — "12 rows failed" is not something anybody
        # can act on with a 200-line spreadsheet in front of them.
        flash("These rows were skipped — everything else was saved. "
              + " | ".join(problems[:10])
              + (" …and %d more" % (len(problems) - 10) if len(problems) > 10 else ""),
              "error")
    elif not created and not updated:
        flash("Nothing in that file had a service name.", "error")
    return redirect(url_for("catalog.index"))
