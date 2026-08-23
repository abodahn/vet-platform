# -*- coding: utf-8 -*-
"""The pre-demo readiness check.

scripts/preflight.py asks whether a deployment is SAFE to hand to a clinic.
This asks a different question: will it hold up in a room with a clinic owner
watching. Both matter; neither answers the other.

These tests keep the script honest about the two things it must never get
wrong: it must not pass a demo that is actually broken, and it must never
change anything.
"""
import io


def test_it_checks_the_things_that_end_a_demo():
    """Each of these has its own way of ending a meeting in the first minute."""
    src = io.open("scripts/demo_check.py", encoding="utf-8").read()
    for fn in ("check_clinic_identity",      # somebody else's name on the invoice
               "check_todays_board",          # an empty first screen
               "check_whatsapp",              # the feature they ask to see
               "check_arabic_pdf",            # where competitors break
               "check_no_published_password", # what a technical buyer looks for
               "check_cds_is_marked"):        # the one that is a liability
        assert "def %s(" % fn in src, "%s is missing from demo_check" % fn
        assert fn in src.split("CHECKS = [")[1], "%s is defined but never run" % fn


def test_it_never_writes_anything():
    """It runs against a live clinic database, sometimes minutes before a
    meeting. A readiness check that mutates the thing it is checking is the
    worst possible tool to run at that moment."""
    src = io.open("scripts/demo_check.py", encoding="utf-8").read()
    for verb in ("INSERT ", "UPDATE ", "DELETE ", "DROP ", "ALTER ",
                 "conn.commit()"):
        assert verb not in src, (
            "demo_check.py contains %r - it must be read-only" % verb)


def test_it_agrees_with_the_demo_script():
    """The checklist lives in two places - the document a person reads and the
    script a machine runs. They drift silently unless something notices."""
    doc = io.open("docs/sales-kit/03_DEMO_SCRIPT.md", encoding="utf-8").read()
    for phrase in ("WhatsApp", "logo", "Arabic"):
        assert phrase in doc, "the demo script no longer mentions %s" % phrase
    assert "wapilot" in doc.lower() or "WhatsApp is connected" in doc


def test_it_runs_without_crashing(app):
    """A checker that throws on a real database teaches nothing."""
    import subprocess
    import sys
    r = subprocess.run([sys.executable, "scripts/demo_check.py"],
                       capture_output=True, text=True, timeout=300)
    out = r.stdout + r.stderr
    assert "DEMO READINESS" in out, "the check produced no report:\n%s" % out[-500:]
    # Exit 1 means FAILs were found, which is a valid outcome, not a crash.
    assert r.returncode in (0, 1, 2), "unexpected exit %d" % r.returncode
    assert "Traceback" not in out, "the check crashed:\n%s" % out[-600:]
