from flask import (
    render_template, request, redirect, url_for,
    session, flash, current_app, jsonify,
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
        denied = _permission_denied()
        if denied is not None:
            return denied
        return f(*args, **kwargs)
    return decorated


def self_service(f):
    """This route serves the logged-in user their OWN record.

    Exempt from the module grant, because the grant is the wrong question here.
    "payroll" means may-administer-payroll; a nurse reading her own payslip is
    not administering anything, and locking her out of it made five tests fail
    with names that say so exactly — "an employee may download their own
    payslip", "may read their own attendance summary".

    This does NOT relax anything else: login is still required, and each of
    these routes already scopes its query to the requesting user, which is what
    stops it becoming an IDOR.
    """
    f._self_service = True
    return f


def _permission_denied():
    """None if the current user may enter this blueprint, else a redirect.

    Enforced HERE because 271 of the 376 routes carry only @login_required with
    no role gate at all — so a groomer, a nurse and a receptionist could each
    open /finance/, /accounting/, /inventory/, /procurement/ and the full client
    list. Fixing that by hand-adding a role list to 271 routes would have missed
    some and locked people out of others; this is the one gate they all pass.

    Falls open, never closed, on anything ungovernable:
      - a role with no grant data      -> unchanged (an upgrade cannot lock a
                                          live clinic out of its own system)
      - a blueprint with no grant key  -> unchanged (launcher, auth, uploads,
                                          notifications: nothing to grant)
    """
    role = (session.get("user") or {}).get("role", "")
    if not role or role == "super_admin":
        return None
    view = current_app.view_functions.get(request.endpoint or "")
    if getattr(view, "_self_service", False):
        return None
    key = _permission_for(getattr(request, "blueprint", "") or "")
    if not key:
        return None
    granted = _role_permissions(role)
    if granted is None:
        return None
    if has_permission(key, role):
        return None
    flash("You don't have permission to access this page.", "danger")
    if request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json":
        return jsonify({"ok": False, "error": "forbidden"}), 403
    return redirect(url_for("launcher.index"))


# Blueprint name -> permission key. Most match; these do not, and guessing
# would silently deny access to a module an administrator believed they had
# granted.
_BP_PERMISSION = {
    "crm":          "patients",
    "finance":      "invoicing",
    "ai_assistant": "ai",
    "clinical":     "visits",
    "doctor":       "visits",
    "petsy":        "petshop",
    # The one-page visit flow is the visits module with a different front door.
    # Mapping it explicitly means it is governed by an existing grant rather
    # than arriving ungoverned — a new blueprint with no key falls open.
    "workflow":     "visits",
}


def _permission_for(blueprint: str) -> str:
    """The grant key governing a blueprint, or "" if none can govern it.

    Returning "" matters: a module with no key cannot be granted on the Roles
    screen, so enforcing against it would lock users out of a permission no
    administrator is able to give them.
    """
    if not blueprint:
        return ""
    key = _BP_PERMISSION.get(blueprint, blueprint)
    return key if key in {k for k, _ in db.ALL_PERMISSIONS} else ""


def role_required(*roles):
    """Allow access only to users whose role is in `roles`.

    Both gates apply, and BOTH must pass. The module grant (checked in
    login_required) says which modules a role may enter at all; this role list
    says who may do this particular thing inside one.

    They are not interchangeable, and treating them as such was a real bug. The
    grant keys are per MODULE, while routes inside a module differ enormously
    in blast radius: deleting a WhatsApp template and viewing the message log
    both live under "whatsapp". Letting the grant REPLACE the role list handed
    every receptionist the destructive routes too — caught by
    test_template_delete_is_role_gated, which put it plainly: "a receptionist
    deleted a template".

    So a grant can only ever narrow. It never widens.
    """
    def decorator(f):
        @wraps(f)
        @login_required            # module-level grant is enforced in there
        def decorated(*args, **kwargs):
            user_role = session.get("user", {}).get("role", "")
            if user_role != "super_admin" and user_role not in roles:
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
# SESSION ESTABLISHMENT
# ─────────────────────────────────────────────
#
# session["user"] is set in exactly ONE place — _establish_session below. Every
# login_required / role_required / permission_required check in the codebase
# tests session.get("user"), so gating that single assignment behind the TOTP
# challenge gates the whole application without touching another blueprint.

_PENDING_2FA = "_pending_2fa"

# A vet at a busy front desk needs long enough to unlock a phone and read a
# code, short enough that an abandoned browser is not a standing half-login.
PENDING_2FA_TTL = 300  # seconds

# Never let these reach session["user"] — the session cookie is signed, not
# encrypted, so anything in it is readable by the browser (and anyone with it).
_SESSION_STRIP = ("password_hash", "password", "pin",
                  "totp_secret", "last_totp_counter")


def _establish_session(user_row, theme, lang, ip, method="password") -> dict:
    """Promote a verified user to a real logged-in session."""
    db.touch_last_login(user_row["id"])
    user = {k: v for k, v in dict(user_row).items() if k not in _SESSION_STRIP}
    if not user.get("theme_preference"):
        user["theme_preference"] = theme

    session.pop(_PENDING_2FA, None)
    session.permanent = True
    session["user"]   = user
    session["theme"]  = user.get("theme_preference", theme)
    session["lang"]   = lang
    sec.touch_session()

    db.log_audit(
        username=user.get("username", ""),
        role=user.get("role", ""),
        action="login",
        module="auth",
        details=f"login via {method}",
        ip=ip,
        user_agent=request.headers.get("User-Agent", ""),
    )
    return user


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

            # Password was right, but that is only the FIRST factor. Do not
            # populate session["user"] yet — park the half-login in a
            # short-lived pending slot that only /auth/2fa can promote.
            try:
                needs_2fa = sec.totp_required(user["id"])
            except sec.TOTPUnavailable as exc:
                # 2FA is enrolled but unavailable on this server. Refuse the
                # login rather than silently downgrading to password-only.
                # The operator's recovery path (TOTP_FAIL_OPEN=1) is named in
                # the server log, not shown to the user.
                db.log_audit(
                    username=username, role=user.get("role", ""),
                    action="login_blocked_2fa_unavailable", module="auth",
                    ip=ip, user_agent=request.headers.get("User-Agent", ""),
                )
                return render_template("login.html", error=str(exc),
                                       username=username)

            if needs_2fa:
                session[_PENDING_2FA] = {
                    "user_id":    user["id"],
                    "username":   user["username"],
                    "theme":      theme,
                    "lang":       lang,
                    "next":       safe_redirect_target(request.args.get("next")),
                    "expires_at": time.time() + PENDING_2FA_TTL,
                }
                # So the challenge page renders in the language just chosen on
                # the login form. Carries no privilege on its own.
                session["lang"] = lang
                db.log_audit(
                    username=username, role=user.get("role", ""),
                    action="2fa_challenge", module="auth",
                    details="password accepted, awaiting TOTP code",
                    ip=ip, user_agent=request.headers.get("User-Agent", ""))
                return redirect(url_for("auth.two_factor"))

            _establish_session(user, theme, lang, ip)
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


@auth_bp.route("/2fa", methods=["GET", "POST"])
def two_factor():
    """Second factor. The ONLY route that promotes a pending login to a session.

    Deliberately NOT in models.security._CSRF_EXEMPT — unlike /auth/login this
    acts on an already-authenticated half-session, so a forged cross-site POST
    here would be an attack worth mounting.
    """
    if session.get("user"):
        return redirect(url_for("launcher.index"))

    pending = session.get(_PENDING_2FA) or {}
    if not pending or pending.get("expires_at", 0) <= time.time():
        session.pop(_PENDING_2FA, None)
        flash("Your sign-in request expired. Please log in again.", "warning")
        return redirect(url_for("auth.login"))

    ip       = sec.get_real_ip(request)
    username = pending.get("username", "")
    # Separate rate-limit key from the password step: 5 tries at a 6-digit code
    # is the whole defence, since 10^6 is guessable at any real request rate.
    rl_key   = f"2fa:{username}"
    error    = None

    if request.method == "POST":
        locked, wait_secs = sec.is_rate_limited(ip, rl_key)
        if locked:
            return render_template(
                "auth/two_factor.html", username=username,
                error=f"Too many incorrect codes. Try again in "
                      f"{wait_secs // 60 + 1} minute(s).")

        code        = request.form.get("code", "")
        user_id     = pending.get("user_id")
        used_backup = False
        ok = sec.verify_totp_code(user_id, code)
        if not ok:
            ok = used_backup = sec.consume_backup_code(user_id, code)

        if ok:
            # Re-read from the database rather than trusting the pending dict:
            # the account may have been deactivated since the password step.
            row = db.get_user(username)
            if not row:
                session.pop(_PENDING_2FA, None)
                flash("That account is no longer active.", "danger")
                return redirect(url_for("auth.login"))
            sec.clear_rate_limit(ip, rl_key)
            _establish_session(row, pending.get("theme", "medical"),
                               pending.get("lang", "en"), ip,
                               method="backup code" if used_backup else "TOTP")
            if used_backup:
                remaining = sec.count_backup_codes(user_id)
                flash(f"Signed in with a backup code — {remaining} left. "
                      "Generate new codes from your profile.", "warning")
            return redirect(safe_redirect_target(pending.get("next")))

        locked_now = sec.record_failed_login(ip, rl_key)
        error = "Invalid authentication code."
        if locked_now:
            error = (f"Too many incorrect codes. Locked for "
                     f"{sec.RATE_LIMIT_WINDOW // 60} minutes.")
        db.log_audit(
            username=username, role="", action="2fa_failed", module="auth",
            details=f"Invalid 2FA code for '{username}' from {ip}",
            ip=ip, user_agent=request.headers.get("User-Agent", ""))

    return render_template("auth/two_factor.html", error=error, username=username)


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

        elif action == "2fa_start":
            # Generates a NEW secret every time this is pressed, so an
            # abandoned half-enrolment cannot be resumed by someone else.
            if not sec.start_totp_enrolment(user["id"]):
                flash("Two-factor authentication is unavailable on this server. "
                      "Ask your administrator to install it.", "error")
                return redirect(url_for("auth.profile"))
            return redirect(url_for("auth.profile", setup=1))

        elif action == "2fa_confirm":
            if sec.confirm_totp_enrolment(user["id"], request.form.get("code", "")):
                codes = sec.generate_backup_codes(user["id"])
                db.log_audit(username=user["username"], role=user.get("role", ""),
                             action="2fa_enabled", module="auth",
                             details="user enabled two-factor authentication",
                             ip=sec.get_real_ip(request))
                # Rendered, not redirected: this is the one and only time the
                # backup codes exist in plaintext.
                return render_template("profile.html", user=user,
                                       totp=sec.totp_status(user["id"]),
                                       setup=None, backup_codes=codes)
            flash("That code was not accepted. Check your phone's clock is "
                  "correct and try the current code.", "error")
            return redirect(url_for("auth.profile", setup=1))

        elif action == "2fa_regen_codes":
            # Running out of backup codes is a real lockout path, so let people
            # top up without an admin. Password-gated: the codes ARE credentials.
            if not db.verify_credentials(user["username"],
                                         request.form.get("password", "")):
                flash("Current password is incorrect.", "error")
                return redirect(url_for("auth.profile"))
            codes = sec.generate_backup_codes(user["id"])
            db.log_audit(username=user["username"], role=user.get("role", ""),
                         action="2fa_backup_codes_regenerated", module="auth",
                         details="user generated new backup codes",
                         ip=sec.get_real_ip(request))
            return render_template("profile.html", user=user,
                                   totp=sec.totp_status(user["id"]),
                                   setup=None, backup_codes=codes)

        elif action == "2fa_disable":
            if not db.verify_credentials(user["username"],
                                         request.form.get("password", "")):
                flash("Current password is incorrect.", "error")
            else:
                sec.disable_totp(user["id"])
                db.log_audit(username=user["username"], role=user.get("role", ""),
                             action="2fa_disabled", module="auth",
                             details="user disabled their own two-factor authentication",
                             ip=sec.get_real_ip(request))
                flash("Two-factor authentication is now off.", "success")
            return redirect(url_for("auth.profile"))

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

    totp  = sec.totp_status(user["id"])
    setup = None
    if request.args.get("setup") and totp["pending"]:
        secret = sec.get_pending_secret(user["id"])
        if secret:
            uri = sec.totp_provisioning_uri(
                secret, user["username"],
                issuer=current_app.config.get("APP_TITLE", "Aleefy"))
            setup = {"secret": secret, "qr": sec.totp_qr_data_uri(uri)}
    return render_template("profile.html", user=user, totp=totp, setup=setup)


# ─────────────────────────────────────────────
# ADMIN 2FA RESET
# ─────────────────────────────────────────────
#
# A vet who loses their phone must not be locked out of patient records. Every
# reset is audit-logged with who did it and to whom.
#
# Residual risk: one compromised owner/super_admin account can strip 2FA from
# every other account, so this endpoint is exactly as strong as the strongest
# admin's password. It is not a hole 2FA introduces — that account could
# already change everyone's password via the user-admin screens — but it does
# mean the admin accounts are the ones that most need to enrol first. The audit
# trail is the detection control; there is no prevention control here short of
# two-person approval, which a single-clinic deployment will not staff.
# ponytail: audit-log as the only check. Add a second-approver flow if this
# ever runs for a multi-branch group with untrusted branch owners.

@auth_bp.route("/2fa/admin")
@role_required("super_admin", "clinic_owner")
def two_factor_admin():
    return render_template("auth/2fa_admin.html", users=sec.list_totp_users())


@auth_bp.route("/2fa/admin/reset/<int:user_id>", methods=["POST"])
@role_required("super_admin", "clinic_owner")
def two_factor_admin_reset(user_id):
    admin  = session["user"]
    target = next((u for u in sec.list_totp_users() if u["id"] == user_id), None)
    if not target:
        flash("No such active user.", "error")
        return redirect(url_for("auth.two_factor_admin"))

    sec.disable_totp(user_id)
    db.log_audit(
        username=admin["username"], role=admin.get("role", ""),
        action="2fa_admin_reset", module="auth",
        entity_type="user", entity_id=str(user_id),
        details=(f"{admin['username']} reset two-factor authentication for "
                 f"'{target['username']}' (id={user_id})"),
        ip=sec.get_real_ip(request),
        user_agent=request.headers.get("User-Agent", ""))
    flash(f"Two-factor authentication reset for {target['username']}. "
          "They can log in with their password and enrol again.", "success")
    return redirect(url_for("auth.two_factor_admin"))
