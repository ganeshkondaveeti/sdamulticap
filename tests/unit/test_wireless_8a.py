from __future__ import annotations

from typing import cast

import pytest

from multicap.app.viewmodels import client_location_row, wireless_plan_rows
from multicap.core.filters import FilterSpec
from multicap.core.topology import Device, TopologyGraph
from multicap.core.wireless import (
    AccessPoint,
    ClientLocationResolver,
    SwitchingMode,
    WirelessController,
    WirelessInventory,
    WirelessPathSolver,
    WlanProfile,
)
from multicap.drivers.base import CaptureFilter, CaptureRequest, DeviceProfile
from multicap.drivers.common import RecordingTransport
from multicap.drivers.discovery import discover_drivers
from multicap.drivers.iosxe_wlc import IosXeWlcDriver


def inventory(mode: SwitchingMode = "central") -> WirelessInventory:
    return WirelessInventory(
        controllers={"wlc-1": WirelessController("wlc-1", "wlc-1", "192.0.2.50", "active", "17.9")},
        aps={"ap-1": AccessPoint("ap-1", "wlc-1", True, "edge-1", "Gi1/0/24", 0, "5GHz", 36, 80)},
        wlans={"corp": WlanProfile("corp", "corp-policy", 20, mode)},
        client_bindings={"aa:bb:cc:dd:ee:ff": ("ap-1", "corp")},
    )


def topology() -> TopologyGraph:
    graph = TopologyGraph()
    graph.add_device(Device("edge-1", "edge-1", "iosxe-switch", "ios-xe", "17.9", "192.0.2.10"))
    graph.add_device(Device("wlc-1", "wlc-1", "iosxe-wlc", "ios-xe-wireless", "17.9", "192.0.2.50"))
    return graph


@pytest.mark.unit
def test_client_location_resolver_maps_mac_to_ap_controller_wlan_and_uplink() -> None:
    location = ClientLocationResolver(inventory()).resolve("AA:BB:CC:DD:EE:FF")

    assert location.state == "associated"
    assert location.ap_name == "ap-1"
    assert location.controller_id == "wlc-1"
    assert location.switching_mode == "central"
    assert location.wired_uplink_device_id == "edge-1"
    assert client_location_row(location).channel == "5GHz ch36/80"


@pytest.mark.unit
@pytest.mark.parametrize("mode", ["flex-local", "fabric"])
def test_wireless_path_solver_redirects_non_central_switching(mode: str) -> None:
    plan = WirelessPathSolver(
        inventory(cast(SwitchingMode, mode)), topology()
    ).solve_client_capture(
        job_id="job-wireless",
        client_mac="aa:bb:cc:dd:ee:ff",
        filter_spec=FilterSpec(protocol="tcp", dst_port=443),
    )

    assert plan.redirected
    assert plan.actions[-1].kind == "wired-redirect"
    assert plan.actions[-1].device_id == "edge-1"
    assert mode in plan.actions[-1].reason
    assert wireless_plan_rows(plan)[-1].action == "wired-redirect"


@pytest.mark.unit
def test_wireless_path_solver_keeps_central_capture_on_controller() -> None:
    plan = WirelessPathSolver(inventory("central"), topology()).solve_client_capture(
        job_id="job-wireless",
        client_mac="aa:bb:cc:dd:ee:ff",
        filter_spec=FilterSpec(protocol="udp", dst_port=53),
    )

    assert not plan.redirected
    assert [action.kind for action in plan.actions] == [
        "wlc-epc",
        "capwap-inner",
        "radioactive-trace",
    ]
    assert "client-mac aa:bb:cc:dd:ee:ff" in plan.actions[0].filter_expression


@pytest.mark.unit
def test_iosxe_wlc_driver_arms_controller_side_capture_actions() -> None:
    transport = RecordingTransport()
    driver = IosXeWlcDriver(transport=transport)
    device = DeviceProfile("wlc-1", "wlc-1", "iosxe-wlc", "ios-xe-wireless", "17.9")
    driver.arm(
        device,
        CaptureRequest(
            "job-1",
            "WLCAP",
            "wireless",
            "physical",
            60,
            CaptureFilter("client-mac aa:bb:cc:dd:ee:ff"),
        ),
    )
    action_plan = WirelessPathSolver(inventory("central"), topology()).solve_client_capture(
        job_id="job-wireless",
        client_mac="aa:bb:cc:dd:ee:ff",
        filter_spec=FilterSpec(protocol="tcp", dst_port=443),
    )
    for action in action_plan.actions:
        driver.arm_wireless_action(device, action, 60)

    commands = [command for _device_id, command in transport.commands]
    assert any("monitor capture WLCAP match any client-mac" in command for command in commands)
    assert any("monitor capture MCAP_CAPWAP inner mac" in command for command in commands)
    assert any("debug wireless mac aa:bb:cc:dd:ee:ff" in command for command in commands)
    assert (
        driver.define_ap_packet_capture_profile("P8A", "ap-1", 36)[0]
        == "ap packet-capture profile P8A"
    )


@pytest.mark.unit
def test_iosxe_wlc_driver_entry_point_is_discoverable() -> None:
    drivers = discover_drivers()

    assert "iosxe-wlc" in drivers
