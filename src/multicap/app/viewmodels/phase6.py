from __future__ import annotations

from dataclasses import dataclass

from multicap.core.job_runner import JobResult
from multicap.core.synchronizer import StatusEvent, TriggerReport


@dataclass(frozen=True, slots=True)
class LiveRunRow:
    device_id: str
    phase: str
    elapsed_seconds: float
    health_summary: str
    message: str


def live_rows(events: tuple[StatusEvent, ...]) -> list[LiveRunRow]:
    rows: list[LiveRunRow] = []
    for event in events:
        health = ""
        if event.health is not None:
            health = f"cpu={event.health.cpu_percent:.1f}% mem={event.health.memory_percent:.1f}%"
        rows.append(
            LiveRunRow(
                event.device_id,
                event.phase,
                event.elapsed_seconds,
                health,
                event.message,
            )
        )
    return rows


def skew_label(report: TriggerReport | JobResult) -> str:
    skew = report.skew_seconds if isinstance(report, TriggerReport) else report.arming_skew_seconds
    return f"{skew * 1000:.1f} ms"
