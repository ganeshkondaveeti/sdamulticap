from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from multicap.core.cleanup import JobState
from multicap.core.safety import DeviceHealth
from multicap.drivers.base import CaptureDriver, CaptureHandle, DeviceProfile

Clock = Callable[[], float]


@dataclass(frozen=True, slots=True)
class ArmedCapture:
    device: DeviceProfile
    driver: CaptureDriver
    handle: CaptureHandle


@dataclass(frozen=True, slots=True)
class TriggerResult:
    device_id: str
    triggered_at: float


@dataclass(frozen=True, slots=True)
class TriggerReport:
    results: tuple[TriggerResult, ...]

    @property
    def skew_seconds(self) -> float:
        if len(self.results) < 2:
            return 0.0
        times = [result.triggered_at for result in self.results]
        return max(times) - min(times)


@dataclass(frozen=True, slots=True)
class StatusEvent:
    job_id: str
    device_id: str
    phase: JobState
    elapsed_seconds: float
    health: DeviceHealth | None = None
    message: str = ""


StatusSink = Callable[[StatusEvent], None]


class Synchronizer:
    def __init__(self, max_workers: int = 32, clock: Clock = time.perf_counter) -> None:
        self._max_workers = max_workers
        self._clock = clock

    def trigger(
        self,
        armed: Mapping[str, ArmedCapture],
        precision_epoch: float | None = None,
    ) -> TriggerReport:
        if not armed:
            return TriggerReport(())
        workers = min(self._max_workers, len(armed))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._trigger_one, capture, precision_epoch): device_id
                for device_id, capture in armed.items()
            }
            results = [future.result() for future in as_completed(futures)]
        return TriggerReport(tuple(sorted(results, key=lambda result: result.device_id)))

    def _trigger_one(self, capture: ArmedCapture, precision_epoch: float | None) -> TriggerResult:
        if precision_epoch is not None:
            # The device-side EEM/scheduler timer owns the actual precise start; this call observes it.
            capture.driver.trigger(capture.device, capture.handle)
            return TriggerResult(capture.device.id, precision_epoch)
        capture.driver.trigger(capture.device, capture.handle)
        return TriggerResult(capture.device.id, self._clock())
