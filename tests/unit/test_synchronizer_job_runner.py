from __future__ import annotations

from pathlib import Path

import pytest

from multicap.core.filters import FilterSpec
from multicap.core.intent import IntentCompiler
from multicap.core.job_runner import JobRunner, assert_skew_within
from multicap.core.planner import PlanGenerator
from multicap.core.safety import DeviceHealth
from multicap.core.synchronizer import ArmedCapture, Synchronizer
from multicap.core.topology import Device, Link, TopologyGraph
from multicap.drivers.base import CaptureRequest, DeviceProfile
from multicap.drivers.common import RecordingTransport
from multicap.drivers.iosxe_switch import IosXeSwitchDriver
from multicap.drivers.nxos import NxosDriver
from multicap.persistence.audit import AuditLog
from multicap.persistence.journal import SessionJournal


def graph(count: int = 3) -> TopologyGraph:
    topology = TopologyGraph()
    previous: str | None = None
    for index in range(count):
        if index % 2 == 0:
            device = Device(
                f"cat-{index}",
                f"cat-{index}",
                "iosxe-switch",
                "ios-xe",
                "17.9",
                f"192.0.2.{index + 1}",
            )
        else:
            device = Device(
                f"nx-{index}", f"nx-{index}", "nxos", "nx-os", "10.2", f"192.0.2.{index + 1}"
            )
        topology.add_device(device)
        if previous is not None:
            topology.add_link(Link(previous, "Gi1/0/1", device.id, "Eth1/1", "cdp"))
        previous = device.id
    return topology


def plan(count: int = 3) -> object:
    topology = graph(count)
    ids = list(topology.devices)
    intent = IntentCompiler().compile_path(
        job_id="job-run",
        src_device_id=ids[0],
        dst_device_id=ids[-1],
        duration_seconds=60,
        filter_spec=FilterSpec(protocol="tcp", dst_port=443),
    )
    return PlanGenerator().generate(topology, intent)


def drivers() -> dict[str, object]:
    return {
        "iosxe-switch": IosXeSwitchDriver(RecordingTransport()),
        "nxos": NxosDriver(RecordingTransport()),
    }


def healthy(plan_obj: object) -> dict[str, DeviceHealth]:
    return {
        strategy.device.id: DeviceHealth(strategy.device.id, 10.0, 20.0, 1024, 0)
        for strategy in plan_obj.per_device
    }


@pytest.mark.unit
def test_synchronizer_triggers_20_devices_under_500ms() -> None:
    driver = IosXeSwitchDriver(RecordingTransport())
    armed = {
        f"cat-{index}": ArmedCapture(
            DeviceProfile(f"cat-{index}", f"cat-{index}", "iosxe-switch", "ios-xe", "17.9"),
            driver,
            driver.arm(
                DeviceProfile(f"cat-{index}", f"cat-{index}", "iosxe-switch", "ios-xe", "17.9"),
                CaptureRequest("job-20", f"MCAP_{index}", "Gi1/0/1", "physical", 60),
            ),
        )
        for index in range(20)
    }

    report = Synchronizer(max_workers=20).trigger(armed, precision_epoch=123.0)

    assert len(report.results) == 20
    assert_skew_within(report.skew_seconds, 0.5)


@pytest.mark.unit
def test_job_runner_completes_wired_lifecycle(tmp_path: Path) -> None:
    plan_obj = plan()
    result = JobRunner(
        SessionJournal(tmp_path / "journal.sqlite3"), AuditLog(tmp_path / "audit.sqlite3")
    ).run(
        plan_obj,
        drivers(),
        healthy(plan_obj),
        tmp_path / "artifacts",
        precision_epoch=456.0,
    )

    assert result.state == "DONE"
    assert result.arming_skew_seconds == 0.0
    assert len(result.artifacts) == 3
    assert {event.phase for event in result.status_events} >= {
        "ARMED",
        "ACTIVE",
        "COLLECTED",
        "DONE",
    }


@pytest.mark.unit
def test_job_runner_cancel_after_armed_reverts_and_reaches_done(tmp_path: Path) -> None:
    plan_obj = plan()
    result = JobRunner(
        SessionJournal(tmp_path / "journal.sqlite3"), AuditLog(tmp_path / "audit.sqlite3")
    ).run(
        plan_obj,
        drivers(),
        healthy(plan_obj),
        tmp_path / "artifacts",
        cancel_after="ARMED",
    )

    assert result.state == "DONE"
    assert result.aborted_reason == "cancelled-after-armed"
    assert any(event.phase == "COMPENSATING" for event in result.status_events)


@pytest.mark.unit
def test_job_runner_ha_invalidation_aborts_before_trigger(tmp_path: Path) -> None:
    plan_obj = plan()
    audit = AuditLog(tmp_path / "audit.sqlite3")
    result = JobRunner(
        SessionJournal(tmp_path / "journal.sqlite3"),
        audit,
        ha_invalidated=lambda device: device.id == "nx-1",
    ).run(plan_obj, drivers(), healthy(plan_obj), tmp_path / "artifacts")

    assert result.state == "DONE"
    assert result.aborted_reason == "ha-sso-switchover"
    assert "ha-sso-invalidation" in [record.event for record in audit.records()]
