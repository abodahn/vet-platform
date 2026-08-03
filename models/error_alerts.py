# -*- coding: utf-8 -*-
"""Tell somebody when the app breaks.

Until now an unhandled 500 was written to a log table and that was the end of
it. Nobody is watching a log table. In a pilot the failure mode is: the clinic
hits an error at 11am, works around it, mentions it three days later as "the
system was being weird", and by then there is nothing left to diagnose.

This turns a 500 into a notification the managers actually see, reusing the
same delivery path backup alerts already use (db.notify_managers) rather than
introducing a second one.

Two things it deliberately does NOT do:

  - It does not send the stack trace to the clinic. Staff cannot act on it and
    it can contain patient data. The trace stays in the logs; the notification
    says where and when, and links to the page that shows the rest.
  - It does not notify on every occurrence. One broken page reloaded twenty
    times is one problem, not twenty; without a cooldown the notification list
    becomes the thing nobody reads.
"""
import logging
import os
import threading
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# How long to stay quiet about the SAME error signature after reporting it.
COOLDOWN_MINUTES = int(os.environ.get("ERROR_ALERT_COOLDOWN_MINUTES", "60"))

# signature -> datetime of last notification.
#
# ponytail: process-local dict, not a table. With N gunicorn workers a burst can
# produce up to N notifications instead of one, which is noisy but never wrong
# and costs nothing when it is not needed. Move it to a table if a real
# deployment finds the duplication annoying.
_last_sent: dict = {}
_lock = threading.Lock()


def _should_send(signature: str) -> bool:
    now = datetime.now()
    with _lock:
        last = _last_sent.get(signature)
        if last and now - last < timedelta(minutes=COOLDOWN_MINUTES):
            return False
        _last_sent[signature] = now
        return True


def reset() -> None:
    """Forget every cooldown. For tests."""
    with _lock:
        _last_sent.clear()


def signature_for(path: str, exc: BaseException) -> str:
    """What counts as 'the same error'.

    Path plus exception type, not the message: a message usually carries the
    specific id or value that varied, so including it would defeat the cooldown
    exactly when a page is failing repeatedly.
    """
    return f"{path}::{type(exc).__name__}"


def report(path: str, exc: BaseException, user: str = "") -> bool:
    """Notify managers that `path` raised. Returns True if a notice was sent.

    Never raises: this runs inside a 500 handler, and an error-reporter that
    can itself fail turns one broken page into a crash loop.
    """
    try:
        sig = signature_for(path, exc)
        if not _should_send(sig):
            return False

        who = f" (while {user} was using it)" if user else ""
        body = (f"{type(exc).__name__} on {path}{who}. "
                f"Staff saw an error page. The details are in "
                f"System → Monitor → recent logs.")

        import models.database as db
        db.notify_managers(
            title="A page failed with an error",
            body=body,
            icon="⚠️",
            link="/system/monitor",
            module="system",
        )
        return True
    except Exception:
        # Logged, never propagated -- see the docstring.
        logger.exception("could not deliver an error alert for %s", path)
        return False
