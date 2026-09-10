from __future__ import annotations

from dataclasses import dataclass

from multicap.core.reporter import EvidenceBundle, LadderHop, PrecisionStatus
from multicap.core.timing import TimingResult
from multicap.persistence.settings import RetentionUsage


@dataclass(frozen=True, slots=True)
class TimelineRow:
    device_id: str
    mechanism: str
    latency: str
    counters: str
    wifi_state: str


@dataclass(frozen=True, slots=True)
class EvidenceBundleRow:
    job_id: str
    verdict: str
    html_path: str
    pdf_path: str
    pcapng_path: str
    audit_path: str


@dataclass(frozen=True, slots=True)
class RetentionSettingsRow:
    days: int
    max_gb: float
    current_gb: float
    last_pruned: str


def timeline_rows(hops: list[LadderHop]) -> list[TimelineRow]:
    return [
        TimelineRow(
            hop.device_id,
            hop.mechanism,
            f"{hop.latency_ms:.1f} ms",
            f"drops={hop.dropped} truncated={hop.truncated}",
            hop.wifi_state,
        )
        for hop in hops
    ]


def coverage_gap_banner(gaps: list[str]) -> str:
    if not gaps:
        return ""
    return "Coverage gaps: " + ", ".join(gaps)


def ntp_degraded_banner(precision: PrecisionStatus) -> str:
    return "" if precision.ntp_synchronized else precision.banner


def evidence_bundle_row(bundle: EvidenceBundle) -> EvidenceBundleRow:
    return EvidenceBundleRow(
        bundle.job_id,
        f"{bundle.verdict.severity}:{bundle.verdict.location}",
        str(bundle.html_path),
        str(bundle.pdf_path),
        str(bundle.pcapng_path),
        str(bundle.audit_path),
    )


def retention_settings_row(usage: RetentionUsage) -> RetentionSettingsRow:
    gb = 1024 * 1024 * 1024
    return RetentionSettingsRow(
        usage.settings.days,
        usage.settings.max_bytes / gb,
        usage.current_bytes / gb,
        usage.last_pruned,
    )


def consent_history(records: list[tuple[str, str]]) -> list[str]:
    return [f"{kind}:{actor}" for kind, actor in records]


def timing_rows(results: list[TimingResult]) -> list[str]:
    return [
        f"{result.scenario.name}: {result.elapsed_seconds:.1f}s / {result.scenario.threshold_seconds:.1f}s {'pass' if result.passed else 'fail'}"
        for result in results
    ]
