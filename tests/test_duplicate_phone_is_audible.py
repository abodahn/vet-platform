# -*- coding: utf-8 -*-
"""A re-used mobile number must be SAID, on every screen that creates a client.

Hatem asked for this in as many words: "المفروض لما بدخل نفس رقم التليفون ما
بيقبلش، بيقول له إنت عندك فايل في السيستم قبل كده."

The rule existed but only spoke on one of the three paths:

  CRM form         refused and named the client          — correct
  Exam screen      attached the pet to the existing
                   owner and said NOTHING                — right outcome, silent
  New Visit wizard checked res.ok, and the refusal came
                   back as HTTP 200, so it was swallowed
                   and the wizard carried on under the
                   OTHER client's name                   — wrong client

Silence is the bug in both cases. The receptionist believes she made a new
client; weeks later the history is filed under a name nobody expected.
"""
import io

from conftest import get_csrf


def _mk_owner(app, name, phone):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        cur = conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                           (name, phone))
        conn.commit()
        oid = cur.lastrowid
        conn.close()
    return oid


def _owner_count(app, phone):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        n = conn.execute("SELECT COUNT(*) FROM owners WHERE phone=?", (phone,)).fetchone()[0]
        conn.close()
    return n


def test_the_exam_screen_says_whose_file_the_animal_joined(auth_client, app):
    phone = "01000000921"
    _mk_owner(app, "صاحب الرقم الأصلي", phone)

    token = get_csrf(auth_client)
    r = auth_client.post("/visits/exam/api/client",
                         json={"full_name": "اسم مختلف تماما", "phone": phone,
                               "pet_name": "بسبس", "species": "Cat"},
                         headers={"X-CSRF-Token": token})

    assert r.status_code == 200, "attaching to the existing client should still succeed"
    data = r.get_json()
    assert data.get("joined_existing") == "صاحب الرقم الأصلي", \
        "the screen cannot tell the receptionist whose file the animal went into"
    assert _owner_count(app, phone) == 1, "a second client was created for one number"


def test_a_genuinely_new_number_says_nothing(auth_client, app):
    """The message must not cry wolf on every walk-in."""
    token = get_csrf(auth_client)
    r = auth_client.post("/visits/exam/api/client",
                         json={"full_name": "عميل جديد", "phone": "01000000922",
                               "pet_name": "لولو"},
                         headers={"X-CSRF-Token": token})
    assert r.status_code == 200
    assert not r.get_json().get("joined_existing"), \
        "a brand-new client was reported as an existing file"


def test_the_crm_refusal_carries_a_status_a_script_can_read(auth_client, app):
    """A browser renders the body whatever the status; a script cannot.

    While this was 200 the New Visit wizard could not distinguish a refusal from
    a success, and its `if (!res.ok)` guard never fired.
    """
    phone = "01000000923"
    _mk_owner(app, "المالك الأول", phone)

    token = get_csrf(auth_client)
    r = auth_client.post("/crm/owners/new",
                         data={"full_name": "محاولة تانية", "phone": phone,
                               "_csrf_token": token})

    assert r.status_code == 409, \
        "a refused mobile still returns 200 — every script caller will read it as success"
    body = r.data.decode("utf-8", errors="replace")
    assert "المالك الأول" in body, "the refusal does not name who holds the number"
    assert _owner_count(app, phone) == 1


def test_a_successful_create_is_not_a_409(auth_client, app):
    token = get_csrf(auth_client)
    r = auth_client.post("/crm/owners/new",
                         data={"full_name": "عميل سليم", "phone": "01000000924",
                               "_csrf_token": token})
    assert r.status_code != 409


def test_the_wizard_checks_before_it_creates():
    """Source-level: the pre-check is what produces a message naming the client."""
    src = io.open("templates/workflow/index.html", encoding="utf-8").read()
    i = src.index('$("btnSaveOwner")')
    handler = src[i:src.index("async function selectOwner", i)]
    assert "res.status === 409" in handler, \
        "the wizard cannot recognise a refusal"
    assert handler.index("already") < handler.index('postForm("/crm/owners/new"'), \
        "the wizard still creates first and asks afterwards"
