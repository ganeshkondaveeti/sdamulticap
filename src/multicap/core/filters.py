from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from multicap.drivers.base import CaptureFilter, DeviceProfile


@dataclass(frozen=True, slots=True)
class FilterSpec:
    protocol: Literal["tcp", "udp", "icmp", "ip"] = "ip"
    src_ip: str | None = None
    dst_ip: str | None = None
    src_port: int | None = None
    dst_port: int | None = None
    mac: str | None = None
    vlan: int | None = None


class FilterBuilder:
    def build(self, spec: FilterSpec, device: DeviceProfile) -> CaptureFilter:
        expression = self._bpf(spec) if device.platform == "nxos" else self._iosxe_match(spec)
        if device.platform == "nxos" and not expression.strip():
            raise ValueError("NX-OS ethanalyzer requires a non-empty filter")
        return CaptureFilter(expression=expression)

    def _bpf(self, spec: FilterSpec) -> str:
        parts: list[str] = []
        if spec.vlan is not None:
            parts.append(f"vlan {spec.vlan}")
        if spec.mac is not None:
            parts.append(f"ether host {spec.mac}")
        if spec.protocol != "ip":
            parts.append(spec.protocol)
        if spec.src_ip is not None:
            parts.append(f"src host {spec.src_ip}")
        if spec.dst_ip is not None:
            parts.append(f"dst host {spec.dst_ip}")
        if spec.src_port is not None:
            parts.append(f"src port {spec.src_port}")
        if spec.dst_port is not None:
            parts.append(f"dst port {spec.dst_port}")
        return " and ".join(parts)

    def _iosxe_match(self, spec: FilterSpec) -> str:
        parts: list[str] = []
        if spec.protocol != "ip":
            parts.append(spec.protocol)
        if spec.src_ip is not None:
            parts.append(f"src host {spec.src_ip}")
        if spec.dst_ip is not None:
            parts.append(f"dst host {spec.dst_ip}")
        if spec.src_port is not None:
            parts.append(f"src port {spec.src_port}")
        if spec.dst_port is not None:
            parts.append(f"dst port {spec.dst_port}")
        if spec.mac is not None:
            parts.append(f"mac {spec.mac}")
        if spec.vlan is not None:
            parts.append(f"vlan {spec.vlan}")
        return " ".join(parts) or "ip"
