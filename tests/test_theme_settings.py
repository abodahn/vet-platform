"""
Theme settings tests (Gap C).
Verifies that the removed 'logo' theme cannot be applied and that
invalid theme values are normalised to the 'medical' default.
"""


def _post_theme(auth_client, theme):
    """POST /settings/theme with CSRF token injected via session."""
    app = auth_client.application

    with auth_client.session_transaction() as sess:
        try:
            from models import security as sec
            token = sess.get(sec._CSRF_SESSION_KEY, "")
        except Exception:
            token = ""

    return auth_client.post(
        "/settings/theme",
        data={"theme": theme, "_csrf_token": token},
        follow_redirects=True,
    )


def test_medical_theme_is_accepted(auth_client):
    resp = _post_theme(auth_client, "medical")
    assert resp.status_code in (200, 302)
    with auth_client.session_transaction() as sess:
        assert sess.get("theme", "medical") == "medical"


def test_logo_theme_is_rejected(auth_client):
    """The 'logo' theme was removed — must be normalised to 'medical'."""
    resp = _post_theme(auth_client, "logo")
    assert resp.status_code in (200, 302)
    with auth_client.session_transaction() as sess:
        assert sess.get("theme", "medical") == "medical", (
            "Session theme must be 'medical', not 'logo'"
        )


def test_unknown_theme_is_normalised(auth_client):
    resp = _post_theme(auth_client, "hacker_red")
    assert resp.status_code in (200, 302)
    with auth_client.session_transaction() as sess:
        assert sess.get("theme", "medical") == "medical"


def test_empty_theme_falls_back_to_medical(auth_client):
    resp = _post_theme(auth_client, "")
    assert resp.status_code in (200, 302)
    with auth_client.session_transaction() as sess:
        assert sess.get("theme", "medical") == "medical"
