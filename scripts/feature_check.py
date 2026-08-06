# -*- coding: utf-8 -*-
"""What can THIS installation actually do — as opposed to what the code has?

    python scripts/feature_check.py
    python scripts/feature_check.py --demo     # only what matters in a demo

Every bug found on the first day the demo server was live was the same bug:

    the screen advertised something this deployment could not deliver

Ten times. Two toolbar buttons and a module card pointing at a Windows program
that is not on a Linux server. A floating AI chat button with no AI provider
configured, answering with the OpenAI SDK's own credential error. A language
toggle posting to a URL that did not exist. A go-live gate that could not see
the backups it was gating on. Printed demo credentials that did not sign in.

None of it was caught by 1,738 tests, because every test asked "does this
feature work?" and none asked "can this box run it?".

That is the question this script asks. It is not a test; it is a report about
one machine at one moment, and it is meant to be run:

  * before a demo — so nothing gets claimed that this server cannot show
  * before a handover — so the clinic is not sold a feature it has no key for
  * after any deployment — because the answer changes with the environment

A feature that is off is fine. A feature that is off while the UI says it is on
is the thing that loses the room.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

READY, OFF, BROKEN = "READY", "OFF", "BROKEN"

_MARK = {READY: "  ✓  ", OFF: "  –  ", BROKEN: " !!! "}

_results: list = []


def report(feature, status, detail="", demo_critical=False):
    _results.append((status, feature, detail, demo_critical))


# ── the checks ────────────────────────────────────────────────────────────────

def check_ai():
    """The Petsy button is on every page and the assistant card says Live."""
    try:
        from blueprints.ai_assistant.routes import (ai_configured, FREELLM_MODEL,
                                                    FREELLM_BASE_URL)
    except Exception as exc:
        return report("AI assistant / Petsy", BROKEN, str(exc)[:80], True)
    if ai_configured():
        where = "local proxy" if "localhost" in FREELLM_BASE_URL else FREELLM_BASE_URL
        report("AI assistant / Petsy", READY, f"{FREELLM_MODEL} via {where}", True)
    else:
        report("AI assistant / Petsy", OFF,
               "no AI_API_KEY and no local proxy — the buttons are visible and "
               "will answer 'not enabled'", True)


def check_whatsapp():
    """Reminders are a headline feature and the reason a clinic recovers
    lapsed vaccinations. Selling it without a provider is selling nothing."""
    token = os.environ.get("WAPILOT_TOKEN", "").strip()
    inst = os.environ.get("WAPILOT_INSTANCE", "").strip()
    if not (token and inst):
        try:
            import models.database as db
            conn = db.get_db()
            try:
                rows = {r[0]: r[1] for r in conn.execute(
                    "SELECT key, value FROM settings WHERE category='wapilot'"
                ).fetchall()}
            finally:
                conn.close()
            token = token or (rows.get("wapilot_token") or "").strip()
            inst = inst or (rows.get("wapilot_instance_id") or "").strip()
        except Exception:
            pass
    if token and inst:
        report("WhatsApp reminders", READY, f"instance {inst[:10]}…", True)
    else:
        report("WhatsApp reminders", OFF,
               "no Wapilot token/instance — nothing will actually send. Do not "
               "promise automatic reminders on this deployment.", True)


def check_payments():
    """Already done right: available() hides an unconfigured gateway rather
    than offering it. Reported so the operator knows what the clinic can take."""
    try:
        from models import payments
        got = payments.available()
    except Exception as exc:
        return report("Payment methods", BROKEN, str(exc)[:80], True)
    names = ", ".join(g.label for g in got)
    online = [g for g in got if not g.offline]
    report("Payment methods", READY if got else BROKEN,
           names + ("" if online else "  (counter methods only — no card gateway)"),
           True)


def check_backups():
    from models import backup as bk
    from config import Config
    data_dir = os.path.dirname(Config.DATABASE_PATH) or "."
    bk.configure(db_path=Config.DATABASE_PATH,
                 backup_dir=os.path.join(data_dir, "backups"))
    off = bk.offsite_targets()
    if off:
        report("Off-site backup", READY, ", ".join(t["label"] for t in off))
    else:
        report("Off-site backup", OFF,
               "backups sit next to the database. The Continuity Guarantee "
               "promises a copy the clinic controls — set BACKUP_OFFSITE_DIR "
               "or BACKUP_S3_BUCKET before signing it.")


def check_legacy():
    enabled = os.environ.get("LEGACY_APP_ENABLED", "1") not in ("0", "false", "no")
    if enabled:
        report("Legacy Windows app", READY if sys.platform == "win32" else BROKEN,
               "enabled — only valid when the platform runs on the clinic's own "
               "Windows PC beside the old program")
    else:
        report("Legacy Windows app", OFF, "correctly disabled on a hosted server")


def check_public_api():
    key = os.environ.get("API_V1_KEY", "").strip()
    report("Public API (v1)", READY if key else OFF,
           "key set" if key else "no API_V1_KEY — integrations cannot authenticate")


def check_tls_and_cookies():
    secure = os.environ.get("SESSION_COOKIE_SECURE", "0") in ("1", "true", "yes")
    env = os.environ.get("FLASK_ENV", "development")
    if env == "production" and not secure:
        report("Secure session cookies", BROKEN,
               "production without Secure cookies — sign-in will silently fail "
               "over plain HTTP", True)
    else:
        report("Secure session cookies", READY if secure else OFF,
               "on" if secure else "development")


def _configure_like_the_app():
    """Point models.backup and models.tenancy where create_app() points them.

    Both keep their target in module globals that only create_app() sets. A CLI
    script that skips this reads the DEFAULT database instead of the clinic's —
    which is how the first run of this very script reported "-1 vaccinations
    due" while the demo clinic had forty. Third time today.
    """
    import models.backup as bk
    from config import Config
    from models import tenancy
    data_dir = os.path.dirname(Config.DATABASE_PATH) or "."
    bk.configure(db_path=Config.DATABASE_PATH,
                 backup_dir=os.path.join(data_dir, "backups"))
    if not tenancy._registry_path:
        tenancy.configure(os.environ.get("TENANT_REGISTRY", "").strip()
                          or os.path.join(data_dir, "tenants.db"))


def check_demo_data():
    """A feature with an empty screen demos as an absence. The vaccination
    reminder list was empty for months because every seeded shot fell due a
    year out and the visit history only went back six."""
    from datetime import date, timedelta

    import models.database as db
    from models import tenancy

    _configure_like_the_app()
    today = date.today().isoformat()
    soon = (date.today() + timedelta(days=30)).isoformat()

    clinics = []
    try:
        clinics = [r["slug"] for r in tenancy.all_tenants(active_only=True)]
    except Exception:
        pass

    def counts():
        conn = db.get_db()
        try:
            def n(sql, *p):
                return conn.execute(sql, p).fetchone()[0]
            return (
                n("SELECT COUNT(*) FROM vaccinations WHERE next_due_at >= ? AND next_due_at <= ?",
                  today, soon),
                n("SELECT COUNT(*) FROM invoices WHERE due_amount > 0"),
                n("SELECT COUNT(*) FROM appointments WHERE appt_date = ?", today),
            )
        finally:
            conn.close()

    for slug in (clinics or [""]):
        label = f"Demo data ({slug})" if slug else "Demo data on key screens"
        try:
            ctx = tenancy.use(slug) if slug else None
            if ctx:
                with ctx:
                    due, unpaid, appts = counts()
            else:
                due, unpaid, appts = counts()
        except Exception as exc:
            # A failed query is not an empty screen, and reporting it as one is
            # how the first version of this check called a broken read "fine".
            report(label, BROKEN, f"could not read the clinic: {str(exc)[:60]}", True)
            continue
        empty = [n for n, v in (("vaccinations due", due),
                                ("unpaid invoices", unpaid),
                                ("today's appointments", appts)) if v == 0]
        if empty:
            report(label, BROKEN,
                   "empty: " + ", ".join(empty) + " — these demo as missing features",
                   True)
        else:
            report(label, READY,
                   f"{due} vaccinations due, {unpaid} unpaid invoices, "
                   f"{appts} appointments today", True)


CHECKS = [check_ai, check_whatsapp, check_payments, check_backups,
          check_legacy, check_public_api, check_tls_and_cookies, check_demo_data]


def run(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--demo", action="store_true",
                   help="only the features that appear in a sales demo")
    args = p.parse_args(argv)

    _results.clear()
    for fn in CHECKS:
        try:
            fn()
        except Exception as exc:
            report(fn.__name__, BROKEN, f"the check itself failed: {str(exc)[:70]}")

    rows = [r for r in _results if r[3]] if args.demo else _results
    width = max(len(f) for _, f, _, _ in rows)
    print()
    for status, feature, detail, _ in rows:
        print(f"{_MARK[status]} {feature.ljust(width)}  {detail}")
    print()

    broken = [r for r in rows if r[0] == BROKEN]
    off = [r for r in rows if r[0] == OFF]
    if broken:
        print(f"  {len(broken)} broken. Fix before showing this to anyone.")
    if off:
        print(f"  {len(off)} switched off. That is fine — just do not claim them:")
        for _, f, _, _ in off:
            print(f"      · {f}")
    if not broken and not off:
        print("  Everything this installation advertises, it can do.")
    print()
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(run())
