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


class IosXeSwitchDriver:
    platform = "iosxe-switch"

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
        matrix = self.probe_capabilities(device)
        feature = f"epc_{request.interface_type.replace('-', '_')}"
        if not matrix.supports(feature):
            raise ValueError(
                f"{device.release_train} does not support IOS-XE EPC on {request.interface_type}"
            )
        commands = self._arm_commands(request)
        for command in commands:
            self.transport.execute(device, command)
        return CaptureHandle(
            job_id=request.job_id,
            device_id=device.id,
            capture_name=request.capture_name,
            commands=tuple(commands),
            metadata={"remote_path": request.output_path, "feature": feature},
        )

    def trigger(self, device: DeviceProfile, handle: CaptureHandle) -> None:
        self.transport.execute(device, f"monitor capture {handle.capture_name} start")

    def stop(self, device: DeviceProfile, handle: CaptureHandle) -> None:
        self.transport.execute(device, f"monitor capture {handle.capture_name} stop")

    def collect(
        self, device: DeviceProfile, handle: CaptureHandle, destination: Path
    ) -> CaptureArtifact:
        self.transport.execute(
            device,
            f"monitor capture {handle.capture_name} export {handle.metadata['remote_path']}",
        )
        return write_mock_artifact(destination, handle)

    def revert(self, device: DeviceProfile, handle: CaptureHandle) -> None:
        self.transport.execute(device, f"no monitor capture {handle.capture_name}")

    def _arm_commands(self, request: CaptureRequest) -> list[str]:
        commands = [
            f"monitor capture {request.capture_name} buffer size {request.buffer_mb}",
            f"monitor capture {request.capture_name} interface {request.interface} both",
        ]
        if request.capture_filter is not None:
            commands.append(
                f"monitor capture {request.capture_name} match any {request.capture_filter.expression}"
            )
        commands.append(
            f"monitor capture {request.capture_name} limit duration {request.duration_seconds}"
        )
        return commands


def create_driver() -> IosXeSwitchDriver:
    return IosXeSwitchDriver()
