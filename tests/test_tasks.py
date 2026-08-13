# -*- coding: utf-8 -*-
"""Tasks — the fourth icon he named, which existed nowhere.

"أدوس على أيقونة أعمل مهمة" — alongside History, Invoices and Attachments.
Three of those four shipped; a repo-wide search for task/todo/مهام matched
docs, a payment module and a font file, and nothing else. No table, no route,
no screen. "Call this owner about the lab result" lived on paper.

Planned and Reminders are NOT tasks: the first is the appointments table, the
second is vaccine due-dates. Neither can hold "chase the unpaid invoice".
"""
import io
from datetime import date, timedelta

from conftest import get_csrf


def _owner_and_pet(app, phone="01000000971"):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        oid = conn.execute("INSERT INTO owners(full_name, phone) VALUES(?,?)",
                           ("صاحب المهام", phone)).lastrowid
        pid = conn.execute(
            "INSERT INTO pets(owner_id, pet_name, species, is_active)"
            " VALUES(?,?,?,1)", (oid, "لولو", "Cat")).lastrowid
        conn.commit()
        conn.close()
    return oid, pid


def _tasks(app, owner_id):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM tasks WHERE owner_id=? ORDER BY id", (owner_id,)).fetchall()]
        conn.close()
    return rows


def test_the_tasks_table_exists(app):
    import models.database as db
    with app.app_context():
        conn = db.get_db()
        conn.execute("SELECT id, title, owner_id, status, due_date FROM tasks LIMIT 1")
        conn.close()


def test_a_task_can_be_created_against_a_client(auth_client, app):
    oid, pid = _owner_and_pet(app)
    r = auth_client.post("/visits/exam/api/task",
                         json={"owner_id": oid, "pet_id": pid,
                               "title": "الاتصال بخصوص نتيجة التحليل",
                               "due_date": date.today().isoformat(),
                               "priority": "High"},
                         headers={"X-CSRF-Token": get_csrf(auth_client)})
    assert r.status_code == 200, r.data[:300]
    rows = _tasks(app, oid)
    assert len(rows) == 1
    assert rows[0]["title"] == "الاتصال بخصوص نتيجة التحليل"
    assert rows[0]["status"] == "Open"
    assert rows[0]["priority"] == "High"


def test_a_task_needs_a_title(auth_client, app):
    oid, _ = _owner_and_pet(app, "01000000972")
    r = auth_client.post("/visits/exam/api/task",
                         json={"owner_id": oid, "title": "   "},
                         headers={"X-CSRF-Token": get_csrf(auth_client)})
    assert r.status_code == 400
    assert _tasks(app, oid) == []


def test_ticking_a_task_off_records_who_and_when(auth_client, app):
    oid, _ = _owner_and_pet(app, "01000000973")
    token = get_csrf(auth_client)
    auth_client.post("/visits/exam/api/task",
                     json={"owner_id": oid, "title": "متابعة الفاتورة"},
                     headers={"X-CSRF-Token": token})
    tid = _tasks(app, oid)[0]["id"]

    r = auth_client.post("/visits/exam/api/task",
                         json={"id": tid, "done": True},
                         headers={"X-CSRF-Token": token})
    assert r.status_code == 200
    row = _tasks(app, oid)[0]
    assert row["status"] == "Done"
    assert row["done_at"], "a completed task records no date"
    assert row["done_by"], "a completed task records nobody"


def test_a_task_can_be_un_ticked(auth_client, app):
    """A mis-tap must be reversible without a database edit."""
    oid, _ = _owner_and_pet(app, "01000000974")
    token = get_csrf(auth_client)
    auth_client.post("/visits/exam/api/task",
                     json={"owner_id": oid, "title": "حجز موعد الأشعة"},
                     headers={"X-CSRF-Token": token})
    tid = _tasks(app, oid)[0]["id"]
    for done in (True, False):
        auth_client.post("/visits/exam/api/task", json={"id": tid, "done": done},
                         headers={"X-CSRF-Token": token})
    row = _tasks(app, oid)[0]
    assert row["status"] == "Open"
    assert row["done_at"] is None and row["done_by"] is None


def test_an_overdue_task_is_badged_and_a_future_one_is_not(auth_client, app):
    oid, _ = _owner_and_pet(app, "01000000975")
    token = get_csrf(auth_client)
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()

    auth_client.post("/visits/exam/api/task",
                     json={"owner_id": oid, "title": "متأخرة", "due_date": yesterday},
                     headers={"X-CSRF-Token": token})
    r = auth_client.post("/visits/exam/api/task",
                         json={"owner_id": oid, "title": "لاحقاً", "due_date": tomorrow},
                         headers={"X-CSRF-Token": token})

    badges = r.get_json()["badges"]
    assert badges["tasks"] == 2, "open task count is wrong"
    assert badges["overdue_tasks"] == 1, \
        "expected exactly one overdue task, got %s" % badges["overdue_tasks"]


def test_a_completed_task_stops_counting_as_overdue(auth_client, app):
    oid, _ = _owner_and_pet(app, "01000000976")
    token = get_csrf(auth_client)
    auth_client.post("/visits/exam/api/task",
                     json={"owner_id": oid, "title": "قديمة",
                           "due_date": (date.today() - timedelta(days=5)).isoformat()},
                     headers={"X-CSRF-Token": token})
    tid = _tasks(app, oid)[0]["id"]
    r = auth_client.post("/visits/exam/api/task", json={"id": tid, "done": True},
                         headers={"X-CSRF-Token": token})
    assert r.get_json()["badges"]["overdue_tasks"] == 0


def test_you_cannot_attach_another_clients_animal(auth_client, app):
    oid_a, pid_a = _owner_and_pet(app, "01000000977")
    oid_b, _ = _owner_and_pet(app, "01000000978")
    r = auth_client.post("/visits/exam/api/task",
                         json={"owner_id": oid_b, "pet_id": pid_a, "title": "خطأ"},
                         headers={"X-CSRF-Token": get_csrf(auth_client)})
    assert r.status_code == 400
    assert _tasks(app, oid_b) == []


def test_tasks_require_a_login(client, app):
    oid, _ = _owner_and_pet(app, "01000000979")
    r = client.post("/visits/exam/api/task", json={"owner_id": oid, "title": "x"})
    assert r.status_code in (302, 401, 403)


def test_the_360_view_carries_tasks(auth_client, app):
    oid, _ = _owner_and_pet(app, "01000000980")
    auth_client.post("/visits/exam/api/task",
                     json={"owner_id": oid, "title": "مهمة للعرض"},
                     headers={"X-CSRF-Token": get_csrf(auth_client)})
    d = auth_client.get("/visits/exam/api/owner/%d" % oid).get_json()
    assert any(t["title"] == "مهمة للعرض" for t in d.get("tasks", [])), \
        "the Tasks tab would render empty"


def test_the_screen_has_a_tasks_tab_with_a_badge():
    src = io.open("templates/visits/exam.html", encoding="utf-8").read()
    assert 'data-tab="tasks"' in src, "no Tasks icon in the tab bar"
    assert 'data-panel="tasks"' in src, "no Tasks panel"
    assert 'data-count="overdue_tasks"' in src, "the Tasks icon carries no overdue badge"


def test_the_task_inputs_do_not_ride_along_with_the_visit():
    src = io.open("templates/visits/exam.html", encoding="utf-8").read()
    i = src.index('data-panel="tasks"')
    block = src[i:src.index("</section>", i)]
    assert "name=" not in block, \
        "a task field carries name= and will be posted with the examination"
