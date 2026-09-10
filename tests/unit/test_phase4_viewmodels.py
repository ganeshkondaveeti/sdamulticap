from __future__ import annotations

import pytest

from multicap.app.viewmodels import FilterBuilderViewModel, PathIntentViewModel, rows_for_plan
from multicap.core.filters import FilterSpec
from multicap.core.topology import Device, Link, TopologyGraph


def view_graph() -> TopologyGraph:
    graph = TopologyGraph()
    graph.add_device(Device("core-a", "core-a", "iosxe-switch", "ios-xe", "17.9", "192.0.2.1"))
    graph.add_device(Device("dist-b", "dist-b", "nxos", "nx-os", "10.2", "192.0.2.2"))
    graph.add_link(Link("core-a", "Gi1/0/1", "dist-b", "Eth1/1", "cdp"))
    return graph


@pytest.mark.unit
def test_path_intent_viewmodel_compiles_plan_review_rows() -> None:
    plan = PathIntentViewModel(view_graph()).compile_plan(
        job_id="job-vm",
        src_device_id="core-a",
        dst_device_id="dist-b",
        duration_seconds=60,
        filter_spec=FilterSpec(protocol="tcp", dst_port=443),
    )

    rows = rows_for_plan(plan)

    assert [(row.device_id, row.role, row.strategy) for row in rows] == [
        ("core-a", "source", "epc"),
        ("dist-b", "destination", "ethanalyzer"),
    ]
    assert rows[1].filter_expression == "tcp and dst port 443"


@pytest.mark.unit
def test_filter_builder_viewmodel_blocks_empty_nxos_preview() -> None:
    with pytest.raises(ValueError, match="requires a non-empty filter"):
        FilterBuilderViewModel().preview(FilterSpec(), "nxos")
