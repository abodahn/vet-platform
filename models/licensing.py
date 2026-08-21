# -*- coding: utf-8 -*-
"""Offline licence activation by challenge and response.

HOW IT WORKS

The clinic's screen shows a challenge derived from that machine:

    ALF-7K2M-9QR4

They read it to you on the phone. You run scripts/make_license.py, which turns
it into a response code that only works on that machine:

    2708-4471-8823

They type it in. No internet, no clock synchronisation, nothing to install.

WHY NOT TOTP, WHEN THE APP ALREADY HAS IT

models/security.py has a full TOTP implementation for user logins, and reusing
it here was the obvious first idea. It is the wrong primitive: TOTP is
time-based and needs both clocks to agree. Clinic PCs frequently have the wrong
system time, and the failure would look identical to a wrong code with nothing
on screen to explain it. Challenge-response has no clock in it at all.

WHAT THE CODE CONTAINS

    2708 - 4471 - 8823
    ^^^^   ^^^^^^^^^^^
    |      truncated HMAC over (machine id, expiry)
    expires end of 2027-08

The expiry is in the open so the code describes itself and so the app can check
the HMAC without being told the date separately. It is inside the HMAC as well,
so editing those four digits invalidates the whole code.

WHAT THIS PROTECTS AGAINST, AND WHAT IT DOES NOT

It stops a clinic handing a working copy to a friend, because the code is bound
to one machine. That is the realistic threat and it is genuinely covered.

It does NOT stop a determined technical person. The verifying secret has to be
on the clinic's machine for offline verification to be possible at all - that is
arithmetic, not a weak library choice - so somebody who can read Python can
extract it and mint their own codes. The same person could equally well delete
the check on the line below. Nothing here pretends otherwise.

The real enforcement for a customer who will not pay is the yearly conversation,
and for anyone unwilling to have it, hosting the system yourself.

BLAST RADIUS

Each clinic gets its OWN secret, derived from your master secret and their
clinic id. A secret lifted from one installation mints codes for that machine
only. The master secret never leaves your laptop and is never in this repo.

ENFORCEMENT

ALEEFY_LICENSE_MODE decides what an unlicensed installation may do.

  banner   (default) A notice, and nothing else. Every screen keeps working.
  block    An installation that has NEVER been activated is held at the licence
           screen until a code is entered. One that WAS activated and has since
           lapsed is held too, but only after the quiet period.

"block" is what a vendor wants: a copy handed to another clinic does nothing
until you are phoned. The blast radius is deliberately limited, because the
thing being withheld is a clinic's patient records:

  - Never-activated is the safe case to block. There is no data in it yet, and
    nobody is mid-consultation. This is ordinary activate-before-use.
  - A lapsed licence gets QUIET_DAYS of silence, then a banner, and only after
    that does it block. A clinic that pays late is inconvenienced, not stranded
    in the middle of a Tuesday.
  - AUTO_GRACE_DAYS past expiry the installation gives itself permanent grace
    and is NEVER blocked again. If the vendor is ill, travelling, has lost the
    master secret or has sold the business, no clinic is bricked by it. This
    protects the vendor as much as the clinic.
  - The licence screen, signing in and out, the health check and static files
    always stay reachable, or the clinic could not activate even with a valid
    code in their hand.

A blocked screen says what is wrong and who to call. It never pretends to be a
crash, and it never suggests the records are gone.
"""
import hashlib
import hmac
import logging
import os
import platform
import re
import uuid
from datetime import date, datetime, timedelta

logger = logging.getLogger(__name__)

# Past this many days beyond expiry the installation stops asking. See the
# module docstring: this is a safety valve, not an oversight.
AUTO_GRACE_DAYS = 90

# An expired licence is silent for this long before the banner appears, so a
# clinic that renews late is inconvenienced rather than alarmed.
QUIET_DAYS = 60

_SETTING_CODE = "license_code"
_SETTING_UNTIL = "license_valid_until"
_SETTING_MACHINE = "license_machine"
_SETTING_FIRST_SEEN = "license_first_seen"

_CODE_RE = re.compile(r"^(\d{4})-?(\d{4})-?(\d{4})$")


# ── the machine ───────────────────────────────────────────────────────────────

def machine_id() -> str:
    """A stable-enough fingerprint of this computer.

    Deliberately built from things that survive a reboot and a Windows update
    but differ between two physical machines. It is not tamper-proof and does
    not need to be - a clinic that edits its own fingerprint is a clinic that
    could edit the check.
    """
    parts = [platform.node() or "", str(uuid.getnode()), platform.machine() or ""]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    # Digits, not hex. This gets read aloud down an Egyptian phone line, where
    # B and D - and C and E - are the same sound, in English and in Arabic.
    # Eight digits is ample: the machine id is an identifier, not a secret.
    return str(int.from_bytes(digest[:6], "big") % 10**8).zfill(8)


def challenge() -> str:
    """The code shown on screen, in groups a person can read over the phone."""
    m = machine_id()
    return "ALF-%s-%s" % (m[:4], m[4:])


# ── the secret ────────────────────────────────────────────────────────────────

def clinic_secret() -> bytes:
    """This installation's own signing secret.

    Read from ALEEFY_LICENSE_SECRET, which lives in the clinic's .env - already
    gitignored, already how every other secret in this app is handled. Generated
    per clinic by scripts/make_license.py --derive, so it is not the master.
    """
    raw = (os.environ.get("ALEEFY_LICENSE_SECRET") or "").strip()
    return raw.encode("utf-8") if raw else b""


def derive_clinic_secret(master: str, clinic_id: str) -> str:
    """Master secret + clinic id -> that clinic's secret. Vendor side only."""
    return hmac.new(master.encode("utf-8"),
                    ("clinic:" + clinic_id).encode("utf-8"),
                    hashlib.sha256).hexdigest()


# ── the code ──────────────────────────────────────────────────────────────────

def _digits(secret: bytes, machine: str, yymm: str, n: int = 8) -> str:
    mac = hmac.new(secret, ("%s|%s" % (machine, yymm)).encode("utf-8"),
                   hashlib.sha256).digest()
    # Truncate the way RFC 4226 does, so the digits come from the whole digest
    # rather than from one arbitrary end of it.
    off = mac[-1] & 0x0F
    val = int.from_bytes(mac[off:off + 4], "big") & 0x7FFFFFFF
    return str(val).zfill(n)[-n:]


def make_code(secret: bytes, machine: str, expiry: date) -> str:
    """Build the response code. Used by the vendor script, and by the tests."""
    yymm = expiry.strftime("%y%m")
    d = _digits(secret, machine, yymm)
    return "%s-%s-%s" % (yymm, d[:4], d[4:])


def _end_of_month(year: int, month: int) -> date:
    return (date(year + (month == 12), (month % 12) + 1, 1)
            - timedelta(days=1))


def parse_code(code: str):
    """(expiry_date, digits) from a typed code, or (None, None) if malformed."""
    m = _CODE_RE.match((code or "").strip().replace(" ", ""))
    if not m:
        return None, None
    yymm, a, b = m.groups()
    try:
        year, month = 2000 + int(yymm[:2]), int(yymm[2:])
        if not 1 <= month <= 12:
            return None, None
        return _end_of_month(year, month), a + b
    except ValueError:
        return None, None


def check_code(code: str, machine: str = None, secret: bytes = None):
    """Verify a typed code. Returns (ok, expiry_date, reason)."""
    secret = clinic_secret() if secret is None else secret
    if not secret:
        return False, None, "no_secret"
    expiry, digits = parse_code(code)
    if not expiry:
        return False, None, "malformed"
    machine = machine or machine_id()
    expected = _digits(secret, machine, expiry.strftime("%y%m"))
    # Constant-time: a timing side channel here is far-fetched, but comparing
    # secrets with == is the habit worth not having.
    if not hmac.compare_digest(expected, digits):
        return False, None, "wrong_code"
    return True, expiry, "ok"


# ── stored state ──────────────────────────────────────────────────────────────

def activate(code: str, updated_by: str = "system"):
    """Verify and store a code. Returns (ok, message)."""
    import models.database as db

    ok, expiry, reason = check_code(code)
    if not ok:
        return False, {
            "no_secret": "This installation has no licence secret configured.",
            "malformed": "That code is not in the right format. It looks like 2708-4471-8823.",
            "wrong_code": "That code is not valid for this computer.",
        }.get(reason, "That code could not be accepted.")

    db.set_setting(_SETTING_CODE, code.strip(), "license", updated_by)
    db.set_setting(_SETTING_UNTIL, expiry.isoformat(), "license", updated_by)
    db.set_setting(_SETTING_MACHINE, machine_id(), "license", updated_by)
    logger.info("Licence activated until %s", expiry.isoformat())
    return True, "Activated until %s." % expiry.strftime("%d %B %Y")


def status() -> dict:
    """Everything the UI and the banner need. Never raises."""
    import models.database as db

    out = {
        "challenge": challenge(),
        "machine": machine_id(),
        "state": "unlicensed",     # unlicensed | active | expiring | lapsed | grace
        "valid_until": None,
        "days_left": None,
        "machine_changed": False,
        "banner": "",
        "blocks_anything": False,  # by design, always False
    }

    try:
        until_s = db.get_setting(_SETTING_UNTIL, "")
        stored_machine = db.get_setting(_SETTING_MACHINE, "")
        first_seen = db.get_setting(_SETTING_FIRST_SEEN, "")
    except Exception:
        logger.debug("licence status unavailable", exc_info=True)
        return out

    # Record when this installation first ran, so auto-grace has a floor even
    # if a licence was never entered at all.
    if not first_seen:
        try:
            db.set_setting(_SETTING_FIRST_SEEN, date.today().isoformat(), "license")
            first_seen = date.today().isoformat()
        except Exception:
            pass

    # Soft binding, as promised: a replaced PC is noted, never punished.
    if stored_machine and stored_machine != machine_id():
        out["machine_changed"] = True
        logger.warning("Licence was activated on machine %s, now running on %s",
                       stored_machine, machine_id())

    if not until_s:
        out["banner"] = ("This copy has not been activated. Everything works "
                         "normally - contact your supplier for an activation code.")
        return out

    try:
        until = datetime.strptime(until_s[:10], "%Y-%m-%d").date()
    except ValueError:
        return out

    out["valid_until"] = until.isoformat()
    left = (until - date.today()).days
    out["days_left"] = left

    if left >= 30:
        out["state"] = "active"
    elif left >= 0:
        out["state"] = "expiring"
        out["banner"] = ("Your licence renews in %d day%s."
                         % (left, "" if left == 1 else "s"))
    elif -left <= QUIET_DAYS:
        # Lapsed but still quiet. Nothing on screen yet.
        out["state"] = "lapsed"
    elif -left <= AUTO_GRACE_DAYS:
        out["state"] = "lapsed"
        out["banner"] = ("Your licence expired on %s. The system keeps working "
                         "as normal - please contact your supplier to renew."
                         % until.strftime("%d %B %Y"))
    else:
        # Past auto-grace. Stop asking, permanently.
        out["state"] = "grace"

    return out


def banner() -> str:
    """One line for base.html, or empty. Must never raise into a template."""
    try:
        return status().get("banner", "")
    except Exception:
        logger.debug("licence banner suppressed", exc_info=True)
        return ""


# ── enforcement ───────────────────────────────────────────────────────────────

# Endpoints reachable even while blocked. Without the licence page itself a
# clinic holding a perfectly good code could never type it in, and without
# auth.login they could not reach the licence page in the first place.
ALWAYS_ALLOWED = frozenset({
    "system.license_page",
    "auth.login", "auth.logout",
    "static",
    # Health checks must answer even while blocked. A blocked install that
    # cannot answer /healthz looks to monitoring exactly like a server that has
    # fallen over, and someone gets paged at 3am for a licence renewal.
    # Endpoint names verified against the live url_map, not guessed.
    "_healthz", "public_api.health",
})


def enforcement_mode() -> str:
    """'banner' (default) or 'block'. Deployment decides, not the code."""
    mode = (os.environ.get("ALEEFY_LICENSE_MODE") or "banner").strip().lower()
    return mode if mode in ("banner", "block") else "banner"


def is_blocked(st=None) -> bool:
    """Whether this installation should be held at the licence screen.

    Only ever true in block mode. Note what is NOT blocked:

      grace   - past AUTO_GRACE_DAYS the installation has given up asking, on
                purpose. An unreachable vendor must not brick a clinic.
      lapsed  - inside the quiet period. A late payer gets QUIET_DAYS before
                anything stops, so a renewal that slips never interrupts a
                consultation.
    """
    if enforcement_mode() != "block":
        return False

    # Block mode with no secret configured is a TRAP, not a lock: status()
    # would say unlicensed, this would block every page, and check_code() would
    # refuse every code with "no_secret" - so nothing could ever unblock it.
    # An install that cannot be rescued from its own front door is worse than
    # one that is not locked at all, so refuse to block and say why, loudly.
    if not clinic_secret():
        logger.error(
            "ALEEFY_LICENSE_MODE=block but ALEEFY_LICENSE_SECRET is not set. "
            "Refusing to block: with no secret no activation code could ever "
            "be accepted, so this would lock the clinic out permanently. "
            "Install the secret with scripts/install_license_secret.sh.")
        return False

    try:
        st = status() if st is None else st
    except Exception:
        # If the licence state cannot be read, ALLOW. A bug in this module must
        # never be the reason a clinic cannot open its own records.
        logger.debug("licence state unreadable - allowing", exc_info=True)
        return False

    state = st.get("state")
    if state == "unlicensed":
        return True
    if state == "lapsed":
        days_past = -(st.get("days_left") or 0)
        return days_past > QUIET_DAYS
    return False        # active, expiring, grace


def block_reason(st=None) -> str:
    """One sentence for the blocked screen. Must never sound like a crash."""
    try:
        st = status() if st is None else st
    except Exception:
        return ""
    if st.get("state") == "unlicensed":
        return ("This copy has not been activated yet. Your records are safe - "
                "nothing has been lost. Contact your supplier with the number "
                "below and they will give you an activation code.")
    return ("Your licence expired on %s. Your records are safe and nothing has "
            "been deleted. Contact your supplier with the number below to renew."
            % (st.get("valid_until") or ""))
