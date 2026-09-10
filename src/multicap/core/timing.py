from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ScenarioKind = Literal["wired-10-device", "wireless-three-domain"]


@dataclass(frozen=True, slots=True)
class TimingScenario:
    name: str
    kind: ScenarioKind
    threshold_seconds: float


@dataclass(frozen=True, slots=True)
class TimingResult:
    scenario: TimingScenario
    elapsed_seconds: float

    @property
    def passed(self) -> bool:
        return self.elapsed_seconds <= self.scenario.threshold_seconds


class WallClockHarness:
    def run(self, scenario: TimingScenario, started_at: float, finished_at: float) -> TimingResult:
        if finished_at < started_at:
            raise ValueError("finished_at must not be before started_at")
        return TimingResult(scenario, finished_at - started_at)

    def assert_sc9(self, results: list[TimingResult]) -> None:
        failures = [result for result in results if not result.passed]
        if failures:
            detail = "; ".join(
                f"{result.scenario.name}={result.elapsed_seconds:.1f}s" for result in failures
            )
            raise ValueError(f"SC-9 wall-clock threshold exceeded: {detail}")


def sc9_scenarios() -> tuple[TimingScenario, TimingScenario]:
    return (
        TimingScenario("10-device wired path", "wired-10-device", 15 * 60),
        TimingScenario("three-domain wireless path", "wireless-three-domain", 20 * 60),
    )
