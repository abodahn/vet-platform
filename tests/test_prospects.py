# -*- coding: utf-8 -*-
"""The target market as a scored database.

Pillar 2 of the APEX proposal, built rather than bought. The scoring weights
are a commercial judgement, so they are tested as a contract rather than as
arithmetic: if somebody changes what a multi-branch clinic is worth, these say
so loudly instead of quietly re-ranking who gets called first.
"""
import pytest

from models import prospects as P


@pytest.fixture
def conn(app):
    import models.database as db
    with app.app_context():
        c = db.get_db()
        P.ensure_tables(c)
        c.execute("DELETE FROM prospects")
        c.commit()
        yield c
        c.close()


# ── scoring ──────────────────────────────────────────────────────────────────

def test_a_single_room_clinic_scores_nothing():
    assert P.score_of({"name": "One Room Vet", "branches": 1}) == 0


def test_the_weights_are_the_ones_agreed():
    """+3 multi-branch, +2 per signal. If this fails somebody changed the
    commercial judgement, which is allowed - but not by accident."""
    assert P.W_MULTI_BRANCH == 3
    assert P.W_SIGNAL == 2
    assert P.score_of({"branches": 2}) == 3
    assert P.score_of({"branches": 1, "has_grooming": 1}) == 2


def test_a_full_service_multi_branch_hospital_scores_highest():
    """The clinic Aleefy is actually built for: the one that needs grooming,
    boarding, a pharmacy counter and a shop in the same system."""
    big = P.score_of({
        "branches": 3, "vets": 8, "is_hospital": 1, "has_grooming": 1,
        "has_boarding": 1, "has_pharmacy": 1, "has_petshop": 1, "has_lab": 1,
    })
    small = P.score_of({"branches": 1, "vets": 1})
    assert big > small
    assert big == 3 + (2 * 7)      # multi-branch + six signals + large team


def test_a_large_team_counts_but_a_small_one_does_not():
    assert P.score_of({"vets": P.LARGE_TEAM}) == P.W_SIGNAL
    assert P.score_of({"vets": P.LARGE_TEAM - 1}) == 0


def test_a_missing_or_junk_vet_count_does_not_crash():
    for bad in (None, "", "many", "٣"):
        assert P.score_of({"vets": bad}) == 0


def test_existing_software_is_recorded_but_never_scored():
    """It points both ways: they have proven they will pay for exactly this,
    and they are mid-contract. A single weight cannot be honest about that, so
    it is a fact for a person to read, not a number."""
    with_sw = P.score_of({"branches": 1, "current_software": "VetICare"})
    without = P.score_of({"branches": 1})
    assert with_sw == without


def test_the_score_explains_itself():
    """A number nobody can account for is a number nobody trusts, and somebody
    is deciding whether to drive across Cairo on it."""
    why = P.explain_score({"branches": 3, "has_grooming": 1, "vets": 9})
    joined = " ".join(why)
    assert "3 branches" in joined
    assert "grooming" in joined
    assert "9 vets" in joined


def test_a_clinic_with_no_signals_still_gets_an_explanation():
    why = P.explain_score({"branches": 1})
    assert why and "nothing recorded" in why[0]


# ── storage ──────────────────────────────────────────────────────────────────

def test_importing_the_same_clinic_twice_updates_it(conn):
    """Two rows for one clinic means phoning somebody twice and looking
    disorganised to the exact person being sold to."""
    row = {"name": "Nile Vet", "district": "Zamalek", "governorate": "Cairo"}
    assert P.upsert(conn, row) == "new"
    assert P.upsert(conn, dict(row, phone="01000000001")) == "updated"
    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
    assert n == 1
    assert conn.execute(
        "SELECT phone FROM prospects").fetchone()[0] == "01000000001"


def test_the_score_is_stored_on_the_way_in(conn):
    P.upsert(conn, {"name": "Big Vet", "district": "Maadi", "branches": 4,
                    "has_grooming": 1})
    conn.commit()
    assert conn.execute("SELECT score FROM prospects").fetchone()[0] == 5


@pytest.mark.parametrize("raw,clean", [
    ("+20 100 123 4567", "01001234567"),
    ("0020 100 123 4567", "01001234567"),
    ("0100-123-4567", "01001234567"),
    ("01001234567", "01001234567"),
])
def test_phone_numbers_are_stored_one_way(raw, clean):
    """Egyptian mobiles arrive in four shapes. Stored one way, a duplicate is
    visible as a duplicate."""
    assert P.clean_phone(raw) == clean


def test_rescoring_picks_up_a_changed_weight(conn, monkeypatch):
    P.upsert(conn, {"name": "Changeable", "district": "Dokki", "branches": 2})
    conn.commit()
    assert conn.execute("SELECT score FROM prospects").fetchone()[0] == 3
    monkeypatch.setattr(P, "W_MULTI_BRANCH", 10)
    assert P.rescore_all(conn) == 1
    assert conn.execute("SELECT score FROM prospects").fetchone()[0] == 10


# ── cohorts ──────────────────────────────────────────────────────────────────

def _many(conn, n):
    for i in range(n):
        P.upsert(conn, {"name": "Clinic %03d" % i, "district": "D%d" % (i % 5),
                        "governorate": "Cairo", "branches": 1 + (i % 4)})
    conn.commit()


def test_cohorts_are_sized_as_agreed(conn):
    _many(conn, 200)
    out = P.assign_cohorts(conn)
    assert out[1] == 50 and out[2] == 50 and out[3] == 100


def test_leftovers_go_to_the_last_cohort_not_nowhere(conn):
    _many(conn, 220)
    out = P.assign_cohorts(conn)
    assert sum(out.values()) == 220, "20 clinics were mapped and then dropped"


def test_spread_does_not_spend_the_best_accounts_on_the_first_pitch(conn):
    """The whole point of 50/50/100 rather than 200 is to be better by the
    third batch. Best-first would burn the most valuable accounts on the least
    practised pitch."""
    _many(conn, 200)
    P.assign_cohorts(conn, strategy="spread")
    avg = {}
    for c in (1, 2, 3):
        avg[c] = conn.execute(
            "SELECT AVG(score) FROM prospects WHERE cohort=?", (c,)).fetchone()[0]
    assert abs(avg[1] - avg[2]) < 1.5, (
        "cohort 1 and 2 have very different quality: %r" % avg)


def test_top_strategy_does_the_opposite_when_asked(conn):
    _many(conn, 200)
    P.assign_cohorts(conn, strategy="top")
    a = conn.execute("SELECT AVG(score) FROM prospects WHERE cohort=1").fetchone()[0]
    c = conn.execute("SELECT AVG(score) FROM prospects WHERE cohort=3").fetchone()[0]
    assert a > c, "top strategy did not put the best accounts first"


# ── working the list ─────────────────────────────────────────────────────────

def test_the_call_list_groups_by_territory_before_score(conn):
    """Five clinics in one district in an afternoon beats five scattered across
    Cairo. Vets in a district talk to each other, and that is the mechanism."""
    P.upsert(conn, {"name": "Far But Good", "governorate": "Cairo",
                    "district": "Zzz", "branches": 5, "is_hospital": 1})
    P.upsert(conn, {"name": "Near And Fine", "governorate": "Cairo",
                    "district": "Aaa", "branches": 1})
    conn.commit()
    names = [r["name"] for r in P.call_list(conn)]
    assert names[0] == "Near And Fine", (
        "the list sent somebody across the city for one better prospect")


def test_won_and_lost_drop_off_the_call_list(conn):
    P.upsert(conn, {"name": "Already Won", "district": "Maadi", "status": "won"})
    P.upsert(conn, {"name": "Still Open", "district": "Maadi"})
    conn.commit()
    names = [r["name"] for r in P.call_list(conn)]
    assert "Already Won" not in names
    assert "Still Open" in names


def test_the_summary_counts_who_can_actually_be_phoned(conn):
    """A clinic with no number is on the map but cannot be worked, and the
    difference between those two numbers is the real size of the pipeline."""
    P.upsert(conn, {"name": "Reachable", "district": "A", "phone": "01000000001"})
    P.upsert(conn, {"name": "On The Map Only", "district": "B"})
    conn.commit()
    s = P.summary(conn)
    assert s["total"] == 2
    assert s["contactable"] == 1
