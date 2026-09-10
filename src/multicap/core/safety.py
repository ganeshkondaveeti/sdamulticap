from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from multicap.core.planner import CapturePlan, CaptureStrategy
from multicap.persistence.audit import AuditLog

HaState = Literal["standalone", "active", "standby", "unknown"]
SafetyStatus = Literal["pass", "fail"]


@dataclass(frozen=True, slots=True)
class DeviceHealth:
    device_id: str
    cpu_percent: float
    memory_percent: float
    flash_free_mb: int
    span_sessions: int
    ha_state: HaState = "standalone"


@dataclass(frozen=True, slots=True)
class SafetyCheck:
    name: str
    device_id: str
    status: SafetyStatus
    detail: str


@dataclass(frozen=True, slots=True)
class SafetyGateReport:
    job_id: str
    checks: tuple[SafetyCheck, ...]

    @property
    def allowed(self) -> bool:
        return all(check.status == "pass" for check in self.checks)

    def failures(self) -> list[SafetyCheck]:
        return [check for check in self.checks if check.status == "fail"]


@dataclass(frozen=True, slots=True)
class SafetyThresholds:
    max_cpu_percent: float = 80.0
    max_memory_percent: float = 85.0
    min_flash_free_mb: int = 256
    max_span_sessions: int = 2


class SafetyGate:
    def __init__(self, thresholds: SafetyThresholds | None = None) -> None:
        self._thresholds = thresholds or SafetyThresholds()

    def evaluate(self, plan: CapturePlan, health: dict[str, DeviceHealth]) -> SafetyGateReport:
        checks: list[SafetyCheck] = []
        for strategy in plan.per_device:
            device_health = health.get(strategy.device.id)
            if device_health is None:
                checks.append(
                    SafetyCheck(
                        "health-present",
                        strategy.device.id,
                        "fail",
                        "missing health telemetry",
                    )
                )
                continue
            checks.extend(self._checks_for(strategy, device_health))
        return SafetyGateReport(plan.job_id, tuple(checks))

    def enforce(
        self,
        plan: CapturePlan,
        health: dict[str, DeviceHealth],
        audit: AuditLog | None = None,
    ) -> SafetyGateReport:
        report = self.evaluate(plan, health)
        if audit is not None:
            audit.append(
                job_id=plan.job_id,
                event="safety-gate",
                payload={
                    "allowed": report.allowed,
                    "failures": [check.detail for check in report.failures()],
                },
            )
        if not report.allowed:
            reasons = "; ".join(check.detail for check in report.failures())
            raise ValueError(f"safety gate refused plan: {reasons}")
        return report

    def _checks_for(self, strategy: CaptureStrategy, health: DeviceHealth) -> list[SafetyCheck]:
        checks = [
            self._check(
                "cpu-headroom",
                health.device_id,
                health.cpu_percent <= self._thresholds.max_cpu_percent,
                f"cpu={health.cpu_percent:.1f}% max={self._thresholds.max_cpu_percent:.1f}%",
            ),
            self._check(
                "memory-headroom",
                health.device_id,
                health.memory_percent <= self._thresholds.max_memory_percent,
                f"memory={health.memory_percent:.1f}% max={self._thresholds.max_memory_percent:.1f}%",
            ),
            self._check(
                "flash-headroom",
                health.device_id,
                health.flash_free_mb >= self._thresholds.min_flash_free_mb,
                f"flash_free={health.flash_free_mb}MB min={self._thresholds.min_flash_free_mb}MB",
            ),
            self._check(
                "ha-active",
                health.device_id,
                health.ha_state in {"standalone", "active"},
                f"ha_state={health.ha_state}",
            ),
        ]
        if strategy.kind in {"span", "erspan"}:
            checks.append(
                self._check(
                    "span-capacity",
                    health.device_id,
                    health.span_sessions < self._thresholds.max_span_sessions,
                    f"span_sessions={health.span_sessions} max={self._thresholds.max_span_sessions}",
                )
            )
        if strategy.kind == "ethanalyzer":
            checks.append(
                self._check(
                    "filter-present",
                    health.device_id,
                    strategy.capture_filter is not None
                    and bool(strategy.capture_filter.expression.strip()),
                    "ethanalyzer requires non-empty capture filter",
                )
            )
        return checks

    def _check(self, name: str, device_id: str, passed: bool, detail: str) -> SafetyCheck:
        return SafetyCheck(name, device_id, "pass" if passed else "fail", detail)


@dataclass(frozen=True, slots=True)
class ConsentRecord:
    job_id: str
    consent_type: Literal["full-payload", "lawful-capture"]
    granted_by: str
    granted: bool


@dataclass(frozen=True, slots=True)
class ExecutionGate:
    change_ticket: str
    full_payload_requested: bool = False
    full_payload_consent: ConsentRecord | None = None
    enforced_mode: bool = True

    def validate(self, job_id: str, audit: AuditLog) -> None:
        if self.enforced_mode and not self.change_ticket.strip():
            audit.append(
                job_id=job_id,
                event="execution-blocked",
                payload={"reason": "missing-change-ticket"},
            )
            raise ValueError("change-ticket is required in enforced mode")
        audit.append(job_id=job_id, event="change-ticket", payload={"ticket": self.change_ticket})
        if self.full_payload_requested:
            if self.full_payload_consent is None or not self.full_payload_consent.granted:
                audit.append(
                    job_id=job_id,
                    event="execution-blocked",
                    payload={"reason": "missing-full-payload-consent"},
                )
                raise ValueError("full-payload consent is required")
            audit.append(
                job_id=job_id,
                event="consent",
                payload={
                    "type": self.full_payload_consent.consent_type,
                    "granted_by": self.full_payload_consent.granted_by,
                    "granted": self.full_payload_consent.granted,
                },
            )
