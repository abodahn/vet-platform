"""
Regression tests for five CDS defects — a doubled unit, a dead breed rule, a
dose card under a DO NOT GIVE card, four silent drug classes and a 500 on an
absurd weight. Each test fails without its fix in blueprints/cds/routes.py.

Pure engine except the last one: no database, no network.
"""
import pytest

from blueprints.cds import routes as cds
from conftest import get_csrf


# ── 1. Insulin's unit ────────────────────────────────────────────────────────

def test_insulin_total_is_in_iu_and_the_per_kg_line_is_not_doubled():
    # "units": "IU/kg" in the data file describes the per-kg rate, not the unit
    # of the total. A tenfold insulin error kills — the label must be exact.
    r = cds.calculate_dose("Insulin", "Cat", "5")
    assert r.ok
    assert r.unit == "IU"                       # not "IU/kg"
    assert r.per_kg_range == "0.25-0.5 IU/kg"   # not "0.25-0.5 IU/kg/kg"
    assert (r.min_total, r.max_total) == ("1.25", "2.5")


def test_milligram_rows_keep_their_unit():
    assert cds.calculate_dose("Meloxicam", "Dog", "10").unit == "mg"


# ── 2. Punctuated breed names ────────────────────────────────────────────────

@pytest.mark.parametrize("breed", ["Long-haired Whippet", "long-haired whippet",
                                   "Longhaired Whippet", "long haired whippet"])
def test_hyphenated_mdr1_breed_fires_the_ivermectin_rule(breed):
    alerts = cds.check_contraindications("Ivermectin", "Dog", breed)
    assert alerts, f"{breed} is on the MDR1 at-risk list and must warn"
    assert alerts[0].severity == cds.CONTRAINDICATED
    assert alerts[0].kind == "breed"


def test_breed_matching_did_not_become_looser():
    assert cds.check_contraindications("Ivermectin", "Dog", "Beagle") == []


# ── 3. No dose card for a drug that must not be given ────────────────────────

def test_contraindicated_drug_gets_no_dose():
    r = cds.calculate_dose("Ivermectin", "Dog", "20", "Collie")
    assert not r.ok
    assert r.min_total is None and r.max_total is None
    assert "contraindicated" in r.refusal_en
    assert any(a.severity == cds.CONTRAINDICATED for a in r.alerts)


def test_screen_suppresses_the_dose_card_for_a_contraindicated_drug():
    result = cds.screen(["Ivermectin"], "Dog", "Border Collie", "20")
    assert result["worst_severity"] == cds.CONTRAINDICATED
    assert [d.ok for d in result["doses"]] == [False]


def test_a_safe_breed_still_gets_its_dose():
    assert cds.calculate_dose("Ivermectin", "Dog", "20", "Beagle").ok


def test_a_species_contraindication_also_blocks_the_dose():
    assert not cds.calculate_dose("Paracetamol", "Cat", "4").ok


# ── 4. Drug classes no rule reaches ──────────────────────────────────────────

def test_an_unreferenced_drug_class_is_named_rather_than_silent():
    alerts = cds.check_interactions(["Tobramycin", "Furosemide"])
    assert alerts, "tobramycin + furosemide must not screen silently"
    a = alerts[0]
    assert a.severity == cds.CAUTION
    assert "aminoglycoside" in a.message_en
    assert "gentamicin" in a.message_en      # names the sibling that IS screened
    assert a.message_ar


def test_a_class_that_rules_do_name_raises_no_gap_alert():
    alerts = cds.check_interactions(["Gentamicin", "Furosemide"])
    assert [a.severity for a in alerts] == [cds.MAJOR]


def test_every_gap_alert_points_at_a_real_class_and_covered_sibling():
    named = {k for e in cds.DATA["interactions"] for k in e["drugs"]}
    for member, (cls, covered) in cds._CLASS_GAPS.items():
        assert member in cds._CLASSES[cls] and member not in named
        assert covered and set(covered) <= named


# ── 5. Absurd weights ────────────────────────────────────────────────────────

@pytest.mark.parametrize("weight", ["nan", "inf", "-inf", "1e28", "1e999999999"])
def test_an_uncomputable_weight_refuses_instead_of_raising(weight):
    r = cds.calculate_dose("Meloxicam", "Dog", weight)   # must not raise
    assert not r.ok
    assert "body weight" in r.refusal_en


def test_1e24_kg_is_refused_not_merely_flagged():
    """ASSERTION DELIBERATELY CHANGED from the first pass, which asserted
    ok=True with min_total "100000000000000000000000" and a MAJOR alert.

    That was a real improvement on the 500 it replaced, and it is not what a
    dose card should do. A flagged card is still a card: it prints
    1e23 mg next to a warning, and a number on a screen reads as considered
    even when the warning above it does not. The exception it replaced was at
    least obviously broken.

    So an impossible weight is now refused outright, and only weights a clinic
    could actually see produce arithmetic. See MAX_BODY_WEIGHT_KG.
    """
    r = cds.calculate_dose("Meloxicam", "Dog", "1e24")
    assert not r.ok
    assert "body weight" in r.refusal_en
    assert r.min_total is None, "a refused weight must not carry a dose"


def test_the_page_does_not_500_on_an_absurd_weight(auth_client):
    r = auth_client.post("/cds/", data={
        "drugs": "Meloxicam", "species": "Dog", "breed": "", "weight_kg": "1e24",
        "_csrf_token": get_csrf(auth_client),
    })
    assert r.status_code == 200


# ── the gap the adversarial verifier missed and the fix half-left ────────────

def test_an_absurd_weight_is_refused_not_answered():
    """Removing the crash was only half the fix.

    A weight of 1e24 stopped raising decimal.InvalidOperation and started
    returning 1e23 mg as a real dose card. That is worse than the crash: an
    exception is obviously wrong, a printed number looks considered. A vet who
    fat-fingers an extra zero must be told, not handed arithmetic.
    """
    from blueprints.cds.routes import calculate_dose, MAX_BODY_WEIGHT_KG
    for bad in (1e24, 1e308, MAX_BODY_WEIGHT_KG + 1, -5, 0):
        r = calculate_dose("meloxicam", "cat", bad)
        assert r.ok is False, "weight %r produced a dose card" % bad


def test_every_real_patient_weight_still_works():
    """The bound must not refuse anything a clinic actually treats — a kitten
    at 200g through a draught horse at 2000kg."""
    from blueprints.cds.routes import calculate_dose, MAX_BODY_WEIGHT_KG
    for good in (0.2, 4.2, 60, 500, MAX_BODY_WEIGHT_KG):
        r = calculate_dose("meloxicam", "cat", good)
        assert r.ok is True, "weight %r was refused" % good


def test_a_species_contraindication_also_suppresses_the_dose(app):
    """The verifier flagged the dose-card guard as breed-only. It is not — but
    nothing pinned the species half, so this pins it.

    permethrin in a cat and penicillin in a guinea pig are both fatal-class
    species contraindications. Neither may be given a dose card.
    """
    from blueprints.cds.routes import calculate_dose
    for drug, species, kg in (("permethrin", "cat", 4.0),
                              ("penicillin", "guinea pig", 0.9)):
        r = calculate_dose(drug, species, kg)
        assert r.ok is False, (
            "%s in a %s is contraindicated but still produced a dose"
            % (drug, species))


def test_a_major_alert_does_not_suppress_the_dose(app):
    """The other side of that guard: only CONTRAINDICATED blocks. A 'major'
    warning must still show a dose, or every cautioned drug becomes
    un-prescribable and the whole module gets ignored."""
    from blueprints.cds.routes import calculate_dose, check_contraindications
    alerts = check_contraindications("meloxicam", "cat", None)
    assert any(a.severity == "major" for a in alerts), "test premise moved"
    assert calculate_dose("meloxicam", "cat", 4.2).ok is True
