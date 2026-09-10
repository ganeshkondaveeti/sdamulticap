from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from multicap.app.demo_data import DemoUiState
from multicap.app.viewmodels import coverage_gap_banner, ntp_degraded_banner


class ScreenBase(QWidget):
    def __init__(self, key: str, title: str, summary: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(f"{key}Screen")
        self.setAccessibleName(title)
        self.setAccessibleDescription(summary)
        self.root: QVBoxLayout = QVBoxLayout(self)
        self.root.setContentsMargins(28, 24, 28, 24)
        self.root.setSpacing(14)
        self._header(title, summary)

    def _header(self, title: str, summary: str) -> None:
        heading = QLabel(title, self)
        heading.setObjectName("screenTitle")
        heading.setAccessibleName(f"{title} title")
        detail = QLabel(summary, self)
        detail.setWordWrap(True)
        detail.setAccessibleName(f"{title} summary")
        self.root.addWidget(heading)
        self.root.addWidget(detail)

    def add_section(self, title: str) -> QGroupBox:
        group = QGroupBox(title, self)
        group.setObjectName("sectionCard")
        group.setAccessibleName(title)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(10)
        self.root.addWidget(group)
        return group


class HomeScreen(ScreenBase):
    def __init__(self, state: DemoUiState, parent: QWidget | None = None) -> None:
        super().__init__(
            "home",
            "Home / Dashboard",
            "Recent jobs, active jobs, and fast paths into the two hero capture flows.",
            parent,
        )
        self.new_path_button: QPushButton = QPushButton("New Path Intent", self)
        self.new_path_button.setObjectName("newPathIntentButton")
        self.new_path_button.setAccessibleName("New Path Intent")
        self.new_client_button: QPushButton = QPushButton("New Client-MAC Intent", self)
        self.new_client_button.setObjectName("newClientIntentButton")
        self.new_client_button.setAccessibleName("New Client-MAC Intent")

        quick_start = self.add_section("Quick Start")
        quick_layout = cast(QVBoxLayout, quick_start.layout())
        buttons = QWidget(quick_start)
        buttons_layout = QHBoxLayout(buttons)
        buttons_layout.setContentsMargins(0, 0, 0, 0)
        buttons_layout.addWidget(self.new_path_button)
        buttons_layout.addWidget(self.new_client_button)
        buttons_layout.addStretch(1)
        quick_layout.addWidget(buttons)

        recent = self.add_section("Recent Jobs")
        recent_layout = cast(QVBoxLayout, recent.layout())
        recent_layout.addWidget(
            _table(
                ["Job", "Intent", "Status", "Duration", "Verdict"],
                [
                    [state.plan.job_id, "Path cat-1 → cat-2", "DONE", "2m14s", state.verdict.severity],
                    ["wireless-demo", "Client aa:bb:cc", "ACTIVE", "6m10s", "collecting"],
                ],
                "recentJobsTable",
            )
        )
        self.root.addStretch(1)


class PlanReviewScreen(ScreenBase):
    def __init__(self, state: DemoUiState, parent: QWidget | None = None) -> None:
        super().__init__(
            "planReview",
            "Plan Review",
            "Consolidated pre-flight with strategy, coverage, safety, consent, and precision state.",
            parent,
        )
        summary = self.add_section("Summary")
        summary_layout = cast(QVBoxLayout, summary.layout())
        summary_layout.addWidget(QLabel(f"Intent: Path cat-1 → cat-2, {len(state.plan.path)} devices", summary))
        summary_layout.addWidget(QLabel(f"Service impact: {state.plan.impact.service_impact}", summary))

        precision = QLabel(ntp_degraded_banner(state.precision), self)
        precision.setObjectName("ntpDegradedBanner")
        precision.setAccessibleName("NTP degraded banner")
        self.root.addWidget(precision)

        gaps = coverage_gap_banner([strategy.device.id for strategy in state.plan.coverage_gaps()])
        gap_label = QLabel(gaps or "No coverage gaps in the compiled plan.", self)
        gap_label.setObjectName("coverageGapBanner")
        gap_label.setAccessibleName("Coverage gap banner")
        self.root.addWidget(gap_label)

        strategies = self.add_section("Per-Device Strategy")
        cast(QVBoxLayout, strategies.layout()).addWidget(
            _table(
                ["Device", "Role", "Strategy", "Filter", "Reason"],
                [
                    [row.device_id, row.role, row.strategy, row.filter_expression, row.reason]
                    for row in state.plan_rows()
                ],
                "planStrategyTable",
            )
        )
        safety = self.add_section("Safety Gate")
        cast(QVBoxLayout, safety.layout()).addWidget(
            _table(
                ["Device", "Check", "Status", "Detail"],
                [[row.device_id, row.check, row.status, row.detail] for row in state.safety_rows()],
                "safetyGateTable",
            )
        )
        consent = self.add_section("Consent Gates")
        consent_layout = cast(QVBoxLayout, consent.layout())
        full_payload = QCheckBox("Full-payload capture consent granted", consent)
        full_payload.setObjectName("fullPayloadConsentCheck")
        full_payload.setAccessibleName("Full-payload consent")
        change_ticket = QLineEdit("CHG-0004421", consent)
        change_ticket.setObjectName("changeTicketField")
        change_ticket.setAccessibleName("Change-ticket ID")
        consent_layout.addWidget(full_payload)
        consent_layout.addWidget(change_ticket)


class LiveRunScreen(ScreenBase):
    def __init__(self, state: DemoUiState, parent: QWidget | None = None) -> None:
        super().__init__(
            "liveRun",
            "Live Run",
            "Per-device state, phase timeline, counters, and operator-safe cancellation controls.",
            parent,
        )
        grid = self.add_section("Device Grid")
        cast(QVBoxLayout, grid.layout()).addWidget(
            _table(
                ["Device", "Phase", "Elapsed", "Health", "Message"],
                [
                    [
                        row.device_id,
                        row.phase,
                        f"{row.elapsed_seconds:.1f}s",
                        row.health_summary,
                        row.message,
                    ]
                    for row in state.live_rows()
                ],
                "liveRunTable",
            )
        )
        timeline = self.add_section("Phase Timeline")
        timeline_layout = cast(QVBoxLayout, timeline.layout())
        timeline_layout.addWidget(QLabel("IDLE → ARMED → ACTIVE → STOPPED → COLLECTED → CORRELATED → VERIFIED → DONE", timeline))
        timeline_layout.addWidget(QLabel("Arming skew ruler: 84.0 ms ✓", timeline))
        status = self.add_section("Status & Actions")
        status_layout = cast(QVBoxLayout, status.layout())
        status_layout.addWidget(QLabel("Phase: ACTIVE", status))
        status_layout.addWidget(QLabel("Coverage: no gaps", status))
        status_layout.addWidget(QLabel(ntp_degraded_banner(state.precision), status))
        abort = QPushButton("Abort Job", status)
        abort.setObjectName("abortJobButton")
        abort.setAccessibleName("Abort Job")
        status_layout.addWidget(abort)


class ReportsScreen(ScreenBase):
    def __init__(self, state: DemoUiState, parent: QWidget | None = None) -> None:
        super().__init__(
            "reports",
            "Reports",
            "Evidence bundles, ladder timeline, coverage counters, metadata, and export paths.",
            parent,
        )
        tabs = QTabWidget(self)
        tabs.setObjectName("reportTabs")
        tabs.setAccessibleName("Report tabs")
        _ = tabs.addTab(
            _label_panel(
                f"Verdict: {state.verdict.severity} at {state.verdict.location}\n{state.verdict.reason}"
            ),
            "Verdict",
        )
        timeline_rows = [
            [row.device_id, row.mechanism, row.latency, row.counters, row.wifi_state]
            for row in state.timeline_rows()
        ]
        _ = tabs.addTab(
            _table(
                ["Device", "Mechanism", "Latency", "Counters", "802.11 State"],
                timeline_rows,
                "reportTimelineTable",
            ),
            "Ladder",
        )
        _ = tabs.addTab(
            _table(
                ["Device", "Mechanism", "Latency", "Counters", "802.11 State"],
                timeline_rows,
                "packetTimelineTable",
            ),
            "Timeline",
        )
        _ = tabs.addTab(_label_panel("Drops: 2\nTruncated: 1\nCoverage gaps: none"), "Coverage & Drops")
        _ = tabs.addTab(_label_panel(state.precision.banner), "Metadata")
        evidence = state.evidence_row()
        _ = tabs.addTab(
            _table(
                ["Job", "Verdict", "HTML", "PDF", "pcapng", "Audit"],
                [
                    [
                        evidence.job_id,
                        evidence.verdict,
                        evidence.html_path,
                        evidence.pdf_path,
                        evidence.pcapng_path,
                        evidence.audit_path,
                    ]
                ],
                "exportsTable",
            ),
            "Exports",
        )
        self.root.addWidget(tabs)


class SettingsScreen(ScreenBase):
    def __init__(self, state: DemoUiState, parent: QWidget | None = None) -> None:
        super().__init__(
            "settings",
            "Settings",
            "Retention, credentials, inventory adapters, enforcement mode, NTP, telemetry, and about.",
            parent,
        )
        retention = self.add_section("Retention")
        row = state.retention_row()
        retention_layout = cast(QVBoxLayout, retention.layout())
        usage = QProgressBar(retention)
        usage.setObjectName("retentionUsageBar")
        usage.setAccessibleName("Retention usage")
        usage.setRange(0, 100)
        usage.setValue(0)
        retention_layout.addWidget(usage)
        retention_layout.addWidget(
            _table(
                ["Days", "Max GB", "Current GB", "Last Pruned"],
                [[str(row.days), f"{row.max_gb:.1f}", f"{row.current_gb:.1f}", row.last_pruned]],
                "retentionTable",
            )
        )
        for title, text in [
            ("Credentials", "Credential profiles render secrets as •••••••• with rotate actions."),
            ("Inventory Adapters", "Catalyst Center first-class; Prime, NSO, Nexus Dashboard, APIC feature-flagged."),
            ("Enforcement Mode", "ENFORCED: change-ticket and consent gates block execution until satisfied."),
            ("NTP Status", "Recently discovered devices feed Plan Review degraded banners."),
            ("Telemetry", "Crash reports only, opt-in, off by default."),
        ]:
            group = self.add_section(title)
            cast(QVBoxLayout, group.layout()).addWidget(QLabel(text, group))


class AuditScreen(ScreenBase):
    def __init__(self, state: DemoUiState, parent: QWidget | None = None) -> None:
        super().__init__(
            "audit",
            "Audit",
            "Immutable hash-chained records, consent history, and chain verification.",
            parent,
        )
        status = QLabel("Hash chain: OK" if state.audit.verify() else "Hash chain: BROKEN", self)
        status.setObjectName("auditChainStatus")
        status.setAccessibleName("Audit chain status")
        self.root.addWidget(status)
        rows = [
            [str(record.id), record.ts, record.job_id, record.event, str(record.payload), record.entry_hash[:12]]
            for record in state.audit_records()
        ]
        self.root.addWidget(_table(["ID", "Timestamp", "Job", "Event", "Payload", "Hash"], rows, "auditTable"))


def _label_panel(text: str) -> QWidget:
    panel = QWidget()
    layout = QVBoxLayout(panel)
    label = QLabel(text, panel)
    label.setWordWrap(True)
    layout.addWidget(label)
    layout.addStretch(1)
    return panel


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]], object_name: str) -> QTableWidget:
    table = QTableWidget(len(rows), len(headers))
    table.setObjectName(object_name)
    table.setAccessibleName(object_name)
    table.setHorizontalHeaderLabels(list(headers))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setAlternatingRowColors(True)
    table.verticalHeader().setVisible(False)
    for row_index, row in enumerate(rows):
        for column_index, value in enumerate(row):
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            table.setItem(row_index, column_index, item)
    table.resizeColumnsToContents()
    table.resizeRowsToContents()
    return table
