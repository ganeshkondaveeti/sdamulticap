from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ParamikoLikeClient(Protocol):
    def get_transport(self) -> object: ...


@dataclass(frozen=True, slots=True)
class PulledFile:
    path: Path
    sha256: str
    bytes_written: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pull_file(client: ParamikoLikeClient, remote_path: str, local_path: Path) -> PulledFile:
    from scp import SCPClient

    local_path.parent.mkdir(parents=True, exist_ok=True)
    with SCPClient(client.get_transport()) as scp_client:
        scp_client.get(remote_path, str(local_path))
    return PulledFile(
        path=local_path,
        sha256=sha256_file(local_path),
        bytes_written=local_path.stat().st_size,
    )


def verify_checksum(path: Path, expected_sha256: str) -> PulledFile:
    actual = sha256_file(path)
    if actual.lower() != expected_sha256.lower():
        raise ValueError(f"checksum mismatch for {path}: expected {expected_sha256}, got {actual}")
    return PulledFile(path=path, sha256=actual, bytes_written=path.stat().st_size)
