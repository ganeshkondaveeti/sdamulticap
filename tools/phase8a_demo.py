from __future__ import annotations

from multicap.core.filters import FilterSpec
from multicap.core.topology import Device, TopologyGraph
from multicap.core.wireless import (
    AccessPoint,
    WirelessController,
    WirelessInventory,
    WirelessPathSolver,
    WlanProfile,
)


def main() -> int:
    topology = TopologyGraph()
    topology.add_device(Device("edge-1", "edge-1", "iosxe-switch", "ios-xe", "17.9", "192.0.2.10"))
    inventory = WirelessInventory(
        controllers={"wlc-1": WirelessController("wlc-1", "wlc-1", "192.0.2.50", "active", "17.9")},
        aps={"ap-1": AccessPoint("ap-1", "wlc-1", True, "edge-1", "Gi1/0/24", 0, "5GHz", 36, 80)},
        wlans={"corp": WlanProfile("corp", "corp-policy", 20, "flex-local")},
        client_bindings={"aa:bb:cc:dd:ee:ff": ("ap-1", "corp")},
    )
    plan = WirelessPathSolver(inventory, topology).solve_client_capture(
        job_id="phase8a-demo",
        client_mac="aa:bb:cc:dd:ee:ff",
        filter_spec=FilterSpec(protocol="tcp", dst_port=443),
    )
    print(f"client={plan.client.client_mac}:{plan.client.ap_name}:ch{plan.client.channel}")
    print(f"redirected={plan.redirected}")
    print(f"actions={[action.kind for action in plan.actions]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
