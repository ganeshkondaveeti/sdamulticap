from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator, Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

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
        self.path: Path = path
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
        with self._connection() as connection:
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
        with self._connection() as connection:
            fetched: object = connection.execute(sql, params).fetchall()
            rows = cast(list[tuple[int, str, str, str, JournalAction, str, str | None]], fetched)
            return [self._row_to_entry(row) for row in rows]

    def replay_compensations(self, job_id: str) -> list[JournalEntry]:
        replayed: list[JournalEntry] = []
        for entry in self.pending_compensations(job_id):
            replayed.append(self.mark_reverted(entry))
        return replayed

    def _initialize(self) -> None:
        with self._connection() as connection:
            _ = connection.execute("PRAGMA journal_mode=WAL")
            _ = connection.execute("PRAGMA foreign_keys=ON")
            _ = connection.execute(
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
            _ = connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_journal_job ON journal_entries(job_id, id)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _row_to_entry(
        self, row: tuple[int, str, str, str, JournalAction, str, str | None]
    ) -> JournalEntry:
        entry_id, ts, job_id, device_id, action, raw_payload, raw_compensating = row
        compensating_payload = None
        if raw_compensating is not None:
            compensating_payload = cast(dict[str, object], json.loads(raw_compensating))
        return JournalEntry(
            id=entry_id,
            ts=ts,
            job_id=job_id,
            device_id=device_id,
            action=action,
            payload=cast(dict[str, object], json.loads(raw_payload)),
            compensating_payload=compensating_payload,
        )


def replay_all(journals: Iterable[SessionJournal], job_id: str) -> list[JournalEntry]:
    replayed: list[JournalEntry] = []
    for journal in journals:
        replayed.extend(journal.replay_compensations(job_id))
    return replayed


def reject_secret_material(payload: object) -> None:
    if isinstance(payload, dict):
        for key, value in cast(dict[object, object], payload).items():
            if isinstance(key, str) and key.lower() in SECRET_KEYS:
                raise ValueError(f"secret material cannot be persisted in journal payload: {key}")
            reject_secret_material(value)
    elif isinstance(payload, list | tuple):
        for item in cast(Iterable[object], payload):
            reject_secret_material(item)
