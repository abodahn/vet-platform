# -*- coding: utf-8 -*-
"""The WhatsApp module, exercised for real.

56 endpoints in `blueprints/whatsapp/` had never been executed by a test, 34
of them write routes. This file drives them the way the browser does — real
HTTP, real CSRF, real session — and then reads the database back to prove the
write landed. A route that returns 200 and writes nothing fails here.

Nothing in this file touches the network. `urllib.request.urlopen` is replaced
process-wide for the duration of every test (module-level autouse fixture), so
a route that grew a real HTTP call would fail loudly rather than quietly
dialling api.wapilot.net from CI. The Wapilot client is intercepted one layer
up, at `WapilotClient._request`, which every one of its 40 methods funnels
through — so each test can assert *what would have been sent*.

SQLite, no PostgreSQL, no network.
"""
import json
import urllib.request
from datetime import date, timedelta

import pytest

import models.database as db
from blueprints.whatsapp.wapilot import WapilotClient


# ─── isolation ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """Any real outbound HTTP from this module is a test failure, not a flake.

    Both `wapilot.py` and `scheduler.py` reach the internet through
    `urllib.request.urlopen`. Replacing the attribute on the module covers
    both, since both look it up at call time.
    """
    def boom(*_a, **_k):
        raise AssertionError("a WhatsApp route tried to make a real network call")
    monkeypatch.setattr(urllib.request, "urlopen", boom)


def _fake_wapilot_response(method, path):
    """Canned Wapilot payloads, shaped like the real v2 API per endpoint."""
    if path.endswith("/messages/stats"):
        return {"data": {"total": 7, "sent": 5, "failed": 1, "queued": 1}}
    if path.endswith("/delay"):
        return {"data": {"wait_between_messages_from": 3,
                         "wait_between_messages_to": 9,
                         "sleep_after_from": 20, "sleep_after_to": 30,
                         "sleep_time_from": 60, "sleep_time_to": 120}}
    if path.endswith("/messages") and method == "GET":
        return {"data": [{"id": "m-1", "chat_id": "201000000001@c.us",
                          "text": "hi", "status": "sent"}]}
    if path == "/campaigns" and method == "GET":
        return {"data": [{"id": "camp-42", "status": "active",
                          "default_message": "Eid discount", "total": 10,
                          "sent": 4, "failed": 0, "queued": 6}]}
    if path == "/campaigns" and method == "POST":
        return {"data": {"id": "camp-new-1"}}
    if path.endswith("/status"):
        return {"data": {"status": "authenticated"}}
    return {"data": {"ok": True}}


@pytest.fixture
def wa(monkeypatch):
    """Wapilot configured, and every outbound call captured instead of sent.

    Returns the capture list. Each entry is the full request the platform
    would have put on the wire — method, path, body and the credentials it
    would have used.
    """
    calls = []

    def fake_request(self, method, path, body=None,
                     content_type="application/json"):
        calls.append({
            "method": method, "path": path, "body": body,
            "content_type": content_type,
            "token": self.token, "instance": self.instance_id,
        })
        return _fake_wapilot_response(method, path), ""

    monkeypatch.setattr(WapilotClient, "_request", fake_request)
    monkeypatch.setenv("WAPILOT_TOKEN", "test-token")
    monkeypatch.setenv("WAPILOT_INSTANCE", "test-instance")
    return calls


@pytest.fixture
def wa_down(monkeypatch):
    """Wapilot configured but the API is refusing — every call returns an error."""
    calls = []

    def fake_request(self, method, path, body=None,
                     content_type="application/json"):
        calls.append({"method": method, "path": path, "body": body})
        return {}, "HTTP 502: Bad Gateway"

    monkeypatch.setattr(WapilotClient, "_request", fake_request)
    monkeypatch.setenv("WAPILOT_TOKEN", "test-token")
    monkeypatch.setenv("WAPILOT_INSTANCE", "test-instance")
    return calls


@pytest.fixture
def wa_unconfigured(monkeypatch, app):
    """No token anywhere — neither environment nor the settings table."""
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    monkeypatch.delenv("WAPILOT_INSTANCE", raising=False)
    with app.app_context():
        conn = db.get_db()
        conn.execute("DELETE FROM settings WHERE category='wapilot'")
        conn.commit()
        conn.close()


# ─── session / CSRF helpers ───────────────────────────────────────────────────

def _login(client, role="super_admin", username="wa_tester"):
    with client.session_transaction() as s:
        s["user"] = {"id": 1, "username": username, "role": role,
                     "full_name": "WhatsApp Tester", "branch_id": 1}
        s["lang"] = "en"


def _csrf(client):
    """The app validates `_csrf_token`; any GET seeds it into the session."""
    from models.security import _CSRF_SESSION_KEY
    client.get("/")
    with client.session_transaction() as s:
        return s.get(_CSRF_SESSION_KEY, "")


def _post(client, url, data, follow=True):
    payload = dict(data)
    payload["_csrf_token"] = _csrf(client)
    return client.post(url, data=payload, follow_redirects=follow)


def _jpost(client, url, body=None, method="POST"):
    """JSON request with the CSRF token in the header, as the module's JS does."""
    return client.open(
        url, method=method,
        data=json.dumps(body or {}),
        content_type="application/json",
        headers={"X-CSRF-Token": _csrf(client)},
    )


def _rows(app, sql, params=()):
    with app.app_context():
        conn = db.get_db()
        out = [dict(r) for r in conn.execute(sql, params).fetchall()]
        conn.close()
    return out


def _exec(app, sql, params=()):
    with app.app_context():
        conn = db.get_db()
        cur = conn.execute(sql, params)
        last = cur.lastrowid
        conn.commit()
        conn.close()
    return last


# ─── seed data ────────────────────────────────────────────────────────────────

MARK = "WATEST"          # every row this module creates carries this marker


@pytest.fixture
def clinic(app):
    """An owner with a WhatsApp number, a pet, and one pending reminder."""
    owner_id = _exec(app,
        "INSERT INTO owners (full_name, phone, whatsapp_phone, email) "
        "VALUES (?,?,?,?)",
        (f"{MARK} Nadia Farid", "01099000011", "201099000011",
         "nadia.watest@example.com"))
    pet_id = _exec(app,
        "INSERT INTO pets (owner_id, pet_name, species) VALUES (?,?,?)",
        (owner_id, f"{MARK}-Simba", "Cat"))
    rid = _exec(app,
        "INSERT INTO reminders (owner_id, pet_id, reminder_type, message, "
        "scheduled_for, status) VALUES (?,?,?,?,?,'Pending')",
        (owner_id, pet_id, "custom",
         f"{MARK} Simba is due for a check-up",
         (date.today() + timedelta(days=1)).isoformat() + " 10:00:00"))
    return {"owner_id": owner_id, "pet_id": pet_id, "reminder_id": rid}


@pytest.fixture
def template(app):
    """One active DB-backed template."""
    name = f"{MARK}-vaccine-due"
    _exec(app, "DELETE FROM whatsapp_templates WHERE name=?", (name,))
    tid = _exec(app,
        "INSERT INTO whatsapp_templates (name, scenario, language, "
        "template_text, variables_json, is_active, is_default) "
        "VALUES (?,?,?,?,?,1,0)",
        (name, "vaccine", "en",
         "Hello {owner}, {pet} is due for a vaccine.", '["owner","pet"]'))
    return {"id": tid, "name": name}


# ═══════════════════════════════════════════════════════════════════════════════
# INSTANCE API — the proxy must keep the token server-side and hit the right path
# ═══════════════════════════════════════════════════════════════════════════════

def test_index_redirects_to_control_center(client, wa):
    _login(client)
    r = client.get("/whatsapp/")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/whatsapp/control")


def test_instance_read_endpoints_call_the_right_wapilot_paths(client, wa):
    _login(client)
    for url, expected_path in [
        ("/whatsapp/api/instance/status",     "/instances/test-instance/status"),
        ("/whatsapp/api/instance/details",    "/instances/test-instance"),
        ("/whatsapp/api/instance/qr",         "/instances/test-instance/qr-code"),
        ("/whatsapp/api/instance/screenshot", "/instances/test-instance/screenshot"),
    ]:
        wa.clear()
        r = client.get(url)
        assert r.status_code == 200, url
        assert r.get_json()["ok"] is True, url
        assert [(c["method"], c["path"]) for c in wa] == [("GET", expected_path)], url


def test_instance_write_endpoints_send_post_and_never_leak_the_token(client, wa):
    _login(client)
    for url, expected_path in [
        ("/whatsapp/api/instance/start",        "/instances/test-instance/start"),
        ("/whatsapp/api/instance/restart",      "/instances/test-instance/restart"),
        ("/whatsapp/api/instance/logout",       "/instances/test-instance/logout"),
        ("/whatsapp/api/instance/troubleshoot", "/instances/test-instance/troubleshoot"),
    ]:
        wa.clear()
        r = _jpost(client, url)
        assert r.status_code == 200, url
        assert wa[0]["method"] == "POST" and wa[0]["path"] == expected_path
        # The token goes to Wapilot, never back to the browser.
        assert "test-token" not in r.get_data(as_text=True), url
        assert wa[0]["token"] == "test-token"


def test_instance_writes_are_role_gated(client, wa):
    """A receptionist cannot restart the clinic's WhatsApp instance."""
    _login(client, role="reception")
    for url in ("/whatsapp/api/instance/start",
                "/whatsapp/api/instance/restart",
                "/whatsapp/api/instance/logout",
                "/whatsapp/api/instance/troubleshoot"):
        wa.clear()
        r = _jpost(client, url)
        assert r.status_code == 302, f"{url} was not role-gated"
        assert wa == [], f"{url} reached Wapilot despite being denied"


def test_troubleshoot_is_owner_only(client, wa):
    """troubleshoot is deliberately narrower than start/restart."""
    _login(client, role="branch_manager")
    r = _jpost(client, "/whatsapp/api/instance/troubleshoot")
    assert r.status_code == 302
    assert wa == []
    # ...but start is allowed for the same role.
    wa.clear()
    assert _jpost(client, "/whatsapp/api/instance/start").status_code == 200
    assert wa[0]["path"].endswith("/start")


def test_queue_settings_put_forwards_the_body(client, wa):
    _login(client)
    r = client.get("/whatsapp/api/instance/queue-settings")
    assert r.status_code == 200
    assert wa[-1]["path"] == "/instances/test-instance/queue-settings"
    assert wa[-1]["method"] == "GET"

    wa.clear()
    body = {"wait_between_messages_from": 5, "wait_between_messages_to": 15}
    r = _jpost(client, "/whatsapp/api/instance/queue-settings", body, method="PUT")
    assert r.status_code == 200
    assert wa[0]["method"] == "PUT"
    assert wa[0]["body"] == body


def test_unconfigured_instance_api_returns_503_not_a_crash(client, wa_unconfigured):
    _login(client)
    r = client.get("/whatsapp/api/instance/status")
    assert r.status_code == 503
    payload = r.get_json()
    assert payload["ok"] is False
    assert "not configured" in payload["error"].lower()


def test_unconfigured_html_page_redirects_to_settings(client, wa_unconfigured):
    _login(client)
    r = client.get("/whatsapp/campaigns")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/whatsapp/settings")


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGES API
# ═══════════════════════════════════════════════════════════════════════════════

def test_list_messages_forwards_query_filters(client, wa):
    _login(client)
    r = client.get("/whatsapp/api/messages?status=failed&limit=25")
    assert r.status_code == 200
    path = wa[0]["path"]
    assert path.startswith("/test-instance/messages?")
    assert "status=failed" in path and "limit=25" in path


def test_message_detail_and_retry(client, wa):
    _login(client)
    assert client.get("/whatsapp/api/messages/msg-77").status_code == 200
    assert wa[-1]["path"] == "/test-instance/messages/msg-77"

    wa.clear()
    r = _jpost(client, "/whatsapp/api/messages/msg-77/retry")
    assert r.status_code == 200
    assert (wa[0]["method"], wa[0]["path"]) == ("POST", "/test-instance/messages/msg-77/retry")


def test_retry_all_is_role_gated_and_forwards_the_filter(client, wa):
    _login(client, role="reception")
    r = _jpost(client, "/whatsapp/api/messages/retry-all", {"status": "failed"})
    assert r.status_code == 302, "retry-all was not role-gated"
    assert wa == []

    _login(client, role="branch_manager")
    wa.clear()
    r = _jpost(client, "/whatsapp/api/messages/retry-all", {"status": "failed"})
    assert r.status_code == 200
    assert wa[0]["path"] == "/test-instance/messages/retry-all"
    assert wa[0]["body"] == {"status": "failed"}


# ═══════════════════════════════════════════════════════════════════════════════
# SEND — every send must leave a row in whatsapp_log
# ═══════════════════════════════════════════════════════════════════════════════

def test_send_center_lists_active_templates(client, template):
    _login(client)
    r = client.get("/whatsapp/send-center")
    assert r.status_code == 200
    assert template["name"] in r.get_data(as_text=True)


def test_send_text_writes_a_log_row_with_what_was_sent(client, app, wa, clinic):
    _login(client)
    phone = "201055000099"
    text = f"{MARK} your results are ready"
    r = _jpost(client, "/whatsapp/api/send/text", {
        "phone": phone, "text": text,
        "owner_id": clinic["owner_id"], "template_name": "results",
    })
    assert r.status_code == 200 and r.get_json()["ok"] is True

    # What went to Wapilot.
    assert wa[0]["path"] == "/test-instance/send-message"
    assert wa[0]["body"] == {"chat_id": f"{phone}@c.us", "text": text}

    # What landed in the database.
    rows = _rows(app, "SELECT * FROM whatsapp_log WHERE phone=?", (phone,))
    assert len(rows) == 1, "send/text returned ok but wrote no log row"
    row = rows[0]
    assert row["message"] == text
    assert row["status"] == "Sent"
    assert row["owner_id"] == clinic["owner_id"]
    assert row["template_name"] == "results"


def test_send_text_records_failure_as_failed_not_sent(client, app, wa_down):
    _login(client)
    phone = "201055000098"
    r = _jpost(client, "/whatsapp/api/send/text",
               {"phone": phone, "text": f"{MARK} undeliverable"})
    assert r.get_json()["ok"] is False

    rows = _rows(app, "SELECT * FROM whatsapp_log WHERE phone=?", (phone,))
    assert len(rows) == 1
    assert rows[0]["status"] == "Failed", "a failed send must not be logged as Sent"
    assert "502" in rows[0]["error"]


def test_send_text_rejects_incomplete_input_without_writing(client, app, wa):
    _login(client)
    before = _rows(app, "SELECT COUNT(*) c FROM whatsapp_log")[0]["c"]
    for body in ({"phone": "", "text": "hi"},
                 {"phone": "201050000001", "text": ""},
                 {}):
        r = _jpost(client, "/whatsapp/api/send/text", body)
        assert r.status_code == 400, body
    assert wa == [], "an invalid send still called Wapilot"
    after = _rows(app, "SELECT COUNT(*) c FROM whatsapp_log")[0]["c"]
    assert after == before, "a rejected send still wrote a log row"


def test_send_text_accepts_a_full_chat_id_unchanged(client, app, wa):
    _login(client)
    r = _jpost(client, "/whatsapp/api/send/text",
               {"phone": "201055000097@c.us", "text": f"{MARK} chat id form"})
    assert r.status_code == 200
    assert wa[0]["body"]["chat_id"] == "201055000097@c.us"


@pytest.mark.parametrize("kind,expected", [
    ("image", "/test-instance/send-image"),
    ("file",  "/test-instance/send-file"),
    ("video", "/test-instance/send-video"),
])
def test_send_media_uploads_the_file_body(client, wa, kind, expected):
    import io
    _login(client)
    r = client.post(
        f"/whatsapp/api/send/{kind}",
        data={"phone": "201055000096", "caption": f"{MARK} caption",
              "media": (io.BytesIO(b"PAYLOAD-BYTES"), f"x.{kind}"),
              "_csrf_token": _csrf(client)},
        content_type="multipart/form-data",
    )
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert wa[0]["path"] == expected
    sent = wa[0]["body"]
    assert b"PAYLOAD-BYTES" in sent
    assert b"201055000096@c.us" in sent
    assert MARK.encode() in sent
    assert wa[0]["content_type"].startswith("multipart/form-data; boundary=")


@pytest.mark.parametrize("kind", ["image", "file", "video"])
def test_send_media_rejects_a_missing_file(client, wa, kind):
    _login(client)
    r = client.post(f"/whatsapp/api/send/{kind}",
                    data={"phone": "201055000095", "_csrf_token": _csrf(client)},
                    content_type="multipart/form-data")
    assert r.status_code == 400
    assert wa == []


def test_send_shortcut_resolves_a_template_and_logs_it(client, app, wa,
                                                       clinic, template):
    """POST /whatsapp/send with only a template id must send the template text."""
    _login(client)
    phone = "201055000094"
    r = _post(client, "/whatsapp/send", {
        "phone": phone, "custom_message": "",
        "owner_id": clinic["owner_id"], "template_id": template["id"],
    })
    assert r.status_code == 200

    assert wa[0]["body"]["text"] == "Hello {owner}, {pet} is due for a vaccine."
    rows = _rows(app, "SELECT * FROM whatsapp_log WHERE phone=?", (phone,))
    assert len(rows) == 1, "/whatsapp/send wrote no log row"
    assert rows[0]["template_name"] == template["name"]
    assert rows[0]["message"] == "Hello {owner}, {pet} is due for a vaccine."
    assert rows[0]["status"] == "Sent"


def test_send_shortcut_refuses_an_empty_message(client, app, wa):
    _login(client)
    before = _rows(app, "SELECT COUNT(*) c FROM whatsapp_log")[0]["c"]
    r = _post(client, "/whatsapp/send", {"phone": "201055000093",
                                         "custom_message": ""})
    assert r.status_code == 200
    assert "Message content is required" in r.get_data(as_text=True)
    assert wa == []
    assert _rows(app, "SELECT COUNT(*) c FROM whatsapp_log")[0]["c"] == before


def test_send_shortcut_refuses_a_missing_phone(client, app, wa):
    _login(client)
    before = _rows(app, "SELECT COUNT(*) c FROM whatsapp_log")[0]["c"]
    r = _post(client, "/whatsapp/send", {"phone": "", "custom_message": "hi"})
    assert "Phone number is required" in r.get_data(as_text=True)
    assert wa == []
    assert _rows(app, "SELECT COUNT(*) c FROM whatsapp_log")[0]["c"] == before


def test_send_requires_login(client, wa):
    """No session at all — the send routes must not reach Wapilot."""
    r = client.post("/whatsapp/send", data={"phone": "2010", "custom_message": "x"})
    assert r.status_code in (302, 403)
    assert wa == []


def test_send_requires_a_csrf_token(client, app, wa):
    _login(client)
    _csrf(client)                                  # seed a token, then omit it
    before = _rows(app, "SELECT COUNT(*) c FROM whatsapp_log")[0]["c"]
    r = client.post("/whatsapp/send",
                    data={"phone": "201055000092", "custom_message": "no token"})
    assert r.status_code == 403
    assert wa == []
    assert _rows(app, "SELECT COUNT(*) c FROM whatsapp_log")[0]["c"] == before


# ═══════════════════════════════════════════════════════════════════════════════
# CAMPAIGNS
# ═══════════════════════════════════════════════════════════════════════════════

def test_campaigns_list_renders_the_upstream_campaigns(client, wa):
    _login(client)
    r = client.get("/whatsapp/campaigns")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "camp-42" in body, "campaign list rendered but showed no campaigns"
    assert "Eid discount" in body


def test_campaigns_list_shows_the_error_when_wapilot_is_down(client, wa_down):
    _login(client)
    r = client.get("/whatsapp/campaigns")
    assert r.status_code == 200
    assert "502" in r.get_data(as_text=True)


def test_campaign_new_get_and_post(client, app, wa):
    _login(client)
    assert client.get("/whatsapp/campaigns/new").status_code == 200

    wa.clear()
    r = _post(client, "/whatsapp/campaigns/new",
              {"default_message": f"{MARK} spring offer"}, follow=False)
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/whatsapp/campaigns/camp-new-1")
    assert wa[0]["method"] == "POST" and wa[0]["path"] == "/campaigns"
    assert wa[0]["body"] == {"instance_uns": ["test-instance"],
                             "default_message": f"{MARK} spring offer"}

    audit = _rows(app,
        "SELECT * FROM audit_log WHERE module='whatsapp' AND entity_type='campaign' "
        "ORDER BY id DESC LIMIT 1")
    assert audit, "campaign creation was not audited"
    assert "camp-new-1" in audit[0]["details"]


def test_campaign_new_reports_upstream_failure_without_redirecting(client, wa_down):
    _login(client)
    r = _post(client, "/whatsapp/campaigns/new", {"default_message": "x"},
              follow=False)
    assert r.status_code == 200
    assert "Failed to create campaign" in r.get_data(as_text=True)


def test_campaign_new_is_role_gated(client, wa):
    _login(client, role="doctor")
    r = _post(client, "/whatsapp/campaigns/new", {"default_message": "sneaky"},
              follow=False)
    assert r.status_code == 302
    assert wa == [], "a denied role still created a campaign upstream"


def test_campaign_detail_shows_stats_and_messages(client, wa):
    _login(client)
    r = client.get("/whatsapp/campaigns/camp-42")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    paths = [c["path"] for c in wa]
    assert "/campaigns/camp-42/messages" in paths
    assert "/campaigns/camp-42/messages/stats" in paths
    assert "/campaigns/camp-42/delay" in paths
    assert "201000000001@c.us" in body, "campaign messages did not reach the page"
    assert ">7<" in body or "7" in body


def test_campaign_api_read_endpoints(client, wa):
    _login(client)
    for url, expected in [
        ("/whatsapp/api/campaigns",                "/campaigns"),
        ("/whatsapp/api/campaigns/c1/stats",       "/campaigns/c1/messages/stats"),
        ("/whatsapp/api/campaigns/c1/queue",       "/campaigns/c1/messages/queue"),
        ("/whatsapp/api/campaigns/c1/done",        "/campaigns/c1/messages/done"),
        ("/whatsapp/api/campaigns/c1/messages",    "/campaigns/c1/messages"),
        ("/whatsapp/api/campaigns/c1/delay",       "/campaigns/c1/delay"),
    ]:
        wa.clear()
        r = client.get(url)
        assert r.status_code == 200, url
        assert [(c["method"], c["path"]) for c in wa] == [("GET", expected)], url


def test_api_create_campaign_forwards_the_body(client, wa):
    _login(client)
    r = _jpost(client, "/whatsapp/api/campaigns",
               {"default_message": "hello", "instance_uns": ["other-inst"]})
    assert r.status_code == 200
    assert r.get_json()["data"]["data"]["id"] == "camp-new-1"
    assert wa[0]["body"] == {"instance_uns": ["other-inst"],
                             "default_message": "hello"}


@pytest.mark.parametrize("url,method,body,expected_method,expected_path", [
    ("/whatsapp/api/campaigns/c1/start",        "POST",   None,
     "POST",   "/campaigns/c1/start"),
    ("/whatsapp/api/campaigns/c1/pause",        "POST",   None,
     "POST",   "/campaigns/c1/pause"),
    ("/whatsapp/api/campaigns/c1/finish",       "PATCH",  None,
     "PATCH",  "/campaigns/c1/finish"),
    ("/whatsapp/api/campaigns/c1/copy",         "POST",   None,
     "POST",   "/campaigns/c1/copy"),
    ("/whatsapp/api/campaigns/c1/reset-failed", "POST",   None,
     "POST",   "/campaigns/c1/reset-failed"),
    ("/whatsapp/api/campaigns/c1/schedule",     "POST",
     {"schedule_date": "2026-08-01 09:00"}, "POST", "/campaigns/c1/schedule"),
    ("/whatsapp/api/campaigns/c1/schedule",     "DELETE", None,
     "DELETE", "/campaigns/c1/schedule"),
    ("/whatsapp/api/campaigns/c1/delay",        "PATCH",
     {"wait_between_messages_from": 4}, "PATCH", "/campaigns/c1/delay"),
    ("/whatsapp/api/campaigns/c1/messages",     "POST",
     {"messages": [{"phone": "2010", "text": "hi"}]},
     "POST",   "/campaigns/c1/messages"),
    ("/whatsapp/api/campaigns/c1/messages",     "DELETE",
     {"ids": ["m-1", "m-2"]}, "DELETE", "/campaigns/c1/messages"),
])
def test_campaign_write_endpoints_reach_wapilot(client, wa, url, method, body,
                                                expected_method, expected_path):
    _login(client)
    r = _jpost(client, url, body, method=method)
    assert r.status_code == 200, r.get_data(as_text=True)[:200]
    assert (wa[0]["method"], wa[0]["path"]) == (expected_method, expected_path)


def test_campaign_schedule_carries_the_date_and_ids(client, wa):
    _login(client)
    _jpost(client, "/whatsapp/api/campaigns/c1/schedule",
           {"schedule_date": "2026-08-01 09:00"})
    assert wa[0]["body"] == {"schedule_date": "2026-08-01 09:00"}

    wa.clear()
    _jpost(client, "/whatsapp/api/campaigns/c1/messages",
           {"messages": [{"phone": "2010", "text": "hi"}]})
    assert wa[0]["body"] == {"messages": [{"phone": "2010", "text": "hi"}]}

    wa.clear()
    _jpost(client, "/whatsapp/api/campaigns/c1/messages",
           {"ids": ["m-1", "m-2"]}, method="DELETE")
    assert wa[0]["body"] == {"ids": ["m-1", "m-2"]}


@pytest.mark.parametrize("url,method", [
    ("/whatsapp/api/campaigns",                 "POST"),
    ("/whatsapp/api/campaigns/c1/start",        "POST"),
    ("/whatsapp/api/campaigns/c1/pause",        "POST"),
    ("/whatsapp/api/campaigns/c1/finish",       "PATCH"),
    ("/whatsapp/api/campaigns/c1/copy",         "POST"),
    ("/whatsapp/api/campaigns/c1/reset-failed", "POST"),
    ("/whatsapp/api/campaigns/c1/schedule",     "POST"),
    ("/whatsapp/api/campaigns/c1/schedule",     "DELETE"),
])
def test_campaign_writes_are_role_gated(client, wa, url, method):
    """A vet must not be able to blast the clinic's whole client list."""
    _login(client, role="doctor")
    r = _jpost(client, url, {}, method=method)
    assert r.status_code == 302, f"{method} {url} was not role-gated"
    assert wa == [], f"{method} {url} reached Wapilot despite being denied"


def test_campaign_bulk_message_writes_need_the_whatsapp_module(client, wa):
    """Still flagged as looser than its siblings — but the module gate holds.

    /api/campaigns/<cid>/messages POST and DELETE mutate a live campaign's
    recipient list but carry only @login_required, while create/finish/copy/
    schedule on the same campaign require branch_manager or above. That gap is
    real and unchanged.

    This test used to assert the routes were reachable by "any logged in user"
    and it signed in as role "veterinarian" — which is not a role this system
    has. An unknown role fell OPEN to every module, so the test passed for the
    wrong reason and documented a hole as a feature. `doctor` is the real role
    and does NOT hold the whatsapp module, so it is now correctly refused;
    reception does hold it and gets through.
    """
    _login(client, role="doctor")
    r = _jpost(client, "/whatsapp/api/campaigns/c1/messages",
               {"messages": [{"phone": "2010", "text": "hi"}]})
    assert r.status_code in (302, 403), \
        "a doctor has no whatsapp grant and must not edit a campaign"

    wa.clear()
    _login(client, role="reception")
    r = _jpost(client, "/whatsapp/api/campaigns/c1/messages",
               {"messages": [{"phone": "2010", "text": "hi"}]})
    assert r.status_code == 200
    assert wa[0]["path"] == "/campaigns/c1/messages"

    wa.clear()
    r = _jpost(client, "/whatsapp/api/campaigns/c1/messages",
               {"ids": ["m-1"]}, method="DELETE")
    assert r.status_code == 200
    assert wa[0]["method"] == "DELETE"


# ═══════════════════════════════════════════════════════════════════════════════
# TEMPLATES — DB-backed, so every assertion is a read-back
# ═══════════════════════════════════════════════════════════════════════════════

def test_template_new_creates_the_row_with_the_values_posted(client, app):
    _login(client)
    name = f"{MARK}-appt-confirm"
    _exec(app, "DELETE FROM whatsapp_templates WHERE name=?", (name,))

    r = _post(client, "/whatsapp/templates/new", {
        "name": name, "scenario": "appointment", "language": "ar",
        "template_text": "مرحبا {owner}، موعد {pet} غدا",
        "variables_json": '["owner","pet"]',
        "is_active": "on", "is_default": "on",
    })
    assert r.status_code == 200

    rows = _rows(app, "SELECT * FROM whatsapp_templates WHERE name=?", (name,))
    assert len(rows) == 1, "template_new returned 200 but created nothing"
    t = rows[0]
    assert t["scenario"] == "appointment"
    assert t["language"] == "ar"
    assert t["template_text"] == "مرحبا {owner}، موعد {pet} غدا"
    assert t["variables_json"] == '["owner","pet"]'
    assert t["is_active"] == 1 and t["is_default"] == 1

    audit = _rows(app,
        "SELECT * FROM audit_log WHERE module='whatsapp' AND entity_type='template' "
        "AND action='create' ORDER BY id DESC LIMIT 1")
    assert audit and name in audit[0]["details"]


def test_template_new_unchecked_boxes_store_zero(client, app):
    _login(client)
    name = f"{MARK}-inactive"
    _exec(app, "DELETE FROM whatsapp_templates WHERE name=?", (name,))
    _post(client, "/whatsapp/templates/new",
          {"name": name, "template_text": "draft"})
    t = _rows(app, "SELECT * FROM whatsapp_templates WHERE name=?", (name,))[0]
    assert t["is_active"] == 0 and t["is_default"] == 0
    assert t["language"] == "en"


def test_template_new_rejects_a_blank_name_without_writing(client, app):
    _login(client)
    before = _rows(app, "SELECT COUNT(*) c FROM whatsapp_templates")[0]["c"]
    r = _post(client, "/whatsapp/templates/new",
              {"name": "  ", "template_text": "orphan body"})
    assert r.status_code == 200
    assert "Template name is required" in r.get_data(as_text=True)
    after = _rows(app, "SELECT COUNT(*) c FROM whatsapp_templates")[0]["c"]
    assert after == before, "a rejected template was written anyway"
    assert not _rows(app,
        "SELECT * FROM whatsapp_templates WHERE template_text=?", ("orphan body",))


def test_template_new_duplicate_name_is_rejected_not_duplicated(client, app, template):
    _login(client)
    r = _post(client, "/whatsapp/templates/new",
              {"name": template["name"], "template_text": "second copy"})
    assert r.status_code == 200
    rows = _rows(app, "SELECT * FROM whatsapp_templates WHERE name=?",
                 (template["name"],))
    assert len(rows) == 1, "UNIQUE(name) was bypassed"
    assert rows[0]["template_text"] != "second copy"


def test_template_edit_updates_every_field(client, app, template):
    _login(client)
    r = client.get(f"/whatsapp/templates/{template['id']}/edit")
    assert r.status_code == 200
    assert template["name"] in r.get_data(as_text=True)

    new_name = f"{MARK}-vaccine-due-v2"
    _exec(app, "DELETE FROM whatsapp_templates WHERE name=?", (new_name,))
    r = _post(client, f"/whatsapp/templates/{template['id']}/edit", {
        "name": new_name, "scenario": "reminder", "language": "ar",
        "template_text": "updated body", "variables_json": '["pet"]',
    })
    assert r.status_code == 200

    t = _rows(app, "SELECT * FROM whatsapp_templates WHERE id=?",
              (template["id"],))[0]
    assert t["name"] == new_name
    assert t["scenario"] == "reminder"
    assert t["language"] == "ar"
    assert t["template_text"] == "updated body"
    assert t["variables_json"] == '["pet"]'
    assert t["is_active"] == 0, "unchecked is_active must clear the flag"


def test_template_edit_unknown_id_redirects_and_writes_nothing(client, app):
    _login(client)
    before = _rows(app, "SELECT COUNT(*) c FROM whatsapp_templates")[0]["c"]
    r = _post(client, "/whatsapp/templates/999999/edit",
              {"name": f"{MARK}-ghost", "template_text": "x"}, follow=False)
    assert r.status_code == 302
    assert _rows(app, "SELECT COUNT(*) c FROM whatsapp_templates")[0]["c"] == before
    assert not _rows(app, "SELECT * FROM whatsapp_templates WHERE name=?",
                     (f"{MARK}-ghost",))


def test_templates_list_shows_the_row(client, template):
    _login(client)
    r = client.get("/whatsapp/templates")
    assert r.status_code == 200
    assert template["name"] in r.get_data(as_text=True)


def test_api_templates_returns_only_active_templates(client, app, template):
    _login(client)
    hidden = f"{MARK}-archived"
    _exec(app, "DELETE FROM whatsapp_templates WHERE name=?", (hidden,))
    _exec(app, "INSERT INTO whatsapp_templates (name, template_text, is_active) "
               "VALUES (?,?,0)", (hidden, "old"))
    r = client.get("/whatsapp/api/templates")
    assert r.status_code == 200
    names = [t["name"] for t in r.get_json()]
    assert template["name"] in names
    assert hidden not in names


def test_template_delete_removes_the_row(client, app, template):
    _login(client)
    r = _post(client, f"/whatsapp/templates/{template['id']}/delete", {})
    assert r.status_code == 200
    assert not _rows(app, "SELECT * FROM whatsapp_templates WHERE id=?",
                     (template["id"],)), "delete returned 200 but the row survived"


def test_template_delete_is_role_gated(client, app, template):
    _login(client, role="reception")
    r = _post(client, f"/whatsapp/templates/{template['id']}/delete", {},
              follow=False)
    assert r.status_code == 302
    assert _rows(app, "SELECT * FROM whatsapp_templates WHERE id=?",
                 (template["id"],)), "a receptionist deleted a template"


def test_template_write_routes_reject_a_veterinarian(client, app):
    _login(client, role="doctor")
    name = f"{MARK}-vet-made"
    r = _post(client, "/whatsapp/templates/new",
              {"name": name, "template_text": "x"}, follow=False)
    assert r.status_code == 302
    assert not _rows(app, "SELECT * FROM whatsapp_templates WHERE name=?", (name,))


# ═══════════════════════════════════════════════════════════════════════════════
# REMINDERS
# ═══════════════════════════════════════════════════════════════════════════════

def test_reminders_page_lists_the_pending_reminder(client, clinic):
    _login(client)
    r = client.get("/whatsapp/reminders")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert f"{MARK} Simba is due for a check-up" in body
    assert "201099000011" in body


def test_reminder_send_sends_logs_and_flips_the_status(client, app, wa, clinic):
    _login(client)
    rid = clinic["reminder_id"]
    r = client.post(f"/whatsapp/reminders/{rid}/send",
                    headers={"X-CSRF-Token": _csrf(client)})
    assert r.status_code == 200
    assert r.get_json() == {"ok": True, "status": "Sent"}

    assert wa[0]["body"]["chat_id"] == "201099000011@c.us"
    assert wa[0]["body"]["text"] == f"{MARK} Simba is due for a check-up"

    row = _rows(app, "SELECT * FROM reminders WHERE id=?", (rid,))[0]
    assert row["status"] == "Sent", "reminder was sent but never marked Sent"
    assert row["sent_at"], "sent_at was not stamped"

    log = _rows(app, "SELECT * FROM whatsapp_log WHERE owner_id=? "
                     "ORDER BY id DESC LIMIT 1", (clinic["owner_id"],))
    assert log and log[0]["status"] == "Sent"
    assert log[0]["message"] == f"{MARK} Simba is due for a check-up"


def test_reminder_send_leaves_status_pending_when_the_send_fails(client, app,
                                                                 wa_down, clinic):
    _login(client)
    rid = clinic["reminder_id"]
    r = client.post(f"/whatsapp/reminders/{rid}/send",
                    headers={"X-CSRF-Token": _csrf(client)})
    assert r.get_json()["ok"] is False

    row = _rows(app, "SELECT * FROM reminders WHERE id=?", (rid,))[0]
    assert row["status"] == "Pending", "a failed send must not mark the reminder Sent"
    log = _rows(app, "SELECT * FROM whatsapp_log WHERE owner_id=? "
                     "ORDER BY id DESC LIMIT 1", (clinic["owner_id"],))
    assert log[0]["status"] == "Failed"


def test_reminder_send_unknown_id_is_404(client, wa):
    _login(client)
    r = client.post("/whatsapp/reminders/999999/send",
                    headers={"X-CSRF-Token": _csrf(client)})
    assert r.status_code == 404
    assert wa == []


def test_reminder_send_with_no_phone_does_not_call_wapilot(client, app, wa):
    _login(client)
    oid = _exec(app, "INSERT INTO owners (full_name, phone, whatsapp_phone) "
                     "VALUES (?,'','')", (f"{MARK} No Phone",))
    rid = _exec(app, "INSERT INTO reminders (owner_id, reminder_type, message, "
                     "scheduled_for, status) VALUES (?,'custom',?,?,'Pending')",
                (oid, f"{MARK} unreachable", date.today().isoformat()))
    r = client.post(f"/whatsapp/reminders/{rid}/send",
                    headers={"X-CSRF-Token": _csrf(client)})
    assert r.get_json()["ok"] is False
    assert wa == []
    assert _rows(app, "SELECT * FROM reminders WHERE id=?", (rid,))[0]["status"] \
        == "Pending"


def test_mark_reminder_sent_updates_the_row(client, app, clinic):
    _login(client)
    rid = clinic["reminder_id"]
    r = _post(client, f"/whatsapp/reminders/{rid}/mark-sent", {})
    assert r.status_code == 200
    row = _rows(app, "SELECT * FROM reminders WHERE id=?", (rid,))[0]
    assert row["status"] == "Sent"
    assert row["sent_at"]


def test_reminder_admin_partitions_upcoming_and_overdue(client, app, clinic):
    _login(client)
    past = _exec(app,
        "INSERT INTO reminders (owner_id, reminder_type, message, scheduled_for, "
        "status) VALUES (?,'custom',?,?,'Pending')",
        (clinic["owner_id"], f"{MARK} overdue call",
         (date.today() - timedelta(days=3)).isoformat() + " 09:00:00"))
    r = client.get("/whatsapp/reminder-admin")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert f"{MARK} overdue call" in body, "an overdue reminder is not shown"
    assert f"{MARK} Simba is due for a check-up" in body, \
        "an upcoming reminder is not shown"
    assert past  # keeps the id referenced


def test_reminder_create_writes_the_row_it_was_given(client, app, clinic):
    _login(client)
    when = (date.today() + timedelta(days=2)).isoformat() + " 14:30:00"
    msg = f"{MARK} bring the vaccination card"
    r = _post(client, "/whatsapp/reminder-admin/reminders/new", {
        "owner_id": clinic["owner_id"], "pet_id": clinic["pet_id"],
        "reminder_type": "vaccine", "scheduled_for": when, "message": msg,
    })
    assert r.status_code == 200

    rows = _rows(app, "SELECT * FROM reminders WHERE message=?", (msg,))
    assert len(rows) == 1, "reminder_create returned 200 but wrote nothing"
    row = rows[0]
    assert row["owner_id"] == clinic["owner_id"]
    assert row["pet_id"] == clinic["pet_id"]
    assert row["reminder_type"] == "vaccine"
    assert row["scheduled_for"] == when
    assert row["status"] == "Pending"


@pytest.mark.parametrize("missing", ["owner_id", "message", "scheduled_for"])
def test_reminder_create_rejects_incomplete_input_without_writing(client, app,
                                                                  clinic, missing):
    _login(client)
    msg = f"{MARK} half-written-{missing}"
    form = {"owner_id": clinic["owner_id"], "reminder_type": "custom",
            "scheduled_for": date.today().isoformat() + " 12:00:00",
            "message": msg}
    form[missing] = ""
    before = _rows(app, "SELECT COUNT(*) c FROM reminders")[0]["c"]
    r = _post(client, "/whatsapp/reminder-admin/reminders/new", form)
    assert r.status_code == 200
    assert "are required" in r.get_data(as_text=True)
    assert _rows(app, "SELECT COUNT(*) c FROM reminders")[0]["c"] == before
    assert not _rows(app, "SELECT * FROM reminders WHERE message=?", (msg,))


def test_reminder_cancel_only_touches_pending(client, app, clinic):
    _login(client)
    rid = clinic["reminder_id"]
    r = _post(client, f"/whatsapp/reminder-admin/reminders/{rid}/cancel", {})
    assert r.status_code == 200
    assert _rows(app, "SELECT * FROM reminders WHERE id=?", (rid,))[0]["status"] \
        == "Cancelled"

    # An already-sent reminder must not be dragged back to Cancelled.
    sent = _exec(app, "INSERT INTO reminders (owner_id, reminder_type, message, "
                      "scheduled_for, status) VALUES (?,'custom',?,?,'Sent')",
                 (clinic["owner_id"], f"{MARK} already gone",
                  date.today().isoformat()))
    _post(client, f"/whatsapp/reminder-admin/reminders/{sent}/cancel", {})
    assert _rows(app, "SELECT * FROM reminders WHERE id=?", (sent,))[0]["status"] \
        == "Sent"


def test_reminder_send_now_sends_and_marks(client, app, wa, clinic):
    _login(client)
    rid = clinic["reminder_id"]
    r = _post(client, f"/whatsapp/reminder-admin/reminders/{rid}/send-now", {})
    assert r.status_code == 200
    assert "Reminder sent successfully" in r.get_data(as_text=True)
    assert wa[0]["body"]["chat_id"] == "201099000011@c.us"
    assert _rows(app, "SELECT * FROM reminders WHERE id=?", (rid,))[0]["status"] \
        == "Sent"


def test_reminder_send_now_unknown_id_is_handled(client, wa):
    _login(client)
    r = _post(client, "/whatsapp/reminder-admin/reminders/999999/send-now", {})
    assert r.status_code == 200
    assert "Reminder not found" in r.get_data(as_text=True)
    assert wa == []


# ═══════════════════════════════════════════════════════════════════════════════
# MESSAGE LOG & SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

def test_message_log_shows_a_logged_message(client, app, clinic):
    _login(client)
    _exec(app, "INSERT INTO whatsapp_log (owner_id, phone, message, status, "
               "template_name) VALUES (?,?,?,?,?)",
          (clinic["owner_id"], "201099000011", f"{MARK} log line", "Sent", "manual"))
    r = client.get("/whatsapp/log")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert f"{MARK} log line" in body, "message log rendered but showed no messages"
    assert f"{MARK} Nadia Farid" in body, "the owner join produced no name"


def test_wa_settings_get_shows_defaults(client, app):
    _login(client)
    r = client.get("/whatsapp/settings")
    assert r.status_code == 200
    assert "reminder_appt_msg" in r.get_data(as_text=True)


def test_wa_settings_post_persists_both_categories(client, app):
    _login(client)
    try:
        r = _post(client, "/whatsapp/settings", {
            "wapilot_token": "tok-from-form",
            "wapilot_instance_id": "inst-from-form",
            "reminder_appt_enabled": "1",
            "reminder_appt_msg": f"{MARK} appt message",
            "reminder_vaccine_msg": f"{MARK} vaccine message",
            "reminder_invoice_msg": f"{MARK} invoice message",
        })
        assert r.status_code == 200

        saved = {row["key"]: row for row in _rows(app,
            "SELECT * FROM settings WHERE category IN ('whatsapp','wapilot')")}
        assert saved["wapilot_token"]["value"] == "tok-from-form"
        assert saved["wapilot_token"]["category"] == "wapilot"
        assert saved["wapilot_instance_id"]["value"] == "inst-from-form"
        assert saved["reminder_appt_msg"]["value"] == f"{MARK} appt message"
        assert saved["reminder_appt_msg"]["category"] == "whatsapp"
        assert saved["reminder_appt_enabled"]["value"] == "1"
        # Unchecked toggles must be stored as off, not left at their default.
        assert saved["reminder_vaccine_enabled"]["value"] == "0"
        assert saved["reminder_invoice_enabled"]["value"] == "0"
        assert saved["wapilot_token"]["updated_by"] == "wa_tester"

        # A second POST that leaves the token blank must not wipe it.
        _post(client, "/whatsapp/settings", {"wapilot_token": "",
                                             "wapilot_instance_id": ""})
        still = _rows(app, "SELECT value FROM settings WHERE key='wapilot_token'")
        assert still[0]["value"] == "tok-from-form", \
            "a blank token field erased the stored credential"

        audit = _rows(app, "SELECT * FROM audit_log WHERE module='whatsapp' "
                           "AND entity_type='settings' ORDER BY id DESC LIMIT 1")
        assert audit, "settings change was not audited"
    finally:
        # These rows would silently configure Wapilot for every later test.
        _exec(app, "DELETE FROM settings WHERE category='wapilot'")


def test_wa_settings_is_role_gated(client, app):
    _login(client, role="doctor")
    r = _post(client, "/whatsapp/settings", {"wapilot_token": "vet-token"},
              follow=False)
    assert r.status_code == 302
    assert not _rows(app, "SELECT * FROM settings WHERE value='vet-token'")


def test_reminder_settings_alias_redirects(client):
    _login(client)
    r = client.get("/whatsapp/reminder-settings")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/whatsapp/settings")


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT ID LOOKUP
# ═══════════════════════════════════════════════════════════════════════════════

def test_lookup_endpoints(client, wa):
    _login(client)
    assert client.get("/whatsapp/api/lookup/lid/12345").status_code == 200
    assert wa[-1]["path"] == "/api/v2/test-instance/lids/12345"

    wa.clear()
    assert client.get("/whatsapp/api/lookup/phone/201099000011").status_code == 200
    assert wa[0]["path"] == "/api/v2/test-instance/lids/pn/201099000011"


# ═══════════════════════════════════════════════════════════════════════════════
# SCHEDULER — the module's whole reason to exist
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def due_work(app, clinic):
    """One appointment tomorrow, one vaccine due today, one overdue invoice.

    Everything a full reminder run should pick up, for the same owner, whose
    whatsapp_phone is set. `reminder_runs` is cleared for these entities so a
    previous test in the same session cannot mask a regression.
    """
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    appt_id = _exec(app,
        "INSERT INTO appointments (owner_id, pet_id, appointment_type, status, "
        "appt_date, appt_start) VALUES (?,?,?,?,?,?)",
        (clinic["owner_id"], clinic["pet_id"], "Vaccination", "Scheduled",
         tomorrow, "11:30"))
    vacc_id = _exec(app,
        "INSERT INTO vaccinations (pet_id, vaccine_name, administered_at, "
        "next_due_at) VALUES (?,?,?,?)",
        (clinic["pet_id"], "Rabies",
         (date.today() - timedelta(days=365)).isoformat(),
         date.today().isoformat()))
    inv_no = f"{MARK}-INV-001"
    _exec(app, "DELETE FROM invoices WHERE invoice_number=?", (inv_no,))
    inv_id = _exec(app,
        "INSERT INTO invoices (invoice_number, owner_id, pet_id, issue_date, "
        "due_date, status, total, due_amount) VALUES (?,?,?,?,?,?,?,?)",
        (inv_no, clinic["owner_id"], clinic["pet_id"],
         (date.today() - timedelta(days=30)).isoformat(),
         (date.today() - timedelta(days=10)).isoformat(),
         "Unpaid", 450.0, 450.0))
    _exec(app, "DELETE FROM reminder_runs WHERE (run_type=? AND entity_id=?) "
               "OR (run_type=? AND entity_id=?) OR (run_type=? AND entity_id=?)",
          ("appt_reminder", appt_id, "vaccine_reminder", vacc_id,
           "invoice_reminder", inv_id))
    # whatsapp_log is append-only and the app fixture is session-scoped, so
    # counts below must start from a clean slate for this phone.
    _exec(app, "DELETE FROM whatsapp_log WHERE phone=?", ("201099000011",))
    return {"appt_id": appt_id, "vacc_id": vacc_id, "inv_id": inv_id,
            "invoice_number": inv_no, "phone": "201099000011"}


def _wa_logs(app, phone, template_name):
    return _rows(app,
        "SELECT * FROM whatsapp_log WHERE phone=? AND template_name=? "
        "ORDER BY id DESC", (phone, template_name))


def test_scheduler_appointment_reminders_actually_run(app, monkeypatch, due_work):
    """The daily appointment job must produce a log row, not an exception."""
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    from blueprints.whatsapp.scheduler import _appointment_reminders
    with app.app_context():
        conn = db.get_db()
        _appointment_reminders(conn)
        conn.commit()
        conn.close()

    logs = _wa_logs(app, due_work["phone"], "appt_reminder")
    assert logs, "the appointment reminder job produced no message at all"
    msg = logs[0]["message"]
    assert f"{MARK}-Simba" in msg
    assert "Vaccination appointment tomorrow" in msg
    assert "11:30" in msg, "the appointment time is missing from the reminder"

    runs = _rows(app, "SELECT * FROM reminder_runs WHERE run_type='appt_reminder' "
                      "AND entity_id=?", (due_work["appt_id"],))
    assert len(runs) == 1, "the run was not recorded for de-duplication"


def test_scheduler_vaccine_reminders_actually_run(app, monkeypatch, due_work):
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    from blueprints.whatsapp.scheduler import _vaccine_reminders
    with app.app_context():
        conn = db.get_db()
        _vaccine_reminders(conn)
        conn.commit()
        conn.close()

    logs = _wa_logs(app, due_work["phone"], "vaccine_reminder")
    assert logs, "the vaccine reminder job produced no message at all"
    assert "Rabies" in logs[0]["message"]
    assert f"{MARK}-Simba" in logs[0]["message"]
    assert _rows(app, "SELECT * FROM reminder_runs WHERE run_type='vaccine_reminder' "
                      "AND entity_id=?", (due_work["vacc_id"],))


def test_scheduler_invoice_reminders_actually_run(app, monkeypatch, due_work):
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    from blueprints.whatsapp.scheduler import _invoice_reminders
    with app.app_context():
        conn = db.get_db()
        _invoice_reminders(conn)
        conn.commit()
        conn.close()

    logs = _wa_logs(app, due_work["phone"], "invoice_reminder")
    assert logs, "the overdue-invoice reminder job produced no message at all"
    msg = logs[0]["message"]
    assert due_work["invoice_number"] in msg
    assert "450.00" in msg, "the amount owed is missing from the reminder"
    assert _rows(app, "SELECT * FROM reminder_runs WHERE run_type='invoice_reminder' "
                      "AND entity_id=?", (due_work["inv_id"],))


def test_unconfigured_sends_are_logged_as_not_configured_never_as_sent(
        app, monkeypatch, due_work):
    """Pinned regression: a message that never left the building is not 'Sent'.

    This module previously logged stub-mode reminders as Sent, so a clinic saw
    a green column of deliveries that had never happened.
    """
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    from blueprints.whatsapp.scheduler import _appointment_reminders
    with app.app_context():
        conn = db.get_db()
        sent = _appointment_reminders(conn)
        conn.commit()
        conn.close()

    logs = _wa_logs(app, due_work["phone"], "appt_reminder")
    assert logs, "nothing was logged"
    assert logs[0]["status"] == "Not Configured"
    assert "not connected" in logs[0]["error"].lower()
    assert sent == 0, "an unsent reminder was counted as sent"

    assert not _rows(app,
        "SELECT * FROM whatsapp_log WHERE template_name='appt_reminder' "
        "AND status='Sent' AND phone=?", (due_work["phone"],))


def test_reminder_run_is_idempotent_within_a_day(app, monkeypatch, due_work):
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    from blueprints.whatsapp.scheduler import _appointment_reminders
    with app.app_context():
        conn = db.get_db()
        _appointment_reminders(conn)
        conn.commit()
        _appointment_reminders(conn)
        conn.commit()
        conn.close()
    logs = _wa_logs(app, due_work["phone"], "appt_reminder")
    assert len(logs) == 1, "the same appointment was reminded about twice in one day"


def test_reminder_run_survives_the_next_day(app, monkeypatch, due_work):
    """Day 2 must not blow up on the UNIQUE(run_type, entity_id, entity_type) key.

    Vaccine and invoice reminders stay eligible for days at a time, so the
    dedup row for an entity is revisited on later runs. Backdating the run to
    yesterday reproduces exactly that.
    """
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    from blueprints.whatsapp.scheduler import _invoice_reminders
    with app.app_context():
        conn = db.get_db()
        _invoice_reminders(conn)
        conn.commit()
        conn.close()
    _exec(app, "UPDATE reminder_runs SET run_at=? WHERE run_type='invoice_reminder' "
               "AND entity_id=?",
          ((date.today() - timedelta(days=1)).isoformat() + " 09:00:00",
           due_work["inv_id"]))

    with app.app_context():
        conn = db.get_db()
        _invoice_reminders(conn)      # must not raise
        conn.commit()
        conn.close()

    logs = _wa_logs(app, due_work["phone"], "invoice_reminder")
    assert len(logs) == 2, "the second day's invoice reminder never went out"
    runs = _rows(app, "SELECT * FROM reminder_runs WHERE run_type='invoice_reminder' "
                      "AND entity_id=?", (due_work["inv_id"],))
    assert len(runs) == 1, "the dedup table grew a duplicate row"


def test_run_reminder_jobs_completes_all_three_and_audits(app, monkeypatch, due_work):
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    from blueprints.whatsapp.scheduler import run_reminder_jobs
    with app.app_context():
        run_reminder_jobs()          # must not raise

    phone = due_work["phone"]
    for kind in ("appt_reminder", "vaccine_reminder", "invoice_reminder"):
        assert _wa_logs(app, phone, kind), f"{kind} produced nothing in a full run"

    audit = _rows(app, "SELECT * FROM audit_log WHERE module='whatsapp' "
                       "AND action='reminder_run' ORDER BY id DESC LIMIT 1")
    assert audit, "the reminder run was not audited"


def test_scheduler_page_counts_the_real_workload(client, app, wa, due_work):
    """The three headline numbers must reflect seeded work, not a swallowed error.

    Each count sits inside its own `try/except: 0`, so a broken query shows the
    clinic a confident zero instead of an error. One appointment tomorrow, one
    vaccine due today and one unpaid invoice are seeded, all for an owner with
    a WhatsApp number, so every figure must be at least 1.
    """
    import re
    _login(client)
    r = client.get("/whatsapp/scheduler")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    nums = [int(n) for n in
            re.findall(r'class="sch-big"[^>]*>\s*(\d+)\s*<', body)]
    assert len(nums) >= 3, f"expected three headline counts, found {nums}"
    appts, vaccines, invoices = nums[:3]      # the queue-overview grid
    assert appts >= 1, "tomorrow's appointment is not counted (query swallowed?)"
    assert vaccines >= 1, "the vaccine due today is not counted (query swallowed?)"
    assert invoices >= 1, "the unpaid invoice is not counted (query swallowed?)"


def test_scheduler_run_appt_reports_a_real_count(client, app, monkeypatch, due_work):
    _login(client)
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    r = _post(client, "/whatsapp/scheduler/run", {"type": "appt"})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Scheduler error" not in body, body[body.find("Scheduler error"):][:300]
    assert "Appointment reminders sent" in body
    assert _wa_logs(app, due_work["phone"], "appt_reminder"), \
        "the route reported success but wrote no message"


@pytest.mark.parametrize("run_type,template_name", [
    ("vaccine", "vaccine_reminder"),
    ("invoice", "invoice_reminder"),
])
def test_scheduler_run_each_job_type(client, app, monkeypatch, due_work,
                                     run_type, template_name):
    _login(client)
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    r = _post(client, "/whatsapp/scheduler/run", {"type": run_type})
    assert r.status_code == 200
    assert "Scheduler error" not in r.get_data(as_text=True)
    assert _wa_logs(app, due_work["phone"], template_name), \
        f"{run_type} run wrote no message"


def test_scheduler_run_all(client, app, monkeypatch, due_work):
    _login(client)
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    r = _post(client, "/whatsapp/scheduler/run", {"type": "all"})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Scheduler error" not in body
    assert "All reminder jobs triggered successfully" in body
    for kind in ("appt_reminder", "vaccine_reminder", "invoice_reminder"):
        assert _wa_logs(app, due_work["phone"], kind), f"{kind} wrote nothing"


def test_scheduler_run_unknown_type_does_nothing(client, app, monkeypatch, clinic):
    _login(client)
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    before = _rows(app, "SELECT COUNT(*) c FROM whatsapp_log")[0]["c"]
    r = _post(client, "/whatsapp/scheduler/run", {"type": "nonsense"})
    assert "Unknown job type" in r.get_data(as_text=True)
    assert _rows(app, "SELECT COUNT(*) c FROM whatsapp_log")[0]["c"] == before


def test_reminder_trigger_runs_the_job(client, app, monkeypatch, due_work):
    _login(client)
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    r = _post(client, "/whatsapp/reminder-admin/trigger", {})
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Reminder job failed" not in body, body[body.find("Reminder job failed"):][:300]
    assert "triggered successfully" in body
    assert _wa_logs(app, due_work["phone"], "appt_reminder"), \
        "the trigger reported success but sent nothing"


def test_reminder_trigger_is_role_gated(client, app, monkeypatch, due_work):
    _login(client, role="doctor")
    monkeypatch.delenv("WAPILOT_TOKEN", raising=False)
    before = _rows(app, "SELECT COUNT(*) c FROM whatsapp_log")[0]["c"]
    r = _post(client, "/whatsapp/reminder-admin/trigger", {}, follow=False)
    assert r.status_code == 302
    assert _rows(app, "SELECT COUNT(*) c FROM whatsapp_log")[0]["c"] == before


def test_scheduler_clear_history_drops_only_old_rows(client, app):
    _login(client)
    old_id = _exec(app,
        "INSERT INTO reminder_runs (run_type, entity_id, entity_type, run_at) "
        "VALUES ('watest_old', 991001, 'watest', ?)",
        ((date.today() - timedelta(days=90)).isoformat() + " 09:00:00",))
    new_id = _exec(app,
        "INSERT INTO reminder_runs (run_type, entity_id, entity_type, run_at) "
        "VALUES ('watest_new', 991002, 'watest', ?)",
        (date.today().isoformat() + " 09:00:00",))

    r = _post(client, "/whatsapp/scheduler/clear-history", {})
    assert r.status_code == 200
    assert "Could not clear history" not in r.get_data(as_text=True)

    assert not _rows(app, "SELECT * FROM reminder_runs WHERE id=?", (old_id,)), \
        "history older than 30 days was not cleared"
    assert _rows(app, "SELECT * FROM reminder_runs WHERE id=?", (new_id,)), \
        "clear-history deleted recent entries too"


def test_scheduler_page_lists_the_run_history(client, app, wa):
    _login(client)
    _exec(app, "DELETE FROM reminder_runs WHERE run_type='watest_history'")
    _exec(app, "INSERT INTO reminder_runs (run_type, entity_id, entity_type, run_at) "
               "VALUES ('watest_history', 991003, 'watest', ?)",
          (date.today().isoformat() + " 08:00:00",))
    r = client.get("/whatsapp/scheduler")
    assert r.status_code == 200
    assert "watest_history" in r.get_data(as_text=True), \
        "the scheduler page showed no run history"


# ═══════════════════════════════════════════════════════════════════════════════
# CONTROL CENTER
# ═══════════════════════════════════════════════════════════════════════════════

def test_control_center_shows_seeded_counts_and_recent_log(client, app, wa,
                                                           clinic, template):
    _login(client)
    _exec(app, "INSERT INTO whatsapp_log (owner_id, phone, message, status) "
               "VALUES (?,?,?,'Sent')",
          (clinic["owner_id"], "201099000011", f"{MARK} control centre line"))
    r = client.get("/whatsapp/control")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert f"{MARK} control centre line" in body, \
        "the control centre rendered but its recent log was empty"
    assert "test-instance" in body
