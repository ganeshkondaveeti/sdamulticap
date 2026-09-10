from __future__ import annotations

import pytest

from multicap.core.filters import FilterBuilder, FilterSpec
from multicap.core.intent import IntentCompiler
from multicap.core.planner import PlanGenerator, WiredPathSolver
from multicap.core.topology import Device, Link, TopologyGraph
from multicap.drivers.base import DeviceProfile


def phase4_graph() -> TopologyGraph:
    graph = TopologyGraph()
    graph.add_device(Device("core-a", "core-a", "iosxe-switch", "ios-xe", "17.9", "192.0.2.1"))
    graph.add_device(Device("dist-b", "dist-b", "nxos", "nx-os", "10.2", "192.0.2.2"))
    graph.add_device(Device("edge-c", "edge-c", "iosxe-switch", "ios-xe", "17.12", "192.0.2.3"))
    graph.add_link(Link("core-a", "Gi1/0/1", "dist-b", "Eth1/1", "cdp"))
    graph.add_link(Link("dist-b", "Eth1/2", "edge-c", "Gi1/0/2", "cdp"))
    return graph


@pytest.mark.unit
def test_intent_compiler_rejects_non_positive_duration() -> None:
    with pytest.raises(ValueError, match="duration_seconds"):
        IntentCompiler().compile_path(
            job_id="job-1",
            src_device_id="core-a",
            dst_device_id="edge-c",
            duration_seconds=0,
        )


@pytest.mark.unit
def test_filter_builder_emits_platform_native_filters() -> None:
    spec = FilterSpec(protocol="tcp", src_ip="10.10.1.5", dst_ip="10.20.4.9", dst_port=443)
    builder = FilterBuilder()

    iosxe = builder.build(spec, DeviceProfile("cat", "cat", "iosxe-switch", "ios-xe", "17.9"))
    nxos = builder.build(spec, DeviceProfile("nx", "nx", "nxos", "nx-os", "10.2"))

    assert iosxe.expression == "tcp src host 10.10.1.5 dst host 10.20.4.9 dst port 443"
    assert nxos.expression == "tcp and src host 10.10.1.5 and dst host 10.20.4.9 and dst port 443"


@pytest.mark.unit
def test_filter_builder_blocks_empty_nxos_filter() -> None:
    with pytest.raises(ValueError, match="requires a non-empty filter"):
        FilterBuilder().build(FilterSpec(), DeviceProfile("nx", "nx", "nxos", "nx-os", "10.2"))


@pytest.mark.unit
def test_wired_path_solver_finds_shortest_path() -> None:
    path = WiredPathSolver().solve(phase4_graph(), "core-a", "edge-c")

    assert [device.id for device in path] == ["core-a", "dist-b", "edge-c"]


@pytest.mark.unit
def test_plan_generator_ranks_strategies_and_estimates_impact() -> None:
    intent = IntentCompiler().compile_path(
        job_id="job-path",
        src_device_id="core-a",
        dst_device_id="edge-c",
        duration_seconds=120,
        filter_spec=FilterSpec(protocol="tcp", src_ip="10.10.1.5", dst_ip="10.20.4.9"),
    )

    plan = PlanGenerator().generate(phase4_graph(), intent)

    assert plan.path == ("core-a", "dist-b", "edge-c")
    assert [(entry.device.id, entry.role, entry.kind) for entry in plan.per_device] == [
        ("core-a", "source", "epc"),
        ("dist-b", "midpoint", "ethanalyzer"),
        ("edge-c", "destination", "epc"),
    ]
    assert plan.coverage_gaps() == []
    assert plan.impact.blast_radius == "low"


@pytest.mark.unit
def test_plan_generator_emits_coverage_gap_for_unknown_release() -> None:
    graph = phase4_graph()
    graph.add_device(Device("legacy", "legacy", "ios-classic", "ios", "12.2", "192.0.2.4"))
    graph.add_link(Link("edge-c", "Gi1/0/3", "legacy", "Fa0/1", "cdp"))
    intent = IntentCompiler().compile_path(
        job_id="job-gap",
        src_device_id="core-a",
        dst_device_id="legacy",
        duration_seconds=120,
        filter_spec=FilterSpec(protocol="udp", dst_port=53),
    )

    plan = PlanGenerator().generate(graph, intent)

    assert plan.coverage_gaps()[0].device.id == "legacy"
    assert plan.coverage_gaps()[0].reason == "unknown-release"
    assert plan.impact.blast_radius == "medium"
