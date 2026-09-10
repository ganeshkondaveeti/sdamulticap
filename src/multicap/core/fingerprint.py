from __future__ import annotations

from dataclasses import dataclass

from multicap.drivers.base import DeviceProfile
from multicap.transport.snmp import SnmpClient


@dataclass(frozen=True, slots=True)
class FingerprintRule:
    oid_prefix: str
    platform: str
    os_family: str
    release_train: str


class SnmpFingerprinter:
    def __init__(self, rules: list[FingerprintRule] | None = None) -> None:
        self._rules = rules or default_fingerprint_rules()

    def fingerprint(self, host: str, snmp: SnmpClient) -> DeviceProfile:
        sys_object_id = snmp.sys_object_id()
        for rule in self._rules:
            if sys_object_id.startswith(rule.oid_prefix):
                return DeviceProfile(
                    id=host,
                    host=host,
                    platform=rule.platform,
                    os_family=rule.os_family,
                    release_train=rule.release_train,
                )
        raise KeyError(f"unknown sysObjectID: {sys_object_id}")


def default_fingerprint_rules() -> list[FingerprintRule]:
    return [
        FingerprintRule("1.3.6.1.4.1.9.1.2494", "iosxe-switch", "ios-xe", "17.9"),
        FingerprintRule("1.3.6.1.4.1.9.12.3.1.3", "nxos", "nx-os", "10.2"),
    ]
