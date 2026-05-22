from flask import (
    render_template, request, redirect, url_for,
    session, flash, current_app,
)
from functools import wraps
from . import auth_bp
import models.database as db
import models.security as sec


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
# ROUTES
# ─────────────────────────────────────────────

@auth_bp.route("/landing")
@auth_bp.route("/")
def landing():
    """Public animated landing page — no login required."""
    if session.get("user"):
        return redirect(url_for("launcher.index"))
    return render_template("landing.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("launcher.index"))

    error = None
    username = ""

    if request.method == "POST":
        ip = request.remote_addr or "unknown"
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        theme    = request.form.get("theme", "medical")
        lang     = request.form.get("lang", "en")

        # Rate limit check
        locked, wait_secs = sec.is_rate_limited(ip)
        if locked:
            mins = wait_secs // 60
            error = f"Too many failed attempts. Try again in {mins} minute(s)."
            return render_template("login.html", error=error, username=username)

        user = db.verify_credentials(username, password)
        if user:
            sec.clear_rate_limit(ip)
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
                ip=ip,
                user_agent=request.headers.get("User-Agent", ""),
            )

            next_page = request.args.get("next") or url_for("launcher.index")
            if not next_page.startswith("/"):
                next_page = url_for("launcher.index")
            return redirect(next_page)
        else:
            locked_now = sec.record_failed_login(ip)
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
        ip=request.remote_addr,
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
            elif len(new_pw) < 12:
                flash("New password must be at least 12 characters.", "error")
            elif new_pw != confirm:
                flash("Passwords do not match.", "error")
            else:
                import models.database as _db
                conn = _db.get_db()
                with conn:
                    conn.execute(
                        "UPDATE users SET password_hash=? WHERE id=?",
                        (_db._hash(new_pw), user["id"]))
                conn.close()
                db.log_audit(username=user["username"], role=user.get("role",""),
                             action="password_change", module="auth",
                             ip=request.remote_addr)
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
