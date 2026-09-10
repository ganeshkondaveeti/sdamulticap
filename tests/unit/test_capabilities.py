from __future__ import annotations

import pytest

from multicap.drivers.base import DeviceProfile
from multicap.drivers.capabilities import CapabilityRegistry
from multicap.drivers.discovery import discover_drivers


@pytest.mark.unit
def test_capability_registry_reports_phase2_release_matrix() -> None:
    registry = CapabilityRegistry.from_default_fixtures()
    matrices = registry.all_matrices()

    iosxe_trains = {
        matrix.release_train
        for matrix in matrices
        if matrix.platform == "iosxe-switch" and matrix.supports("epc_physical")
    }
    nxos_trains = {
        matrix.release_train
        for matrix in matrices
        if matrix.platform == "nxos" and matrix.supports("ethanalyzer")
    }

    assert iosxe_trains == {"17.6", "17.9", "17.12"}
    assert nxos_trains == {"9.3", "10.2"}


@pytest.mark.unit
def test_capability_registry_probes_device_profile() -> None:
    registry = CapabilityRegistry.from_default_fixtures()
    matrix = registry.probe(
        DeviceProfile(
            id="cat9k-1",
            host="cat9k-1.example.test",
            platform="iosxe-switch",
            os_family="ios-xe",
            release_train="17.12",
        )
    )

    assert matrix.supports("epc_svi")


@pytest.mark.unit
def test_driver_entry_points_are_discoverable() -> None:
    drivers = discover_drivers()

    assert sorted(drivers) == ["iosxe-switch", "iosxe-wlc", "nxos"]
