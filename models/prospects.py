# -*- coding: utf-8 -*-
"""The target market as a finite, scored database - not an ad audience.

There are a countable number of veterinary clinics in Cairo and Giza. Every one
of them either becomes a customer or does not, and which ones are worth a visit
first is a question with an answer. That is what this holds.

SCORING

The weights come from the APEX proposal, Pillar 2, and they are deliberately
kept as visible constants rather than buried in a query, because they are a
commercial judgement that will change once real conversations disagree with
them:

    +3  more than one branch
    +2  each of: hospital, large team, grooming, boarding, pharmacy, pet shop

The logic behind them is that Aleefy's breadth is its differentiator - a
single-vet clinic that only needs records and billing can buy anything, and
several competitors are cheaper. A clinic that also runs grooming, boarding, a
pharmacy counter and a shop is one of the few buyers for whom "all of it in one
system" is worth paying for. The score is really a measure of "how much of what
we already built does this clinic actually need".

WHAT IS DELIBERATELY NOT IN THE SCORE

Whether they already pay for software. It is recorded - `current_software` -
because it matters enormously, but it points BOTH ways and no single weight is
honest: a clinic already paying VetICare has proven it will spend money on
exactly this, which makes it a better prospect than a paper clinic; it is also
mid-contract and harder to move. That is a judgement for a person reading the
row, not a number to be added.

THIS IS PROSPECT DATA, NOT CLINICAL DATA

It lives in its own table with no foreign key into owners, pets or invoices. A
prospect is a business that has not bought anything; conflating that with a
customer record is how a sales note ends up on a patient file.
"""
import logging
import re

import models.database as db

logger = logging.getLogger(__name__)

# ── the weights, in one place ────────────────────────────────────────────────
W_MULTI_BRANCH = 3
W_SIGNAL = 2
LARGE_TEAM = 5              # vets, above which a clinic counts as a large team

SIGNALS = ("is_hospital", "has_grooming", "has_boarding",
           "has_pharmacy", "has_petshop", "has_lab")

# Pipeline stages, in order. Kept as a tuple so a report can sort by progress
# rather than alphabetically, which would put "won" between "new" and "lost".
STAGES = ("new", "researching", "contacted", "conversation",
          "demo", "proposal", "won", "lost", "unreachable")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    name_ar         TEXT,

    -- Territory. Penetration is won by density in one area, not by national
    -- reach, so these two decide the running order more than the score does.
    governorate     TEXT,
    district        TEXT,
    address         TEXT,

    phone           TEXT,
    whatsapp        TEXT,
    email           TEXT,
    website         TEXT,
    facebook        TEXT,
    instagram       TEXT,
    maps_url        TEXT,

    contact_name    TEXT,
    contact_role    TEXT,

    -- Signals. Each is 0/1 except branches and vets.
    branches        INTEGER DEFAULT 1,
    vets            INTEGER,
    is_hospital     INTEGER DEFAULT 0,
    has_grooming    INTEGER DEFAULT 0,
    has_boarding    INTEGER DEFAULT 0,
    has_pharmacy    INTEGER DEFAULT 0,
    has_petshop     INTEGER DEFAULT 0,
    has_lab         INTEGER DEFAULT 0,

    -- Recorded, never scored. See the module docstring.
    current_software TEXT,

    score           INTEGER DEFAULT 0,
    cohort          INTEGER,

    status          TEXT DEFAULT 'new',
    last_contact    TEXT,
    next_action     TEXT,
    next_action_on  TEXT,
    notes           TEXT,

    -- Where this row came from. A market database nobody can audit is a list
    -- of rumours, and the first wrong phone number destroys trust in all of it.
    source          TEXT,
    source_url      TEXT,

    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);
"""

_INDEXES = (
    "CREATE INDEX IF NOT EXISTS ix_prospects_score ON prospects(score DESC)",
    "CREATE INDEX IF NOT EXISTS ix_prospects_terr ON prospects(governorate, district)",
    "CREATE INDEX IF NOT EXISTS ix_prospects_status ON prospects(status)",
    # Two rows for one clinic means calling somebody twice and looking
    # disorganised to the exact person being sold to.
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_prospects_key ON prospects(name, district)",
)

_ready = False


def ensure_tables(conn=None) -> None:
    """Idempotent DDL. Uses db._try_stmt so a failed statement cannot abort the
    surrounding PostgreSQL transaction - a bare try/except does not save it."""
    global _ready
    if _ready:
        return
    own = conn is None
    conn = conn or db.get_db()
    try:
        db._try_stmt(conn, _SCHEMA)
        for stmt in _INDEXES:
            db._try_stmt(conn, stmt)
        conn.commit()
        _ready = True
    finally:
        if own:
            conn.close()


# ── scoring ──────────────────────────────────────────────────────────────────

def score_of(row: dict) -> int:
    """The APEX weights, applied to one clinic.

    Pure and side-effect free so it can be tested without a database, and so a
    change to the weights can be diffed against real rows before it is applied.
    """
    total = 0
    if int(row.get("branches") or 1) > 1:
        total += W_MULTI_BRANCH
    for sig in SIGNALS:
        if int(row.get(sig) or 0):
            total += W_SIGNAL
    vets = row.get("vets")
    if vets is not None and str(vets).strip() != "":
        try:
            if int(vets) >= LARGE_TEAM:
                total += W_SIGNAL
        except (TypeError, ValueError):
            pass
    return total


def explain_score(row: dict) -> list:
    """Why a clinic scored what it did, in words.

    A number nobody can account for is a number nobody trusts, and the person
    deciding whether to drive across Cairo deserves the reasons.
    """
    why = []
    if int(row.get("branches") or 1) > 1:
        why.append("+%d  %s branches" % (W_MULTI_BRANCH, row.get("branches")))
    labels = {
        "is_hospital": "hospital, not a single-room clinic",
        "has_grooming": "grooming",
        "has_boarding": "boarding",
        "has_pharmacy": "pharmacy counter",
        "has_petshop": "pet shop / retail",
        "has_lab": "in-house laboratory",
    }
    for sig in SIGNALS:
        if int(row.get(sig) or 0):
            why.append("+%d  %s" % (W_SIGNAL, labels[sig]))
    try:
        if row.get("vets") and int(row["vets"]) >= LARGE_TEAM:
            why.append("+%d  %s vets" % (W_SIGNAL, row["vets"]))
    except (TypeError, ValueError):
        pass
    if not why:
        why.append("0   nothing recorded beyond a single-site clinic")
    return why


def rescore_all(conn) -> int:
    """Recompute every score. Run after changing a weight, or after an import."""
    ensure_tables(conn)
    rows = [dict(r) for r in conn.execute("SELECT * FROM prospects").fetchall()]
    n = 0
    for r in rows:
        s = score_of(r)
        if s != (r.get("score") or 0):
            conn.execute("UPDATE prospects SET score=?,"
                         " updated_at=datetime('now') WHERE id=?", (s, r["id"]))
            n += 1
    conn.commit()
    return n


# ── cohorts ──────────────────────────────────────────────────────────────────

COHORT_SIZES = (50, 50, 100)


def assign_cohorts(conn, sizes=COHORT_SIZES, strategy: str = "spread") -> dict:
    """Split the mapped market into the three test cohorts.

    strategy="spread" (default) puts a MIX of scores in cohort 1, deliberately.
    The obvious alternative - best prospects first - spends your most valuable
    accounts on your least practised pitch, and the whole point of running
    50/50/100 rather than 200 is to be better by the third batch. Cohort 3
    should get the sharpened pitch, so the highest scores are held back for it.

    strategy="top" does it the other way for anyone who disagrees, because this
    is a commercial judgement and not a fact.
    """
    ensure_tables(conn)
    rows = [dict(r) for r in conn.execute(
        "SELECT id, score FROM prospects WHERE status='new'"
        " ORDER BY score DESC, id").fetchall()]
    if not rows:
        return {}

    order = []
    if strategy == "top":
        order = [r["id"] for r in rows]
    else:
        # Deal the sorted list round-robin across the cohorts, so each gets the
        # same spread of strong and weak accounts, then hand the leftovers to
        # the last cohort.
        buckets = [[] for _ in sizes]
        for i, r in enumerate(rows):
            buckets[i % len(sizes)].append(r["id"])
        # Weight the deal by the requested sizes rather than evenly.
        flat = []
        for b in buckets:
            flat.extend(b)
        order = flat

    out, at = {}, 0
    for idx, size in enumerate(sizes, start=1):
        chunk = order[at:at + size]
        at += size
        for pid in chunk:
            conn.execute("UPDATE prospects SET cohort=?,"
                         " updated_at=datetime('now') WHERE id=?", (idx, pid))
        out[idx] = len(chunk)
    leftover = order[at:]
    for pid in leftover:
        conn.execute("UPDATE prospects SET cohort=?,"
                     " updated_at=datetime('now') WHERE id=?", (len(sizes), pid))
    if leftover:
        out[len(sizes)] = out.get(len(sizes), 0) + len(leftover)
    conn.commit()
    return out


# ── writing ──────────────────────────────────────────────────────────────────

_PHONE = re.compile(r"[^\d+]")


def clean_phone(raw: str) -> str:
    """Egyptian mobiles arrive as +20 10..., 0020..., 010..., with spaces and
    dashes. Stored one way so a duplicate is visible as a duplicate."""
    s = _PHONE.sub("", str(raw or ""))
    if s.startswith("+20"):
        s = "0" + s[3:]
    elif s.startswith("0020"):
        s = "0" + s[4:]
    elif s.startswith("20") and len(s) > 10:
        s = "0" + s[2:]
    return s


def upsert(conn, row: dict) -> str:
    """Insert a clinic, or update the one already there. Returns 'new' | 'updated'.

    Matched on (name, district) rather than phone, because the phone number is
    the field most often wrong or missing in scraped data, and a clinic with no
    phone still belongs in the market map.
    """
    ensure_tables(conn)
    row = dict(row)
    for k in ("phone", "whatsapp"):
        if row.get(k):
            row[k] = clean_phone(row[k])
    row["score"] = score_of(row)

    cols = [c for c in row if c not in ("id", "created_at", "updated_at")]
    existing = conn.execute(
        "SELECT id FROM prospects WHERE name=? AND COALESCE(district,'')=?",
        (row.get("name"), row.get("district") or "")).fetchone()

    if existing:
        sets = ", ".join("%s=?" % c for c in cols)
        conn.execute("UPDATE prospects SET %s, updated_at=datetime('now')"
                     " WHERE id=?" % sets,
                     tuple(row[c] for c in cols) + (existing[0],))
        return "updated"

    conn.execute("INSERT INTO prospects (%s) VALUES (%s)"
                 % (", ".join(cols), ", ".join("?" * len(cols))),
                 tuple(row[c] for c in cols))
    return "new"


# ── reading ──────────────────────────────────────────────────────────────────

def summary(conn) -> dict:
    ensure_tables(conn)
    total = conn.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
    by_status = {r[0]: r[1] for r in conn.execute(
        "SELECT status, COUNT(*) FROM prospects GROUP BY status").fetchall()}
    by_gov = {r[0] or "?": r[1] for r in conn.execute(
        "SELECT governorate, COUNT(*) FROM prospects"
        " GROUP BY governorate ORDER BY COUNT(*) DESC").fetchall()}
    by_cohort = {r[0]: r[1] for r in conn.execute(
        "SELECT cohort, COUNT(*) FROM prospects WHERE cohort IS NOT NULL"
        " GROUP BY cohort").fetchall()}
    scored = conn.execute(
        "SELECT COUNT(*) FROM prospects WHERE score > 0").fetchone()[0]
    contactable = conn.execute(
        "SELECT COUNT(*) FROM prospects"
        " WHERE COALESCE(phone,'') <> '' OR COALESCE(whatsapp,'') <> ''"
    ).fetchone()[0]
    return {
        "total": total, "scored": scored, "contactable": contactable,
        "by_status": by_status, "by_governorate": by_gov, "by_cohort": by_cohort,
    }


def call_list(conn, cohort=None, governorate=None, limit=200) -> list:
    """Who to call, in the order to call them.

    Territory first, then score. Density beats a marginally better prospect on
    the other side of Cairo: five clinics in Nasr City in one afternoon is
    worth more than five scattered across the governorate, because vets in a
    district talk to each other and that is the whole mechanism.
    """
    ensure_tables(conn)
    where, args = ["status IN ('new','researching','contacted')"], []
    if cohort:
        where.append("cohort=?")
        args.append(cohort)
    if governorate:
        where.append("governorate=?")
        args.append(governorate)
    args.append(limit)
    rows = conn.execute(
        "SELECT * FROM prospects WHERE %s"
        " ORDER BY governorate, district, score DESC, name LIMIT ?"
        % " AND ".join(where), tuple(args)).fetchall()
    return [dict(r) for r in rows]


# ── how usable is a record ───────────────────────────────────────────────────

# What a row needs before somebody can act on it. A clinic with a name and
# nothing else is a lead in name only, and counting those as "mapped" is how a
# pipeline looks full while nobody can be phoned.
_ESSENTIAL = ("phone", "whatsapp")
_USEFUL = ("district", "address", "name_ar", "website", "facebook",
           "contact_name", "vets")


def completeness(row: dict) -> tuple:
    """(level, missing) - level is 'callable' | 'researchable' | 'name only'.

    Deliberately three words rather than a percentage. "62% complete" tells
    nobody what to do next; "researchable - no phone, has a Facebook page"
    tells them exactly.
    """
    has_number = any((row.get(k) or "").strip() for k in _ESSENTIAL)
    has_route = any((row.get(k) or "").strip()
                    for k in ("website", "facebook", "instagram", "address"))
    missing = [k for k in _USEFUL if not str(row.get(k) or "").strip()]
    if has_number:
        return "callable", missing
    if has_route:
        return "researchable", missing
    return "name only", missing
