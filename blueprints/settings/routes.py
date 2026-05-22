from flask import request, session, redirect, url_for, jsonify
from . import settings_bp
import models.database as db


# Only "medical" is supported — the legacy "logo" theme was removed in Gap-C cleanup.
_VALID_THEMES = {"medical"}


@settings_bp.route("/")
def index():
    """Settings root — redirect to the launcher dashboard."""
    return redirect(url_for("launcher.index"))


@settings_bp.route("/theme", methods=["POST"])
def set_theme():
    """Switch theme for the current user session.

    Only the 'medical' theme is valid. Any other value (including the
    removed 'logo' theme) is silently normalised to 'medical'.
    """
    if request.is_json:
        body = request.get_json(silent=True) or {}
        theme = body.get("theme", "medical")
    else:
        theme = request.form.get("theme", "medical")

    # Normalise: reject any theme not in the allowed set
    if theme not in _VALID_THEMES:
        theme = "medical"

    session["theme"] = theme
    user = session.get("user")
    if user:
        user["theme_preference"] = theme
        session["user"] = user
        db.update_user_theme(user["username"], theme)

    if request.is_json:
        return jsonify({"ok": True, "theme": theme})

    next_page = request.form.get("next") or request.referrer or url_for("launcher.index")
    return redirect(next_page)


@settings_bp.route("/lang", methods=["POST"])
def set_lang():
    """Switch UI language."""
    lang = request.form.get("lang", "en")
    if lang not in ("en", "ar"):
        lang = "en"
    session["lang"] = lang
    user = session.get("user")
    if user:
        user["language"] = lang
        session["user"] = user

    next_page = request.form.get("next") or request.referrer or url_for("launcher.index")
    return redirect(next_page)
