from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Literal

from multicap.core.filters import FilterBuilder
from multicap.core.intent import PathIntent
from multicap.core.topology import Device, TopologyGraph
from multicap.drivers.base import CapabilityMatrix, CaptureFilter
from multicap.drivers.capabilities import CapabilityRegistry

StrategyKind = Literal["epc", "ethanalyzer", "erspan", "span", "coverage-gap"]
DeviceRole = Literal["source", "destination", "midpoint"]


@dataclass(frozen=True, slots=True)
class CaptureStrategy:
    kind: StrategyKind
    device: Device
    role: DeviceRole
    capture_filter: CaptureFilter | None
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class PlanImpact:
    blast_radius: Literal["low", "medium", "high"]
    service_impact: str


@dataclass(frozen=True, slots=True)
class CapturePlan:
    job_id: str
    path: tuple[str, ...]
    per_device: tuple[CaptureStrategy, ...]
    impact: PlanImpact

    def coverage_gaps(self) -> list[CaptureStrategy]:
        return [strategy for strategy in self.per_device if strategy.kind == "coverage-gap"]


class WiredPathSolver:
    def solve(self, graph: TopologyGraph, src_device_id: str, dst_device_id: str) -> list[Device]:
        if src_device_id not in graph.devices:
            raise KeyError(f"unknown source device: {src_device_id}")
        if dst_device_id not in graph.devices:
            raise KeyError(f"unknown destination device: {dst_device_id}")
        queue: deque[list[str]] = deque([[src_device_id]])
        visited = {src_device_id}
        while queue:
            path = queue.popleft()
            current = path[-1]
            if current == dst_device_id:
                return [graph.devices[device_id] for device_id in path]
            for neighbor in graph.neighbors(current):
                if neighbor.id not in visited:
                    visited.add(neighbor.id)
                    queue.append([*path, neighbor.id])
        raise ValueError(f"no wired path from {src_device_id} to {dst_device_id}")


class PlanGenerator:
    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        filters: FilterBuilder | None = None,
        solver: WiredPathSolver | None = None,
    ) -> None:
        self._registry = registry or CapabilityRegistry.from_default_fixtures()
        self._filters = filters or FilterBuilder()
        self._solver = solver or WiredPathSolver()

    def generate(self, graph: TopologyGraph, intent: PathIntent) -> CapturePlan:
        path = self._solver.solve(graph, intent.src.device_id, intent.dst.device_id)
        strategies = tuple(
            self._strategy_for(device, role_for(index, len(path)), intent)
            for index, device in enumerate(path)
        )
        return CapturePlan(
            job_id=intent.job_id,
            path=tuple(device.id for device in path),
            per_device=strategies,
            impact=estimate_impact(strategies),
        )

    def _strategy_for(
        self, device: Device, role: DeviceRole, intent: PathIntent
    ) -> CaptureStrategy:
        try:
            matrix = self._registry.probe(device.profile())
        except KeyError:
            return CaptureStrategy("coverage-gap", device, role, None, "unknown-release")

        capture_filter = self._filters.build(intent.filter_spec, device.profile())
        kind = select_strategy_kind(matrix)
        if kind == "coverage-gap":
            return CaptureStrategy(kind, device, role, None, "no-supported-capture-strategy")
        return CaptureStrategy(kind, device, role, capture_filter)


def select_strategy_kind(matrix: CapabilityMatrix) -> StrategyKind:
    if (
        matrix.supports("epc_physical")
        or matrix.supports("epc_svi")
        or matrix.supports("epc_subinterface")
    ):
        return "epc"
    if matrix.supports("ethanalyzer"):
        return "ethanalyzer"
    if matrix.supports("erspan"):
        return "erspan"
    if matrix.supports("span"):
        return "span"
    return "coverage-gap"


def role_for(index: int, length: int) -> DeviceRole:
    if index == 0:
        return "source"
    if index + 1 == length:
        return "destination"
    return "midpoint"


def estimate_impact(strategies: tuple[CaptureStrategy, ...]) -> PlanImpact:
    if any(strategy.kind == "coverage-gap" for strategy in strategies):
        return PlanImpact(
            "medium", "Plan contains explicit coverage gaps; no device mutation for gaps."
        )
    if any(strategy.kind in {"erspan", "span"} for strategy in strategies):
        return PlanImpact("high", "SPAN/ERSPAN can touch forwarding telemetry configuration.")
    if len(strategies) > 4:
        return PlanImpact("medium", "Multiple devices require coordinated capture state.")
    return PlanImpact("low", "Native filtered on-box capture only.")
