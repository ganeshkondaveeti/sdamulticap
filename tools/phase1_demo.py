from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from multicap.persistence.audit import AuditLog
from multicap.persistence.journal import SessionJournal
from multicap.persistence.pcap_store import PcapStore, RetentionPolicy
from multicap.transport.ssh_pool import SshConnectionPool, SshTarget


class DemoConnection:
    def send_command(self, command: str, **kwargs: object) -> str:
        return f"demo-output:{command}"

    def disconnect(self) -> None:
        return None


def main() -> int:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        pool = SshConnectionPool(connection_factory=lambda **kwargs: DemoConnection())
        target = SshTarget(
            host="demo-switch", platform="cisco_ios", username="demo", password="demo"
        )
        ssh_output = pool.execute(target, "show clock")

        journal = SessionJournal(root / "journal.sqlite3")
        journal.append(
            job_id="phase1-demo",
            device_id="demo-switch",
            action="apply",
            payload={"command": "monitor capture start"},
            compensating_payload={"command": "monitor capture stop"},
        )
        replayed = journal.replay_compensations("phase1-demo")

        audit = AuditLog(root / "audit.sqlite3")
        audit.append(job_id="phase1-demo", event="ssh-exec", payload={"output": ssh_output})

        source = root / "demo.pcapng"
        source.write_bytes(b"demo-pcapng")
        store = PcapStore(root / "pcaps", RetentionPolicy(max_age_days=30, max_bytes=1024))
        stored = store.put("phase1-demo", source)

        print(f"ssh={ssh_output}")
        print(f"replayed={len(replayed)}")
        print(f"audit_ok={audit.verify()}")
        print(f"pcap_bytes={stored.bytes_written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
