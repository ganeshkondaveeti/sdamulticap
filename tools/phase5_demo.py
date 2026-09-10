from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from multicap.core.cleanup import CleanupStateManager
from multicap.core.filters import FilterSpec
from multicap.core.intent import IntentCompiler
from multicap.core.planner import PlanGenerator
from multicap.core.safety import ConsentRecord, DeviceHealth, ExecutionGate, SafetyGate
from multicap.core.topology import Device, Link, TopologyGraph
from multicap.persistence.audit import AuditLog
from multicap.persistence.journal import SessionJournal


def graph() -> TopologyGraph:
    topology = TopologyGraph()
    topology.add_device(Device("core-a", "core-a", "iosxe-switch", "ios-xe", "17.9", "192.0.2.1"))
    topology.add_device(Device("dist-b", "dist-b", "nxos", "nx-os", "10.2", "192.0.2.2"))
    topology.add_link(Link("core-a", "Gi1/0/1", "dist-b", "Eth1/1", "cdp"))
    return topology


def main() -> int:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        audit = AuditLog(root / "audit.sqlite3")
        journal = SessionJournal(root / "journal.sqlite3")
        intent = IntentCompiler().compile_path(
            job_id="phase5-demo",
            src_device_id="core-a",
            dst_device_id="dist-b",
            duration_seconds=60,
            filter_spec=FilterSpec(protocol="tcp", dst_port=443),
        )
        plan = PlanGenerator().generate(graph(), intent)
        report = SafetyGate().enforce(
            plan,
            {
                "core-a": DeviceHealth("core-a", 20.0, 30.0, 1024, 0),
                "dist-b": DeviceHealth("dist-b", 25.0, 35.0, 1024, 0),
            },
            audit,
        )
        ExecutionGate(
            "CHG123",
            full_payload_requested=True,
            full_payload_consent=ConsentRecord("phase5-demo", "full-payload", "demo-user", True),
        ).validate("phase5-demo", audit)
        manager = CleanupStateManager(journal, audit)
        for state in ["ARMED", "ACTIVE", "STOPPED", "COLLECTED", "CORRELATED"]:
            manager.transition("phase5-demo", state)
        manager.verify("phase5-demo", "")
        manager.transition("phase5-demo", "DONE")
        print(f"safety_allowed={report.allowed}")
        print(f"final_state={manager.state('phase5-demo')}")
        print(f"audit_ok={audit.verify()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
