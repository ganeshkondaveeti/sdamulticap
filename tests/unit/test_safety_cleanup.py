from __future__ import annotations

from pathlib import Path

import pytest

from multicap.core.cleanup import CleanupStateManager, ConfigDiffAssertion, DeadManTimerInstaller
from multicap.core.filters import FilterSpec
from multicap.core.intent import IntentCompiler
from multicap.core.planner import PlanGenerator
from multicap.core.safety import ConsentRecord, DeviceHealth, ExecutionGate, SafetyGate
from multicap.core.topology import Device, Link, TopologyGraph
from multicap.drivers.base import DeviceProfile
from multicap.drivers.common import RecordingTransport
from multicap.persistence.audit import AuditLog
from multicap.persistence.journal import SessionJournal


def planned_graph() -> TopologyGraph:
    graph = TopologyGraph()
    graph.add_device(Device("core-a", "core-a", "iosxe-switch", "ios-xe", "17.9", "192.0.2.1"))
    graph.add_device(Device("dist-b", "dist-b", "nxos", "nx-os", "10.2", "192.0.2.2"))
    graph.add_link(Link("core-a", "Gi1/0/1", "dist-b", "Eth1/1", "cdp"))
    return graph


def planned_job() -> object:
    intent = IntentCompiler().compile_path(
        job_id="job-safe",
        src_device_id="core-a",
        dst_device_id="dist-b",
        duration_seconds=60,
        filter_spec=FilterSpec(protocol="tcp", dst_port=443),
    )
    return PlanGenerator().generate(planned_graph(), intent)


@pytest.mark.unit
def test_safety_gate_passes_healthy_filtered_plan(tmp_path: Path) -> None:
    audit = AuditLog(tmp_path / "audit.sqlite3")
    report = SafetyGate().enforce(
        planned_job(),
        {
            "core-a": DeviceHealth("core-a", 20.0, 30.0, 1024, 0),
            "dist-b": DeviceHealth("dist-b", 25.0, 35.0, 1024, 0, "active"),
        },
        audit,
    )

    assert report.allowed
    assert audit.records()[-1].event == "safety-gate"


@pytest.mark.unit
def test_safety_gate_refuses_bad_health_and_records_reason(tmp_path: Path) -> None:
    audit = AuditLog(tmp_path / "audit.sqlite3")

    with pytest.raises(ValueError, match="safety gate refused"):
        SafetyGate().enforce(
            planned_job(),
            {
                "core-a": DeviceHealth("core-a", 95.0, 30.0, 1024, 0),
                "dist-b": DeviceHealth("dist-b", 25.0, 35.0, 1024, 0, "standby"),
            },
            audit,
        )

    payload = audit.records()[-1].payload
    assert payload["allowed"] is False


@pytest.mark.unit
def test_execution_gate_requires_change_ticket_and_full_payload_consent(tmp_path: Path) -> None:
    audit = AuditLog(tmp_path / "audit.sqlite3")

    with pytest.raises(ValueError, match="change-ticket"):
        ExecutionGate(change_ticket="").validate("job-1", audit)

    with pytest.raises(ValueError, match="full-payload"):
        ExecutionGate(change_ticket="CHG123", full_payload_requested=True).validate("job-2", audit)

    ExecutionGate(
        change_ticket="CHG123",
        full_payload_requested=True,
        full_payload_consent=ConsentRecord("job-3", "full-payload", "tac-user", True),
    ).validate("job-3", audit)

    assert [record.event for record in audit.records()][-2:] == ["change-ticket", "consent"]


@pytest.mark.unit
def test_cleanup_state_machine_blocks_invalid_and_requires_clean_diff(tmp_path: Path) -> None:
    manager = CleanupStateManager(
        SessionJournal(tmp_path / "journal.sqlite3"),
        AuditLog(tmp_path / "audit.sqlite3"),
    )

    with pytest.raises(ValueError, match="invalid cleanup transition"):
        manager.transition("job-1", "DONE")

    manager.transition("job-1", "ARMED")
    manager.transition("job-1", "ACTIVE")
    manager.transition("job-1", "STOPPED")
    manager.transition("job-1", "COLLECTED")
    manager.transition("job-1", "CORRELATED")
    with pytest.raises(ValueError, match="non-empty config diff"):
        manager.verify("job-1", "+ monitor capture left behind")

    assert manager.verify("job-1", "").state == "VERIFIED"
    assert manager.transition("job-1", "DONE").state == "DONE"


@pytest.mark.unit
def test_dead_man_timer_generates_iosxe_and_nxos_cleanup_commands() -> None:
    transport = RecordingTransport()
    installer = DeadManTimerInstaller(transport)
    iosxe = installer.install(
        DeviceProfile("cat", "cat", "iosxe-switch", "ios-xe", "17.9"), "job1", 300
    )
    nxos = installer.install(DeviceProfile("nx", "nx", "nxos", "nx-os", "10.2"), "job1", 300)
    degraded = installer.build(DeviceProfile("xr", "xr", "iosxr", "ios-xr", "7.8"), "job1", 300)

    assert iosxe.commands[0] == "event manager applet MULTICAP_job1"
    assert nxos.commands[0] == "scheduler job name multicap_job1"
    assert degraded.degraded
    assert len(transport.commands) == len(iosxe.commands) + len(nxos.commands)


@pytest.mark.unit
def test_config_diff_assertion_blocks_verified_on_residual_config() -> None:
    with pytest.raises(ValueError, match="VERIFIED blocked"):
        ConfigDiffAssertion().assert_clean("+ scheduler job name multicap_job1")
