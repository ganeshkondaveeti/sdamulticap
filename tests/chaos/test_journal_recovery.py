from __future__ import annotations

from pathlib import Path

import pytest

from multicap.persistence.journal import SessionJournal


@pytest.mark.chaos
def test_journal_recovery_after_mid_transaction_process_loss(tmp_path: Path) -> None:
    journal_path = tmp_path / "journal.sqlite3"
    before_crash = SessionJournal(journal_path)
    before_crash.append(
        job_id="job-crash",
        device_id="nxos-1",
        action="apply",
        payload={"command": "feature monitor-session"},
        compensating_payload={"command": "no feature monitor-session"},
    )

    after_restart = SessionJournal(journal_path)
    replayed = after_restart.replay_compensations("job-crash")

    assert [entry.payload for entry in replayed] == [{"command": "no feature monitor-session"}]
    assert after_restart.pending_compensations("job-crash") == []
