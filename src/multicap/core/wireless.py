from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from multicap.core.filters import FilterSpec
from multicap.core.topology import Device, TopologyGraph

SwitchingMode = Literal["central", "flex-local", "fabric"]
HaRole = Literal["active", "standby"]
WirelessActionKind = Literal["wlc-epc", "capwap-inner", "radioactive-trace", "wired-redirect"]


@dataclass(frozen=True, slots=True)
class WirelessController:
    id: str
    host: str
    management_ip: str
    ha_role: HaRole
    release_train: str

    def device(self) -> Device:
        return Device(
            id=self.id,
            host=self.host,
            platform="iosxe-wlc",
            os_family="ios-xe-wireless",
            release_train=self.release_train,
            management_ip=self.management_ip,
            source="wireless-discovery",
        )


@dataclass(frozen=True, slots=True)
class AccessPoint:
    name: str
    controller_id: str
    joined: bool
    attached_switch_id: str
    attached_interface: str
    radio_slot: int
    band: str
    channel: int
    channel_width_mhz: int


@dataclass(frozen=True, slots=True)
class WlanProfile:
    ssid: str
    policy_profile: str
    vlan: int
    switching_mode: SwitchingMode


@dataclass(frozen=True, slots=True)
class ClientLocation:
    client_mac: str
    state: Literal["associated", "not-associated"]
    ap_name: str
    controller_id: str
    wlan_ssid: str
    vlan: int
    switching_mode: SwitchingMode
    band: str
    channel: int
    channel_width_mhz: int
    wired_uplink_device_id: str
    wired_uplink_interface: str


@dataclass(frozen=True, slots=True)
class WirelessInventory:
    controllers: dict[str, WirelessController]
    aps: dict[str, AccessPoint]
    wlans: dict[str, WlanProfile]
    client_bindings: dict[str, tuple[str, str]]


class ClientLocationResolver:
    def __init__(self, inventory: WirelessInventory) -> None:
        self._inventory = inventory

    def resolve(self, client_mac: str) -> ClientLocation:
        binding = self._inventory.client_bindings.get(client_mac.lower())
        if binding is None:
            return ClientLocation(
                client_mac=client_mac.lower(),
                state="not-associated",
                ap_name="",
                controller_id="",
                wlan_ssid="",
                vlan=0,
                switching_mode="central",
                band="",
                channel=0,
                channel_width_mhz=0,
                wired_uplink_device_id="",
                wired_uplink_interface="",
            )
        ap_name, ssid = binding
        ap = self._inventory.aps[ap_name]
        wlan = self._inventory.wlans[ssid]
        return ClientLocation(
            client_mac=client_mac.lower(),
            state="associated" if ap.joined else "not-associated",
            ap_name=ap.name,
            controller_id=ap.controller_id,
            wlan_ssid=wlan.ssid,
            vlan=wlan.vlan,
            switching_mode=wlan.switching_mode,
            band=ap.band,
            channel=ap.channel,
            channel_width_mhz=ap.channel_width_mhz,
            wired_uplink_device_id=ap.attached_switch_id,
            wired_uplink_interface=ap.attached_interface,
        )


@dataclass(frozen=True, slots=True)
class WirelessCaptureAction:
    kind: WirelessActionKind
    device_id: str
    filter_expression: str
    reason: str = ""


@dataclass(frozen=True, slots=True)
class WirelessCapturePlan:
    job_id: str
    client: ClientLocation
    actions: tuple[WirelessCaptureAction, ...]
    redirected: bool


class WirelessPathSolver:
    def __init__(self, inventory: WirelessInventory, topology: TopologyGraph) -> None:
        self._inventory = inventory
        self._topology = topology

    def solve_client_capture(
        self,
        *,
        job_id: str,
        client_mac: str,
        filter_spec: FilterSpec,
    ) -> WirelessCapturePlan:
        client = ClientLocationResolver(self._inventory).resolve(client_mac)
        if client.state != "associated":
            raise ValueError(f"client {client_mac} is not associated")
        controller = self._inventory.controllers[client.controller_id]
        if controller.ha_role != "active":
            raise ValueError(f"controller {controller.id} is not HA active")
        expression = wireless_filter_expression(client, filter_spec)
        actions = [
            WirelessCaptureAction("wlc-epc", controller.id, expression),
            WirelessCaptureAction("capwap-inner", controller.id, expression),
            WirelessCaptureAction("radioactive-trace", controller.id, client.client_mac),
        ]
        redirected = client.switching_mode in {"flex-local", "fabric"}
        if redirected:
            if client.wired_uplink_device_id not in self._topology.devices:
                raise ValueError(
                    f"wired uplink {client.wired_uplink_device_id} is absent from topology"
                )
            actions.append(
                WirelessCaptureAction(
                    "wired-redirect",
                    client.wired_uplink_device_id,
                    expression,
                    f"{client.switching_mode} traffic bypasses the controller data plane",
                )
            )
        return WirelessCapturePlan(job_id, client, tuple(actions), redirected)


def wireless_filter_expression(client: ClientLocation, spec: FilterSpec) -> str:
    parts = [f"client-mac {client.client_mac}", f"vlan {client.vlan}"]
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
    return " ".join(parts)
