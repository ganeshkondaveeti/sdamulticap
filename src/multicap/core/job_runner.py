from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from multicap.core.cleanup import (
    CleanupStateManager,
    DeadManTimerInstaller,
    JobState,
)
from multicap.core.planner import CapturePlan, CaptureStrategy
from multicap.core.safety import DeviceHealth, SafetyGate
from multicap.core.synchronizer import ArmedCapture, StatusEvent, StatusSink, Synchronizer
from multicap.drivers.base import CaptureArtifact, CaptureDriver, CaptureRequest, DeviceProfile
from multicap.persistence.audit import AuditLog
from multicap.persistence.journal import SessionJournal

ConfigDiffProvider = Callable[[str], str]
HaInvalidationDetector = Callable[[DeviceProfile], bool]


@dataclass(frozen=True, slots=True)
class JobResult:
    job_id: str
    state: JobState
    artifacts: tuple[CaptureArtifact, ...]
    arming_skew_seconds: float
    status_events: tuple[StatusEvent, ...]
    aborted_reason: str | None = None


@dataclass(slots=True)
class JobRunner:
    journal: SessionJournal
    audit: AuditLog
    synchronizer: Synchronizer = field(default_factory=Synchronizer)
    dead_man: DeadManTimerInstaller = field(default_factory=DeadManTimerInstaller)
    safety: SafetyGate = field(default_factory=SafetyGate)
    config_diff: ConfigDiffProvider = lambda job_id: ""
    ha_invalidated: HaInvalidationDetector = lambda device: False
    clock: Callable[[], float] = time.perf_counter

    def run(
        self,
        plan: CapturePlan,
        drivers: Mapping[str, CaptureDriver],
        health: Mapping[str, DeviceHealth],
        destination: Path,
        *,
        precision_epoch: float | None = None,
        cancel_after: JobState | None = None,
        status_sink: StatusSink | None = None,
    ) -> JobResult:
        cleanup = CleanupStateManager(self.journal, self.audit)
        events: list[StatusEvent] = []
        started_at = self.clock()

        def emit(device_id: str, phase: JobState, message: str = "") -> None:
            event = StatusEvent(
                job_id=plan.job_id,
                device_id=device_id,
                phase=phase,
                elapsed_seconds=self.clock() - started_at,
                health=health.get(device_id),
                message=message,
            )
            events.append(event)
            if status_sink is not None:
                status_sink(event)

        self.safety.enforce(plan, dict(health), self.audit)
        armed: dict[str, ArmedCapture] = {}
        artifacts: list[CaptureArtifact] = []

        for strategy in plan.per_device:
            if strategy.kind == "coverage-gap":
                emit(strategy.device.id, "ARMED", "coverage-gap")
                continue
            driver = drivers[strategy.device.platform]
            request = request_for_strategy(plan.job_id, strategy)
            timer = self.dead_man.build(
                strategy.device.profile(), plan.job_id, request.duration_seconds + 60
            )
            handle = driver.arm(strategy.device.profile(), request)
            self.journal.append(
                job_id=plan.job_id,
                device_id=strategy.device.id,
                action="apply",
                payload={"state": "ARMED", "capture": handle.capture_name},
                compensating_payload={"state": "REVERT", "capture": handle.capture_name},
            )
            self.audit.append(
                job_id=plan.job_id,
                event="dead-man-timer",
                payload={"device_id": timer.device_id, "degraded": timer.degraded},
            )
            armed[strategy.device.id] = ArmedCapture(strategy.device.profile(), driver, handle)
            emit(strategy.device.id, "ARMED")

        cleanup.transition(plan.job_id, "ARMED")
        if cancel_after == "ARMED":
            return self._abort(
                plan.job_id, cleanup, armed, events, artifacts, "cancelled-after-armed"
            )
        invalidated = next(
            (capture for capture in armed.values() if self.ha_invalidated(capture.device)), None
        )
        if invalidated is not None:
            self.audit.append(
                job_id=plan.job_id,
                event="ha-sso-invalidation",
                payload={"device_id": invalidated.device.id},
            )
            return self._abort(plan.job_id, cleanup, armed, events, artifacts, "ha-sso-switchover")

        trigger_report = self.synchronizer.trigger(armed, precision_epoch)
        cleanup.transition(plan.job_id, "ACTIVE", f"skew={trigger_report.skew_seconds:.6f}")
        for result in trigger_report.results:
            emit(result.device_id, "ACTIVE", f"triggered_at={result.triggered_at:.6f}")
        if cancel_after == "ACTIVE":
            return self._abort(
                plan.job_id, cleanup, armed, events, artifacts, "cancelled-after-active"
            )

        for capture in armed.values():
            capture.driver.stop(capture.device, capture.handle)
            emit(capture.device.id, "STOPPED")
        cleanup.transition(plan.job_id, "STOPPED")

        for capture in armed.values():
            artifact = capture.driver.collect(capture.device, capture.handle, destination)
            artifacts.append(artifact)
            emit(capture.device.id, "COLLECTED")
        cleanup.transition(plan.job_id, "COLLECTED")
        cleanup.transition(plan.job_id, "CORRELATED", "placeholder-correlator")

        for capture in armed.values():
            capture.driver.revert(capture.device, capture.handle)
        cleanup.verify(plan.job_id, self.config_diff(plan.job_id))
        cleanup.transition(plan.job_id, "DONE")
        for capture in armed.values():
            emit(capture.device.id, "DONE")
        return JobResult(
            job_id=plan.job_id,
            state=cleanup.state(plan.job_id),
            artifacts=tuple(artifacts),
            arming_skew_seconds=trigger_report.skew_seconds,
            status_events=tuple(events),
        )

    def _abort(
        self,
        job_id: str,
        cleanup: CleanupStateManager,
        armed: Mapping[str, ArmedCapture],
        events: list[StatusEvent],
        artifacts: list[CaptureArtifact],
        reason: str,
    ) -> JobResult:
        cleanup.transition(job_id, "COMPENSATING", reason)
        for capture in armed.values():
            capture.driver.revert(capture.device, capture.handle)
            events.append(
                StatusEvent(job_id, capture.device.id, "COMPENSATING", 0.0, message=reason)
            )
        cleanup.verify(job_id, self.config_diff(job_id))
        cleanup.transition(job_id, "DONE", reason)
        self.audit.append(job_id=job_id, event="job-aborted", payload={"reason": reason})
        return JobResult(
            job_id=job_id,
            state=cleanup.state(job_id),
            artifacts=tuple(artifacts),
            arming_skew_seconds=0.0,
            status_events=tuple(events),
            aborted_reason=reason,
        )


def request_for_strategy(job_id: str, strategy: CaptureStrategy) -> CaptureRequest:
    interface_type: Literal["physical", "svi", "subinterface", "control-plane"] = (
        "control-plane" if strategy.kind == "ethanalyzer" else "physical"
    )
    return CaptureRequest(
        job_id=job_id,
        capture_name=f"MCAP_{strategy.device.id.replace('-', '_')}",
        interface="mgmt" if strategy.kind == "ethanalyzer" else "Gi1/0/1",
        interface_type=interface_type,
        duration_seconds=60,
        capture_filter=strategy.capture_filter,
        output_path=f"bootflash:{job_id}-{strategy.device.id}.pcap",
    )


def assert_skew_within(report_seconds: float, max_seconds: float = 0.5) -> None:
    if report_seconds > max_seconds:
        raise ValueError(f"arming skew {report_seconds:.6f}s exceeds {max_seconds:.6f}s")
