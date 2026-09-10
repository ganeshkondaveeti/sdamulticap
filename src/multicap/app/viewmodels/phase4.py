from __future__ import annotations

from dataclasses import dataclass

from multicap.core.filters import FilterBuilder, FilterSpec
from multicap.core.intent import IntentCompiler
from multicap.core.planner import CapturePlan, PlanGenerator
from multicap.core.topology import TopologyGraph


@dataclass(frozen=True, slots=True)
class PlanReviewRow:
    device_id: str
    role: str
    strategy: str
    filter_expression: str
    reason: str


class PathIntentViewModel:
    def __init__(
        self,
        graph: TopologyGraph,
        compiler: IntentCompiler | None = None,
        generator: PlanGenerator | None = None,
    ) -> None:
        self._graph = graph
        self._compiler = compiler or IntentCompiler()
        self._generator = generator or PlanGenerator()

    def compile_plan(
        self,
        *,
        job_id: str,
        src_device_id: str,
        dst_device_id: str,
        duration_seconds: int,
        filter_spec: FilterSpec | None = None,
    ) -> CapturePlan:
        intent = self._compiler.compile_path(
            job_id=job_id,
            src_device_id=src_device_id,
            dst_device_id=dst_device_id,
            duration_seconds=duration_seconds,
            filter_spec=filter_spec,
        )
        return self._generator.generate(self._graph, intent)


class FilterBuilderViewModel:
    def __init__(self, builder: FilterBuilder | None = None) -> None:
        self._builder = builder or FilterBuilder()

    def preview(self, spec: FilterSpec, platform: str) -> str:
        from multicap.drivers.base import DeviceProfile

        device = DeviceProfile("preview", "preview", platform, platform, "preview")
        return self._builder.build(spec, device).expression


def rows_for_plan(plan: CapturePlan) -> list[PlanReviewRow]:
    rows: list[PlanReviewRow] = []
    for strategy in plan.per_device:
        rows.append(
            PlanReviewRow(
                device_id=strategy.device.id,
                role=strategy.role,
                strategy=strategy.kind,
                filter_expression=strategy.capture_filter.expression
                if strategy.capture_filter
                else "",
                reason=strategy.reason or "",
            )
        )
    return rows
