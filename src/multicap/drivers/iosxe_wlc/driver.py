from __future__ import annotations

from pathlib import Path

from multicap.core.wireless import WirelessCaptureAction
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


class IosXeWlcDriver:
    platform = "iosxe-wlc"

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
        for command in commands:
            self.transport.execute(device, command)
        return CaptureHandle(
            job_id=request.job_id,
            device_id=device.id,
            capture_name=request.capture_name,
            commands=tuple(commands),
            metadata={"remote_path": request.output_path},
        )

    def trigger(self, device: DeviceProfile, handle: CaptureHandle) -> None:
        self.transport.execute(device, f"monitor capture {handle.capture_name} start")

    def stop(self, device: DeviceProfile, handle: CaptureHandle) -> None:
        self.transport.execute(device, f"monitor capture {handle.capture_name} stop")

    def collect(
        self, device: DeviceProfile, handle: CaptureHandle, destination: Path
    ) -> CaptureArtifact:
        self.transport.execute(
            device, f"monitor capture {handle.capture_name} export {handle.metadata['remote_path']}"
        )
        return write_mock_artifact(destination, handle)

    def revert(self, device: DeviceProfile, handle: CaptureHandle) -> None:
        self.transport.execute(device, f"no monitor capture {handle.capture_name}")

    def arm_wireless_action(
        self,
        device: DeviceProfile,
        action: WirelessCaptureAction,
        duration_seconds: int,
    ) -> CaptureHandle:
        if action.kind == "radioactive-trace":
            commands = (
                f"debug wireless mac {action.filter_expression} monitor-time {duration_seconds}",
                "show wireless stats trace-on-failure",
            )
        elif action.kind == "capwap-inner":
            commands = (
                f"monitor capture MCAP_CAPWAP inner mac {action.filter_expression}",
                f"monitor capture MCAP_CAPWAP limit duration {duration_seconds}",
            )
        else:
            commands = (
                f"monitor capture MCAP_WLC match any {action.filter_expression}",
                f"monitor capture MCAP_WLC limit duration {duration_seconds}",
            )
        for command in commands:
            self.transport.execute(device, command)
        return CaptureHandle(
            job_id="wireless-action",
            device_id=device.id,
            capture_name=action.kind,
            commands=commands,
            metadata={"action": action.kind, "remote_path": "bootflash:wireless-action.pcap"},
        )

    def define_ap_packet_capture_profile(
        self, profile_name: str, ap_name: str, channel: int
    ) -> tuple[str, ...]:
        return (
            f"ap packet-capture profile {profile_name}",
            f"ap name {ap_name}",
            f"channel {channel}",
            "shutdown",
        )


def create_driver() -> IosXeWlcDriver:
    return IosXeWlcDriver()
