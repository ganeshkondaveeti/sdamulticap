from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from multicap.drivers.base import CommandTransport, DeviceProfile
from multicap.persistence.audit import AuditLog
from multicap.persistence.journal import JournalEntry, SessionJournal

JobState = Literal[
    "IDLE",
    "ARMED",
    "ACTIVE",
    "STOPPED",
    "COLLECTED",
    "CORRELATED",
    "COMPENSATING",
    "VERIFIED",
    "DONE",
    "FAILED",
]

TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    "IDLE": frozenset({"ARMED", "FAILED"}),
    "ARMED": frozenset({"ACTIVE", "COMPENSATING", "FAILED"}),
    "ACTIVE": frozenset({"STOPPED", "COMPENSATING", "FAILED"}),
    "STOPPED": frozenset({"COLLECTED", "COMPENSATING", "FAILED"}),
    "COLLECTED": frozenset({"CORRELATED", "COMPENSATING", "FAILED"}),
    "CORRELATED": frozenset({"COMPENSATING", "VERIFIED", "FAILED"}),
    "COMPENSATING": frozenset({"VERIFIED", "FAILED"}),
    "VERIFIED": frozenset({"DONE"}),
    "DONE": frozenset(),
    "FAILED": frozenset({"COMPENSATING"}),
}


@dataclass(frozen=True, slots=True)
class JobSnapshot:
    job_id: str
    state: JobState


class CleanupStateManager:
    def __init__(self, journal: SessionJournal, audit: AuditLog) -> None:
        self._journal = journal
        self._audit = audit
        self._states: dict[str, JobState] = {}

    def state(self, job_id: str) -> JobState:
        return self._states.get(job_id, "IDLE")

    def transition(self, job_id: str, target: JobState, detail: str = "") -> JobSnapshot:
        current = self.state(job_id)
        if target not in TRANSITIONS[current]:
            raise ValueError(f"invalid cleanup transition {current} -> {target}")
        self._states[job_id] = target
        self._journal.append(
            job_id=job_id,
            device_id="orchestrator",
            action="apply",
            payload={"state": target, "detail": detail},
        )
        self._audit.append(
            job_id=job_id,
            event="state-transition",
            payload={"from": current, "to": target, "detail": detail},
        )
        return JobSnapshot(job_id, target)

    def verify(self, job_id: str, config_diff: str) -> JobSnapshot:
        ConfigDiffAssertion().assert_clean(config_diff)
        current = self.state(job_id)
        if current not in {"CORRELATED", "COMPENSATING"}:
            raise ValueError(f"VERIFIED requires CORRELATED or COMPENSATING, got {current}")
        return self.transition(job_id, "VERIFIED", "clean-config-diff")

    def recover(self, job_id: str) -> list[JournalEntry]:
        self._states[job_id] = "COMPENSATING"
        self._audit.append(job_id=job_id, event="recovery-started", payload={})
        replayed = self._journal.replay_compensations(job_id)
        self._audit.append(
            job_id=job_id,
            event="recovery-completed",
            payload={"replayed": len(replayed)},
        )
        return replayed


class ConfigDiffAssertion:
    def assert_clean(self, diff: str) -> None:
        if diff.strip():
            raise ValueError("VERIFIED blocked by non-empty config diff")


@dataclass(frozen=True, slots=True)
class DeadManTimer:
    device_id: str
    commands: tuple[str, ...]
    revert_commands: tuple[str, ...]
    degraded: bool = False


class DeadManTimerInstaller:
    def __init__(self, transport: CommandTransport | None = None) -> None:
        self._transport = transport

    def build(self, device: DeviceProfile, job_id: str, timeout_seconds: int) -> DeadManTimer:
        if device.os_family == "ios-xe":
            applet = f"MULTICAP_{job_id}"
            return DeadManTimer(
                device_id=device.id,
                commands=(
                    f"event manager applet {applet}",
                    f"event timer countdown time {timeout_seconds}",
                    'action 1.0 cli command "enable"',
                    'action 2.0 cli command "monitor capture stop all"',
                    f'action 3.0 cli command "no event manager applet {applet}"',
                ),
                revert_commands=(f"no event manager applet {applet}",),
            )
        if device.os_family == "nx-os":
            job = f"multicap_{job_id}"
            return DeadManTimer(
                device_id=device.id,
                commands=(
                    f"scheduler job name {job}",
                    "delete bootflash:multicap.pcap no-prompt",
                    f"scheduler schedule name {job}",
                    f"time start +{timeout_seconds}",
                    f"job name {job}",
                ),
                revert_commands=(
                    f"no scheduler schedule name {job}",
                    f"no scheduler job name {job}",
                ),
            )
        return DeadManTimer(device.id, (), (), degraded=True)

    def install(self, device: DeviceProfile, job_id: str, timeout_seconds: int) -> DeadManTimer:
        timer = self.build(device, job_id, timeout_seconds)
        if self._transport is not None:
            for command in timer.commands:
                self._transport.execute(device, command)
        return timer
