from __future__ import annotations

from pathlib import Path

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


class NxosDriver:
    platform = "nxos"

    def __init__(
        self,
        transport: CommandTransport | None = None,
        registry: CapabilityRegistry | None = None,
    ) -> None:
        self.transport = transport or RecordingTransport()
        self.registry = registry or CapabilityRegistry.from_default_fixtures()

    def probe_capabilities(self, device: DeviceProfile) -> CapabilityMatrix:
        return self.registry.probe(device)

    def arm(self, device: DeviceProfile, request: CaptureRequest) -> CaptureHandle:
        if request.capture_filter is None or not request.capture_filter.expression.strip():
            raise ValueError("NX-OS ethanalyzer requires a non-empty capture filter")
        matrix = self.probe_capabilities(device)
        if not matrix.supports("ethanalyzer"):
            raise ValueError(f"{device.release_train} does not support ethanalyzer")
        command = (
            f"ethanalyzer local interface {request.interface} capture-filter "
            f'"{request.capture_filter.expression}" limit-captured-frames 0 write {request.output_path}'
        )
        self.transport.execute(device, command)
        return CaptureHandle(
            job_id=request.job_id,
            device_id=device.id,
            capture_name=request.capture_name,
            commands=(command,),
            metadata={"remote_path": request.output_path},
        )

    def trigger(self, device: DeviceProfile, handle: CaptureHandle) -> None:
        self.transport.execute(device, f"ethanalyzer session {handle.capture_name} start")

    def stop(self, device: DeviceProfile, handle: CaptureHandle) -> None:
        self.transport.execute(device, f"ethanalyzer session {handle.capture_name} stop")

    def collect(
        self, device: DeviceProfile, handle: CaptureHandle, destination: Path
    ) -> CaptureArtifact:
        self.transport.execute(device, f"copy {handle.metadata['remote_path']} scp://collector/")
        return write_mock_artifact(destination, handle)

    def revert(self, device: DeviceProfile, handle: CaptureHandle) -> None:
        self.transport.execute(device, f"delete {handle.metadata['remote_path']} no-prompt")


def create_driver() -> NxosDriver:
    return NxosDriver()
