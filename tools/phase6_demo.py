from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from multicap.core.filters import FilterSpec
from multicap.core.intent import IntentCompiler
from multicap.core.job_runner import JobRunner
from multicap.core.planner import PlanGenerator
from multicap.core.safety import DeviceHealth
from multicap.core.topology import Device, Link, TopologyGraph
from multicap.drivers.common import RecordingTransport
from multicap.drivers.iosxe_switch import IosXeSwitchDriver
from multicap.drivers.nxos import NxosDriver
from multicap.persistence.audit import AuditLog
from multicap.persistence.journal import SessionJournal


def demo_plan() -> object:
    topology = TopologyGraph()
    topology.add_device(Device("core-a", "core-a", "iosxe-switch", "ios-xe", "17.9", "192.0.2.1"))
    topology.add_device(Device("dist-b", "dist-b", "nxos", "nx-os", "10.2", "192.0.2.2"))
    topology.add_link(Link("core-a", "Gi1/0/1", "dist-b", "Eth1/1", "cdp"))
    intent = IntentCompiler().compile_path(
        job_id="phase6-demo",
        src_device_id="core-a",
        dst_device_id="dist-b",
        duration_seconds=60,
        filter_spec=FilterSpec(protocol="tcp", dst_port=443),
    )
    return PlanGenerator().generate(topology, intent)


def main() -> int:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        plan = demo_plan()
        result = JobRunner(
            SessionJournal(root / "journal.sqlite3"), AuditLog(root / "audit.sqlite3")
        ).run(
            plan,
            {
                "iosxe-switch": IosXeSwitchDriver(RecordingTransport()),
                "nxos": NxosDriver(RecordingTransport()),
            },
            {
                strategy.device.id: DeviceHealth(strategy.device.id, 10.0, 20.0, 1024, 0)
                for strategy in plan.per_device
            },
            root / "artifacts",
            precision_epoch=100.0,
        )
        print(f"state={result.state}")
        print(f"artifacts={len(result.artifacts)}")
        print(f"skew_ms={result.arming_skew_seconds * 1000:.1f}")
        print(f"events={len(result.status_events)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
