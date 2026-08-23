# -*- coding: utf-8 -*-
"""An off-site backup must not carry patient records in the clear.

Option B for a single-clinic-in-a-building deployment: the app runs on a PC in
the clinic, so the internet is never in the path of daily work, and a nightly
copy goes off-site whenever the internet happens to be up.

That copy leaves the building - onto somebody else's storage, or onto a USB
stick that travels in a pocket. It holds every patient record, every client's
phone number and every invoice the clinic has ever raised.

These tests cover the two ways that goes wrong: sending it unencrypted, and
encrypting it with a key nobody can produce later. The second is worse. The
first is a breach; the second is a year of green dashboards and nothing to
restore.
"""
import io
import os

import pytest

from models import backup as bk


@pytest.fixture
def key(monkeypatch):
    from cryptography.fernet import Fernet
    k = Fernet.generate_key().decode()
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", k)
    return k


@pytest.fixture
def archive(tmp_path):
    """Something recognisable, so 'was it encrypted' is not a guess."""
    p = tmp_path / "clinic_20260823.db"
    p.write_bytes(b"SQLite format 3\x00" + b"Yasmine Abdelwadoud 01099887766 " * 400)
    return str(p)


# ── the round trip ───────────────────────────────────────────────────────────

def test_an_encrypted_archive_restores_byte_for_byte(key, archive, tmp_path):
    enc = bk._encrypt_for_offsite(archive)
    back = bk.decrypt_archive(enc, str(tmp_path / "restored.db"))
    assert open(back, "rb").read() == open(archive, "rb").read()


def test_the_encrypted_file_does_not_contain_the_patient_data(key, archive):
    """The test that would have caught 'encryption' that did nothing."""
    enc = bk._encrypt_for_offsite(archive)
    blob = open(enc, "rb").read()
    assert b"Yasmine Abdelwadoud" not in blob, "the client's name is readable"
    assert b"01099887766" not in blob, "the client's phone number is readable"
    assert b"SQLite format 3" not in blob, "it is still recognisably a database"
    assert blob != open(archive, "rb").read()


def test_the_wrong_key_says_so_rather_than_looking_like_damage(archive,
                                                               monkeypatch):
    """'Wrong key' and 'corrupt file' need different answers from a person.
    One is a five-minute fix; the other means the backup is gone."""
    from cryptography.fernet import Fernet
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    enc = bk._encrypt_for_offsite(archive)
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    with pytest.raises(RuntimeError) as exc:
        bk.decrypt_archive(enc)
    msg = str(exc.value)
    assert "wrong key" in msg.lower()
    assert "not damaged" in msg.lower(), (
        "the message does not tell the reader their data is still fine")


def test_no_key_at_all_says_it_cannot_be_opened_by_anyone(archive, monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("BACKUP_ENCRYPTION_KEY", Fernet.generate_key().decode())
    enc = bk._encrypt_for_offsite(archive)
    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc:
        bk.decrypt_archive(enc)
    assert "not set" in str(exc.value)


# ── failing closed ───────────────────────────────────────────────────────────

def test_without_a_key_nothing_is_sent_off_site(archive, tmp_path, monkeypatch):
    """The decision that matters. Refusing to send is recoverable - somebody
    sets the key and tomorrow's copy goes. Sending is not: it cannot be
    recalled from a bucket, a NAS or a stick somebody already has."""
    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY", raising=False)
    dest = tmp_path / "offsite"
    monkeypatch.setenv("BACKUP_OFFSITE_DIR", str(dest))

    results = bk.copy_offsite(archive)

    assert results, "it reported nothing at all, so nobody would know"
    assert all(not r["ok"] for r in results)
    assert any("encryption key" in (r.get("error") or "") for r in results)
    assert not dest.exists() or not list(dest.iterdir()), (
        "an unencrypted archive was written off-site")


def test_with_a_key_the_off_site_copy_is_encrypted(key, archive, tmp_path,
                                                   monkeypatch):
    dest = tmp_path / "offsite"
    monkeypatch.setenv("BACKUP_OFFSITE_DIR", str(dest))

    results = bk.copy_offsite(archive)
    assert results and all(r["ok"] for r in results), results

    written = list(dest.iterdir())
    assert written, "nothing arrived off-site"
    for f in written:
        assert f.name.endswith(bk.ENCRYPTED_SUFFIX), "sent without .enc: %s" % f.name
        assert b"Yasmine Abdelwadoud" not in f.read_bytes()


def test_the_local_archive_is_left_readable(key, archive, tmp_path, monkeypatch):
    """Deliberate: the local copy sits on the clinic's own disk beside the
    database it came from. An encrypted local backup whose key has been lost is
    not a backup at all."""
    monkeypatch.setenv("BACKUP_OFFSITE_DIR", str(tmp_path / "offsite"))
    bk.copy_offsite(archive)
    assert b"SQLite format 3" in open(archive, "rb").read(), (
        "the local archive was encrypted in place")


def test_the_encrypted_temporary_does_not_pile_up(key, archive, tmp_path,
                                                  monkeypatch):
    """It is a transport artefact. Left behind it doubles the disk the backup
    directory uses and puts files in the restore list that cannot be read."""
    monkeypatch.setenv("BACKUP_OFFSITE_DIR", str(tmp_path / "offsite"))
    bk.copy_offsite(archive)
    assert not os.path.exists(archive + bk.ENCRYPTED_SUFFIX)


def test_no_off_site_target_configured_is_not_an_error(key, archive, monkeypatch):
    monkeypatch.delenv("BACKUP_OFFSITE_DIR", raising=False)
    monkeypatch.delenv("BACKUP_S3_BUCKET", raising=False)
    assert bk.copy_offsite(archive) == []


# ── the tool that proves the key ─────────────────────────────────────────────

def test_the_key_checker_refuses_to_pass_without_a_key(monkeypatch):
    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY", raising=False)
    from scripts.verify_backup_key import _round_trip
    assert _round_trip() == 1


def test_the_key_checker_passes_with_a_real_key(key):
    from scripts.verify_backup_key import _round_trip
    assert _round_trip() == 0


def test_the_key_tool_tells_you_not_to_keep_it_only_on_that_machine():
    """The failure this whole feature exists to survive is that computer dying.
    A key stored only on it dies with it, and the year of uploads is unopenable."""
    src = io.open("scripts/verify_backup_key.py", encoding="utf-8").read()
    assert "password manager" in src
    assert "not live only in the place" in src or "not only on the clinic" in src
