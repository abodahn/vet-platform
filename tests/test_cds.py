"""
Clinical Decision Support — rule engine tests.

These tests ARE the safety specification. The known-lethal cases at the top
(paracetamol in cats, permethrin in cats, ivermectin in an MDR1 herding breed)
must never stop failing loudly if the data file is edited badly.

Nothing here touches PostgreSQL, the network, or the AI service. The engine is
pure and the data file is local — if any of this needs a service to pass, the
module has been built wrong.
"""
import json
from decimal import Decimal

import pytest

from blueprints.cds import routes as cds


# ═══════════════════════════════════════════════════════════════════════════
#  THE THREE THAT KILL
# ═══════════════════════════════════════════════════════════════════════════

def _worst(alerts):
    return alerts[0].severity if alerts else None


def test_paracetamol_in_cat_is_contraindicated():
    alerts = cds.check_contraindications("Paracetamol", "Cat")
    assert _worst(alerts) == cds.CONTRAINDICATED
    assert any("glucuronyl" in a.message_en.lower() for a in alerts)
    assert all(a.source for a in alerts if a.kind == "contraindication")


@pytest.mark.parametrize("name", [
    "Acetaminophen", "Panadol 500mg Tablets", "باراسيتامول", "  paracetamol  ",
])
def test_paracetamol_synonyms_and_trade_names_still_fire(name):
    assert _worst(cds.check_contraindications(name, "Cat")) == cds.CONTRAINDICATED


def test_paracetamol_in_dog_does_not_fire_the_cat_rule():
    # Not a claim that it is safe in dogs — only that the feline rule is
    # species-scoped and does not leak.
    assert cds.check_contraindications("Paracetamol", "Dog") == []


def test_permethrin_in_cat_is_contraindicated():
    alerts = cds.check_contraindications("Permethrin", "Cat")
    assert _worst(alerts) == cds.CONTRAINDICATED
    assert any("cat" in a.message_en.lower() for a in alerts)


def test_permethrin_canine_spot_on_trade_name_in_cat_fires():
    assert _worst(cds.check_contraindications("K9 Advantix spot-on", "Cat")) == cds.CONTRAINDICATED


def test_permethrin_in_dog_is_routine():
    assert cds.check_contraindications("Permethrin", "Dog") == []


@pytest.mark.parametrize("breed", [
    "Collie", "Border Collie", "Rough Collie", "Australian Shepherd",
    "Shetland Sheepdog", "Old English Sheepdog",
])
def test_ivermectin_in_mdr1_herding_breed_is_contraindicated(breed):
    alerts = cds.check_contraindications("Ivermectin", "Dog", breed)
    assert _worst(alerts) == cds.CONTRAINDICATED
    hit = alerts[0]
    assert hit.kind == "breed"
    assert "MDR1" in (hit.message_en or "")
    # The nuance must survive: the low heartworm-prevention dose is not the
    # thing that kills. Dropping it turns a real warning into alert fatigue.
    assert "6 mcg/kg" in hit.message_en


def test_ivermectin_in_non_herding_breed_warns_only_that_breed_matters():
    alerts = cds.check_contraindications("Ivermectin", "Dog", "Labrador Retriever")
    assert alerts == []


def test_ivermectin_with_no_breed_recorded_does_not_go_quiet():
    alerts = cds.check_contraindications("Ivermectin", "Dog", None)
    assert alerts, "a missing breed must not silence a breed-specific contraindication"
    assert alerts[0].severity == cds.CAUTION
    assert "breed" in alerts[0].message_en.lower()


def test_loperamide_is_the_easily_missed_mdr1_drug():
    alerts = cds.check_contraindications("Imodium", "Dog", "Australian Shepherd")
    assert _worst(alerts) == cds.CONTRAINDICATED


# ═══════════════════════════════════════════════════════════════════════════
#  Fail loud, never silent
# ═══════════════════════════════════════════════════════════════════════════

def test_unknown_drug_is_reported_not_ignored():
    alerts = cds.check_contraindications("Zorbaxifen", "Cat")
    assert len(alerts) == 1
    assert alerts[0].severity == cds.UNVERIFIED
    assert "not in" in alerts[0].message_en.lower()
    assert "safe" in alerts[0].message_en.lower()  # explicitly denies safety


def test_unknown_species_blocks_the_contraindication_check_loudly():
    alerts = cds.check_contraindications("Paracetamol", "Ferret")
    assert alerts[0].severity == cds.UNVERIFIED
    assert "species" in alerts[0].message_en.lower()


def test_unverified_outranks_moderate_in_the_sort_order():
    assert cds.SEVERITY_RANK[cds.UNVERIFIED] < cds.SEVERITY_RANK[cds.MODERATE]


def test_screen_reports_which_drugs_were_not_checked():
    result = cds.screen(["Paracetamol", "Zorbaxifen"], "Cat")
    assert result["unrecognised"] == ["Zorbaxifen"]


def test_screen_with_nothing_matching_still_carries_the_advisory():
    result = cds.screen(["Praziquantel"], "Dog")
    assert result["worst_severity"] is None
    assert "veterinarian" in result["advisory"]["en"]
    assert "Dr. Hatem" in result["advisory"]["en"]


# ═══════════════════════════════════════════════════════════════════════════
#  Name matching — exact, never fuzzy
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("raw,expected", [
    ("Metacam 1.5 mg/ml Oral Suspension for Dogs", ["meloxicam"]),
    ("Synulox 250mg Tablets", ["amoxicillin_clavulanate"]),
    ("Amoxicillin + Clavulanic acid", ["amoxicillin_clavulanate"]),
    ("Amoxicillin 500mg caps", ["amoxicillin"]),
    ("ميلوكسيكام", ["meloxicam"]),
    ("Baytril 5% injection", ["enrofloxacin"]),
])
def test_name_cleaning_survives_strengths_forms_and_arabic(raw, expected):
    assert cds.resolve_drug(raw).canonicals == expected


def test_longest_ngram_wins_so_combinations_are_not_read_as_the_base_drug():
    assert cds.resolve_drug("amoxicillin clavulanate").canonicals == ["amoxicillin_clavulanate"]


def test_near_miss_is_not_guessed():
    # 'prednisolon' is one character from a real drug. Guessing is the failure
    # mode that gets an animal killed, so it must resolve to nothing.
    assert cds.resolve_drug("prednisolon").canonicals == []


def test_combination_product_screens_every_component():
    m = cds.resolve_drug("Ivermectin and Praziquantel tablets")
    assert m.reason == "combination"
    assert set(m.canonicals) == {"ivermectin", "praziquantel"}


# ═══════════════════════════════════════════════════════════════════════════
#  Interactions
# ═══════════════════════════════════════════════════════════════════════════

def test_nsaid_plus_corticosteroid_is_major():
    alerts = cds.check_interactions(["Meloxicam", "Prednisolone"])
    assert any(a.severity == cds.MAJOR and "ulcer" in a.message_en.lower() for a in alerts)


def test_two_different_nsaids_fire_the_class_rule():
    alerts = cds.check_interactions(["Carprofen", "Aspirin"])
    assert any(a.severity == cds.MAJOR for a in alerts)


def test_single_nsaid_alone_does_not_fire_the_nsaid_nsaid_rule():
    assert cds.check_interactions(["Carprofen"]) == []


def test_duplicate_active_ingredient_under_two_names_is_caught():
    alerts = cds.check_interactions(["Rimadyl", "Carprofen"])
    assert any("duplicate" in a.message_en.lower() for a in alerts)


def test_selegiline_plus_ssri_is_contraindicated():
    alerts = cds.check_interactions(["Selegiline", "Fluoxetine"])
    assert alerts[0].severity == cds.CONTRAINDICATED


def test_interaction_order_does_not_matter():
    a = cds.check_interactions(["Prednisolone", "Meloxicam"])
    b = cds.check_interactions(["Meloxicam", "Prednisolone"])
    assert [x.message_en for x in a] == [x.message_en for x in b]


def test_unknown_drug_in_an_interaction_list_is_flagged_per_drug():
    alerts = cds.check_interactions(["Meloxicam", "Zorbaxifen"])
    assert any(a.severity == cds.UNVERIFIED and "Zorbaxifen" in a.drugs[0] for a in alerts)


def test_every_interaction_entry_cites_a_source():
    for entry in cds.DATA["interactions"]:
        assert entry.get("source"), entry["drugs"]


def test_every_contraindication_entry_cites_a_source():
    for entry in cds.DATA["species_contraindications"] + cds.DATA["breed_contraindications"]:
        assert entry.get("source"), entry["drug"]
        assert entry["severity"] in cds.SEVERITY_RANK


def test_every_dose_entry_cites_a_source():
    for row in cds.DATA["doses"]:
        assert row.get("source"), row["drug"]


# ═══════════════════════════════════════════════════════════════════════════
#  Dosing — Decimal, ranges, refusals
# ═══════════════════════════════════════════════════════════════════════════

def test_dose_returns_a_range_and_a_daily_maximum():
    r = cds.calculate_dose("Amoxicillin", "Dog", "10")
    assert r.ok
    assert r.min_total == "100" and r.max_total == "200"
    assert r.max_daily_total == "400"
    assert r.unit == "mg"


def test_dose_arithmetic_is_exact_not_float():
    # 0.1 * 4.2 is 0.42000000000000004 in binary floating point.
    r = cds.calculate_dose("Meloxicam", "Dog", "4.2")
    assert r.min_total == "0.42"
    assert Decimal(r.min_total) == Decimal("0.1") * Decimal("4.2")


def test_feline_enrofloxacin_ceiling_is_not_the_canine_one():
    cat = cds.calculate_dose("Enrofloxacin", "Cat", "4")
    dog = cds.calculate_dose("Enrofloxacin", "Dog", "4")
    assert cat.max_total == "20"      # 5 mg/kg hard ceiling — retinal toxicity
    assert dog.max_total == "80"
    assert "retinal" in cat.note_en.lower()


def test_dose_refuses_unknown_drug_rather_than_extrapolating():
    r = cds.calculate_dose("Zorbaxifen", "Dog", "10")
    assert not r.ok
    assert "not in the clinical database" in r.refusal_en
    assert r.min_total is None


def test_dose_refuses_a_species_with_no_entry():
    r = cds.calculate_dose("Meloxicam", "Rabbit", "2")
    assert not r.ok
    assert "extrapolate" in r.refusal_en


def test_dose_refuses_unknown_species():
    assert not cds.calculate_dose("Meloxicam", "Ferret", "1").ok


@pytest.mark.parametrize("weight", ["0", "-5", "", None, "abc"])
def test_dose_refuses_an_unusable_weight(weight):
    assert not cds.calculate_dose("Meloxicam", "Dog", weight).ok


def test_implausible_weight_for_species_is_flagged_but_still_calculated():
    r = cds.calculate_dose("Meloxicam", "Cat", "45")   # 45 kg cat = mis-keyed
    assert r.ok
    assert r.alerts and r.alerts[0].severity == cds.MAJOR
    assert "plausible weight range" in r.alerts[0].message_en


def test_plausible_weight_raises_no_flag():
    assert cds.calculate_dose("Meloxicam", "Cat", "4.2").alerts == []


def test_insulin_is_dosed_in_units_not_milligrams():
    """ASSERTION CORRECTED: this test used to require r.unit == "IU/kg".

    `.unit` labels the TOTAL dose - it is "mg" for meloxicam and amoxicillin,
    and min_total/max_total/max_daily_total are all expressed in it. A total
    of "1 IU/kg" is not a quantity, and the same raw string also drove the
    per-kg line, which printed "0.25-0.5 IU/kg/kg". So the test was pinning
    the defect in place: any correct fix had to fail it.

    Insulin is a drug where a tenfold misread is fatal, so the unit on the
    card has to be the unit of the number beside it.
    """
    r = cds.calculate_dose("Caninsulin", "Cat", "4")
    assert r.ok
    assert r.unit == "IU", "the total dose must be labelled IU, not IU/kg"
    assert "/kg/kg" not in repr(r), "doubled unit is back"


def test_dose_refuses_a_combination_product():
    r = cds.calculate_dose("Ivermectin and Praziquantel", "Dog", "10")
    assert not r.ok
    assert "combination" in r.refusal_en


# ═══════════════════════════════════════════════════════════════════════════
#  screen() — the shape the prescribing flow consumes
# ═══════════════════════════════════════════════════════════════════════════

def test_screen_sorts_worst_first():
    result = cds.screen(
        ["Sucralfate", "Doxycycline", "Paracetamol"], "Cat", weight_kg="4",
    )
    assert result["worst_severity"] == cds.CONTRAINDICATED
    ranks = [a.rank for a in result["alerts"]]
    assert ranks == sorted(ranks)


def test_screen_is_bilingual_all_the_way_down():
    result = cds.screen(["Paracetamol"], "Cat")
    for a in result["alerts"]:
        assert a.message_en and a.message_ar


def test_screen_without_a_weight_skips_dosing_but_still_screens():
    result = cds.screen(["Paracetamol"], "Cat")
    assert result["doses"] == []
    assert result["worst_severity"] == cds.CONTRAINDICATED


def test_data_file_is_json_a_vet_can_edit():
    with open(cds._DATA_PATH, encoding="utf-8") as fh:
        raw = json.load(fh)
    assert "_README_FOR_VETERINARIANS" in raw
    assert "_KNOWN_GAPS" in raw


def test_all_dose_numbers_are_strings_so_decimal_stays_exact():
    for row in cds.DATA["doses"]:
        for key in ("min_mg_per_kg", "max_mg_per_kg", "max_mg_per_kg_per_day"):
            assert row.get(key) is None or isinstance(row[key], str), row["drug"]


def test_every_alias_points_at_a_real_canonical_name():
    canonicals = set(cds._ALIASES.values())
    referenced = (
        {e["drug"] for e in cds.DATA["species_contraindications"]}
        | {e["drug"] for e in cds.DATA["breed_contraindications"]}
        | {d for e in cds.DATA["interactions"] for d in e["drugs"]}
        | {r["drug"] for r in cds.DATA["doses"]}
    )
    classes = set(cds._CLASSES)
    unknown = referenced - canonicals - classes
    assert not unknown, f"rules reference names with no alias entry: {sorted(unknown)}"


def test_drug_class_members_are_all_reachable():
    # A class member with no alias can never be matched from a real drug name,
    # so a class rule written against it would silently never fire.
    canonicals = set(cds._ALIASES.values())
    for cls, members in cds._CLASSES.items():
        assert [m for m in members if m not in canonicals] == [], cls


# ═══════════════════════════════════════════════════════════════════════════
#  HTTP surface — blueprint registered by this test file, not by app.py
# ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def cds_app(app):
    """Builds its own app so the blueprint is reachable over HTTP.

    app.py now registers cds_bp itself (standalone reference page), so the
    explicit register_blueprint below is skipped when it is already present —
    Flask raises ValueError on a duplicate blueprint name. The fixture still
    builds a second app rather than using conftest's, because Flask refuses
    register_blueprint after the first request and earlier test modules have
    already served requests by the time this file runs.

    It deliberately reuses conftest's session database file rather than making a
    second one. create_app() points models.database's module globals at whatever
    DATABASE_PATH it is given, and conftest's autouse _restore_db_globals
    snapshots those globals at a point that is not ordered against a
    module-scoped fixture — so a second database file would leak into every
    later test module. Same file in, same file out, no leak.

    (It would also hit models.security._tables_ready, a process-global that
    makes the login_attempts DDL run for the first app only.)
    """
    from app import create_app
    from config import Config
    from blueprints.cds import cds_bp

    class CdsTestConfig(Config):
        TESTING = True
        DATABASE_PATH = app.config["DATABASE_PATH"]
        WTF_CSRF_ENABLED = False
        SECRET_KEY = "test-secret-key"
        POSTGRES_DSN = app.config.get("POSTGRES_DSN", "")
        SEED_ADMIN_PASS = "1234"

    application = create_app(CdsTestConfig)
    if cds_bp.name not in application.blueprints:
        application.register_blueprint(cds_bp)
    return application


@pytest.fixture
def cds_client(cds_app):
    c = cds_app.test_client()
    c.post("/auth/login", data={"username": "admin", "password": "1234"})
    c.get("/")
    return c


def _csrf(client):
    from models.security import _CSRF_SESSION_KEY
    with client.session_transaction() as sess:
        return sess.get(_CSRF_SESSION_KEY, "")


def test_page_requires_login(cds_app):
    r = cds_app.test_client().get("/cds/")
    assert r.status_code in (302, 401, 403)


def test_page_renders(cds_client):
    r = cds_client.get("/cds/")
    assert r.status_code == 200
    assert b"NOT YET REVIEWED" in r.data


def test_page_screens_a_lethal_combination(cds_client):
    r = cds_client.post("/cds/", data={
        "drugs": "Paracetamol", "species": "Cat", "breed": "", "weight_kg": "",
        "_csrf_token": _csrf(cds_client),
    })
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert "DO NOT GIVE" in body
    assert "Dr. Hatem" in body


def test_api_screen_returns_sorted_alerts(cds_client):
    r = cds_client.post(
        "/cds/api/screen",
        json={"drugs": ["Metacam", "Prednisolone"], "species": "Dog", "weight_kg": "10"},
        headers={"X-CSRF-Token": _csrf(cds_client)},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["worst_severity"] == cds.MAJOR
    assert body["alerts"][0]["severity_label"]["ar"]
    assert body["advisory"]["ar"]


def test_api_dose_refuses_loudly(cds_client):
    r = cds_client.post(
        "/cds/api/dose",
        json={"drug": "Zorbaxifen", "species": "Dog", "weight_kg": "10"},
        headers={"X-CSRF-Token": _csrf(cds_client)},
    )
    body = r.get_json()
    assert body["ok"] is False
    assert body["min_total"] is None
