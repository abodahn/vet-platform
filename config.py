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
    SEED_ADMIN_USER = os.environ.get("PLATFORM_ADMIN_USER", "admin")
    SEED_ADMIN_PASS = os.environ.get("PLATFORM_ADMIN_PASS", "admin")

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

    # Dev uses local PostgreSQL (or falls back to SQLite automatically)
    POSTGRES_DSN = os.environ.get(
        "POSTGRES_DSN",
        f"postgresql://postgres:1234@localhost:5432/vetclinic"
    )

    # Relaxed cookie security — no HTTPS on localhost
    SESSION_COOKIE_SECURE = False

    # Seeded admin credentials for dev
    SEED_ADMIN_USER = os.environ.get("PLATFORM_ADMIN_USER", "admin")
    SEED_ADMIN_PASS = os.environ.get("PLATFORM_ADMIN_PASS", "Ahmed@1122")


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
