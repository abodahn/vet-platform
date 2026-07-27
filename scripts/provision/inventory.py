#!/usr/bin/env python3
"""
What is running, what version, when did it last back up.

    python3 inventory.py              # table for a human
    python3 inventory.py --json       # for a cron job / monitor
    python3 inventory.py --quiet      # only clinics with a problem

Reads each clinic's .env for its port and version, probes /api/v1/health, and
takes the newest archive in its backup directory as the last-backup record —
the same rule models/backup.py uses, deliberately: a status table that can
disagree with the files on disk is how "nightly backup OK" gets logged while
no file exists.

Prints no secrets. Safe to pipe into a file, a chat, or a ticket.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from clinic_env import parse_env  # noqa: E402

DEFAULT_ROOT = Path(os.environ.get("ALEEFY_ROOT", "/srv/aleefy"))
BACKUP_PREFIXES = ("platform_backup_", "pre_restore_", "uploaded_")
BACKUP_EXTS = (".db", ".dump")
STALE_AFTER_DAYS = 2       # matches models/backup.py BACKUP_STALE_DAYS default


def probe(port: str, timeout: float = 4.0) -> dict:
    """GET /api/v1/health. 503 is a real answer (degraded), not a failure."""
    url = f"http://127.0.0.1:{port}/api/v1/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return {"up": True, **json.loads(resp.read().decode())}
    except urllib.error.HTTPError as exc:
        try:
            return {"up": True, **json.loads(exc.read().decode())}
        except (ValueError, OSError):
            return {"up": True, "status": f"http {exc.code}"}
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"up": False, "status": "down", "error": str(exc)}


def last_backup(backup_dir: Path) -> dict:
    """Newest readable archive, or an explicit 'never'."""
    if not backup_dir.is_dir():
        return {"at": None, "age_days": None, "file": None, "note": "no backup dir"}
    newest = None
    for entry in backup_dir.iterdir():
        if entry.suffix in BACKUP_EXTS and entry.name.startswith(BACKUP_PREFIXES):
            try:
                mtime = entry.stat().st_mtime
            except OSError:
                continue
            if newest is None or mtime > newest[0]:
                newest = (mtime, entry.name)
    if newest is None:
        return {"at": None, "age_days": None, "file": None, "note": "never"}
    when = datetime.fromtimestamp(newest[0])
    return {
        "at": when.isoformat(timespec="minutes"),
        "age_days": round((datetime.now() - when) / timedelta(days=1), 1),
        "file": newest[1],
        "note": "",
    }


def collect(root: Path) -> list[dict]:
    rows = []
    clinics = root / "clinics"
    if not clinics.is_dir():
        return rows
    for env_file in sorted(clinics.glob("*/.env")):
        clinic_dir = env_file.parent
        try:
            env = parse_env(env_file.read_text(encoding="utf-8"))
        except OSError as exc:
            rows.append({"clinic": clinic_dir.name, "error": f"unreadable .env: {exc}"})
            continue
        port = env.get("CLINIC_HOST_PORT", "")
        health = probe(port) if port else {"up": False, "status": "no port in .env"}
        backup = last_backup(clinic_dir / "data" / "backups")
        rows.append({
            "clinic":   clinic_dir.name,
            "port":     port,
            "version":  env.get("APP_VERSION", "?"),
            "image":    env.get("APP_IMAGE", "?"),
            "db":       "postgres" if env.get("POSTGRES_DSN") else "sqlite",
            "up":       health.get("up", False),
            "status":   health.get("status", "unknown"),
            "database": health.get("database", "?"),
            "backup":   backup,
            "problems": problems(health, backup),
        })
    return rows


def problems(health: dict, backup: dict) -> list[str]:
    out = []
    if not health.get("up"):
        out.append("DOWN")
    elif health.get("status") != "healthy":
        out.append(f"degraded ({health.get('database', '?')})")
    if backup["at"] is None:
        out.append("NO BACKUP EVER")
    elif backup["age_days"] is not None and backup["age_days"] > STALE_AFTER_DAYS:
        out.append(f"backup {backup['age_days']}d old")
    return out


def as_table(rows: list[dict]) -> str:
    if not rows:
        return "no clinics provisioned"
    head = f"{'CLINIC':<18}{'PORT':<7}{'VERSION':<14}{'DB':<10}{'UP':<5}{'LAST BACKUP':<18}NOTES"
    lines = [head, "-" * len(head)]
    for r in rows:
        if "error" in r:
            lines.append(f"{r['clinic']:<18}{'':<7}{'':<14}{'':<10}{'?':<5}{'':<18}{r['error']}")
            continue
        age = r["backup"]["at"] or r["backup"]["note"] or "never"
        lines.append(
            f"{r['clinic']:<18}{r['port']:<7}{r['version']:<14}{r['db']:<10}"
            f"{('yes' if r['up'] else 'NO'):<5}{age:<18}{', '.join(r['problems'])}"
        )
    bad = sum(1 for r in rows if r.get("problems") or "error" in r)
    lines += ["", f"{len(rows)} clinic(s), {bad} needing attention"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    p.add_argument("--json", action="store_true")
    p.add_argument("--quiet", action="store_true", help="only clinics with problems")
    args = p.parse_args(argv)

    rows = collect(args.root)
    if args.quiet:
        rows = [r for r in rows if r.get("problems") or "error" in r]
    print(json.dumps(rows, indent=2) if args.json else as_table(rows))
    # Non-zero when something needs a human, so cron mails you only then.
    return 1 if any(r.get("problems") or "error" in r for r in rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
