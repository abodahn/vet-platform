# -*- coding: utf-8 -*-
"""The CDS module must not look more reviewed than it is.

Its rule set ships marked DRAFT - NOT YET REVIEWED BY A LICENSED VETERINARIAN.
The engine's defects are fixed, but no vet has signed off on the clinical
content, and a drug combination absent from the rule set produces no warning at
all. Understating what this module checks is safe; overstating it is not.
"""
import io


def test_the_warning_comes_before_the_first_answer(auth_client):
    """It used to appear only in the results footer - underneath an answer the
    reader had already acted on."""
    body = auth_client.get("/cds/").get_data(as_text=True)
    assert "not reviewed by a licensed" in body, "no DRAFT warning on the page"
    assert body.index("not reviewed by a licensed") < body.index("</form>"), (
        "the warning sits below the form, so it is read after the answer")


def test_the_warning_says_silence_is_not_safety(auth_client):
    """The specific misreading that could hurt an animal: a clinician assuming
    'no alert' means 'no interaction'."""
    body = auth_client.get("/cds/").get_data(as_text=True)
    assert "no warning is NOT a statement that" in body or \
           "no warning is not a statement" in body.lower(), (
        "the page does not say that an absent warning is not a safety claim")


def test_both_languages_carry_the_warning():
    """t() renders one language at a time, so this checks the template source
    rather than a rendered page - an Arabic-first clinic must not be the one
    that never sees it."""
    src = io.open("templates/cds/index.html", encoding="utf-8").read()
    assert "not reviewed by a licensed veterinarian" in src
    assert "لم تُراجَع" in src, "the Arabic warning is missing from the template"


def test_the_launcher_card_does_not_oversell_it():
    src = io.open("blueprints/launcher/routes.py", encoding="utf-8").read()
    i = src.index('"id":          "cds"')
    assert "DRAFT" in src[i:i + 500], (
        "the launcher card still describes this like a finished clinical feature")
