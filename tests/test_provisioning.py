"""
Provisioning: secret generation, uniqueness, and the rules that make a
re-run safe.

No PostgreSQL, no Docker, no network, no shelling out. Everything under test
is a pure function over strings and dicts in scripts/provision/clinic_env.py —
the shell scripts are thin wrappers around exactly these calls.

The one thing worth stating: the failure mode these guard against is not "the
script errors". It is "the script succeeds and quietly replaces a live clinic's
session key, admin password, or database password", which locks a clinic out of
its own patient records with no error message anywhere.
"""
import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "provision"))

import clinic_env as ce  # noqa: E402

from models.security import validate_password_strength  # noqa: E402


# ── generation ───────────────────────────────────────────────────────────────

def test_secret_key_satisfies_production_validator():
    key = ce.gen_secret_key()
    assert len(key) >= 32
    assert "CHANGE" not in key          # config.ProductionConfig.validate()


def test_admin_password_passes_the_apps_own_validator():
    """Generated, not chosen — but it still has to clear models.security."""
    for _ in range(200):
        ok, msg = validate_password_strength(ce.gen_admin_password())
        assert ok, msg


def test_admin_password_is_not_on_the_weak_list():
    weak = {"admin", "1234", "password", "Admin", "admin123"}
    assert ce.gen_admin_password() not in weak


def test_generated_values_survive_env_and_shell_unquoted():
    """A '$' would be eaten by docker-compose interpolation, a quote or '#'
    by the .env parser, a space by both. Any of those silently truncates a
    secret instead of failing."""
    forbidden = set(" \t\"'#$\\`")
    for _ in range(100):
        for value in (ce.gen_admin_password(), ce.gen_db_password(),
                      ce.gen_token(), ce.gen_secret_key()):
            assert not (set(value) & forbidden), repr(value)


def test_db_password_needs_no_url_encoding():
    """It goes inside postgresql://user:PASS@host verbatim."""
    for _ in range(100):
        assert ce.gen_db_password().isalnum()


def test_dsn_matches_the_shape_app_py_requires():
    """app.py regex-matches postgresql://user:pass@host:port/db. A DSN that
    does not match falls back to SQLite *silently* — an empty local file
    nobody backs up."""
    dsn = ce.build_dsn("clinic_a", ce.gen_db_password(), "127.0.0.1", 5432, "clinic_a")
    assert re.match(r"^postgresql://[^:]+:[^@]+@[^:]+:\d+/\w+$", dsn)


def test_admin_password_length_floor_is_enforced():
    with pytest.raises(ValueError):
        ce.gen_admin_password(length=8)


# ── uniqueness across runs ───────────────────────────────────────────────────

def test_every_secret_is_unique_across_runs():
    """The bug this replaces: deploy.sh shipped one PostgreSQL password to
    every customer, in a committed file."""
    runs = [ce.generate_secrets(db_user="u", db_host="h", db_port=5432,
                                db_name="d")
            for _ in range(50)]
    for key in ce.GENERATED_SECRETS:
        values = [r[key] for r in runs]
        assert len(set(values)) == len(values), f"{key} repeated across installs"


def test_no_secret_is_ever_empty_or_a_default():
    s = ce.generate_secrets(db_user="u", db_host="h", db_port=5432, db_name="d")
    assert set(s) == set(ce.GENERATED_SECRETS)
    for key, value in s.items():
        assert value, f"{key} is empty"
        assert "CHANGE" not in value
        assert "change-me" not in value.lower()
        assert len(value) >= 16


def test_sqlite_mode_leaves_the_dsn_empty_and_nothing_else():
    s = ce.generate_secrets(db_user="u", db_host="h", db_port=5432,
                            db_name="d", sqlite=True)
    assert s["POSTGRES_DSN"] == ""
    assert s["PLATFORM_SECRET_KEY"] and s["PLATFORM_ADMIN_PASS"]


# ── the secret surface is complete ───────────────────────────────────────────

def test_generated_set_covers_every_secret_the_app_reads():
    """Derived from a grep of os.environ.get across the tree. If someone adds
    a new secret-bearing env var and does not add it here, this is the test
    that should have caught it — update both together."""
    assert set(ce.GENERATED_SECRETS) == {
        "PLATFORM_SECRET_KEY", "PLATFORM_ADMIN_PASS", "POSTGRES_DSN",
        "WAITING_ROOM_TOKEN", "API_V1_KEY",
    }
    # Operator-supplied keys are never generated, but must never be wiped.
    for key in ("AI_API_KEY", "WAPILOT_TOKEN", "BACKUP_S3_SECRET", "SENTRY_DSN"):
        assert key in ce.PRESERVED_ON_UPGRADE


def test_built_env_has_what_production_config_validate_demands():
    env = ce.build_env(
        slug="acme", domain="acme.vet", host_port=5101,
        secrets_map=ce.generate_secrets(db_user="u", db_host="h",
                                        db_port=5432, db_name="d"),
        app_image="aleefy:v1")
    assert env["FLASK_ENV"] == "production"
    assert env["POSTGRES_DSN"]
    assert len(env["PLATFORM_SECRET_KEY"]) >= 32
    assert env["PLATFORM_ADMIN_PASS"]
    assert env["CORS_ALLOWED_ORIGIN"] == "https://acme.vet"   # not "*"
    assert env["CORS_ALLOW_WILDCARD"] == "0"
    assert env["SESSION_COOKIE_SECURE"] == "1"


def test_container_port_and_host_port_are_different_things():
    """gunicorn.conf.py binds PLATFORM_PORT *inside* the container; the host
    mapping is CLINIC_HOST_PORT. Conflating them makes the clinic answer on
    a port nothing is proxying to."""
    env = ce.build_env(slug="acme", domain="", host_port=5107,
                       secrets_map=ce.generate_secrets(
                           db_user="u", db_host="h", db_port=5432, db_name="d"),
                       app_image="aleefy:v1")
    assert env["PLATFORM_PORT"] == "5100"
    assert env["CLINIC_HOST_PORT"] == "5107"


# ── round-trip ───────────────────────────────────────────────────────────────

def test_env_round_trips_without_mangling_secrets():
    values = ce.build_env(slug="acme", domain="acme.vet", host_port=5101,
                          secrets_map=ce.generate_secrets(
                              db_user="u", db_host="h", db_port=5432, db_name="d"),
                          app_image="aleefy:v1")
    parsed = ce.parse_env(ce.render_env(values, "acme", "now"))
    for key, value in values.items():
        assert parsed[key] == value, key


def test_parse_env_ignores_comments_and_strips_quotes():
    parsed = ce.parse_env('# note\n\nA=1\nB="two"\nC=  three  \nbroken\n')
    assert parsed == {"A": "1", "B": "two", "C": "three"}


# ── idempotency ──────────────────────────────────────────────────────────────

def test_state_detection(tmp_path):
    assert ce.install_state(tmp_path / "nope") == "absent"
    half = tmp_path / "half"
    (half / "data").mkdir(parents=True)
    assert ce.install_state(half) == "partial"
    (half / ".env").write_text("A=1")
    assert ce.install_state(half) == "present"


def test_rerun_on_a_live_clinic_is_refused_not_overwritten():
    with pytest.raises(ce.InstallExists) as exc:
        ce.plan("present", upgrade=False)
    assert "--upgrade" in str(exc.value)


def test_fresh_and_half_finished_installs_are_created():
    assert ce.plan("absent", upgrade=False) == "create"
    assert ce.plan("partial", upgrade=False) == "create"   # nothing to lose
    assert ce.plan("present", upgrade=True) == "upgrade"


def test_upgrade_keeps_every_existing_secret():
    """Regenerating PLATFORM_SECRET_KEY logs everyone out; regenerating
    POSTGRES_DSN orphans the clinic from its own database."""
    existing = ce.build_env(slug="acme", domain="acme.vet", host_port=5101,
                            secrets_map=ce.generate_secrets(
                                db_user="u", db_host="h", db_port=5432, db_name="d"),
                            app_image="aleefy:v1")
    fresh = ce.build_env(slug="acme", domain="acme.vet", host_port=5101,
                         secrets_map=ce.generate_secrets(
                             db_user="u", db_host="h", db_port=5432, db_name="d"),
                         app_image="aleefy:v2")
    merged = ce.merge_env(existing, fresh)
    for key in ce.GENERATED_SECRETS:
        assert merged[key] == existing[key], f"{key} was regenerated on upgrade"
    assert merged["APP_IMAGE"] == "aleefy:v2"      # config does move forward


def test_upgrade_preserves_operator_supplied_keys():
    existing = {"AI_API_KEY": "sk-paid-for-this", "WAPILOT_TOKEN": "wa-123"}
    merged = ce.merge_env(existing, {"AI_API_KEY": "", "FLASK_ENV": "production"})
    assert merged["AI_API_KEY"] == "sk-paid-for-this"
    assert merged["WAPILOT_TOKEN"] == "wa-123"      # unknown-to-fresh keys survive


def test_upgrade_can_still_fill_in_a_blank_secret():
    """A placeholder line is not a value — a later run may legitimately set it."""
    merged = ce.merge_env({"WAITING_ROOM_TOKEN": "   "},
                          {"WAITING_ROOM_TOKEN": "real-token"})
    assert merged["WAITING_ROOM_TOKEN"] == "real-token"


def test_upgrade_does_not_resurrect_a_deliberately_removed_var():
    """Only PRESERVED keys are carried over as secrets; plain config follows
    the new template."""
    merged = ce.merge_env({"LOG_LEVEL": "DEBUG"}, {"LOG_LEVEL": "INFO"})
    assert merged["LOG_LEVEL"] == "INFO"


# ── ports ────────────────────────────────────────────────────────────────────

def test_ports_do_not_collide():
    taken = {5100: "a", 5101: "b", 5103: "c"}
    assert ce.next_port(taken) == 5102


def test_port_exhaustion_is_an_error_not_a_collision():
    with pytest.raises(ValueError):
        ce.next_port(set(range(5100, 5110)), base=5100, limit=5110)


def test_taken_ports_reads_provisioned_clinics(tmp_path):
    for slug, port in (("a", 5100), ("b", 5104)):
        d = tmp_path / "clinics" / slug
        d.mkdir(parents=True)
        (d / ".env").write_text(f"CLINIC_HOST_PORT={port}\nPLATFORM_PORT=5100\n")
    assert ce.taken_ports(tmp_path) == {5100: "a", 5104: "b"}
    assert ce.next_port(ce.taken_ports(tmp_path)) == 5101


def test_taken_ports_on_a_fresh_host_is_empty(tmp_path):
    assert ce.taken_ports(tmp_path) == {}


# ── file permissions ─────────────────────────────────────────────────────────

def test_env_is_written_not_world_readable(tmp_path):
    path = tmp_path / "clinic" / ".env"
    warnings = ce.write_env(path, "PLATFORM_ADMIN_PASS=hunter2\n")
    assert path.read_text() == "PLATFORM_ADMIN_PASS=hunter2\n"
    if os.name == "nt":
        # Honest about the limit rather than asserting a mode Windows cannot set.
        assert warnings and "Windows" in warnings[0]
    else:
        assert not warnings
        assert path.stat().st_mode & 0o777 == 0o600
        assert not path.stat().st_mode & 0o077   # no group, no other


def test_slug_rules_reject_what_would_break_a_container_name():
    for bad in ("A", "ab", "-abc", "abc-", "a b", "a_b", "a" * 40, "clinic/../x"):
        assert not ce.SLUG_RE.match(bad), bad
    for good in ("acme", "happy-tails", "clinic-01"):
        assert ce.SLUG_RE.match(good), good
