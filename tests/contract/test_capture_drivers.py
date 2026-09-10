from __future__ import annotations

from pathlib import Path
from typing import Literal, cast

import pytest

from multicap.drivers.base import CaptureFilter, CaptureRequest, DeviceProfile
from multicap.drivers.common import RecordingTransport
from multicap.drivers.iosxe_switch import IosXeSwitchDriver
from multicap.drivers.nxos import NxosDriver

InterfaceType = Literal["physical", "svi", "subinterface", "control-plane"]


@pytest.fixture
def iosxe_device() -> DeviceProfile:
    return DeviceProfile(
        id="cat9k-1",
        host="cat9k-1.example.test",
        platform="iosxe-switch",
        os_family="ios-xe",
        release_train="17.9",
    )


@pytest.fixture
def nxos_device() -> DeviceProfile:
    return DeviceProfile(
        id="nexus-1",
        host="nexus-1.example.test",
        platform="nxos",
        os_family="nx-os",
        release_train="10.2",
    )


@pytest.mark.contract
@pytest.mark.parametrize(
    "interface_type,interface",
    [("physical", "Gi1/0/1"), ("svi", "Vlan10"), ("subinterface", "Gi1/0/1.10")],
)
@pytest.mark.parametrize("capture_filter", [None, CaptureFilter("ipv4 host 192.0.2.10")])
def test_iosxe_switch_driver_contract_round_trip(
    tmp_path: Path,
    iosxe_device: DeviceProfile,
    interface_type: str,
    interface: str,
    capture_filter: CaptureFilter | None,
) -> None:
    transport = RecordingTransport()
    driver = IosXeSwitchDriver(transport=transport)
    request = CaptureRequest(
        job_id="job-iosxe",
        capture_name="MCAP",
        interface=interface,
        interface_type=cast(InterfaceType, interface_type),
        duration_seconds=30,
        capture_filter=capture_filter,
    )

    handle = driver.arm(iosxe_device, request)
    driver.trigger(iosxe_device, handle)
    driver.stop(iosxe_device, handle)
    artifact = driver.collect(iosxe_device, handle, tmp_path)
    driver.revert(iosxe_device, handle)

    commands = [command for _device_id, command in transport.commands]
    assert f"monitor capture MCAP interface {interface} both" in commands
    assert "monitor capture MCAP start" in commands
    assert "monitor capture MCAP stop" in commands
    assert "no monitor capture MCAP" in commands
    assert artifact.local_path is not None and artifact.local_path.exists()
    if capture_filter is None:
        assert not any(" match any " in command for command in commands)
    else:
        assert any("match any ipv4 host 192.0.2.10" in command for command in commands)


@pytest.mark.contract
def test_nxos_driver_contract_round_trip_with_filter(
    tmp_path: Path, nxos_device: DeviceProfile
) -> None:
    transport = RecordingTransport()
    driver = NxosDriver(transport=transport)
    request = CaptureRequest(
        job_id="job-nxos",
        capture_name="NXCAP",
        interface="mgmt",
        interface_type="control-plane",
        duration_seconds=30,
        capture_filter=CaptureFilter("host 192.0.2.10"),
        output_path="bootflash:nxcap.pcap",
    )

    handle = driver.arm(nxos_device, request)
    driver.trigger(nxos_device, handle)
    driver.stop(nxos_device, handle)
    artifact = driver.collect(nxos_device, handle, tmp_path)
    driver.revert(nxos_device, handle)

    commands = [command for _device_id, command in transport.commands]
    assert commands[0].startswith("ethanalyzer local interface mgmt capture-filter")
    assert '"host 192.0.2.10"' in commands[0]
    assert artifact.local_path is not None and artifact.local_path.exists()


@pytest.mark.contract
def test_nxos_unfiltered_ethanalyzer_refuses_before_transport(nxos_device: DeviceProfile) -> None:
    transport = RecordingTransport()
    driver = NxosDriver(transport=transport)
    request = CaptureRequest(
        job_id="job-nxos",
        capture_name="NXCAP",
        interface="mgmt",
        interface_type="control-plane",
        duration_seconds=30,
    )

    with pytest.raises(ValueError, match="requires a non-empty capture filter"):
        driver.arm(nxos_device, request)

    assert transport.commands == []
