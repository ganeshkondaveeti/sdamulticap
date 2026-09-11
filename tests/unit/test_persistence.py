from __future__ import annotations

import os
import shutil
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from multicap.persistence.audit import AuditLog
from multicap.persistence.journal import SessionJournal
from multicap.persistence.pcap_store import PcapStore, RetentionPolicy


@pytest.mark.unit
def test_session_journal_replays_pending_compensations_once(tmp_path: Path) -> None:
    journal = SessionJournal(tmp_path / "journal.sqlite3")

    _ = journal.append(
        job_id="job-1",
        device_id="switch-1",
        action="apply",
        payload={"command": "monitor capture start"},
        compensating_payload={"command": "monitor capture stop"},
    )

    replayed = journal.replay_compensations("job-1")
    replayed_again = journal.replay_compensations("job-1")

    assert [entry.payload for entry in replayed] == [{"command": "monitor capture stop"}]
    assert replayed_again == []
    assert [entry.action for entry in journal.entries("job-1")] == ["apply", "revert"]


@pytest.mark.unit
def test_session_journal_uses_sqlite_wal(tmp_path: Path) -> None:
    path = tmp_path / "journal.sqlite3"
    _ = SessionJournal(path)

    with sqlite3.connect(path) as connection:
        mode = _fetch_required_string_row(connection, "PRAGMA journal_mode")[0]

    assert mode == "wal"


@pytest.mark.unit
def test_audit_log_hash_chain_detects_tampering(tmp_path: Path) -> None:
    path = tmp_path / "audit.sqlite3"
    audit = AuditLog(path)

    first = audit.append(job_id="job-1", event="consent", payload={"ticket": "CHG123"})
    second = audit.append(job_id="job-1", event="armed", payload={"devices": ["switch-1"]})

    assert second.previous_hash == first.entry_hash
    assert audit.verify()

    with sqlite3.connect(path) as connection:
        _ = connection.execute(
            "UPDATE audit_records SET payload = ? WHERE id = 1", ('{"ticket":"CHG999"}',)
        )

    assert not audit.verify()


@pytest.mark.unit
def test_pcap_store_prunes_by_age_and_size(tmp_path: Path) -> None:
    store = PcapStore(tmp_path / "pcaps", RetentionPolicy(max_age_days=1, max_bytes=8))
    source = tmp_path / "source.pcapng"

    _ = source.write_bytes(b"old-old")
    old = store.put("job-old", source).path
    old_time = (datetime.now(UTC) - timedelta(days=3)).timestamp()
    os.utime(old, (old_time, old_time))

    _ = source.write_bytes(b"new-one")
    first_new = store.put("job-new-1", source).path
    _ = source.write_bytes(b"new-two")
    second_new = store.put("job-new-2", source).path

    deleted = store.prune(now=datetime.now(UTC))

    assert old in deleted
    assert first_new in deleted
    assert second_new.exists()


@pytest.mark.unit
def test_persistence_rejects_plaintext_secret_payloads(tmp_path: Path) -> None:
    journal = SessionJournal(tmp_path / "journal.sqlite3")
    audit = AuditLog(tmp_path / "audit.sqlite3")

    with pytest.raises(ValueError, match="secret material"):
        _ = journal.append(
            job_id="job-1",
            device_id="switch-1",
            action="apply",
            payload={"username": "admin", "password": "not-on-disk"},
        )

    with pytest.raises(ValueError, match="secret material"):
        _ = audit.append(job_id="job-1", event="credential", payload={"token": "not-on-disk"})


@pytest.mark.unit
def test_sqlite_persistence_releases_files_for_windows_cleanup(tmp_path: Path) -> None:
    root = tmp_path / "temporary-ui-state"
    root.mkdir()
    journal = SessionJournal(root / "journal.sqlite3")
    audit = AuditLog(root / "audit.sqlite3")

    _ = journal.append(
        job_id="job-1",
        device_id="switch-1",
        action="apply",
        payload={"command": "monitor capture start"},
    )
    _ = audit.append(job_id="job-1", event="consent", payload={"ticket": "CHG123"})
    assert journal.entries("job-1")
    assert audit.records()

    shutil.rmtree(root)
    assert not root.exists()


def _fetch_required_string_row(connection: sqlite3.Connection, sql: str) -> tuple[str]:
    fetched = cast(object, connection.execute(sql).fetchone())
    assert fetched is not None
    return cast(tuple[str], fetched)
