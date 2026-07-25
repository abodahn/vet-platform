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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ═══════════════════════════════════════════════════════════════
#  BASE — shared by all stages
# ═══════════════════════════════════════════════════════════════
class Config:
    # ── Identity ──────────────────────────────────────────────
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
