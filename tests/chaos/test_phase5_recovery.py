from __future__ import annotations

from pathlib import Path

import pytest

from multicap.core.cleanup import CleanupStateManager
from multicap.persistence.audit import AuditLog
from multicap.persistence.journal import SessionJournal


@pytest.mark.chaos
def test_phase5_recovery_replays_pending_device_compensation(tmp_path: Path) -> None:
    journal = SessionJournal(tmp_path / "journal.sqlite3")
    audit = AuditLog(tmp_path / "audit.sqlite3")
    journal.append(
        job_id="job-crash",
        device_id="core-a",
        action="apply",
        payload={"command": "monitor capture MCAP start"},
        compensating_payload={"command": "no monitor capture MCAP"},
    )

    replayed = CleanupStateManager(journal, audit).recover("job-crash")

    assert [entry.payload for entry in replayed] == [{"command": "no monitor capture MCAP"}]
    assert [record.event for record in audit.records()] == [
        "recovery-started",
        "recovery-completed",
    ]
