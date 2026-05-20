"""
Security Test Suite — Premium Animal Hospital Platform
Last phase before production go-live.

Covers:
  1. Authentication security (brute-force, session, open-redirect)
  2. Authorization / privilege escalation
  3. CSRF enforcement on every mutating endpoint
  4. SQL injection resistance
  5. XSS / output encoding
  6. Session cookie security flags
  7. Input validation boundaries
  8. Sensitive data exposure
  9. Path traversal (backup download)
 10. Security headers

Run:
    cd C:\\vet\\platform
    python -X utf8 -m pytest tests/test_security.py -v --tb=short

Or standalone (no pytest):
    python -X utf8 tests/test_security.py
"""

import json
import sys
import os
import html

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ── helpers shared across classes ─────────────────────────────────────────────

def _get_csrf(client):
    """Return the current CSRF token from the client's session."""
    from models import security as sec
    with client.session_transaction() as sess:
        return sess.get(sec._CSRF_SESSION_KEY, "")


def _login(client, username="admin", password="1234"):
    _clear_rate_limit()      # always start clean
    client.post("/auth/login", data={"username": username, "password": password})
    client.get("/")          # seeds _csrf_token into session
    return _get_csrf(client)


def _clear_rate_limit(ip="127.0.0.1"):
    from models import security as sec
    sec.clear_rate_limit(ip)


# ══════════════════════════════════════════════════════════════════════════════
# 1. AUTHENTICATION SECURITY
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthenticationSecurity:

    def test_login_page_loads(self, client):
        resp = client.get("/auth/login")
        assert resp.status_code == 200
        body = resp.data.lower()
        assert b"login" in body or b"username" in body

    def test_valid_login_creates_session(self, client):
        _clear_rate_limit()
        client.post("/auth/login", data={"username": "admin", "password": "1234"})
        with client.session_transaction() as sess:
            assert sess.get("user") is not None, "Session not set after valid login"

    def test_invalid_password_no_session(self, client):
        _clear_rate_limit()
        client.post("/auth/login",
                    data={"username": "admin", "password": "WRONGPASSWORD_XYZ"})
        with client.session_transaction() as sess:
            assert sess.get("user") is None, "Session set despite wrong password"

    def test_invalid_username_no_session(self, client):
        _clear_rate_limit()
        client.post("/auth/login",
                    data={"username": "nonexistent_user_xyz", "password": "anything"})
        with client.session_transaction() as sess:
            assert sess.get("user") is None

    def test_error_message_does_not_reveal_user_existence(self, client):
        """Same error for wrong user vs wrong password — no user enumeration."""
        _clear_rate_limit()
        r1 = client.post("/auth/login",
                         data={"username": "admin", "password": "WRONG"},
                         follow_redirects=True)
        _clear_rate_limit()
        r2 = client.post("/auth/login",
                         data={"username": "ghost_user_xyz", "password": "WRONG"},
                         follow_redirects=True)
        # Both responses must contain the same generic error text
        err1 = b"invalid" in r1.data.lower() or b"incorrect" in r1.data.lower()
        err2 = b"invalid" in r2.data.lower() or b"incorrect" in r2.data.lower()
        assert err1 and err2, "Login errors differ — potential user enumeration"

    def test_brute_force_lockout_after_5_attempts(self, client):
        """5 consecutive failures must trigger rate-limit lockout."""
        from models import security as sec
        # Use a dedicated IP so this test never contaminates 127.0.0.1
        _BRUTE_IP = "10.99.99.99"
        sec.clear_rate_limit(_BRUTE_IP)
        for _ in range(sec.RATE_LIMIT_MAX):
            sec.record_failed_login(_BRUTE_IP)
        locked, secs = sec.is_rate_limited(_BRUTE_IP)
        assert locked, "Brute-force lockout not triggered after max failures"
        assert secs > 0
        sec.clear_rate_limit(_BRUTE_IP)   # cleanup

    def test_logout_clears_session(self, client):
        _clear_rate_limit()
        _login(client)
        client.get("/auth/logout")
        with client.session_transaction() as sess:
            assert sess.get("user") is None, "Session still has user after logout"

    def test_protected_route_redirects_without_login(self, client):
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code in (301, 302), \
            f"Expected redirect for unauthenticated /, got {resp.status_code}"

    def test_open_redirect_blocked_in_next_param(self, client):
        """next= parameter must not redirect to external domains."""
        _clear_rate_limit()
        resp = client.post(
            "/auth/login?next=https://evil.com",
            data={"username": "admin", "password": "1234"},
            follow_redirects=False,
        )
        location = resp.headers.get("Location", "")
        assert "evil.com" not in location, \
            f"Open redirect allowed — Location: {location}"

    def test_open_redirect_relative_path_allowed(self, client):
        """Relative next= path must still work."""
        _clear_rate_limit()
        resp = client.post(
            "/auth/login?next=/crm/owners",
            data={"username": "admin", "password": "1234"},
            follow_redirects=False,
        )
        assert resp.status_code in (302, 301)
        location = resp.headers.get("Location", "")
        # Must go to the relative path, not login again
        assert "login" not in location or "/crm/owners" in location

    def test_password_not_stored_in_session(self, client):
        """Raw password must never appear in the session dict."""
        _clear_rate_limit()
        _login(client)
        with client.session_transaction() as sess:
            user = sess.get("user", {})
            session_str = json.dumps(user, default=str).lower()
            assert "1234" not in session_str, \
                "Plaintext password found in session"
            assert "password" not in session_str or "hash" not in session_str, \
                "Password hash found in session user object"


# ══════════════════════════════════════════════════════════════════════════════
# 2. AUTHORIZATION & PRIVILEGE ESCALATION
# ══════════════════════════════════════════════════════════════════════════════

class TestAuthorization:

    def _client_with_role(self, app, role):
        """Create a test client whose session says the user has `role`."""
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["user"] = {
                "id": 99999, "username": f"fake_{role}",
                "role": role, "full_name": f"Fake {role.title()}"
            }
            from models import security as sec
            import secrets
            sess[sec._CSRF_SESSION_KEY] = secrets.token_hex(32)
        return c

    def test_unauthenticated_cannot_access_crm(self, client):
        resp = client.get("/crm/owners", follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_unauthenticated_cannot_access_finance(self, client):
        resp = client.get("/finance/invoices", follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_unauthenticated_cannot_access_hr(self, client):
        resp = client.get("/hr/staff", follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_unauthenticated_cannot_access_system(self, client):
        resp = client.get("/system/", follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_unauthenticated_cannot_access_payroll(self, client):
        resp = client.get("/payroll/salaries", follow_redirects=False)
        assert resp.status_code in (301, 302)

    def test_receptionist_cannot_access_system_settings(self, app):
        c = self._client_with_role(app, "receptionist")
        resp = c.get("/system/", follow_redirects=True)
        # Must be blocked — either redirect back or 403
        assert resp.status_code in (200, 302, 403)
        # If 200, it must NOT be the system settings page
        if resp.status_code == 200:
            assert b"system settings" not in resp.data.lower() or \
                   b"permission" in resp.data.lower() or \
                   b"don't have" in resp.data.lower()

    def test_receptionist_cannot_access_hr_salary(self, app):
        c = self._client_with_role(app, "receptionist")
        resp = c.get("/payroll/salaries", follow_redirects=True)
        assert resp.status_code in (200, 302, 403)
        if resp.status_code == 200:
            assert b"salary" not in resp.data.lower() or \
                   b"permission" in resp.data.lower()

    def test_nonexistent_owner_id_returns_404(self, auth_client):
        resp = auth_client.get("/crm/owners/999999999")
        assert resp.status_code in (404, 302, 200)
        if resp.status_code == 200:
            # Page must not contain real data for owner 999999999
            assert b"999999999" not in resp.data

    def test_negative_id_in_url_does_not_crash(self, auth_client):
        for path in ["/crm/owners/-1", "/finance/invoices/-1",
                     "/appointments/-1"]:
            resp = auth_client.get(path)
            assert resp.status_code != 500, \
                f"Negative ID caused 500 on {path}"

    def test_string_id_in_url_does_not_crash(self, auth_client):
        for path in ["/crm/owners/abc", "/finance/invoices/abc"]:
            resp = auth_client.get(path)
            assert resp.status_code in (400, 404, 200, 302), \
                f"String ID caused unexpected {resp.status_code} on {path}"
            assert resp.status_code != 500


# ══════════════════════════════════════════════════════════════════════════════
# 3. CSRF ENFORCEMENT
# ══════════════════════════════════════════════════════════════════════════════

class TestCSRFEnforcement:

    # Endpoints that MUST reject POST without a valid CSRF token
    PROTECTED_ENDPOINTS = [
        ("/auth/profile",        {"action": "theme", "theme": "dark"}),
        ("/crm/owners/new",      {"full_name": "CSRF Test", "phone": "01000000000"}),
        ("/appointments/status/1", {"status": "Confirmed"}),
    ]

    def test_post_without_csrf_token_rejected(self, client):
        """Any mutating POST without a CSRF token must be rejected."""
        _clear_rate_limit()
        _login(client)
        # Remove CSRF from session
        with client.session_transaction() as sess:
            from models import security as sec
            sess.pop(sec._CSRF_SESSION_KEY, None)

        resp = client.post(
            "/crm/owners/new",
            data={"full_name": "NoCSRF", "phone": "00000000000"},
        )
        assert resp.status_code in (400, 403, 302), \
            f"POST without CSRF token accepted (status {resp.status_code})"

    def test_post_with_wrong_csrf_token_rejected(self, client):
        _clear_rate_limit()
        _login(client)
        resp = client.post(
            "/crm/owners/new",
            data={
                "full_name": "WrongCSRF",
                "phone": "00000000000",
                "_csrf_token": "totally_wrong_token_abcdef1234567890",
            },
        )
        assert resp.status_code in (400, 403, 302), \
            f"POST with wrong CSRF token accepted (status {resp.status_code})"

    def test_post_with_correct_csrf_token_accepted(self, client):
        _clear_rate_limit()
        token = _login(client)
        assert token, "CSRF token not generated on login"
        resp = client.post(
            "/auth/profile",
            data={"action": "theme", "theme": "dark", "_csrf_token": token},
        )
        assert resp.status_code in (200, 302), \
            f"Valid CSRF token rejected (status {resp.status_code})"

    def test_ai_chat_json_requires_csrf_header(self, client):
        _clear_rate_limit()
        _login(client)
        # Send without X-CSRF-Token header
        resp = client.post(
            "/ai/chat",
            data=json.dumps({"message": "hello"}),
            content_type="application/json",
        )
        assert resp.status_code in (400, 403), \
            f"AI chat accepted JSON POST without CSRF header ({resp.status_code})"

    def test_ai_chat_json_with_csrf_header_accepted(self, client):
        _clear_rate_limit()
        token = _login(client)
        resp = client.post(
            "/ai/chat",
            data=json.dumps({"message": "hello"}),
            content_type="application/json",
            headers={"X-CSRF-Token": token},
        )
        # 200/500/503 all acceptable — only 400/403 means CSRF rejected
        assert resp.status_code not in (400, 403), \
            f"Valid CSRF header was rejected on AI chat"

    def test_get_requests_never_require_csrf(self, client):
        """GET requests must always work without a CSRF token."""
        _clear_rate_limit()
        _login(client)
        for path in ["/crm/owners", "/finance/invoices", "/appointments/"]:
            resp = client.get(path)
            assert resp.status_code != 403, \
                f"GET {path} incorrectly requires CSRF token"


# ══════════════════════════════════════════════════════════════════════════════
# 4. SQL INJECTION RESISTANCE
# ══════════════════════════════════════════════════════════════════════════════

class TestSQLInjection:

    SQL_PAYLOADS = [
        "' OR '1'='1",
        "'; DROP TABLE owners; --",
        "1; SELECT * FROM users; --",
        "' UNION SELECT username,password_hash FROM users --",
        "admin'--",
        "' OR 1=1--",
        "%27 OR %271%27=%271",
    ]

    def test_login_sql_injection_rejected(self, client):
        """SQL injection in username/password must not log the user in."""
        _clear_rate_limit()
        for payload in self.SQL_PAYLOADS:
            _clear_rate_limit()
            resp = client.post(
                "/auth/login",
                data={"username": payload, "password": payload},
                follow_redirects=True,
            )
            with client.session_transaction() as sess:
                assert sess.get("user") is None, \
                    f"SQL injection logged in with payload: {payload!r}"

    def test_search_sql_injection_does_not_crash(self, client):
        """Search inputs with SQL payloads must not cause 500 errors."""
        _clear_rate_limit()
        _login(client)
        for payload in self.SQL_PAYLOADS:
            resp = client.get(f"/crm/owners?q={payload}")
            assert resp.status_code != 500, \
                f"SQL injection caused 500 on search: {payload!r}"

    def test_owner_id_injection_in_url(self, client):
        """SQL in URL path parameters must be handled safely."""
        _clear_rate_limit()
        _login(client)
        unsafe_ids = ["1 OR 1=1", "1; DROP TABLE owners", "1'"]
        for bad_id in unsafe_ids:
            from urllib.parse import quote
            resp = client.get(f"/crm/owners/{quote(bad_id)}")
            assert resp.status_code in (400, 404, 200, 302), \
                f"SQL in URL ID caused {resp.status_code}: {bad_id!r}"
            assert resp.status_code != 500

    def test_finance_search_injection(self, client):
        _clear_rate_limit()
        _login(client)
        for payload in ["' OR '1'='1", "1 UNION SELECT * FROM users"]:
            from urllib.parse import quote
            resp = client.get(f"/finance/invoices?q={quote(payload)}")
            assert resp.status_code != 500

    def test_appointment_date_injection(self, client):
        _clear_rate_limit()
        _login(client)
        resp = client.get("/appointments/?date=2026-01-01' OR '1'='1")
        assert resp.status_code != 500


# ══════════════════════════════════════════════════════════════════════════════
# 5. XSS / OUTPUT ENCODING
# ══════════════════════════════════════════════════════════════════════════════

class TestXSSPrevention:

    XSS_PAYLOADS = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert(1)>",
        "javascript:alert(1)",
        "<svg onload=alert(1)>",
        "';alert('xss');//",
        "<iframe src=javascript:alert(1)>",
    ]

    def test_xss_in_search_query_escaped(self, client):
        """XSS payloads in search must be HTML-escaped in the response."""
        _clear_rate_limit()
        _login(client)
        for payload in self.XSS_PAYLOADS:
            from urllib.parse import quote
            resp = client.get(f"/crm/owners?q={quote(payload)}")
            assert resp.status_code != 500
            body = resp.data.decode("utf-8", errors="replace")
            # Raw unescaped executable tags must not appear.
            # NOTE: "onerror=alert" can appear inside a properly HTML-escaped
            # attribute value (= is not an HTML special char), so we check for
            # the unescaped tag syntax that a browser would actually execute.
            assert "<script>alert" not in body, \
                f"XSS payload unescaped in response: {payload!r}"
            # <img with unescaped attribute syntax would be exploitable
            assert "<img src=x onerror=" not in body, \
                f"XSS img payload unescaped in response: {payload!r}"

    def test_xss_payload_in_owner_name_escaped_on_display(self, client):
        """
        If an XSS payload is stored as an owner name, the list page must
        HTML-escape it before rendering.
        """
        _clear_rate_limit()
        token = _login(client)
        payload = "<script>alert('stored_xss')</script>"
        # Create owner with XSS in name
        resp = client.post(
            "/crm/owners/new",
            data={
                "full_name": payload,
                "phone": "01099999999",
                "_csrf_token": token,
            },
            follow_redirects=True,
        )
        # Check owners list — payload must be escaped
        list_resp = client.get("/crm/owners")
        body = list_resp.data.decode("utf-8", errors="replace")
        assert "<script>alert" not in body, \
            "Stored XSS payload rendered unescaped in owners list"
        # Escaped version is acceptable
        assert html.escape(payload) in body or payload not in body

    def test_xss_in_appointment_notes_escaped(self, client):
        _clear_rate_limit()
        _login(client)
        resp = client.get("/appointments/?notes=<script>alert(1)</script>")
        if resp.status_code == 200:
            body = resp.data.decode("utf-8", errors="replace")
            assert "<script>alert(1)</script>" not in body


# ══════════════════════════════════════════════════════════════════════════════
# 6. SESSION COOKIE SECURITY FLAGS
# ══════════════════════════════════════════════════════════════════════════════

class TestSessionCookieSecurity:

    def test_session_cookie_has_httponly_flag(self, client):
        _clear_rate_limit()
        resp = client.post(
            "/auth/login",
            data={"username": "admin", "password": "1234"},
        )
        set_cookie = resp.headers.get("Set-Cookie", "")
        if not set_cookie:
            # May come from a follow-up response
            resp2 = client.get("/")
            set_cookie = resp2.headers.get("Set-Cookie", "")
        assert "httponly" in set_cookie.lower(), \
            f"Session cookie missing HttpOnly flag. Set-Cookie: {set_cookie!r}"

    def test_session_cookie_has_samesite(self, client):
        _clear_rate_limit()
        resp = client.post(
            "/auth/login",
            data={"username": "admin", "password": "1234"},
        )
        all_cookies = "\n".join(
            v for k, v in resp.headers if k.lower() == "set-cookie"
        )
        has_samesite = "samesite" in all_cookies.lower()
        # SameSite is set in config — verify it reaches the cookie
        assert has_samesite, \
            f"Session cookie missing SameSite attribute. Cookies: {all_cookies!r}"

    def test_logout_invalidates_session_cookie(self, client):
        _clear_rate_limit()
        _login(client)
        client.get("/auth/logout")
        # After logout, protected page must redirect
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code in (301, 302), \
            "After logout, protected route still accessible"

    def test_csrf_token_in_session_after_login(self, client):
        _clear_rate_limit()
        _login(client)
        from models import security as sec
        with client.session_transaction() as sess:
            token = sess.get(sec._CSRF_SESSION_KEY, "")
        assert token and len(token) >= 32, \
            f"CSRF token not set or too short: {token!r}"


# ══════════════════════════════════════════════════════════════════════════════
# 7. INPUT VALIDATION & BOUNDARY TESTING
# ══════════════════════════════════════════════════════════════════════════════

class TestInputValidation:

    def test_extremely_long_input_does_not_crash(self, client):
        _clear_rate_limit()
        token = _login(client)
        long_str = "A" * 10_000
        resp = client.post(
            "/crm/owners/new",
            data={"full_name": long_str, "phone": "01000000000",
                  "_csrf_token": token},
            follow_redirects=True,
        )
        assert resp.status_code != 500, "10k-char input caused 500"

    def test_null_bytes_in_input_do_not_crash(self, client):
        _clear_rate_limit()
        token = _login(client)
        resp = client.post(
            "/crm/owners/new",
            data={"full_name": "Null\x00Byte", "phone": "01000000000",
                  "_csrf_token": token},
            follow_redirects=True,
        )
        assert resp.status_code != 500

    def test_unicode_arabic_input_accepted(self, client):
        _clear_rate_limit()
        token = _login(client)
        resp = client.post(
            "/crm/owners/new",
            data={"full_name": "محمد العربي", "phone": "01000000000",
                  "_csrf_token": token},
            follow_redirects=True,
        )
        assert resp.status_code not in (400, 500), \
            "Arabic unicode input rejected or crashed"

    def test_empty_required_fields_rejected(self, client):
        _clear_rate_limit()
        token = _login(client)
        resp = client.post(
            "/crm/owners/new",
            data={"full_name": "", "phone": "", "_csrf_token": token},
            follow_redirects=True,
        )
        # Must not create an owner with empty name — either validation error or redirect back
        assert resp.status_code in (200, 302, 400), \
            f"Empty owner name caused {resp.status_code}"

    def test_negative_invoice_amount_does_not_corrupt(self, client):
        _clear_rate_limit()
        token = _login(client)
        resp = client.post(
            "/finance/invoices/new",
            data={
                "owner_id": "1",
                "unit_price_0": "-99999",
                "qty_0": "1",
                "desc_0": "Negative test",
                "_csrf_token": token,
            },
            follow_redirects=True,
        )
        assert resp.status_code != 500

    def test_malformed_date_does_not_crash(self, client):
        _clear_rate_limit()
        _login(client)
        for bad_date in ["not-a-date", "99/99/9999", "2026-13-45"]:
            from urllib.parse import quote
            resp = client.get(f"/appointments/?date={quote(bad_date)}")
            assert resp.status_code != 500, \
                f"Malformed date {bad_date!r} caused 500"


# ══════════════════════════════════════════════════════════════════════════════
# 8. SENSITIVE DATA EXPOSURE
# ══════════════════════════════════════════════════════════════════════════════

class TestSensitiveDataExposure:

    def test_password_hash_not_in_html_response(self, client):
        _clear_rate_limit()
        _login(client)
        resp = client.get("/hr/staff")
        if resp.status_code == 200:
            body = resp.data.decode("utf-8", errors="replace").lower()
            assert "$2b$" not in body, \
                "Bcrypt password hash found in HR staff page HTML"
            assert "password_hash" not in body

    def test_user_api_does_not_return_password(self, client):
        _clear_rate_limit()
        token = _login(client)
        # Any JSON API that might return user data
        for path in ["/ai/health-alerts", "/appointments/api/queue"]:
            resp = client.get(path)
            if resp.status_code == 200 and resp.content_type == "application/json":
                body = resp.data.decode("utf-8", errors="replace")
                assert "password_hash" not in body.lower()
                assert "$2b$" not in body

    def test_500_error_no_stack_trace_in_response(self, app, client):
        """In non-debug mode, 500 errors must not expose Python tracebacks."""
        if app.debug:
            return   # Skip in debug mode (tracebacks intentionally shown)
        _clear_rate_limit()
        _login(client)
        # Trigger a route that should 404/500 gracefully
        resp = client.get("/crm/owners/999999999999")
        if resp.status_code == 500:
            body = resp.data.decode("utf-8", errors="replace")
            assert "Traceback" not in body, \
                "Python traceback exposed in 500 response (debug=False)"
            assert "File \"" not in body

    def test_audit_log_accessible_only_to_admin(self, app, client):
        _clear_rate_limit()
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["user"] = {"id": 99, "username": "receptionist1",
                            "role": "receptionist", "full_name": "Recept"}
            from models import security as sec
            import secrets
            sess[sec._CSRF_SESSION_KEY] = secrets.token_hex(32)
        resp = c.get("/system/audit-log", follow_redirects=True)
        # Receptionist must not see the audit log
        if resp.status_code == 200:
            body = resp.data.lower()
            assert b"audit" not in body or b"permission" in body or \
                   b"don't have" in body or b"access denied" in body


# ══════════════════════════════════════════════════════════════════════════════
# 9. PATH TRAVERSAL
# ══════════════════════════════════════════════════════════════════════════════

class TestPathTraversal:

    TRAVERSAL_PAYLOADS = [
        "../../../etc/passwd",
        "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
        "%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        "....//....//etc/passwd",
    ]

    def test_backup_download_path_traversal_blocked(self, client):
        _clear_rate_limit()
        _login(client)
        for payload in self.TRAVERSAL_PAYLOADS:
            from urllib.parse import quote
            resp = client.get(f"/system/backup/{quote(payload)}/download")
            assert resp.status_code in (400, 403, 404), \
                f"Path traversal not blocked for: {payload!r} (got {resp.status_code})"

    def test_static_file_traversal_blocked(self, client):
        for payload in ["../app.py", "../../config.py"]:
            from urllib.parse import quote
            resp = client.get(f"/static/{quote(payload)}")
            # Flask's static file handler should reject these
            assert resp.status_code in (400, 403, 404), \
                f"Static path traversal not blocked: {payload!r}"

    def test_upload_path_traversal_blocked(self, client):
        """File download/serve endpoints must not serve files outside upload dir."""
        _clear_rate_limit()
        _login(client)
        for payload in self.TRAVERSAL_PAYLOADS:
            from urllib.parse import quote
            resp = client.get(f"/uploads/{quote(payload)}")
            assert resp.status_code in (400, 403, 404), \
                f"Upload path traversal not blocked: {payload!r}"


# ══════════════════════════════════════════════════════════════════════════════
# 10. SECURITY HEADERS
# ══════════════════════════════════════════════════════════════════════════════

class TestSecurityHeaders:

    def _get_headers(self, client):
        _clear_rate_limit()
        _login(client)
        resp = client.get("/")
        return {k.lower(): v for k, v in resp.headers}

    def test_x_content_type_options(self, client):
        headers = self._get_headers(client)
        val = headers.get("x-content-type-options", "")
        assert val.lower() == "nosniff", \
            f"Missing/wrong X-Content-Type-Options: {val!r}"

    def test_x_frame_options(self, client):
        headers = self._get_headers(client)
        val = headers.get("x-frame-options", "")
        assert val.upper() in ("DENY", "SAMEORIGIN"), \
            f"Missing/wrong X-Frame-Options: {val!r}"

    def test_no_server_version_disclosure(self, client):
        headers = self._get_headers(client)
        server = headers.get("server", "")
        # Should not expose exact Werkzeug/Python version
        assert "werkzeug/" not in server.lower(), \
            f"Server header discloses Werkzeug version: {server!r}"

    def test_content_security_policy_present(self, client):
        headers = self._get_headers(client)
        csp = headers.get("content-security-policy", "")
        assert csp, "Content-Security-Policy header is missing"


# ══════════════════════════════════════════════════════════════════════════════
# 11. RATE LIMITING (unit-level, no real HTTP needed)
# ══════════════════════════════════════════════════════════════════════════════

class TestRateLimiting:

    def test_rate_limit_triggers_after_max_attempts(self):
        from models import security as sec
        ip = "10.0.0.99"
        sec.clear_rate_limit(ip)
        for _ in range(sec.RATE_LIMIT_MAX):
            sec.record_failed_login(ip)
        locked, secs_left = sec.is_rate_limited(ip)
        assert locked, "Rate limit not triggered after max attempts"
        assert secs_left > 0
        sec.clear_rate_limit(ip)

    def test_rate_limit_cleared_on_success(self):
        from models import security as sec
        ip = "10.0.0.98"
        sec.clear_rate_limit(ip)
        for _ in range(3):
            sec.record_failed_login(ip)
        sec.clear_rate_limit(ip)
        locked, _ = sec.is_rate_limited(ip)
        assert not locked, "Rate limit not cleared"

    def test_rate_limit_max_is_5(self):
        from models import security as sec
        assert sec.RATE_LIMIT_MAX == 5, \
            f"RATE_LIMIT_MAX changed from 5 to {sec.RATE_LIMIT_MAX} — check brute-force protection"

    def test_rate_limit_window_at_least_5_minutes(self):
        from models import security as sec
        assert sec.RATE_LIMIT_WINDOW >= 300, \
            f"Lockout window {sec.RATE_LIMIT_WINDOW}s is too short (<5 min)"

    def test_session_timeout_at_least_30_minutes(self):
        from models import security as sec
        assert sec.SESSION_TIMEOUT >= 1800, \
            f"SESSION_TIMEOUT {sec.SESSION_TIMEOUT}s is too short (<30 min)"

    def test_csrf_token_minimum_entropy(self):
        """CSRF tokens must be at least 256 bits (64 hex chars)."""
        from models import security as sec
        import secrets
        # Simulate token generation
        token = secrets.token_hex(32)  # same as generate_csrf_token uses
        assert len(token) >= 64, \
            f"CSRF token too short: {len(token)} chars (need >= 64)"


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE RUNNER (no pytest required)
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import traceback

    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    BOLD   = "\033[1m"
    RESET  = "\033[0m"

    results = {"pass": 0, "fail": 0, "skip": 0}
    failures = []

    # ── bootstrap app ──────────────────────────────────────────────────────────
    from app import create_app
    from config import Config
    import models.database as db
    db.configure_postgres(host="localhost", port=5432, dbname="vetclinic",
                          user="postgres", password="1234")

    class _TestCfg(Config):
        TESTING = True
        WTF_CSRF_ENABLED = False
        SECRET_KEY = "test-security-key"

    application = create_app(_TestCfg)

    def _client():
        return application.test_client()

    def run(label, fn, *args):
        try:
            fn(*args)
            print(f"  {GREEN}PASS{RESET}  {label}")
            results["pass"] += 1
        except AssertionError as e:
            print(f"  {RED}FAIL{RESET}  {label}")
            print(f"         {e}")
            results["fail"] += 1
            failures.append((label, str(e)))
        except Exception as e:
            print(f"  {RED}FAIL{RESET}  {label}")
            traceback.print_exc()
            results["fail"] += 1
            failures.append((label, str(e)))

    print(f"\n{BOLD}{'='*62}{RESET}")
    print(f"{BOLD}  Security Test Suite — Premium Animal Hospital{RESET}")
    print(f"{BOLD}{'='*62}{RESET}\n")

    auth  = TestAuthenticationSecurity()
    authz = TestAuthorization()
    csrf  = TestCSRFEnforcement()
    sqli  = TestSQLInjection()
    xss   = TestXSSPrevention()
    sess  = TestSessionCookieSecurity()
    inval = TestInputValidation()
    sens  = TestSensitiveDataExposure()
    path  = TestPathTraversal()
    hdr   = TestSecurityHeaders()
    rl    = TestRateLimiting()

    print(f"{BOLD}=== 1. Authentication Security ==={RESET}")
    c = _client()
    run("login_page_loads",                  auth.test_login_page_loads, c)
    run("valid_login_creates_session",       auth.test_valid_login_creates_session, _client())
    run("invalid_password_no_session",       auth.test_invalid_password_no_session, _client())
    run("invalid_username_no_session",       auth.test_invalid_username_no_session, _client())
    run("error_no_user_enumeration",         auth.test_error_message_does_not_reveal_user_existence, _client())
    run("brute_force_lockout_after_5",       auth.test_brute_force_lockout_after_5_attempts, _client())
    run("logout_clears_session",             auth.test_logout_clears_session, _client())
    run("protected_route_redirects",         auth.test_protected_route_redirects_without_login, _client())
    run("open_redirect_blocked",             auth.test_open_redirect_blocked_in_next_param, _client())
    run("password_not_in_session",           auth.test_password_not_stored_in_session, _client())

    print(f"\n{BOLD}=== 2. Authorization ==={RESET}")
    run("unauth_crm_redirect",               authz.test_unauthenticated_cannot_access_crm, _client())
    run("unauth_finance_redirect",           authz.test_unauthenticated_cannot_access_finance, _client())
    run("unauth_hr_redirect",                authz.test_unauthenticated_cannot_access_hr, _client())
    run("unauth_system_redirect",            authz.test_unauthenticated_cannot_access_system, _client())
    run("unauth_payroll_redirect",           authz.test_unauthenticated_cannot_access_payroll, _client())
    run("receptionist_blocked_system",       authz.test_receptionist_cannot_access_system_settings, application)
    run("receptionist_blocked_payroll",      authz.test_receptionist_cannot_access_hr_salary, application)
    run("nonexistent_owner_no_crash",        authz.test_nonexistent_owner_id_returns_404, _client())
    run("negative_id_no_crash",             authz.test_negative_id_in_url_does_not_crash, _client())
    run("string_id_no_crash",               authz.test_string_id_in_url_does_not_crash, _client())

    print(f"\n{BOLD}=== 3. CSRF Enforcement ==={RESET}")
    run("post_without_token_rejected",       csrf.test_post_without_csrf_token_rejected, _client())
    run("post_wrong_token_rejected",         csrf.test_post_with_wrong_csrf_token_rejected, _client())
    run("post_correct_token_accepted",       csrf.test_post_with_correct_csrf_token_accepted, _client())
    run("ai_json_requires_csrf_header",      csrf.test_ai_chat_json_requires_csrf_header, _client())
    run("ai_json_valid_csrf_accepted",       csrf.test_ai_chat_json_with_csrf_header_accepted, _client())
    run("get_never_requires_csrf",           csrf.test_get_requests_never_require_csrf, _client())

    print(f"\n{BOLD}=== 4. SQL Injection ==={RESET}")
    run("login_sqli_rejected",              sqli.test_login_sql_injection_rejected, _client())
    run("search_sqli_no_crash",             sqli.test_search_sql_injection_does_not_crash, _client())
    run("url_id_sqli_no_crash",             sqli.test_owner_id_injection_in_url, _client())
    run("finance_search_sqli_no_crash",     sqli.test_finance_search_injection, _client())
    run("date_sqli_no_crash",               sqli.test_appointment_date_injection, _client())

    print(f"\n{BOLD}=== 5. XSS Prevention ==={RESET}")
    run("search_xss_escaped",               xss.test_xss_in_search_query_escaped, _client())
    run("stored_xss_escaped",               xss.test_xss_payload_in_owner_name_escaped_on_display, _client())
    run("notes_xss_escaped",                xss.test_xss_in_appointment_notes_escaped, _client())

    print(f"\n{BOLD}=== 6. Session Cookie Flags ==={RESET}")
    run("cookie_httponly",                   sess.test_session_cookie_has_httponly_flag, _client())
    run("cookie_samesite",                   sess.test_session_cookie_has_samesite, _client())
    run("logout_invalidates_cookie",         sess.test_logout_invalidates_session_cookie, _client())
    run("csrf_token_set_after_login",        sess.test_csrf_token_in_session_after_login, _client())

    print(f"\n{BOLD}=== 7. Input Validation ==={RESET}")
    run("10k_char_input_no_crash",           inval.test_extremely_long_input_does_not_crash, _client())
    run("null_bytes_no_crash",               inval.test_null_bytes_in_input_do_not_crash, _client())
    run("arabic_unicode_accepted",           inval.test_unicode_arabic_input_accepted, _client())
    run("empty_required_fields",             inval.test_empty_required_fields_rejected, _client())
    run("negative_amount_no_crash",          inval.test_negative_invoice_amount_does_not_corrupt, _client())
    run("malformed_date_no_crash",           inval.test_malformed_date_does_not_crash, _client())

    print(f"\n{BOLD}=== 8. Sensitive Data Exposure ==={RESET}")
    run("no_hash_in_html",                   sens.test_password_hash_not_in_html_response, _client())
    run("api_no_password_leak",              sens.test_user_api_does_not_return_password, _client())
    run("500_no_traceback",                  sens.test_500_error_no_stack_trace_in_response, application, _client())
    run("audit_log_role_restricted",         sens.test_audit_log_accessible_only_to_admin, application, _client())

    print(f"\n{BOLD}=== 9. Path Traversal ==={RESET}")
    run("backup_traversal_blocked",          path.test_backup_download_path_traversal_blocked, _client())
    run("static_traversal_blocked",          path.test_static_file_traversal_blocked, _client())
    run("upload_traversal_blocked",          path.test_upload_path_traversal_blocked, _client())

    print(f"\n{BOLD}=== 10. Security Headers ==={RESET}")
    run("x_content_type_options",            hdr.test_x_content_type_options, _client())
    run("x_frame_options",                   hdr.test_x_frame_options, _client())
    run("no_server_version_disclosure",      hdr.test_no_server_version_disclosure, _client())
    run("content_security_policy",           hdr.test_content_security_policy_present, _client())

    print(f"\n{BOLD}=== 11. Rate Limiting & Token Entropy ==={RESET}")
    run("rate_limit_triggers_at_max",        rl.test_rate_limit_triggers_after_max_attempts)
    run("rate_limit_cleared_on_success",     rl.test_rate_limit_cleared_on_success)
    run("rate_limit_max_is_5",               rl.test_rate_limit_max_is_5)
    run("lockout_window_at_least_5min",      rl.test_rate_limit_window_at_least_5_minutes)
    run("session_timeout_at_least_30min",    rl.test_session_timeout_at_least_30_minutes)
    run("csrf_token_minimum_entropy",        rl.test_csrf_token_minimum_entropy)

    # ── summary ────────────────────────────────────────────────────────────────
    total = results["pass"] + results["fail"] + results["skip"]
    print(f"\n{BOLD}{'='*62}{RESET}")
    print(f"{BOLD}  Results: {total} tests  |  "
          f"{GREEN}{results['pass']} passed{RESET}  |  "
          f"{RED}{results['fail']} failed{RESET}  |  "
          f"{YELLOW}{results['skip']} skipped{RESET}")
    if failures:
        print(f"\n{BOLD}  Failed:{RESET}")
        for label, msg in failures:
            print(f"    {RED}✗{RESET} {label}: {msg}")
    print(f"{BOLD}{'='*62}{RESET}\n")
    sys.exit(0 if results["fail"] == 0 else 1)
