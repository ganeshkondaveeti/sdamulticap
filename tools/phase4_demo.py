from __future__ import annotations

from multicap.app.viewmodels import PathIntentViewModel, rows_for_plan
from multicap.core.filters import FilterSpec
from multicap.core.topology import Device, Link, TopologyGraph


def demo_graph() -> TopologyGraph:
    graph = TopologyGraph()
    graph.add_device(Device("core-a", "core-a", "iosxe-switch", "ios-xe", "17.9", "192.0.2.1"))
    graph.add_device(Device("dist-b", "dist-b", "nxos", "nx-os", "10.2", "192.0.2.2"))
    graph.add_device(Device("edge-c", "edge-c", "iosxe-switch", "ios-xe", "17.12", "192.0.2.3"))
    graph.add_link(Link("core-a", "Gi1/0/1", "dist-b", "Eth1/1", "cdp"))
    graph.add_link(Link("dist-b", "Eth1/2", "edge-c", "Gi1/0/2", "cdp"))
    return graph


def main() -> int:
    plan = PathIntentViewModel(demo_graph()).compile_plan(
        job_id="phase4-demo",
        src_device_id="core-a",
        dst_device_id="edge-c",
        duration_seconds=120,
        filter_spec=FilterSpec(protocol="tcp", src_ip="10.10.1.5", dst_ip="10.20.4.9"),
    )
    print(f"path={list(plan.path)}")
    print(f"impact={plan.impact.blast_radius}")
    for row in rows_for_plan(plan):
        print(f"{row.device_id}:{row.role}:{row.strategy}:{row.filter_expression}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
