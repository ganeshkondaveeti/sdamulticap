from __future__ import annotations

import json
from pathlib import Path

import pytest

from multicap.app.viewmodels import (
    coverage_gap_banner,
    evidence_bundle_row,
    ntp_degraded_banner,
    retention_settings_row,
    timeline_rows,
    timing_rows,
)
from multicap.core.correlator_facade import CorrelationSummary
from multicap.core.filters import FilterSpec
from multicap.core.intent import IntentCompiler
from multicap.core.planner import PlanGenerator
from multicap.core.reporter import (
    EvidenceReporter,
    FaultVerdictEngine,
    LadderDiagramBuilder,
    PrecisionStatus,
)
from multicap.core.timing import WallClockHarness, sc9_scenarios
from multicap.core.topology import Device, Link, TopologyGraph
from multicap.persistence.audit import AuditLog
from multicap.persistence.settings import RetentionPruner, RetentionSettings
from tests.unit.test_synchronizer_job_runner import healthy
from tests.unit.test_synchronizer_job_runner import plan as planned_path


def phase9_plan() -> object:
    topology = TopologyGraph()
    topology.add_device(Device("cat-1", "cat-1", "iosxe-switch", "ios-xe", "17.9", "192.0.2.1"))
    topology.add_device(Device("nx-1", "nx-1", "nxos", "nx-os", "10.2", "192.0.2.2"))
    topology.add_link(Link("cat-1", "Gi1/0/1", "nx-1", "Eth1/1", "cdp"))
    intent = IntentCompiler().compile_path(
        job_id="phase9-job",
        src_device_id="cat-1",
        dst_device_id="nx-1",
        duration_seconds=60,
        filter_spec=FilterSpec(protocol="tcp", dst_port=443),
    )
    return PlanGenerator().generate(topology, intent)


def coverage_gap_plan() -> object:
    topology = TopologyGraph()
    topology.add_device(Device("cat-1", "cat-1", "iosxe-switch", "ios-xe", "17.9", "192.0.2.1"))
    topology.add_device(Device("classic-1", "classic-1", "ios-classic", "ios", "15.2", "192.0.2.4"))
    topology.add_link(Link("cat-1", "Gi1/0/1", "classic-1", "Gi0/1", "cdp"))
    intent = IntentCompiler().compile_path(
        job_id="coverage-gap-job",
        src_device_id="cat-1",
        dst_device_id="classic-1",
        duration_seconds=60,
        filter_spec=FilterSpec(protocol="tcp", dst_port=443),
    )
    return PlanGenerator().generate(topology, intent)


@pytest.mark.unit
def test_reporter_builds_ladder_bundle_and_fault_verdict(tmp_path: Path) -> None:
    plan_obj = planned_path()
    audit = AuditLog(tmp_path / "audit.sqlite3")
    audit.append(job_id="phase9-job", event="consent", payload={"type": "full-payload"})
    correlation = CorrelationSummary(tmp_path / "merged.pcapng", 42, 2, 1)
    correlation.output_path.write_text("packet\n", encoding="utf-8")
    events = tuple()
    hops = LadderDiagramBuilder().build(plan_obj, events, correlation)

    bundle = EvidenceReporter().build_bundle(
        job_id="phase9-job",
        plan=plan_obj,
        hops=hops,
        correlation=correlation,
        audit=audit,
        precision=PrecisionStatus(False, ("nx-1",), 500),
        output_dir=tmp_path / "evidence",
    )

    assert bundle.html_path.exists()
    assert bundle.pdf_path.read_bytes().startswith(b"%PDF-1.4")
    assert bundle.verdict.severity == "packet-loss"
    assert "NTP degraded" in bundle.html_path.read_text(encoding="utf-8")
    assert json.loads(bundle.audit_path.read_text(encoding="utf-8"))[0]["event"] == "consent"
    assert evidence_bundle_row(bundle).verdict == "packet-loss:cat-2"


@pytest.mark.unit
def test_phase9_viewmodels_render_counters_gaps_ntp_and_retention(tmp_path: Path) -> None:
    plan_obj = phase9_plan()
    correlation = CorrelationSummary(tmp_path / "merged.pcapng", 1, 0, 3)
    rows = timeline_rows(LadderDiagramBuilder().build(plan_obj, tuple(), correlation))
    precision = PrecisionStatus(False, ("cat-1",), 500)
    pruner = RetentionPruner(tmp_path / "pcaps", RetentionSettings(days=7, max_bytes=1024))

    assert rows[-1].counters == "drops=0 truncated=3"
    assert coverage_gap_banner(["classic-1"]) == "Coverage gaps: classic-1"
    assert "cat-1" in ntp_degraded_banner(precision)
    assert retention_settings_row(pruner.usage()).days == 7


@pytest.mark.unit
def test_fault_verdict_engine_prefers_coverage_gap() -> None:
    plan_obj = coverage_gap_plan()
    hops = LadderDiagramBuilder().build(
        plan_obj, tuple(), CorrelationSummary(Path("out.pcapng"), 0, 0, 0)
    )

    assert FaultVerdictEngine().evaluate(hops, plan_obj).severity == "coverage-gap"


@pytest.mark.unit
def test_sc9_wall_clock_harness_asserts_wired_and_wireless_thresholds() -> None:
    wired, wireless = sc9_scenarios()
    harness = WallClockHarness()
    results = [harness.run(wired, 0.0, 14 * 60), harness.run(wireless, 0.0, 19 * 60)]

    harness.assert_sc9(results)
    assert "pass" in timing_rows(results)[0]
    with pytest.raises(ValueError, match="SC-9"):
        harness.assert_sc9([harness.run(wired, 0.0, 16 * 60)])


@pytest.mark.unit
def test_phase9_retains_existing_job_health_fixture() -> None:
    plan_obj = planned_path()
    assert set(healthy(plan_obj)) == {strategy.device.id for strategy in plan_obj.per_device}
