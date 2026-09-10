from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from multicap.core.correlator_facade import CorrelationSummary
from multicap.core.planner import CapturePlan
from multicap.core.synchronizer import StatusEvent
from multicap.persistence.audit import AuditLog, AuditRecord


@dataclass(frozen=True, slots=True)
class PrecisionStatus:
    ntp_synchronized: bool
    affected_devices: tuple[str, ...] = ()
    degraded_bound_ms: int = 500

    @property
    def banner(self) -> str:
        if self.ntp_synchronized:
            return "Precision timing healthy: all devices are NTP synchronized."
        devices = ", ".join(self.affected_devices)
        return (
            f"NTP degraded: alignment bound is ±{self.degraded_bound_ms} ms; "
            f"affected devices: {devices}."
        )


@dataclass(frozen=True, slots=True)
class LadderHop:
    device_id: str
    interface: str
    mechanism: str
    latency_ms: float
    dropped: int = 0
    truncated: int = 0
    wifi_state: str = ""


@dataclass(frozen=True, slots=True)
class FaultVerdict:
    location: str
    severity: str
    reason: str


@dataclass(frozen=True, slots=True)
class EvidenceBundle:
    job_id: str
    html_path: Path
    pdf_path: Path
    pcapng_path: Path
    audit_path: Path
    verdict: FaultVerdict
    precision: PrecisionStatus


class FaultVerdictEngine:
    def evaluate(self, hops: list[LadderHop], plan: CapturePlan) -> FaultVerdict:
        coverage_gaps = plan.coverage_gaps()
        if coverage_gaps:
            devices = ",".join(strategy.device.id for strategy in coverage_gaps)
            return FaultVerdict(
                devices,
                "coverage-gap",
                "Plan contains devices without a supported capture strategy.",
            )
        lossy = next((hop for hop in hops if hop.dropped or hop.truncated), None)
        if lossy is not None:
            return FaultVerdict(
                lossy.device_id,
                "packet-loss",
                f"Drop/truncation counters increased on {lossy.device_id}.",
            )
        slow = next((hop for hop in hops if hop.latency_ms > 50.0), None)
        if slow is not None:
            return FaultVerdict(
                slow.device_id,
                "latency",
                f"Per-hop latency {slow.latency_ms:.1f} ms exceeds seeded threshold.",
            )
        return FaultVerdict("end-to-end", "clear", "No seeded fault heuristic matched.")


class LadderDiagramBuilder:
    def build(
        self,
        plan: CapturePlan,
        status_events: tuple[StatusEvent, ...],
        summary: CorrelationSummary,
    ) -> list[LadderHop]:
        coverage_gap_ids = {strategy.device.id for strategy in plan.coverage_gaps()}
        first_active = {
            event.device_id: event.elapsed_seconds
            for event in status_events
            if event.phase == "ACTIVE" and event.device_id not in coverage_gap_ids
        }
        baseline = min(first_active.values(), default=0.0)
        hops: list[LadderHop] = []
        for index, strategy in enumerate(plan.per_device):
            dropped = summary.dropped if index == len(plan.per_device) - 1 else 0
            truncated = summary.truncated if index == len(plan.per_device) - 1 else 0
            metadata_state = ""
            if strategy.device.platform in {"ap", "iosxe-wlc"}:
                metadata_state = "association/auth state retained"
            hops.append(
                LadderHop(
                    device_id=strategy.device.id,
                    interface="coverage-gap" if strategy.kind == "coverage-gap" else "capture",
                    mechanism=strategy.kind,
                    latency_ms=max(first_active.get(strategy.device.id, baseline) - baseline, 0.0)
                    * 1000,
                    dropped=dropped,
                    truncated=truncated,
                    wifi_state=metadata_state,
                )
            )
        return hops


class EvidenceReporter:
    def __init__(self, verdict_engine: FaultVerdictEngine | None = None) -> None:
        self._verdict_engine = verdict_engine or FaultVerdictEngine()

    def build_bundle(
        self,
        *,
        job_id: str,
        plan: CapturePlan,
        hops: list[LadderHop],
        correlation: CorrelationSummary,
        audit: AuditLog,
        precision: PrecisionStatus,
        output_dir: Path,
    ) -> EvidenceBundle:
        output_dir.mkdir(parents=True, exist_ok=True)
        audit_path = output_dir / f"{job_id}-audit.json"
        html_path = output_dir / f"{job_id}-evidence.html"
        pdf_path = output_dir / f"{job_id}-evidence.pdf"
        verdict = self._verdict_engine.evaluate(hops, plan)

        audit_path.write_text(self._audit_json(audit.records()), encoding="utf-8")
        html_doc = self._html(job_id, hops, verdict, correlation, precision, audit_path)
        html_path.write_text(html_doc, encoding="utf-8")
        pdf_path.write_bytes(self._pdf_placeholder(job_id, verdict, precision))
        return EvidenceBundle(
            job_id=job_id,
            html_path=html_path,
            pdf_path=pdf_path,
            pcapng_path=correlation.output_path,
            audit_path=audit_path,
            verdict=verdict,
            precision=precision,
        )

    def _audit_json(self, records: list[AuditRecord]) -> str:
        rows = [asdict(record) for record in records]
        return json.dumps(rows, indent=2, sort_keys=True)

    def _html(
        self,
        job_id: str,
        hops: list[LadderHop],
        verdict: FaultVerdict,
        correlation: CorrelationSummary,
        precision: PrecisionStatus,
        audit_path: Path,
    ) -> str:
        hop_rows = "\n".join(
            "<tr>"
            f"<td>{html.escape(hop.device_id)}</td>"
            f"<td>{html.escape(hop.mechanism)}</td>"
            f"<td>{hop.latency_ms:.1f} ms</td>"
            f"<td>{hop.dropped}</td>"
            f"<td>{hop.truncated}</td>"
            f"<td>{html.escape(hop.wifi_state)}</td>"
            "</tr>"
            for hop in hops
        )
        return f"""<!doctype html>
<html lang=\"en\">
<head><meta charset=\"utf-8\"><title>MultiCap Evidence {html.escape(job_id)}</title></head>
<body>
<h1>MultiCap Evidence Bundle: {html.escape(job_id)}</h1>
<aside>{html.escape(precision.banner)}</aside>
<section><h2>Fault verdict</h2><p><strong>{html.escape(verdict.severity)}</strong> at {html.escape(verdict.location)}: {html.escape(verdict.reason)}</p></section>
<section><h2>Ladder diagram</h2><table><thead><tr><th>Device</th><th>Mechanism</th><th>Latency</th><th>Drops</th><th>Truncation</th><th>802.11 state</th></tr></thead><tbody>{hop_rows}</tbody></table></section>
<section><h2>Artifacts</h2><ul><li>pcapng: {html.escape(str(correlation.output_path))}</li><li>audit: {html.escape(str(audit_path))}</li><li>packets: {correlation.packet_count}</li></ul></section>
</body></html>"""

    def _pdf_placeholder(
        self, job_id: str, verdict: FaultVerdict, precision: PrecisionStatus
    ) -> bytes:
        body = (
            f"MultiCap Evidence Bundle {job_id}\n"
            f"Verdict: {verdict.severity} at {verdict.location}\n"
            f"{precision.banner}\n"
        )
        return b"%PDF-1.4\n% MultiCap text evidence placeholder\n" + body.encode("utf-8")
