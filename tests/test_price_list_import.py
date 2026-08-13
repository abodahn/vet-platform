# -*- coding: utf-8 -*-
"""Loading a clinic's own price list.

"عشان أنا مش مدخل لسه الليستة الخاصة بيا … هندخل الليستة الخاصة بيا كعادة
ويبقى الموضوع سهل، صح كده؟"

The answer was no. The catalog added one service per form, with no import and
no export, and the Data Import wizard covers owners/pets/visits only — its 19
fields include no price, service or category. So the prices in his screenshots
(Biochemistry Panel 750, Basic Bath 300) are the 23 services the database seeds
itself with when the catalog is empty: OUR numbers, not his. A practice with
200 services faced 200 forms before it could quote a single correct figure.
"""
import csv
import io

from conftest import get_csrf


def _upload(auth_client, text, filename="prices.csv", encoding="utf-8-sig"):
    return auth_client.post(
        "/catalog/import",
        data={"file": (io.BytesIO(text.encode(encoding)), filename),
              "_csrf_token": get_csrf(auth_client)},
        content_type="multipart/form-data", follow_redirects=True)


def _service(app, name):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        row = conn.execute(
            "SELECT * FROM service_catalog WHERE name=? ORDER BY id DESC LIMIT 1",
            (name,)).fetchone()
        conn.close()
    return dict(row) if row else None


def test_a_price_list_loads_in_one_go(auth_client, app):
    _upload(auth_client,
            "code,name,name_ar,category,standard_price\n"
            "CON1,Consultation Premium,كشف مميز,Consultation,350\n"
            "XR1,Chest X-Ray,أشعة صدر,Laboratory,600\n")

    a = _service(app, "Consultation Premium")
    assert a and float(a["standard_price"]) == 350
    assert a["name_ar"] == "كشف مميز"
    b = _service(app, "Chest X-Ray")
    assert b and float(b["standard_price"]) == 600


def test_loading_the_same_list_twice_updates_instead_of_duplicating(auth_client, app):
    """A clinic corrects a price and re-uploads. It must not get two rows."""
    import models.database as db
    csv_text = "code,name,category,standard_price\nDNT1,Dental Scaling,Surgery,%s\n"
    _upload(auth_client, csv_text % "400")
    _upload(auth_client, csv_text % "480")

    with app.app_context():
        conn = db.get_db()
        rows = conn.execute(
            "SELECT standard_price FROM service_catalog WHERE code=?", ("DNT1",)).fetchall()
        conn.close()
    assert len(rows) == 1, "re-importing created a duplicate service"
    assert float(rows[0][0]) == 480, "the corrected price did not take"


def test_a_service_with_no_code_is_matched_on_its_name(auth_client, app):
    import models.database as db
    _upload(auth_client, "name,category,standard_price\nNail Clipping,Grooming,60\n")
    _upload(auth_client, "name,category,standard_price\nnail  clipping,Grooming,75\n")
    with app.app_context():
        conn = db.get_db()
        n = conn.execute(
            "SELECT COUNT(*) FROM service_catalog WHERE LOWER(name) LIKE 'nail%clipping'"
        ).fetchone()[0]
        conn.close()
    assert n == 1, "case and spacing differences created a second service"


def test_one_bad_row_does_not_abandon_the_rest(auth_client, app):
    """200 rows and a typo in row 2 must still load the other 199."""
    r = _upload(auth_client,
                "name,category,standard_price\n"
                "Good Service A,Treatment,100\n"
                "Broken Service,Treatment,1O0\n"
                "Good Service B,Treatment,200\n")
    assert _service(app, "Good Service A") is not None
    assert _service(app, "Good Service B") is not None
    assert _service(app, "Broken Service") is None
    body = r.data.decode("utf-8", errors="replace")
    assert "Broken Service" in body, "the skipped row is not named, so nobody can fix it"


def test_arabic_survives_an_excel_export(auth_client, app):
    """Windows Excel in Cairo writes cp1256, not UTF-8."""
    _upload(auth_client,
            "name,name_ar,category,standard_price\nSpay,تعقيم,Surgery,900\n",
            encoding="cp1256")
    row = _service(app, "Spay")
    assert row and row["name_ar"] == "تعقيم", "Arabic came back as mojibake"


def test_a_semicolon_file_is_understood(auth_client, app):
    """An Arabic Windows Excel writes semicolons."""
    _upload(auth_client,
            "name;category;standard_price\nUltrasound Scan;Laboratory;450\n")
    row = _service(app, "Ultrasound Scan")
    assert row is not None, "a semicolon-delimited export was read as one column"
    assert float(row["standard_price"]) == 450


def test_a_thousands_separator_is_read_as_a_number(auth_client, app):
    _upload(auth_client, 'name,category,standard_price\nOrthopaedic Surgery,Surgery,"1,500"\n')
    row = _service(app, "Orthopaedic Surgery")
    assert row and float(row["standard_price"]) == 1500


def test_a_file_without_a_name_column_is_refused(auth_client, app):
    r = _upload(auth_client, "code,price\nX1,50\n")
    body = r.data.decode("utf-8", errors="replace")
    assert "name" in body.lower()


def test_the_export_round_trips_into_the_import(auth_client, app):
    """The advertised way to bulk-EDIT: download, change, upload."""
    _upload(auth_client, "code,name,category,standard_price\nRT1,Round Trip Service,Treatment,111\n")

    dump = auth_client.get("/catalog/export.csv")
    assert dump.status_code == 200
    text = dump.data.decode("utf-8-sig")
    assert "Round Trip Service" in text

    rows = list(csv.DictReader(io.StringIO(text)))
    assert rows and "name" in rows[0], "the export cannot be fed back in"
    for row in rows:
        if row["code"] == "RT1":
            row["standard_price"] = "222"
    out = io.StringIO()
    w = csv.DictWriter(out, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    _upload(auth_client, out.getvalue())

    assert float(_service(app, "Round Trip Service")["standard_price"]) == 222


def test_import_is_refused_to_staff_who_cannot_price(client, app):
    """Prices are a manager's decision — the same gate as the Add form."""
    import models.database as db
    with app.app_context():
        db.create_user({"username": "nurse_price", "password": "Str0ng!Pass9",
                        "full_name": "Nurse", "role": "nurse"})
    client.post("/auth/login", data={"username": "nurse_price",
                                     "password": "Str0ng!Pass9"},
                follow_redirects=True)
    r = client.post("/catalog/import",
                    data={"file": (io.BytesIO(b"name,standard_price\nHack,1\n"), "x.csv"),
                          "_csrf_token": get_csrf(client)},
                    content_type="multipart/form-data", follow_redirects=True)
    assert _service(app, "Hack") is None, "a non-manager rewrote the price list"
