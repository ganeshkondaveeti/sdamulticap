from __future__ import annotations

import pytest

from multicap.app.viewmodels import ap_state_diff_row, sniffer_consent_rows, wireless_safety_summary
from multicap.collectors.peekremote import PeekremoteCollector, PeekremoteDatagram
from multicap.core.filters import FilterSpec
from multicap.core.topology import Device, TopologyGraph
from multicap.core.wireless import (
    AccessPoint,
    ApCapabilityRegistry,
    ApRestorationAssertion,
    ApStateSnapshot,
    ClientLocationResolver,
    SnifferApSelector,
    SnifferConsentRecord,
    WirelessController,
    WirelessInventory,
    WirelessPathSolver,
    WirelessSafetyGate,
    WlanProfile,
)
from multicap.core.wireless_correlator import RadioactiveTraceEvent, WirelessCorrelator
from multicap.drivers.ap import ApDriver
from multicap.drivers.base import CaptureRequest, DeviceProfile
from multicap.drivers.common import RecordingTransport
from multicap.drivers.discovery import discover_drivers


def inventory(client_count: int = 3, joined: bool = True) -> WirelessInventory:
    return WirelessInventory(
        controllers={"wlc-1": WirelessController("wlc-1", "wlc-1", "192.0.2.50", "active", "17.9")},
        aps={
            "ap-1": AccessPoint(
                "ap-1", "wlc-1", joined, "edge-1", "Gi1/0/24", 0, "5GHz", 36, 80, client_count
            ),
            "ap-2": AccessPoint("ap-2", "wlc-1", True, "edge-1", "Gi1/0/25", 0, "5GHz", 40, 80, 1),
        },
        wlans={"corp": WlanProfile("corp", "corp-policy", 20, "central")},
        client_bindings={"aa:bb:cc:dd:ee:ff": ("ap-1", "corp")},
    )


def topology() -> TopologyGraph:
    graph = TopologyGraph()
    graph.add_device(Device("edge-1", "edge-1", "iosxe-switch", "ios-xe", "17.9", "192.0.2.10"))
    return graph


@pytest.mark.unit
def test_ap_capability_probe_and_sniffer_recommendation() -> None:
    candidates = SnifferApSelector(ApCapabilityRegistry.defaults()).candidates(inventory(), "wlc-1")

    assert [candidate.ap.name for candidate in candidates if candidate.recommended] == ["ap-2"]
    assert candidates[0].capability.sniffer_supported


@pytest.mark.unit
def test_wireless_safety_requires_sniffer_consent_and_live_channel_match() -> None:
    inv = inventory(client_count=4)
    location = ClientLocationResolver(inv).resolve("aa:bb:cc:dd:ee:ff")
    candidates = SnifferApSelector().candidates(inv, "wlc-1")

    blocked = WirelessSafetyGate().evaluate(location, candidates, None, live_channel=36)
    allowed = WirelessSafetyGate().evaluate(
        location,
        candidates,
        SnifferConsentRecord("job-1", "ap-1", "operator", True),
        live_channel=36,
    )
    changed = WirelessSafetyGate().evaluate(
        location,
        candidates,
        SnifferConsentRecord("job-1", "ap-1", "operator", True),
        live_channel=44,
    )

    assert not blocked.allowed
    assert allowed.allowed
    assert "Protected 802.11" in allowed.disclosure
    assert "blocked:" in wireless_safety_summary(changed)


@pytest.mark.unit
def test_wireless_path_plan_includes_ap_sniffer_action() -> None:
    plan = WirelessPathSolver(inventory(), topology()).solve_client_capture(
        job_id="job-1",
        client_mac="aa:bb:cc:dd:ee:ff",
        filter_spec=FilterSpec(protocol="tcp", dst_port=443),
    )

    assert plan.actions[0].kind == "ap-sniffer"


@pytest.mark.unit
def test_ap_driver_transitions_and_restoration_assertion() -> None:
    transport = RecordingTransport()
    driver = ApDriver(transport)
    device = DeviceProfile("ap-1", "ap-1", "ap", "ap-ios-xe", "17.9")
    handle = driver.arm(device, CaptureRequest("job-1", "SNIFF", "5GHz", "physical", 60))
    driver.trigger(device, handle)
    driver.stop(device, handle)
    driver.revert(device, handle)

    commands = [command for _device_id, command in transport.commands]
    assert "ap name ap-1 mode sniffer" in commands
    assert "ap name ap-1 mode local" in commands

    before = ApStateSnapshot("ap-1", "local", "5GHz", 36, 80)
    after = ApStateSnapshot("ap-1", "local", "5GHz", 36, 80)
    diff = ApRestorationAssertion().compare(before, after)
    assert ap_state_diff_row(diff).restored

    with pytest.raises(ValueError, match="restoration failed"):
        ApRestorationAssertion().assert_restored(
            before, ApStateSnapshot("ap-1", "sniffer", "5GHz", 36, 80)
        )


@pytest.mark.unit
def test_wireless_correlator_normalizes_peekremote_and_fuses_trace() -> None:
    location = ClientLocationResolver(inventory()).resolve("aa:bb:cc:dd:ee:ff")
    packet = (
        PeekremoteCollector()
        .collect([PeekremoteDatagram(1.0, b"PEEKHDR:80211", "ap-1")])
        .packets[0]
    )
    normalized = WirelessCorrelator().normalize_peekremote(packet, location)
    outer, inner = WirelessCorrelator().capwap_inner_view(normalized, "corr-1")
    fused = WirelessCorrelator().fuse_radioactive_trace(
        [outer, inner], [RadioactiveTraceEvent(1.5, location.client_mac, "client authenticated")]
    )

    assert normalized.payload == b"80211"
    assert normalized.metadata["channel"] == 36
    assert outer.metadata["correlation_id"] == "corr-1"
    assert [packet.mechanism for packet in fused] == [
        "capwap-inner",
        "capwap-outer",
        "radioactive-trace",
    ]


@pytest.mark.unit
def test_phase8b_viewmodel_rows_and_ap_entrypoint() -> None:
    rows = sniffer_consent_rows(SnifferApSelector().candidates(inventory(), "wlc-1"), "disclosure")

    assert rows[0].ap_name == "ap-1"
    assert "ap" in discover_drivers()
