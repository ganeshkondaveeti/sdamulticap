from __future__ import annotations

from dataclasses import dataclass

from multicap.core.wireless import ClientLocation, WirelessCapturePlan


@dataclass(frozen=True, slots=True)
class ClientLocationRow:
    client_mac: str
    ap_name: str
    controller_id: str
    channel: str
    switching_mode: str
    wired_uplink: str


@dataclass(frozen=True, slots=True)
class WirelessPlanRow:
    device_id: str
    action: str
    filter_expression: str
    reason: str


def client_location_row(location: ClientLocation) -> ClientLocationRow:
    return ClientLocationRow(
        client_mac=location.client_mac,
        ap_name=location.ap_name,
        controller_id=location.controller_id,
        channel=f"{location.band} ch{location.channel}/{location.channel_width_mhz}",
        switching_mode=location.switching_mode,
        wired_uplink=f"{location.wired_uplink_device_id}:{location.wired_uplink_interface}",
    )


def wireless_plan_rows(plan: WirelessCapturePlan) -> list[WirelessPlanRow]:
    return [
        WirelessPlanRow(action.device_id, action.kind, action.filter_expression, action.reason)
        for action in plan.actions
    ]
