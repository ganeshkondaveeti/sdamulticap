from __future__ import annotations

from dataclasses import dataclass

from multicap.core.safety import ExecutionGate, SafetyGateReport


@dataclass(frozen=True, slots=True)
class SafetyGateRow:
    device_id: str
    check: str
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class ConsentGateViewModel:
    change_ticket: str
    full_payload_requested: bool
    full_payload_granted: bool
    enforced_mode: bool = True

    def can_execute(self) -> bool:
        if self.enforced_mode and not self.change_ticket.strip():
            return False
        return not self.full_payload_requested or self.full_payload_granted


def safety_rows(report: SafetyGateReport) -> list[SafetyGateRow]:
    return [
        SafetyGateRow(check.device_id, check.name, check.status, check.detail)
        for check in report.checks
    ]


def gate_from_viewmodel(viewmodel: ConsentGateViewModel) -> ExecutionGate:
    return ExecutionGate(
        change_ticket=viewmodel.change_ticket,
        full_payload_requested=viewmodel.full_payload_requested,
        enforced_mode=viewmodel.enforced_mode,
    )
