from __future__ import annotations

from pathlib import Path

from multicap.core.wireless import ApStateSnapshot
from multicap.drivers.base import (
    CapabilityMatrix,
    CaptureArtifact,
    CaptureHandle,
    CaptureRequest,
    CommandTransport,
    DeviceProfile,
)
from multicap.drivers.capabilities import CapabilityRegistry
from multicap.drivers.common import RecordingTransport, write_mock_artifact


class ApDriver:
    platform = "ap"

    def __init__(
        self, transport: CommandTransport | None = None, registry: CapabilityRegistry | None = None
    ) -> None:
        self.transport = transport or RecordingTransport()
        self.registry = registry or CapabilityRegistry.from_default_fixtures()

    def probe_capabilities(self, device: DeviceProfile) -> CapabilityMatrix:
        return self.registry.probe(device)

    def arm(self, device: DeviceProfile, request: CaptureRequest) -> CaptureHandle:
        commands = (
            f"ap name {device.id} dot11 {request.interface} shutdown",
            f"ap name {device.id} mode sniffer",
            f"ap name {device.id} packet-dump profile {request.capture_name}",
        )
        for command in commands:
            self.transport.execute(device, command)
        return CaptureHandle(
            job_id=request.job_id,
            device_id=device.id,
            capture_name=request.capture_name,
            commands=commands,
            metadata={"remote_path": request.output_path},
        )

    def trigger(self, device: DeviceProfile, handle: CaptureHandle) -> None:
        self.transport.execute(
            device, f"ap name {device.id} packet-dump start {handle.capture_name}"
        )

    def stop(self, device: DeviceProfile, handle: CaptureHandle) -> None:
        self.transport.execute(
            device, f"ap name {device.id} packet-dump stop {handle.capture_name}"
        )

    def collect(
        self, device: DeviceProfile, handle: CaptureHandle, destination: Path
    ) -> CaptureArtifact:
        return write_mock_artifact(destination, handle, ".pcapng")

    def revert(self, device: DeviceProfile, handle: CaptureHandle) -> None:
        self.transport.execute(
            device, f"ap name {device.id} no packet-dump profile {handle.capture_name}"
        )
        self.transport.execute(device, f"ap name {device.id} mode local")

    def snapshot(
        self, ap_name: str, mode: str, band: str, channel: int, width: int
    ) -> ApStateSnapshot:
        return ApStateSnapshot(ap_name, mode, band, channel, width)  # type: ignore[arg-type]


def create_driver() -> ApDriver:
    return ApDriver()
