# -*- coding: utf-8 -*-
"""The exam screen's proportions and its scrolling.

Two complaints from the same recording session, both measurable in the
stylesheet rather than in behaviour:

  "جزء الفاتورة واخد تلتين الصفحة … الجزء بتاع العرض مساحته محدودة شوية"
  "الاسكرول ده صعب شوية برضه … مش سلس"

The first was exactly right: the grid was 1fr / 1.35fr / .85fr, so the
examination — the entire reason the screen exists — got 31% of the width and
the money got 69%. The second is a real, nameable defect: nine inner tables
capped at 260px with no overscroll containment, which swallow the wheel.
"""
import io
import re

EXAM = "templates/visits/exam.html"


def _src():
    return io.open(EXAM, encoding="utf-8").read()


def _grid_tracks(src):
    """The three fr weights of .hw-grid, in order."""
    m = re.search(r"\.hw-grid\{[^}]*grid-template-columns:([^}]+)\}", src, re.S)
    assert m, ".hw-grid no longer declares its columns"
    return [float(x) for x in re.findall(r"([\d.]+)fr", m.group(1))]


def test_the_examination_gets_more_width_than_either_billing_column():
    tracks = _grid_tracks(_src())
    assert len(tracks) == 3, "expected three columns, got %r" % (tracks,)
    clinical, services, payment = tracks
    assert clinical > services, \
        "the services column is still wider than the examination (%.2f vs %.2f)" % (services, clinical)
    assert clinical > payment


def test_billing_no_longer_takes_two_thirds():
    """His actual words were 'تلتين الصفحة'. Hold the line at half."""
    clinical, services, payment = _grid_tracks(_src())
    total = clinical + services + payment
    billing = (services + payment) / total
    assert billing < 0.60, \
        "billing still takes %.0f%% of the exam screen" % (billing * 100)
    assert clinical / total > 0.40, \
        "the clinical column is only %.0f%% wide" % (clinical / total * 100)


def test_the_symptom_box_is_not_five_rows_in_the_narrowest_column():
    src = _src()
    m = re.search(r'id="fSymptom"[^>]*rows="(\d+)"', src)
    assert m, "the symptom field lost its rows attribute"
    assert int(m.group(1)) >= 8, \
        "the symptom box is still %s rows — the complaint was that it is cramped" % m.group(1)


def test_billing_can_be_put_away_while_charting():
    src = _src()
    assert ".hw-grid.hw-focus>.hw-bill{display:none}" in src, \
        "no way to reclaim the billing width while writing up the visit"
    assert src.count('hw-bill"') + src.count('hw-bill ') >= 2, \
        "fewer than two panes are marked as billing"
    assert "hwFocusTotal" in src, \
        "hiding billing must keep the running total visible, not just remove it"


def test_the_toggle_is_remembered():
    """A vet who works this way works this way all day."""
    src = _src()
    i = src.index("function billingToggle")
    body = src[i:src.index("function rememberFolds", i)]
    assert "localStorage" in body, "the billing toggle resets on every page load"


def test_inner_scrollers_do_not_swallow_the_page_scroll():
    src = _src()
    m = re.search(r"\.hw-scroll\{([^}]*)\}", src)
    assert m, ".hw-scroll rule is gone"
    assert "overscroll-behavior-y" in m.group(1), \
        "the 260px inner tables still capture the wheel until they bottom out"


def test_the_sticky_money_pane_clears_the_top_bar():
    """top:1rem is 15px against a 60px opaque sticky bar."""
    src = _src()
    m = re.search(r"\.hw-grid>\.hw-money-pane\{([^}]*)\}", src, re.S)
    assert m, "the sticky money pane rule is gone"
    top = re.search(r"top:\s*(\d+)px", m.group(1))
    assert top and int(top.group(1)) >= 60, \
        "the money pane still slides under the 60px top bar (top:%s)" % (
            m.group(1).split("top:")[1].split(";")[0] if "top:" in m.group(1) else "?")


def test_the_screen_still_renders(auth_client):
    """Cheap guard: none of the CSS surgery broke the template."""
    r = auth_client.get("/visits/exam")
    assert r.status_code == 200
    body = r.data.decode("utf-8", errors="replace")
    assert 'id="hwGrid"' in body and 'id="hwFocus"' in body
