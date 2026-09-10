from __future__ import annotations

from dataclasses import dataclass

from multicap.core.wireless import ApStateDiff, SnifferCandidate, WirelessSafetyReport


@dataclass(frozen=True, slots=True)
class SnifferConsentRow:
    ap_name: str
    recommended: bool
    client_count: int
    disclosure: str


@dataclass(frozen=True, slots=True)
class ApStateDiffRow:
    ap_name: str
    restored: bool
    differences: str


def sniffer_consent_rows(
    candidates: list[SnifferCandidate], disclosure: str
) -> list[SnifferConsentRow]:
    return [
        SnifferConsentRow(
            candidate.ap.name, candidate.recommended, candidate.ap.client_count, disclosure
        )
        for candidate in candidates
    ]


def ap_state_diff_row(diff: ApStateDiff) -> ApStateDiffRow:
    return ApStateDiffRow(diff.ap_name, diff.restored, ",".join(diff.differences))


def wireless_safety_summary(report: WirelessSafetyReport) -> str:
    if report.allowed:
        return f"allowed:{report.selected_ap}"
    return f"blocked:{';'.join(report.failures)}"
