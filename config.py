"""
Premium Animal Hospital Platform — Configuration

Two stages:
  development  →  local Windows machine, DEBUG on, SQLite fallback OK
  production   →  Koyeb (free) + Neon.tech PostgreSQL (free), HTTPS, DEBUG off

Stage is selected by the FLASK_ENV environment variable (default: development).
All sensitive values come from environment variables / .env file — never hardcoded.

Usage:
  FLASK_ENV=development  python run.py        # dev
  FLASK_ENV=production   gunicorn ...         # prod (Koyeb / any server)
"""

import os
import socket
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ═══════════════════════════════════════════════════════════════
#  VERSION — one source of truth for "which build is this clinic on"
#
#  20 clinics, two people, no remote access. When one of them calls,
#  the first question is which build they are running. The VERSION file
#  answers it; the commit says exactly which code; the date says when it
#  landed on that machine.
# ═══════════════════════════════════════════════════════════════
_VERSION_FILE = os.path.join(BASE_DIR, "VERSION")


def _git_commit() -> str:
    """Short commit hash, or "" when there is no .git — the normal deployed case.

    Reads .git/HEAD directly instead of shelling out to `git`: a clinic
    workstation has no git binary, and a subprocess on every boot buys nothing.

    # ponytail: loose refs only. Ceiling: a repo whose current branch ref has
    # been packed into .git/packed-refs reports "" instead of the hash. Set
    # GIT_COMMIT in the build/deploy step if that ever bites.
    """
    env = os.environ.get("GIT_COMMIT", "").strip()
    if env:
        return env[:12]
    git_dir = os.path.join(BASE_DIR, ".git")
    try:
        with open(os.path.join(git_dir, "HEAD"), encoding="utf-8") as fh:
            head = fh.read().strip()
        if head.startswith("ref:"):
            ref = head.split(None, 1)[1]
            with open(os.path.join(git_dir, *ref.split("/")), encoding="utf-8") as fh:
                head = fh.read().strip()
    except (OSError, IndexError, UnicodeDecodeError):
        return ""      # no .git, or .git is a worktree pointer file — expected
    ok = len(head) == 40 and all(c in "0123456789abcdef" for c in head.lower())
    return head[:12] if ok else ""


def _read_version() -> dict:
    """{version, commit, built, full}. Never raises — a missing file is not fatal."""
    try:
        with open(_VERSION_FILE, encoding="utf-8") as fh:
            number = fh.read().strip().splitlines()[0].strip()
        # No build step in this project, so the file's mtime is the honest
        # answer to "when did this code land on this machine".
        built = datetime.fromtimestamp(os.path.getmtime(_VERSION_FILE)).strftime("%Y-%m-%d")
    except (OSError, IndexError):
        number, built = "0.0.0-unknown", "unknown"
    commit = _git_commit()
    return {
        "version": number,
        "commit":  commit,
        "built":   os.environ.get("BUILD_DATE", "").strip() or built,
        "full":    f"{number}+{commit}" if commit else number,
    }


VERSION_INFO = _read_version()

# blueprints/system/routes.py and blueprints/api_v1/routes.py already read these
# three names from the environment. Seeding them here makes the VERSION file the
# single source of truth without editing those files; an explicitly-set env var
# still wins, so a container can override.
os.environ.setdefault("APP_VERSION",  VERSION_INFO["version"])
os.environ.setdefault("BUILD_NUMBER", VERSION_INFO["commit"] or "source")
os.environ.setdefault("RELEASE_DATE", VERSION_INFO["built"])

# ── Deployment identity ────────────────────────────────────────
# One deployment = one clinic (see docs/market/05_PRODUCT_READINESS.md §3.1).
# Without this, an aggregated error report cannot say whose clinic it came from,
# which is the difference between a useful alert and noise. Hostname is the
# honest default: it is what the clinic's own machine calls itself.
_CLINIC_ID = os.environ.get("CLINIC_ID", "").strip() or socket.gethostname()
CLINIC_ID = _CLINIC_ID


# ═══════════════════════════════════════════════════════════════
#  BASE — shared by all stages
# ═══════════════════════════════════════════════════════════════
class Config:
    # ── Identity ──────────────────────────────────────────────
    VERSION      = VERSION_INFO["version"]
    VERSION_FULL = VERSION_INFO["full"]
    CLINIC_ID    = _CLINIC_ID
    APP_TITLE    = os.environ.get("PLATFORM_TITLE",    "Aleefy")
    APP_TITLE_AR = os.environ.get("PLATFORM_TITLE_AR", "اليفي")
    APP_SUBTITLE = os.environ.get("PLATFORM_SUBTITLE", "Dr. Hatem El Khateeb")
    APP_TAGLINE  = os.environ.get("PLATFORM_TAGLINE",  "Happy Pets, Healthy Lives")

    # ── Security ──────────────────────────────────────────────
    SECRET_KEY = os.environ.get(
        "PLATFORM_SECRET_KEY",
        "dev-only-key-CHANGE-IN-PRODUCTION-please"
    )
    SESSION_COOKIE_HTTPONLY  = True
    SESSION_COOKIE_SAMESITE  = "Lax"
    SESSION_COOKIE_SECURE    = os.environ.get("SESSION_COOKIE_SECURE", "0") in ("1", "true", "yes")
    PERMANENT_SESSION_LIFETIME = 86400   # 24 h

    # ── Database ──────────────────────────────────────────────
    DATABASE_PATH = os.environ.get(
        "PLATFORM_DB_PATH",
        os.path.join(BASE_DIR, "data", "platform.db")
    )
    POSTGRES_DSN = os.environ.get("POSTGRES_DSN", "")

    # ── Server ────────────────────────────────────────────────
    HOST  = os.environ.get("PLATFORM_HOST", "0.0.0.0")
    PORT  = int(os.environ.get("PLATFORM_PORT", "5100"))
    DEBUG = False

    # ── Seed admin (used only on first DB init) ───────────────
    # SEED_ADMIN_PASS default is empty string — must be set via env var.
    # A blank value prevents accidental seeding with "admin" in production.
    SEED_ADMIN_USER = os.environ.get("PLATFORM_ADMIN_USER", "admin")
    SEED_ADMIN_PASS = os.environ.get("PLATFORM_ADMIN_PASS", "")

    # ── CORS ─────────────────────────────────────────────────
    # Set CORS_ALLOWED_ORIGIN to your website domain in production (e.g. https://aleefy.vet)
    CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGIN", "*")

    # ── Legacy clinic app ─────────────────────────────────────
    LEGACY_APP_URL     = os.environ.get("LEGACY_APP_URL", "http://localhost:5000")
    LEGACY_APP_ENABLED = os.environ.get("LEGACY_APP_ENABLED", "1") not in ("0", "false", "no")

    # ── Uploads ───────────────────────────────────────────────
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024   # 16 MB

    # ── Legacy data dir ───────────────────────────────────────
    LEGACY_DATA_DIR = os.environ.get(
        "LEGACY_DATA_DIR",
        os.path.join(BASE_DIR, "..", "ppc_diagnostics_work", "data"),
    )


# ═══════════════════════════════════════════════════════════════
#  DEVELOPMENT — local Windows/Mac/Linux dev machine
#  python run.py   (or FLASK_ENV=development python run.py)
# ═══════════════════════════════════════════════════════════════
class DevelopmentConfig(Config):
    DEBUG   = True
    TESTING = False

    # Dev uses local PostgreSQL when POSTGRES_DSN is set (see .env.development),
    # otherwise falls back to SQLite. No hardcoded credentials — a default DSN
    # here would also make the SQLite fallback unreachable.
    POSTGRES_DSN = os.environ.get("POSTGRES_DSN", "")

    # Relaxed cookie security — no HTTPS on localhost
    SESSION_COOKIE_SECURE = False

    # Seeded admin credentials for dev — must be overridden via env var in production
    SEED_ADMIN_USER = os.environ.get("PLATFORM_ADMIN_USER", "admin")
    SEED_ADMIN_PASS = os.environ.get("PLATFORM_ADMIN_PASS", "")


# ═══════════════════════════════════════════════════════════════
#  PRODUCTION — Koyeb (free) + Neon.tech PostgreSQL (free)
#  All values MUST come from environment variables / .env.production
#  gunicorn -c gunicorn.conf.py "app:create_app()"
# ═══════════════════════════════════════════════════════════════
class ProductionConfig(Config):
    DEBUG   = False
    TESTING = False

    # HTTPS cookies — Koyeb provides SSL automatically
    SESSION_COOKIE_SECURE = True

    # Neon.tech free PostgreSQL DSN — set in Koyeb environment variables
    # Format: postgresql://user:pass@ep-xxx.region.aws.neon.tech/vetclinic?sslmode=require
    POSTGRES_DSN = os.environ.get("POSTGRES_DSN", "")

    # Production secret key — set in Koyeb environment variables
    SECRET_KEY = os.environ.get("PLATFORM_SECRET_KEY", "")

    @classmethod
    def validate(cls):
        """Call at startup to catch missing required production env vars."""
        errors = []
        if not cls.POSTGRES_DSN:
            errors.append("POSTGRES_DSN is not set")
        if not cls.SECRET_KEY or "CHANGE" in cls.SECRET_KEY:
            errors.append("PLATFORM_SECRET_KEY is not set or still default")
        elif len(cls.SECRET_KEY) < 32:
            errors.append(
                f"PLATFORM_SECRET_KEY is too short ({len(cls.SECRET_KEY)} chars, need >= 32). "
                'Generate one with: python -c "import secrets; print(secrets.token_hex(64))"'
            )
        seed_pass = os.environ.get("PLATFORM_ADMIN_PASS", "")
        if not seed_pass:
            errors.append("PLATFORM_ADMIN_PASS is not set (required for first DB seed)")
        if seed_pass in ("admin", "1234", "password", "Admin", "admin123"):
            errors.append("PLATFORM_ADMIN_PASS is set to a trivially weak value")
        # CORS: blueprints/public_api/routes.py defaults _CORS_ORIGIN to "*", so an
        # UNSET var is a live wildcard — the old check only caught a literal "*" and
        # therefore never fired. Both cases are now hard errors. Escape hatch for a
        # deployment that genuinely needs the wildcard: CORS_ALLOW_WILDCARD=1.
        cors = os.environ.get("CORS_ALLOWED_ORIGIN", "")
        if (not cors or cors == "*") and os.environ.get("CORS_ALLOW_WILDCARD", "") != "1":
            errors.append(
                "CORS_ALLOWED_ORIGIN is unset or '*' — the public API would answer any "
                "origin. Set it to your website domain (e.g. https://aleefy.vet), or set "
                "CORS_ALLOW_WILDCARD=1 to accept the wildcard deliberately."
            )
        if errors:
            raise RuntimeError(
                "Production config is incomplete:\n" +
                "\n".join(f"  - {e}" for e in errors)
            )


# ═══════════════════════════════════════════════════════════════
#  STAGE SELECTOR
# ═══════════════════════════════════════════════════════════════
_ENV = os.environ.get("FLASK_ENV", "development").lower()

config = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "default":     DevelopmentConfig,
}

# The active config for this run
ActiveConfig = config.get(_ENV, DevelopmentConfig)

# Alias used by app.py and run.py
Config = ActiveConfig
