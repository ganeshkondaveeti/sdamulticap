from __future__ import annotations

from dataclasses import dataclass, field

from multicap.core.filters import FilterSpec


@dataclass(frozen=True, slots=True)
class Endpoint:
    device_id: str
    interface: str | None = None


@dataclass(frozen=True, slots=True)
class PathIntent:
    job_id: str
    src: Endpoint
    dst: Endpoint
    duration_seconds: int
    filter_spec: FilterSpec = field(default_factory=FilterSpec)


class IntentCompiler:
    def compile_path(
        self,
        *,
        job_id: str,
        src_device_id: str,
        dst_device_id: str,
        duration_seconds: int,
        filter_spec: FilterSpec | None = None,
    ) -> PathIntent:
        if duration_seconds <= 0:
            raise ValueError("duration_seconds must be positive")
        return PathIntent(
            job_id=job_id,
            src=Endpoint(src_device_id),
            dst=Endpoint(dst_device_id),
            duration_seconds=duration_seconds,
            filter_spec=filter_spec or FilterSpec(),
        )
