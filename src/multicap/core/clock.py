from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ClockSample:
    device_id: str
    sent_at: float
    device_time: float
    received_at: float

    @property
    def rtt_seconds(self) -> float:
        return self.received_at - self.sent_at

    @property
    def offset_seconds(self) -> float:
        midpoint = self.sent_at + self.rtt_seconds / 2
        return self.device_time - midpoint


@dataclass(frozen=True, slots=True)
class ClockOffset:
    device_id: str
    offset_seconds: float

    def to_local(self, device_timestamp: float) -> float:
        return device_timestamp - self.offset_seconds


class ClockAligner:
    def estimate(self, samples: list[ClockSample]) -> dict[str, ClockOffset]:
        grouped: dict[str, list[ClockSample]] = {}
        for sample in samples:
            grouped.setdefault(sample.device_id, []).append(sample)
        return {
            device_id: ClockOffset(
                device_id,
                min(device_samples, key=lambda sample: sample.rtt_seconds).offset_seconds,
            )
            for device_id, device_samples in grouped.items()
        }

    def beacon(self, job_id: str, sequence: int) -> bytes:
        return f"multicap-beacon:{job_id}:{sequence}".encode()
