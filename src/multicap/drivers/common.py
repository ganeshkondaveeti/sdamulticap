from __future__ import annotations

from pathlib import Path

from multicap.drivers.base import CaptureArtifact, CaptureHandle, DeviceProfile


class RecordingTransport:
    def __init__(self) -> None:
        self.commands: list[tuple[str, str]] = []

    def execute(self, target: DeviceProfile, command: str, **kwargs: object) -> str:
        self.commands.append((target.id, command))
        return "ok"


def write_mock_artifact(
    destination: Path, handle: CaptureHandle, suffix: str = ".pcap"
) -> CaptureArtifact:
    destination.mkdir(parents=True, exist_ok=True)
    local_path = destination / f"{handle.device_id}-{handle.capture_name}{suffix}"
    local_path.write_bytes(f"multicap artifact {handle.job_id} {handle.device_id}".encode())
    return CaptureArtifact(
        job_id=handle.job_id,
        device_id=handle.device_id,
        remote_path=str(handle.metadata["remote_path"]),
        local_path=local_path,
    )
