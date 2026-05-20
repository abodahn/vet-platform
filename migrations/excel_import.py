#!/usr/bin/env python3
"""
Excel -> SQLite Migration Tool
Premium Animal Hospital — Premium Platform

Usage:
  python migrations/excel_import.py [--dry-run] [--db path/to/platform.db] [--only owners,pets]

Reads legacy Excel files from C:\\vet\\ppc_diagnostics_work\\data\\ and imports
them into the platform SQLite database.
"""

import sys
import os
import argparse
from datetime import datetime
from pathlib import Path

# Add platform root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import openpyxl
except ImportError:
    print("ERROR: openpyxl not installed. Run: pip install openpyxl")
    sys.exit(1)

import sqlite3

LEGACY_DATA = Path(__file__).parent.parent.parent / "ppc_diagnostics_work" / "data"


# ── DB helpers ────────────────────────────────────────────────────────────────

def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Excel reader ──────────────────────────────────────────────────────────────

def read_excel(filename: str) -> list:
    """Read an Excel file and return list of dicts (header row as keys)."""
    path = LEGACY_DATA / filename
    if not path.exists():
        print(f"  [SKIP] {filename} not found at {path}")
        return []

    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        wb.close()
        return []

    headers = [
        str(h).strip() if h is not None else f"col_{i}"
        for i, h in enumerate(rows[0])
    ]
    result = []
    for row in rows[1:]:
        if all(v is None for v in row):
            continue
        result.append({headers[i]: row[i] for i in range(len(headers))})

    wb.close()
    return result


def _str(val) -> str:
    """Convert a cell value to a clean string, returning '' for None/None-like."""
    if val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("none", "nan", "null", "-", "n/a") else s


# ── Importers ─────────────────────────────────────────────────────────────────

def migrate_owners(conn: sqlite3.Connection, rows: list, dry_run: bool) -> int:
    """Import owners from owners.xlsx."""
    count = 0
    for row in rows:
        name  = _str(row.get("name") or row.get("full_name") or row.get("Name") or row.get("owner_name") or "")
        phone = _str(row.get("phone") or row.get("Phone") or row.get("mobile") or row.get("Mobile") or "")
        email = _str(row.get("email") or row.get("Email") or "")
        addr  = _str(row.get("address") or row.get("Address") or "")
        notes = _str(row.get("notes") or row.get("Notes") or "")

        if not name:
            continue

        if not dry_run:
            # Avoid duplicates by name + phone
            existing = conn.execute(
                "SELECT id FROM owners WHERE full_name=? OR (phone=? AND phone != '')",
                (name, phone),
            ).fetchone()

            if not existing:
                conn.execute(
                    """INSERT INTO owners
                       (full_name, phone, whatsapp_phone, email, address, notes, created_by)
                       VALUES (?,?,?,?,?,?,'excel_import')""",
                    (name, phone, phone, email or None, addr or None, notes or None),
                )
                count += 1
        else:
            count += 1

    if not dry_run:
        conn.commit()
    return count


def migrate_pets(conn: sqlite3.Connection, rows: list, dry_run: bool) -> int:
    """Import pets from pets.xlsx."""
    count = 0
    for row in rows:
        pet_name   = _str(row.get("pet_name") or row.get("name") or row.get("Pet Name") or row.get("Pet") or "")
        owner_name = _str(row.get("owner_name") or row.get("owner") or row.get("Owner") or "")
        species    = _str(row.get("species") or row.get("Species") or row.get("type") or row.get("Type") or "Unknown")
        breed      = _str(row.get("breed") or row.get("Breed") or "")
        sex        = _str(row.get("sex") or row.get("gender") or row.get("Sex") or "Unknown")
        dob        = _str(row.get("dob") or row.get("DOB") or row.get("date_of_birth") or "")

        if not pet_name:
            continue

        if not dry_run:
            # Find or create owner
            owner_id = None
            if owner_name:
                owner_row = conn.execute(
                    "SELECT id FROM owners WHERE full_name LIKE ?",
                    (f"%{owner_name}%",),
                ).fetchone()
                if owner_row:
                    owner_id = owner_row["id"]

            if owner_id is None:
                conn.execute(
                    "INSERT INTO owners (full_name, created_by) VALUES (?, 'excel_import')",
                    (owner_name or "Unknown Owner",),
                )
                owner_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Avoid duplicates
            existing = conn.execute(
                "SELECT id FROM pets WHERE pet_name=? AND owner_id=?",
                (pet_name, owner_id),
            ).fetchone()

            if not existing:
                conn.execute(
                    """INSERT INTO pets
                       (owner_id, pet_name, species, breed, sex, dob, created_at)
                       VALUES (?,?,?,?,?,?,datetime('now'))""",
                    (owner_id, pet_name, species, breed or None, sex, dob or None),
                )
                count += 1
        else:
            count += 1

    if not dry_run:
        conn.commit()
    return count


def migrate_bookings(conn: sqlite3.Connection, rows: list, dry_run: bool) -> int:
    """Import bookings/appointments from bookings.xlsx."""
    count = 0
    for row in rows:
        owner_name = _str(row.get("owner_name") or row.get("owner") or row.get("Owner") or "")
        pet_name   = _str(row.get("pet_name") or row.get("pet") or row.get("Pet") or "")
        appt_date  = _str(row.get("appointment_date") or row.get("date") or row.get("Date") or "")
        appt_start = _str(row.get("appointment_start") or row.get("time") or row.get("Time") or "09:00")
        reason     = _str(row.get("reason") or row.get("Reason") or row.get("notes") or "")
        doctor     = _str(row.get("doctor") or row.get("Doctor") or row.get("doctor_name") or "")

        if not appt_date:
            continue

        # Normalize date — may come as datetime object
        if hasattr(appt_date, "date"):
            appt_date = appt_date.date().isoformat()
        elif len(appt_date) > 10:
            appt_date = appt_date[:10]

        # Normalize time
        if hasattr(appt_start, "time"):
            appt_start = appt_start.strftime("%H:%M")
        elif "T" in str(appt_start):
            appt_start = str(appt_start).split("T")[1][:5]
        elif len(str(appt_start)) > 5:
            appt_start = str(appt_start)[:5]

        if not dry_run:
            # Resolve owner
            owner_id = None
            if owner_name:
                o = conn.execute(
                    "SELECT id FROM owners WHERE full_name LIKE ?", (f"%{owner_name}%",)
                ).fetchone()
                if o:
                    owner_id = o["id"]
            if owner_id is None:
                conn.execute(
                    "INSERT INTO owners (full_name, created_by) VALUES (?, 'excel_import')",
                    (owner_name or "Unknown Owner",),
                )
                owner_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            # Resolve pet
            pet_id = None
            if pet_name:
                p = conn.execute(
                    "SELECT id FROM pets WHERE pet_name LIKE ? AND owner_id=?",
                    (f"%{pet_name}%", owner_id),
                ).fetchone()
                if p:
                    pet_id = p["id"]
            if pet_id is None:
                conn.execute(
                    "INSERT INTO pets (owner_id, pet_name, species, created_at) VALUES (?,?,?,datetime('now'))",
                    (owner_id, pet_name or "Unknown Pet", "Unknown"),
                )
                pet_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute(
                """INSERT INTO appointments
                   (owner_id, pet_id, doctor_name, appt_date, appt_start,
                    reason, status, created_by)
                   VALUES (?,?,?,?,?,?,'Scheduled','excel_import')""",
                (owner_id, pet_id, doctor, appt_date, appt_start[:5], reason),
            )
            count += 1
        else:
            count += 1

    if not dry_run:
        conn.commit()
    return count


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Import legacy Excel data into the Premium Animal Hospital platform database."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would be imported without writing to the database.",
    )
    parser.add_argument(
        "--db", default="data/platform.db",
        help="Path to platform.db (default: data/platform.db relative to platform root).",
    )
    parser.add_argument(
        "--only",
        help="Comma-separated list of tables to import: owners, pets, bookings. Default: all.",
    )
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.is_absolute():
        db_path = Path(__file__).parent.parent / args.db

    if not db_path.exists():
        print(f"\nERROR: Database not found at {db_path}")
        print("Start the platform once to initialize the database, then run this tool.")
        sys.exit(1)

    print(f"\n{'='*62}")
    print(f"  Premium Animal Hospital — Excel Migration Tool")
    print(f"  {'DRY RUN — no changes will be written' if args.dry_run else 'LIVE IMPORT — writing to database'}")
    print(f"  Database  : {db_path}")
    print(f"  Legacy dir: {LEGACY_DATA}")
    print(f"{'='*62}\n")

    if not LEGACY_DATA.exists():
        print(f"WARNING: Legacy data directory not found at {LEGACY_DATA}")
        print("Continuing — individual file reads will be skipped if not found.\n")

    conn = get_connection(str(db_path))
    results: dict = {}

    tables = [t.strip() for t in (args.only or "owners,pets,bookings").split(",") if t.strip()]

    if "owners" in tables:
        print("Importing owners...")
        rows = read_excel("owners.xlsx")
        if rows:
            n = migrate_owners(conn, rows, args.dry_run)
            results["owners"] = n
            print(f"  {'Would import' if args.dry_run else 'Imported'}: {n} new owner(s) from {len(rows)} rows.\n")
        else:
            print("  No owners data found — skipping.\n")

    if "pets" in tables:
        print("Importing pets...")
        rows = read_excel("pets.xlsx")
        if rows:
            n = migrate_pets(conn, rows, args.dry_run)
            results["pets"] = n
            print(f"  {'Would import' if args.dry_run else 'Imported'}: {n} new pet(s) from {len(rows)} rows.\n")
        else:
            print("  No pets data found — skipping.\n")

    if "bookings" in tables:
        print("Importing bookings/appointments...")
        rows = read_excel("bookings.xlsx")
        if rows:
            n = migrate_bookings(conn, rows, args.dry_run)
            results["bookings"] = n
            print(f"  {'Would import' if args.dry_run else 'Imported'}: {n} appointment(s) from {len(rows)} rows.\n")
        else:
            print("  No bookings data found — skipping.\n")

    conn.close()

    print(f"{'='*62}")
    print(f"  Migration {'simulation' if args.dry_run else 'complete'}!")
    if results:
        for table, count in results.items():
            print(f"  {table:<12}: {count:>6} record(s)")
    else:
        print("  No data was imported.")
    if args.dry_run:
        print("\n  Re-run without --dry-run to apply changes.")
    print(f"{'='*62}\n")


if __name__ == "__main__":
    main()
