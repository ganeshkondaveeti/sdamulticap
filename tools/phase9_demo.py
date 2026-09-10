from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from multicap.core.correlator_facade import CorrelationSummary
from multicap.core.filters import FilterSpec
from multicap.core.intent import IntentCompiler
from multicap.core.planner import CapturePlan, PlanGenerator
from multicap.core.reporter import EvidenceReporter, LadderDiagramBuilder, PrecisionStatus
from multicap.core.timing import WallClockHarness, sc9_scenarios
from multicap.core.topology import Device, Link, TopologyGraph
from multicap.persistence.audit import AuditLog


def demo_plan() -> CapturePlan:
    topology = TopologyGraph()
    topology.add_device(Device("cat-1", "cat-1", "iosxe-switch", "ios-xe", "17.9", "192.0.2.1"))
    topology.add_device(Device("nx-1", "nx-1", "nxos", "nx-os", "10.2", "192.0.2.2"))
    topology.add_device(Device("cat-2", "cat-2", "iosxe-switch", "ios-xe", "17.9", "192.0.2.3"))
    topology.add_link(Link("cat-1", "Gi1/0/1", "nx-1", "Eth1/1", "cdp"))
    topology.add_link(Link("nx-1", "Eth1/2", "cat-2", "Gi1/0/1", "cdp"))
    intent = IntentCompiler().compile_path(
        job_id="phase9-demo",
        src_device_id="cat-1",
        dst_device_id="cat-2",
        duration_seconds=60,
        filter_spec=FilterSpec(protocol="tcp", dst_port=443),
    )
    return PlanGenerator().generate(topology, intent)


def main() -> int:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        plan = demo_plan()
        audit = AuditLog(root / "audit.sqlite3")
        audit.append(job_id="phase9-demo", event="consent", payload={"type": "full-payload"})
        pcapng = root / "merged.pcapng"
        pcapng.write_text("packet\n", encoding="utf-8")
        correlation = CorrelationSummary(pcapng, packet_count=1, dropped=1, truncated=0)
        hops = LadderDiagramBuilder().build(plan, tuple(), correlation)
        bundle = EvidenceReporter().build_bundle(
            job_id="phase9-demo",
            plan=plan,
            hops=hops,
            correlation=correlation,
            audit=audit,
            precision=PrecisionStatus(False, ("nx-1",), 500),
            output_dir=root / "evidence",
        )
        harness = WallClockHarness()
        timing = [harness.run(scenario, 0.0, 10.0) for scenario in sc9_scenarios()]
        harness.assert_sc9(timing)
        print(f"verdict={bundle.verdict.severity}:{bundle.verdict.location}")
        print(f"html={bundle.html_path.name}")
        print(f"pdf={bundle.pdf_path.name}")
        print(f"timing={[result.passed for result in timing]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
