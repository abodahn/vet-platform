# -*- coding: utf-8 -*-
"""The exam screen's Paid button, when the payment does NOT go through.

`fetch()` only rejects on a network error. A 403 from an expired CSRF token, a
409 from a closed invoice, a 500 from anything — all of them land in .then()
looking exactly like success. The dialog closed, the list refreshed behind it,
and the cashier moved to the next client with the invoice still unpaid and no
signal that anything had gone wrong. The client had already handed over cash.

These are source-level assertions rather than browser tests because the bug is
in a branch that only a failing server response reaches, and the project does
not run a JS engine in CI (cerebrum: "Do NOT use Chrome/browser automation").
They are written to fail if the guard is removed, which is the point.
"""
import io
import re

EXAM = "templates/visits/exam.html"


def _script(path=EXAM):
    return io.open(path, encoding="utf-8").read()


def _pay_handler(src):
    """The body of the hwPayConfirm click handler."""
    i = src.index("$('hwPayConfirm').addEventListener")
    j = src.index("var payNonce", i)
    return src[i:j]


def test_a_non_ok_response_is_not_treated_as_a_payment():
    body = _pay_handler(_script())
    assert re.search(r"if\s*\(\s*!\s*r\.ok\s*\)", body), \
        "the pay fetch does not check response.ok — a 403/500 closes the dialog as if paid"
    assert "throw" in body, "a non-OK response must reach the failure branch"


def test_the_dialog_stays_open_when_the_payment_fails():
    """The cashier has to SEE it failed — the client is standing there."""
    body = _pay_handler(_script())
    catch = body[body.index(".catch("):]
    assert "closePay()" not in catch, \
        "the failure branch closes the dialog, hiding the fact that nothing was taken"
    assert "hwPayError" in catch, "the failure branch shows no message"


def test_the_failure_message_says_no_money_moved():
    src = _script()
    assert "payFailed" in src and "payRetry" in src, \
        "no wording that tells the cashier the payment was not recorded"
    assert "لم يُخصم" in src, "the Arabic wording does not say nothing was deducted"


def test_settling_in_full_offers_the_next_case():
    """Hatem: 'close it, then start fresh so I can open a new case'."""
    src = _script()
    assert "function offerNewCase" in src, "no way back to a blank form after settling"
    body = _pay_handler(src)
    assert "offerNewCase()" in body, "the paid-in-full branch does not offer a new case"


def test_a_part_payment_says_what_is_still_owed():
    """Note 9 was confusion about 1700/1000/700. Silence repeats it."""
    body = _pay_handler(_script())
    assert "stillOwes" in body, "a partial payment gives no running balance"


def test_a_failed_pet_load_clears_the_form():
    """The worst swallowed error on this screen.

    loadPet() used to ignore failures, leaving the PREVIOUS animal's chart on
    screen. The vet examines the cat in front of them and charts the dog.
    """
    src = _script()
    i = src.index("function loadPet(")
    body = src[i:src.index("\n  }", i)]
    assert body.count("resetForm()") >= 2, \
        "loadPet does not clear the form on failure — the previous pet stays on screen"
    assert "couldNotOpen" in body, "a failed pet load says nothing"


def test_the_alert_colours_follow_the_apps_own_theme_switch():
    """The app switches theme with [data-theme] and defaults to light.

    These boxes used to key off @media (prefers-color-scheme) alone, so the
    Night button left them light-on-dark and a dark OS made them dark-on-light
    while the rest of the page stayed light.
    """
    src = _script()
    assert 'html[data-theme="dark"] .hw-danger' in src, \
        "alert colours ignore the in-app theme switch"
    assert 'html:not([data-theme="light"]) .hw-danger' in src, \
        "an explicit light choice must beat a dark OS"


def test_every_alert_class_used_by_the_script_is_actually_styled():
    """alert3('hw-ok', ...) with no .hw-ok rule renders an unstyled box."""
    src = _script()
    used = set(re.findall(r"alert3\(\s*'(hw-[a-z]+)'", src))
    assert used, "no alert3 calls found — this test is watching nothing"
    for cls in sorted(used):
        assert re.search(r"^\." + cls + r"\{", src, re.M), \
            "%s is used by the script but has no CSS rule" % cls
