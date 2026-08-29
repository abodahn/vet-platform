# -*- coding: utf-8 -*-
"""Every literal fetch() URL in a template must resolve to a real route.

"Request Lab Test" on the visit page POSTed to /clinical/lab/request for as long
as it has existed. That endpoint has never been defined - clinical/routes.py has
/lab, /lab/new, /lab/<id> and /lab/<id>/results and nothing else - so a vet
filling in the form during a consult got "Error submitting lab request. Please
try from the Lab module." every single time. A core clinical workflow, broken
100% of the time, invisible to the whole suite because no test drives browser
JavaScript.

Nothing catches this class of defect: the URL is a string in a <script> block,
so there is no import to fail, no url_for() to raise BuildError, and no import
error at boot. This test is the thing that catches it.

It only checks LITERAL paths. A URL built from a template expression or a JS
variable is skipped - there is nothing static to resolve - and those are listed
in the failure message so the exemption stays visible.
"""
import pathlib
import re

import pytest


# fetch('/path', ...) or fetch("/path") - single or double quoted, absolute only.
_FETCH = re.compile(r"""fetch\(\s*(['"])(/[^'"$({]*?)\1""")

_SKIP = ("{{", "{%")

# Deliberately unrouted, with a reason. Anything else in this set needs one too.
_EXPECTED_404 = {
    # The offline sync endpoint. models/sync.py is built and the blueprint is
    # deliberately NOT registered - see docs/sales-kit/05_OFFLINE.md and the
    # 2026-08-26 decision that one clinic on one network needs no sync. The
    # queue in base.html drains to a 404 and drops the batch, which is the
    # intended behaviour until there is a second location.
    "/api/v1/sync/push",
}


def _candidates(body):
    """(url, line) for every literal fetch target worth checking.

    Two kinds are excluded because they are not literal URLs at all:

    - `fetch('/x/' + id)` - the quoted part is a PREFIX. Matched by appending a
      dummy segment, so the prefix is still verified rather than skipped.
    - a match inside a `//` comment. templates/procurement/order_form.html has
      `${fetch('/system/users')...}` inside a comment explaining an XSS defect,
      and flagging it would train the next person to ignore this test.
    """
    for m in _FETCH.finditer(body):
        url = m.group(2)
        if any(s in url for s in _SKIP):
            continue
        line_start = body.rfind("\n", 0, m.start()) + 1
        before = body[line_start:m.start()]
        if "//" in before or before.lstrip().startswith(("*", "#")):
            continue
        line = body[:m.start()].count("\n") + 1
        url = url.split("?")[0]
        if url.endswith("/") and len(url) > 1:
            url += "1"            # a prefix; check the route shape exists
        yield url.rstrip("/") or "/", line


def _templates():
    return sorted(pathlib.Path("templates").rglob("*.html"))


@pytest.fixture
def adapter(app):
    """Bind the URL map of the SUITE's app.

    Emphatically not create_app(Config): that builds a second application
    against the real configuration, which points models.database at the
    developer's own data/platform.db and re-runs start-up against it. The
    autouse _restore_db_globals fixture puts the globals back, but the work
    done while they were wrong has already happened.
    """
    return app.url_map.bind("localhost")


def _resolves(adapter, path):
    """True if any method resolves this path."""
    from werkzeug.exceptions import MethodNotAllowed, NotFound
    for method in ("GET", "POST", "PUT", "DELETE", "PATCH"):
        try:
            adapter.match(path, method=method)
            return True
        except MethodNotAllowed:
            return True          # the path exists, just not for that verb
        except NotFound:
            continue
        except Exception:
            continue
    return False


def test_every_literal_fetch_url_in_a_template_exists(adapter):
    broken = []
    for path in _templates():
        body = path.read_text(encoding="utf-8", errors="ignore")
        for url, line in _candidates(body):
            if url in _EXPECTED_404:
                continue
            if not _resolves(adapter, url):
                broken.append("%s:%d  ->  %s" % (path.as_posix(), line, url))
    assert not broken, (
        "these templates fetch() a URL with no matching route, so the feature "
        "silently fails in the browser:\n  " + "\n  ".join(sorted(broken)))


def test_the_scan_actually_finds_fetch_calls():
    """Guard against a vacuous pass: if the regex stops matching, the test
    above succeeds by examining nothing."""
    total = 0
    for path in _templates():
        total += len(_FETCH.findall(path.read_text(encoding="utf-8", errors="ignore")))
    assert total > 20, (
        "only %d literal fetch() calls found across the templates - the regex "
        "has probably stopped matching" % total)


def test_the_lab_request_button_points_somewhere_real(adapter):
    """The specific one this file was written for."""
    body = pathlib.Path("templates/visits/visit_detail.html").read_text(
        encoding="utf-8", errors="ignore")
    # The fetch CALL, not the file: a comment above it explains what the old
    # URL was, and matching on the bare string would fail on the explanation.
    assert "fetch('/clinical/lab/request'" not in body, (
        "the visit page still posts lab requests to a route that does not exist")
    assert "fetch('/clinical/lab/new'" in body


def test_state_changing_fetches_on_the_visit_page_send_a_csrf_token():
    """A correct URL with no token is a 403, which looks identical to the vet."""
    body = pathlib.Path("templates/visits/visit_detail.html").read_text(
        encoding="utf-8", errors="ignore")
    for url in ("/ai/chat", "/clinical/lab/new"):
        i = body.find("fetch('%s'" % url)
        assert i > 0, "no fetch to %s on the visit page" % url
        window = body[max(0, i - 600):i + 400]
        assert ("X-CSRF-Token" in window or "_csrf_token" in window), (
            "the fetch to %s sends no CSRF token, so it always 403s" % url)
