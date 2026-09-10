from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

JournalAction = Literal["apply", "revert"]
SECRET_KEYS = frozenset({"password", "passwd", "secret", "token", "api_key", "private_key"})


@dataclass(frozen=True, slots=True)
class JournalEntry:
    id: int | None
    ts: str
    job_id: str
    device_id: str
    action: JournalAction
    payload: dict[str, object]
    compensating_payload: dict[str, object] | None = None


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class SessionJournal:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def append(
        self,
        *,
        job_id: str,
        device_id: str,
        action: JournalAction,
        payload: dict[str, object],
        compensating_payload: dict[str, object] | None = None,
    ) -> JournalEntry:
        entry = JournalEntry(
            id=None,
            ts=utc_now(),
            job_id=job_id,
            device_id=device_id,
            action=action,
            payload=payload,
            compensating_payload=compensating_payload,
        )
        reject_secret_material(entry.payload)
        if entry.compensating_payload is not None:
            reject_secret_material(entry.compensating_payload)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO journal_entries(ts, job_id, device_id, action, payload, compensating_payload)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.ts,
                    entry.job_id,
                    entry.device_id,
                    entry.action,
                    json.dumps(entry.payload, sort_keys=True),
                    json.dumps(entry.compensating_payload, sort_keys=True)
                    if entry.compensating_payload is not None
                    else None,
                ),
            )
            return JournalEntry(
                id=cursor.lastrowid,
                ts=entry.ts,
                job_id=entry.job_id,
                device_id=entry.device_id,
                action=entry.action,
                payload=entry.payload,
                compensating_payload=entry.compensating_payload,
            )

    def pending_compensations(self, job_id: str) -> list[JournalEntry]:
        entries = self.entries(job_id)
        applied = [
            entry for entry in entries if entry.action == "apply" and entry.compensating_payload
        ]
        reverted_payloads = {
            json.dumps(entry.payload, sort_keys=True)
            for entry in entries
            if entry.action == "revert"
        }
        return [
            entry
            for entry in reversed(applied)
            if json.dumps(entry.compensating_payload, sort_keys=True) not in reverted_payloads
        ]

    def mark_reverted(self, entry: JournalEntry) -> JournalEntry:
        if entry.compensating_payload is None:
            raise ValueError("journal entry has no compensating payload")
        return self.append(
            job_id=entry.job_id,
            device_id=entry.device_id,
            action="revert",
            payload=entry.compensating_payload,
        )

    def entries(self, job_id: str | None = None) -> list[JournalEntry]:
        sql = "SELECT id, ts, job_id, device_id, action, payload, compensating_payload FROM journal_entries"
        params: tuple[object, ...] = ()
        if job_id is not None:
            sql += " WHERE job_id = ?"
            params = (job_id,)
        sql += " ORDER BY id"
        with self._connect() as connection:
            return [self._row_to_entry(row) for row in connection.execute(sql, params)]

    def replay_compensations(self, job_id: str) -> list[JournalEntry]:
        replayed: list[JournalEntry] = []
        for entry in self.pending_compensations(job_id):
            replayed.append(self.mark_reverted(entry))
        return replayed

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS journal_entries(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    action TEXT NOT NULL CHECK(action IN ('apply', 'revert')),
                    payload TEXT NOT NULL,
                    compensating_payload TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_journal_job ON journal_entries(job_id, id)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _row_to_entry(self, row: sqlite3.Row) -> JournalEntry:
        return JournalEntry(
            id=row["id"],
            ts=row["ts"],
            job_id=row["job_id"],
            device_id=row["device_id"],
            action=row["action"],
            payload=json.loads(row["payload"]),
            compensating_payload=json.loads(row["compensating_payload"])
            if row["compensating_payload"] is not None
            else None,
        )


def replay_all(journals: Iterable[SessionJournal], job_id: str) -> list[JournalEntry]:
    replayed: list[JournalEntry] = []
    for journal in journals:
        replayed.extend(journal.replay_compensations(job_id))
    return replayed


def reject_secret_material(payload: object) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() in SECRET_KEYS:
                raise ValueError(f"secret material cannot be persisted in journal payload: {key}")
            reject_secret_material(value)
    elif isinstance(payload, list | tuple):
        for item in payload:
            reject_secret_material(item)
