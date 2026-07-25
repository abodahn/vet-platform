from flask import (
    render_template, request, redirect, url_for,
    session, flash, current_app,
)
from functools import wraps
from urllib.parse import urlparse
import json
import logging
import re
import threading
import time
from . import auth_bp
import models.database as db
import models.security as sec

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# SAFE REDIRECT
# ─────────────────────────────────────────────

# Browsers strip ASCII control characters and spaces while parsing a URL, so
# "/\n/evil.com" is fetched as "//evil.com". Strip them before validating,
# and validate the stripped form that the browser will actually act on.
_URL_JUNK = re.compile(r"[\x00-\x20\x7f]")


def safe_redirect_target(target: str, fallback: str = None) -> str:
    """Return `target` only if it is a same-site, path-only URL.

    Rejects the whole class of off-site redirects rather than one instance:
      - absolute URLs with a scheme        (http://evil.com)
      - scheme-relative / protocol-relative (//evil.com, /\\evil.com)
      - anything carrying a netloc          (https:evil.com)
      - backslashes, which browsers and Windows normalise to "/"
    """
    if fallback is None:
        fallback = url_for("launcher.index")
    if not target:
        return fallback
    cleaned = _URL_JUNK.sub("", target)
    # Backslash normalises to "/" in every major browser: "/\evil.com" == "//evil.com"
    if not cleaned or "\\" in cleaned:
        return fallback
    # Must be an absolute path, and must not be protocol-relative.
    if not cleaned.startswith("/") or cleaned.startswith("//"):
        return fallback
    parsed = urlparse(cleaned)
    if parsed.scheme != "" or parsed.netloc != "":
        return fallback
    return cleaned


# ─────────────────────────────────────────────
# DECORATORS
# ─────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """Allow access only to users whose role is in `roles`."""
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            user_role = session.get("user", {}).get("role", "")
            if user_role not in roles and user_role != "super_admin":
                flash("You don't have permission to access this page.", "danger")
                return redirect(url_for("launcher.index"))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ─────────────────────────────────────────────
# DATA-DRIVEN PERMISSIONS
# ─────────────────────────────────────────────
#
# `roles.permissions_json` holds a flat JSON array of module keys drawn from
# db.ALL_PERMISSIONS, e.g. ["patients", "appointments", "invoicing"] — exactly
# what templates/system/roles.html posts as `permissions` and what
# db.create_role / db.update_role serialise.
#
# The seed data inserts roles WITHOUT permissions_json, so every existing role
# defaults to '[]'. Treating empty as "deny everything" would lock a live
# clinic out of its own system on upgrade, so an empty/missing/unparseable
# value means "no permission data for this role" and the caller falls back to
# the hardcoded role list — never to open access.

_PERM_TTL = 60          # seconds; roles change rarely, requests are frequent
_perm_cache: dict = {}  # role -> (expires_at, frozenset | None)
_perm_cache_lock = threading.Lock()


def clear_permission_cache() -> None:
    """Drop the cached permission sets. Call after editing roles in the admin UI."""
    with _perm_cache_lock:
        _perm_cache.clear()


def _role_permissions(role: str):
    """Granted module keys for `role`, or None when there is no usable data.

    None is distinct from an empty set: it means "fall back to the hardcoded
    role list", not "this role is allowed nothing".
    """
    now = time.time()
    with _perm_cache_lock:
        hit = _perm_cache.get(role)
        if hit and hit[0] > now:
            return hit[1]

    perms = None
    try:
        conn = db.get_db()
        try:
            row = conn.execute(
                "SELECT permissions_json FROM roles WHERE name=?", (role,)).fetchone()
        finally:
            conn.close()
        if row is not None and row[0]:
            parsed = json.loads(row[0])
            if isinstance(parsed, list):
                keys = frozenset(
                    p.strip().lower() for p in parsed
                    if isinstance(p, str) and p.strip()
                )
                # An empty list carries no information — fall back, don't deny.
                perms = keys or None
            else:
                logger.warning(
                    "roles.permissions_json for role %r is %s, expected list — "
                    "falling back to hardcoded roles", role, type(parsed).__name__)
    except (ValueError, TypeError) as exc:
        logger.warning("Unparseable roles.permissions_json for role %r (%s) — "
                       "falling back to hardcoded roles", role, exc)
    except Exception as exc:
        logger.error("Could not read permissions for role %r (%s) — "
                     "falling back to hardcoded roles", role, exc)

    with _perm_cache_lock:
        _perm_cache[role] = (now + _PERM_TTL, perms)
    return perms


def has_permission(permission: str, role: str = None) -> bool:
    """True if `role` (default: the logged-in user's) grants `permission`.

    `permission` is "module.action"; grants are stored per module, so
    "invoicing.refund" is satisfied by a stored "invoicing" grant. An exact
    match on the full string is also honoured, so finer-grained keys can be
    added later without changing callers.

    Fails CLOSED: returns False when there is no usable permission data. Use
    @permission_required if you want the hardcoded-role fallback instead.
    """
    if role is None:
        role = (session.get("user") or {}).get("role", "")
    if not role:
        return False
    if role == "super_admin":
        return True
    granted = _role_permissions(role)
    if not granted:
        return False
    wanted = (permission or "").strip().lower()
    if not wanted:
        return False
    return wanted in granted or wanted.split(".", 1)[0] in granted


def permission_required(permission: str, *fallback_roles):
    """Require `permission` ("module.action") for the logged-in user.

    `fallback_roles` are the roles the route currently hardcodes. They are used
    ONLY when the role has no usable permission data, so migrating a route is
    mechanical and cannot widen access:

        @role_required("doctor", "nurse")
        →
        @permission_required("visits.edit", "doctor", "nurse")

    super_admin always passes, matching role_required.
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated(*args, **kwargs):
            user_role = (session.get("user") or {}).get("role", "")
            if user_role == "super_admin":
                return f(*args, **kwargs)
            granted = _role_permissions(user_role)
            if granted is None:
                allowed = user_role in fallback_roles
            else:
                allowed = has_permission(permission, user_role)
            if not allowed:
                flash("You don't have permission to access this page.", "danger")
                return redirect(url_for("launcher.index"))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("launcher.index"))

    error = None
    username = ""

    if request.method == "POST":
        ip = sec.get_real_ip(request)
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        theme    = request.form.get("theme", "medical")
        lang     = request.form.get("lang", "en")

        # Rate limit check — keyed on IP *and* the account being targeted
        locked, wait_secs = sec.is_rate_limited(ip, username)
        if locked:
            mins = wait_secs // 60
            error = f"Too many failed attempts. Try again in {mins} minute(s)."
            return render_template("login.html", error=error, username=username)

        user = db.verify_credentials(username, password)
        if user:
            sec.clear_rate_limit(ip, username)
            db.touch_last_login(user["id"])
            if not user.get("theme_preference"):
                user["theme_preference"] = theme

            # Strip sensitive fields before storing in session
            user = {k: v for k, v in user.items()
                    if k not in ("password_hash", "password", "pin")}

            session.permanent = True
            session["user"]   = user
            session["theme"]  = user.get("theme_preference", theme)
            session["lang"]   = lang
            sec.touch_session()

            db.log_audit(
                username=username,
                role=user.get("role", ""),
                action="login",
                module="auth",
                ip=ip,  # already uses get_real_ip above
                user_agent=request.headers.get("User-Agent", ""),
            )

            return redirect(safe_redirect_target(request.args.get("next")))
        else:
            locked_now = sec.record_failed_login(ip, username)
            error = "Invalid username or password."
            if locked_now:
                error = f"Too many failed attempts. Account locked for {sec.RATE_LIMIT_WINDOW // 60} minutes."
            db.log_audit(
                username=username,
                role="",
                action="login_failed",
                module="auth",
                details=f"Failed login for '{username}' from {ip}",
                ip=ip,
                user_agent=request.headers.get("User-Agent", ""),
            )

    return render_template("login.html", error=error, username=username)


@auth_bp.route("/logout")
def logout():
    user = session.get("user") or {}
    db.log_audit(
        username=user.get("username", "unknown"),
        role=user.get("role", ""),
        action="logout",
        module="auth",
        ip=sec.get_real_ip(request),
    )
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = session["user"]
    if request.method == "POST":
        action = request.form.get("action", "theme")
        if action == "change_password":
            old_pw   = request.form.get("old_password", "")
            new_pw   = request.form.get("new_password", "")
            confirm  = request.form.get("confirm_password", "")
            if not db.verify_credentials(user["username"], old_pw):
                flash("Current password is incorrect.", "error")
            elif new_pw != confirm:
                flash("Passwords do not match.", "error")
            else:
                pw_ok, pw_err = sec.validate_password_strength(new_pw)
                if not pw_ok:
                    flash(pw_err, "error")
                else:
                    import models.database as _db
                    conn = _db.get_db()
                    with conn:
                        conn.execute(
                            "UPDATE users SET password_hash=%s WHERE id=%s",
                            (_db._hash(new_pw), user["id"]))
                    conn.close()
                    db.log_audit(username=user["username"], role=user.get("role",""),
                                 action="password_change", module="auth",
                                 ip=sec.get_real_ip(request))
                    flash("Password changed successfully.", "success")
        else:
            theme = request.form.get("theme", user.get("theme_preference", "medical"))
            lang  = request.form.get("lang",  user.get("language", "en"))
            db.update_user_theme(user["username"], theme)
            user["theme_preference"] = theme
            user["language"]         = lang
            session["user"]  = user
            session["theme"] = theme
            session["lang"]  = lang
            flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("profile.html", user=user)
