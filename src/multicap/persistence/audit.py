from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from multicap.persistence.journal import reject_secret_material, utc_now

GENESIS_HASH = "0" * 64


@dataclass(frozen=True, slots=True)
class AuditRecord:
    id: int
    ts: str
    job_id: str
    event: str
    payload: dict[str, object]
    previous_hash: str
    entry_hash: str


class AuditLog:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def append(self, *, job_id: str, event: str, payload: dict[str, object]) -> AuditRecord:
        reject_secret_material(payload)
        with self._connect() as connection:
            previous = self._last_hash(connection)
            ts = utc_now()
            entry_hash = self._hash(ts, job_id, event, payload, previous)
            cursor = connection.execute(
                """
                INSERT INTO audit_records(ts, job_id, event, payload, previous_hash, entry_hash)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (ts, job_id, event, json.dumps(payload, sort_keys=True), previous, entry_hash),
            )
            record_id = cursor.lastrowid
            if record_id is None:
                raise RuntimeError("SQLite did not return an audit record id")
            return AuditRecord(
                id=record_id,
                ts=ts,
                job_id=job_id,
                event=event,
                payload=payload,
                previous_hash=previous,
                entry_hash=entry_hash,
            )

    def records(self) -> list[AuditRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT id, ts, job_id, event, payload, previous_hash, entry_hash FROM audit_records ORDER BY id"
            )
            return [
                AuditRecord(
                    id=row["id"],
                    ts=row["ts"],
                    job_id=row["job_id"],
                    event=row["event"],
                    payload=json.loads(row["payload"]),
                    previous_hash=row["previous_hash"],
                    entry_hash=row["entry_hash"],
                )
                for row in rows
            ]

    def verify(self) -> bool:
        previous = GENESIS_HASH
        for record in self.records():
            if record.previous_hash != previous:
                return False
            if record.entry_hash != self._hash(
                record.ts,
                record.job_id,
                record.event,
                record.payload,
                record.previous_hash,
            ):
                return False
            previous = record.entry_hash
        return True

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_records(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    job_id TEXT NOT NULL,
                    event TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL UNIQUE
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _last_hash(self, connection: sqlite3.Connection) -> str:
        row = connection.execute(
            "SELECT entry_hash FROM audit_records ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return GENESIS_HASH
        return str(row["entry_hash"])

    def _hash(
        self,
        ts: str,
        job_id: str,
        event: str,
        payload: dict[str, object],
        previous_hash: str,
    ) -> str:
        canonical = json.dumps(
            {
                "event": event,
                "job_id": job_id,
                "payload": payload,
                "previous_hash": previous_hash,
                "ts": ts,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()
