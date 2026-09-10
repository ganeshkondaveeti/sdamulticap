from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

SnmpGetter = Callable[[str, str, str, int], str]


@dataclass(frozen=True, slots=True)
class SnmpEndpoint:
    host: str
    community: str
    port: int = 161


@dataclass(slots=True)
class SnmpClient:
    endpoint: SnmpEndpoint
    getter: SnmpGetter | None = None

    def sys_object_id(self) -> str:
        return self._getter()(
            self.endpoint.host, self.endpoint.community, "1.3.6.1.2.1.1.2.0", self.endpoint.port
        )

    def _getter(self) -> SnmpGetter:
        if self.getter is not None:
            return self.getter
        return _pysnmp_get


def _pysnmp_get(host: str, community: str, oid: str, port: int) -> str:
    from pysnmp.hlapi import (
        CommunityData,
        ContextData,
        ObjectIdentity,
        ObjectType,
        SnmpEngine,
        UdpTransportTarget,
        getCmd,
    )

    iterator = getCmd(
        SnmpEngine(),
        CommunityData(community),
        UdpTransportTarget((host, port)),
        ContextData(),
        ObjectType(ObjectIdentity(oid)),
    )
    error_indication, error_status, _error_index, var_binds = next(iterator)
    if error_indication:
        raise RuntimeError(str(error_indication))
    if error_status:
        raise RuntimeError(str(error_status))
    return str(var_binds[0][1])
