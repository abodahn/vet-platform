import base64
import io
import logging

from flask import request, session, redirect, url_for, jsonify
from . import settings_bp
from blueprints.auth.routes import safe_redirect_target
import models.database as db

logger = logging.getLogger(__name__)

# Only "medical" is supported — the legacy "logo" theme was removed in Gap-C cleanup.
_VALID_THEMES = {"medical"}


# ── Clinic logo ────────────────────────────────────────────────────────────────
# WHERE IT LIVES: clinic.logo_data, as a `data:image/png;base64,...` URI.
#
# Not the filesystem. models/backup.py copies the *database* (sqlite backup /
# pg_dump) and nothing else, so a logo under uploads/ would survive a backup but
# vanish on restore — every clinic would silently lose its branding on the one
# day it was already having a bad time. TEXT in the row that is backed up is the
# only storage here that survives the round trip.
#
# Being a full data URI means templates can do `<img src="{{ clinic.logo_data }}">`
# with no serving route, and get_clinic()'s existing 5-minute cache covers it.

try:
    from PIL import Image           # ships with qrcode[pil], already required
    _PIL_OK = True
except ImportError:                 # pragma: no cover
    _PIL_OK = False

# Magic-byte signatures, same approach as blueprints/uploads/routes.py: the
# extension is attacker-controlled and says nothing about the bytes.
_IMAGE_MAGIC = (
    (b"\xff\xd8\xff",       "JPEG"),
    (b"\x89PNG\r\n\x1a\n",  "PNG"),
    (b"GIF87a",             "GIF"),
    (b"GIF89a",             "GIF"),
    (b"RIFF",               "WEBP"),   # confirmed further at offset 8
)

LOGO_MAX_UPLOAD = 2 * 1024 * 1024   # bytes accepted from the browser
LOGO_MAX_PX     = 400               # longest side after normalisation

# ponytail: the stored blob is re-encoded PNG at <=400px, which lands at roughly
# 20-80 KB (~30-110 KB once base64'd) and is inlined into every page that renders
# it — no browser caching, and it rides along in every DB backup. Ceiling: if a
# clinic ever wants a large or animated mark, move to an attachments row served
# by blueprints/uploads and add that folder to models/backup.py's archive.


class LogoError(ValueError):
    """Upload rejected. The message is safe to show the user verbatim."""


def sniff_image(head: bytes) -> str | None:
    """Identify an image from its first bytes. None when it is not one."""
    for sig, kind in _IMAGE_MAGIC:
        if head[:len(sig)] == sig:
            if kind == "WEBP" and head[8:12] != b"WEBP":
                return None
            return kind
    return None


def encode_logo(raw: bytes, max_px: int = LOGO_MAX_PX) -> str:
    """Validate, downscale and encode an uploaded image as a `data:` URI.

    Raises LogoError with a user-facing reason for anything not accepted.

    `max_px` is a parameter because the Instapay QR needs more room than a logo:
    a payment QR downscaled to 400px loses modules and stops scanning, and a QR
    that will not scan at the counter is worse than none — the client is already
    holding their phone out.
    """
    if not raw:
        raise LogoError("No file received.")
    if len(raw) > LOGO_MAX_UPLOAD:
        raise LogoError(
            f"Image is too large. Maximum {LOGO_MAX_UPLOAD // (1024 * 1024)} MB."
        )
    if not sniff_image(raw[:16]):
        raise LogoError("That file is not a PNG, JPEG, GIF or WebP image.")
    if not _PIL_OK:                 # pragma: no cover
        raise LogoError("Image support is unavailable on this server (Pillow missing).")

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()                  # forces decode: truncated and bomb images fail here
    except Exception as exc:
        raise LogoError("That image could not be read. Try re-saving it as a PNG.") from exc

    img.thumbnail((max_px, max_px))
    out = io.BytesIO()
    img.convert("RGBA").save(out, format="PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode("ascii")


# A payment QR carries fine detail that a 400px logo box destroys. 800 keeps it
# scannable from a phone held at arm's length while staying well inside the
# 2 MB upload ceiling once re-encoded.
QR_MAX_PX = 800


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

    # Through the same-site check, not straight into redirect(). Both of
    # these routes are in _CSRF_EXEMPT, so this is the one shape of
    # off-site redirect an attacker does not need a token to reach. The
    # helper already existed and was used correctly by /auth/login.
    return redirect(safe_redirect_target(
        request.form.get("next") or request.referrer,
        url_for("launcher.index")))


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

    # Through the same-site check, not straight into redirect(). Both of
    # these routes are in _CSRF_EXEMPT, so this is the one shape of
    # off-site redirect an attacker does not need a token to reach. The
    # helper already existed and was used correctly by /auth/login.
    return redirect(safe_redirect_target(
        request.form.get("next") or request.referrer,
        url_for("launcher.index")))
