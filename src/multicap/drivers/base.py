from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol, runtime_checkable

FeatureMap = dict[str, bool]
CaptureAction = Literal["arm", "trigger", "stop", "collect", "revert"]


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    id: str
    host: str
    platform: str
    os_family: str
    release_train: str


@dataclass(frozen=True, slots=True)
class CaptureFilter:
    expression: str


@dataclass(frozen=True, slots=True)
class CaptureRequest:
    job_id: str
    capture_name: str
    interface: str
    interface_type: Literal["physical", "svi", "subinterface", "control-plane"]
    duration_seconds: int
    capture_filter: CaptureFilter | None = None
    output_path: str = "bootflash:multicap.pcap"
    buffer_mb: int = 32


@dataclass(frozen=True, slots=True)
class CaptureHandle:
    job_id: str
    device_id: str
    capture_name: str
    commands: tuple[str, ...]
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class CaptureArtifact:
    job_id: str
    device_id: str
    remote_path: str
    local_path: Path | None = None
    sha256: str | None = None


@dataclass(frozen=True, slots=True)
class CapabilityMatrix:
    platform: str
    os_family: str
    release_train: str
    features: FeatureMap

    def supports(self, feature: str) -> bool:
        return self.features.get(feature, False)


class CommandTransport(Protocol):
    def execute(self, target: DeviceProfile, command: str, **kwargs: object) -> str: ...


@runtime_checkable
class CaptureDriver(Protocol):
    platform: str

    def probe_capabilities(self, device: DeviceProfile) -> CapabilityMatrix: ...

    def arm(self, device: DeviceProfile, request: CaptureRequest) -> CaptureHandle: ...

    def trigger(self, device: DeviceProfile, handle: CaptureHandle) -> None: ...

    def stop(self, device: DeviceProfile, handle: CaptureHandle) -> None: ...

    def collect(
        self, device: DeviceProfile, handle: CaptureHandle, destination: Path
    ) -> CaptureArtifact: ...

    def revert(self, device: DeviceProfile, handle: CaptureHandle) -> None: ...
