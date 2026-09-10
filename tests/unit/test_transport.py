from __future__ import annotations

from pathlib import Path
from threading import Thread

import pytest

from multicap.transport.scp import sha256_file, verify_checksum
from multicap.transport.ssh_pool import RetryPolicy, SshConnectionPool, SshTarget


class FakeConnection:
    def __init__(self, failures: int = 0) -> None:
        self.failures = failures
        self.commands: list[str] = []
        self.closed = False

    def send_command(self, command: str, **kwargs: object) -> str:
        self.commands.append(command)
        if self.failures:
            self.failures -= 1
            raise OSError("temporary transport failure")
        return f"ok:{command}"

    def disconnect(self) -> None:
        self.closed = True


class FlakyFactory:
    def __init__(self) -> None:
        self.connections = [
            FakeConnection(failures=1),
            FakeConnection(failures=1),
            FakeConnection(),
        ]

    def __call__(self, **kwargs: object) -> FakeConnection:
        return self.connections.pop(0)


@pytest.mark.unit
def test_ssh_pool_reuses_persistent_connection_and_closes_it() -> None:
    connections: list[FakeConnection] = []

    def factory(**kwargs: object) -> FakeConnection:
        connection = FakeConnection()
        connections.append(connection)
        return connection

    pool = SshConnectionPool(connection_factory=factory)
    target = SshTarget(host="switch1", platform="cisco_ios", username="u", password="p")

    assert pool.execute(target, "show clock") == "ok:show clock"
    assert pool.execute(target, "show version") == "ok:show version"

    assert len(connections) == 1
    assert connections[0].commands == ["show clock", "show version"]

    pool.close_all()
    assert connections[0].closed


@pytest.mark.unit
def test_ssh_pool_retries_with_backoff() -> None:
    sleeps: list[float] = []
    factory = FlakyFactory()
    pool = SshConnectionPool(
        connection_factory=factory,
        retry=RetryPolicy(attempts=3, base_delay_seconds=1.0, jitter_seconds=0.0),
        sleeper=sleeps.append,
        jitter=lambda start, end: 0.0,
    )
    target = SshTarget(host="router1", platform="cisco_ios", username="u", password="p")

    assert pool.execute(target, "show ip int brief") == "ok:show ip int brief"
    assert sleeps == [1.0, 2.0]
    assert factory.connections == []


@pytest.mark.unit
def test_sha256_file_reports_capture_checksum(tmp_path: Path) -> None:
    capture = tmp_path / "capture.pcapng"
    capture.write_bytes(b"pcapng bytes")

    assert (
        sha256_file(capture) == "f2ff261077eaae7ea13906cb3ca1d88b5f1de308f14c1a108188af4553373234"
    )


@pytest.mark.unit
def test_verify_checksum_rejects_corrupt_capture(tmp_path: Path) -> None:
    capture = tmp_path / "capture.pcapng"
    capture.write_bytes(b"pcapng bytes")

    with pytest.raises(ValueError, match="checksum mismatch"):
        verify_checksum(capture, "0" * 64)


@pytest.mark.unit
def test_ssh_pool_sustains_100_mock_sessions() -> None:
    created: list[FakeConnection] = []

    def factory(**kwargs: object) -> FakeConnection:
        connection = FakeConnection()
        created.append(connection)
        return connection

    pool = SshConnectionPool(
        connection_factory=factory,
        platform_caps={"cisco_ios": 100},
        per_host_cap=1,
    )
    results: list[str] = []

    def worker(index: int) -> None:
        target = SshTarget(
            host=f"device-{index}",
            platform="cisco_ios",
            username="u",
            password="p",
        )
        results.append(pool.execute(target, "show clock"))

    threads = [Thread(target=worker, args=(index,)) for index in range(100)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(results) == 100
    assert len(created) == 100
