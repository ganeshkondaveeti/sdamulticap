from __future__ import annotations

import pytest

from multicap.core.fingerprint import FingerprintRule, SnmpFingerprinter
from multicap.core.inventory import (
    CatalystCenterInventorySource,
    InventoryIngestService,
    StaticInventorySource,
    thin_inventory_sources,
)
from multicap.transport.restconf import RestconfEndpoint
from multicap.transport.snmp import SnmpClient, SnmpEndpoint


class FakeRestconfClient:
    def __init__(self, payload: object) -> None:
        self.endpoint = RestconfEndpoint("https://catalyst-center.example.test", "user", "pass")
        self.payload = payload
        self.paths: list[str] = []

    def get_json(self, path: str) -> object:
        self.paths.append(path)
        return self.payload


@pytest.mark.unit
def test_snmp_fingerprinter_maps_sys_object_id_to_device_profile() -> None:
    snmp = SnmpClient(
        SnmpEndpoint("192.0.2.20", "public"),
        getter=lambda host, community, oid, port: "1.3.6.1.4.1.9.1.2494.1",
    )
    profile = SnmpFingerprinter(
        [FingerprintRule("1.3.6.1.4.1.9.1.2494", "iosxe-switch", "ios-xe", "17.9")]
    ).fingerprint("cat9k-20", snmp)

    assert profile.platform == "iosxe-switch"
    assert profile.release_train == "17.9"


@pytest.mark.unit
def test_catalyst_center_inventory_ingests_devices() -> None:
    restconf = FakeRestconfClient(
        {
            "response": [
                {
                    "id": "device-1",
                    "hostname": "cat9k-1",
                    "managementIpAddress": "192.0.2.21",
                    "platformId": "iosxe-switch",
                    "softwareType": "ios-xe",
                    "softwareVersion": "17.9",
                }
            ]
        }
    )
    source = CatalystCenterInventorySource(restconf)
    graph = InventoryIngestService([source]).ingest()

    assert sorted(graph.devices) == ["device-1"]
    assert graph.devices["device-1"].source == "catalyst-center"
    assert restconf.paths == ["dna/intent/api/v1/network-device"]


@pytest.mark.unit
def test_thin_inventory_sources_are_feature_flagged_off_by_default() -> None:
    sources = thin_inventory_sources()
    graph = InventoryIngestService(sources).ingest()

    assert graph.devices == {}
    assert [source.name for source in sources] == ["prime", "nso", "nexus-dashboard", "apic"]
    assert all(
        isinstance(source, StaticInventorySource) and not source.enabled for source in sources
    )
