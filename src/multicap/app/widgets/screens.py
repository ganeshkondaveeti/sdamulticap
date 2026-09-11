from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from multicap.app.demo_data import DemoUiState
from multicap.app.viewmodels import (
    ap_state_diff_row,
    client_location_row,
    coverage_gap_banner,
    ntp_degraded_banner,
    sniffer_consent_rows,
    wireless_plan_rows,
    wireless_safety_summary,
)


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
                    [
                        state.plan.job_id,
                        "Path cat-1 → cat-2",
                        "DONE",
                        "2m14s",
                        state.verdict.severity,
                    ],
                    ["wireless-demo", "Client aa:bb:cc", "ACTIVE", "6m10s", "collecting"],
                ],
                "recentJobsTable",
            )
        )
        self.root.addStretch(1)


class DiscoveryScreen(ScreenBase):
    def __init__(self, state: DemoUiState, parent: QWidget | None = None) -> None:
        super().__init__(
            "discovery",
            "Discovery",
            "Seed devices, credentials, crawl progress, and topology graph/table views.",
            parent,
        )
        controls = self.add_section("Crawl Controls")
        controls_layout = cast(QVBoxLayout, controls.layout())
        controls_layout.addWidget(QLabel("Seeds: 192.0.2.0/28, cat-1, WLC-9800-A", controls))
        controls_layout.addWidget(QLabel("Credential profile: lab-readonly ••••••••", controls))
        controls_layout.addWidget(
            QLabel(
                "Discovery methods: CDP/LLDP crawl, subnet sweep, Catalyst Center sync", controls
            )
        )
        progress = QProgressBar(controls)
        progress.setObjectName("discoveryProgress")
        progress.setAccessibleName("Discovery crawl progress")
        progress.setRange(0, 100)
        progress.setValue(72)
        controls_layout.addWidget(progress)

        topology = self.add_section("Topology Graph")
        topology_layout = cast(QVBoxLayout, topology.layout())
        graph = TopologyGraph(state, topology)
        topology_layout.addWidget(graph)
        topology_layout.addWidget(
            _table(
                ["Device", "Platform", "OS", "Train", "Management IP"],
                [
                    [
                        device.id,
                        device.platform,
                        device.os_family,
                        device.release_train,
                        device.management_ip,
                    ]
                    for device in state.topology.devices.values()
                ],
                "deviceTable",
            )
        )
        self.root.addStretch(1)


class IntentsScreen(ScreenBase):
    def __init__(self, state: DemoUiState, parent: QWidget | None = None) -> None:
        super().__init__(
            "intents",
            "Intents",
            "Path and client-MAC capture forms with progressive disclosure and compile actions.",
            parent,
        )
        path = self.add_section("New Path Intent")
        path_layout = cast(QVBoxLayout, path.layout())
        path_layout.addWidget(QLabel("Source: cat-1", path))
        path_layout.addWidget(QLabel("Destination: cat-2", path))
        path_layout.addWidget(QLabel("Duration: 120 seconds", path))
        path_layout.addWidget(
            QLabel("Advanced ▸ protocol=tcp, dst-port=443, snap-length=headers-only", path)
        )
        path_layout.addWidget(QLabel("Path Preview: cat-1 → nx-1 → cat-2 (3 hops)", path))
        self.compile_path_button: QPushButton = QPushButton("Compile → Plan Review", path)
        self.compile_path_button.setObjectName("compilePathIntentButton")
        self.compile_path_button.setAccessibleName("Compile path intent")
        path_layout.addWidget(self.compile_path_button)

        wireless = self.add_section("New Client-MAC Intent")
        wireless_layout = cast(QVBoxLayout, wireless.layout())
        location = client_location_row(state.client_location)
        wireless_layout.addWidget(QLabel(f"Client MAC: {location.client_mac}", wireless))
        wireless_layout.addWidget(QLabel("Duration: 180 seconds", wireless))
        location_text = (
            f"Client Location: AP {location.ap_name}, controller {location.controller_id}, "
            f"{location.channel}, switching {location.switching_mode}"
        )
        wireless_layout.addWidget(QLabel(location_text, wireless))
        wireless_layout.addWidget(QLabel(f"Redirect target: {location.wired_uplink}", wireless))
        self.compile_client_button: QPushButton = QPushButton(
            "Compile Client-MAC → Plan Review", wireless
        )
        self.compile_client_button.setObjectName("compileClientIntentButton")
        self.compile_client_button.setAccessibleName("Compile client MAC intent")
        wireless_layout.addWidget(self.compile_client_button)
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
        summary_layout.addWidget(
            QLabel(f"Intent: Path cat-1 → cat-2, {len(state.plan.path)} devices", summary)
        )
        summary_layout.addWidget(
            QLabel(f"Service impact: {state.plan.impact.service_impact}", summary)
        )

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
        full_payload.setChecked(False)
        change_ticket = QLineEdit("CHG-0004421", consent)
        change_ticket.setObjectName("changeTicketField")
        change_ticket.setAccessibleName("Change-ticket ID")
        consent_layout.addWidget(full_payload)
        for row in sniffer_consent_rows(state.sniffer_candidates, state.wireless_safety.disclosure):
            sniffer_text = (
                f"AP Sniffer consent: {row.ap_name} ({row.client_count} clients, "
                f"{'recommended' if row.recommended else 'candidate'})"
            )
            sniffer = QCheckBox(sniffer_text, consent)
            sniffer.setObjectName(f"snifferConsentCheck-{row.ap_name}")
            sniffer.setAccessibleName(f"AP sniffer consent for {row.ap_name}")
            sniffer.setChecked(row.recommended)
            consent_layout.addWidget(sniffer)
        disclosure = QCheckBox(state.wireless_safety.disclosure, consent)
        disclosure.setObjectName("keyMaterialDisclosureCheck")
        disclosure.setAccessibleName("Key-material disclosure acknowledgement")
        disclosure.setChecked(True)
        consent_layout.addWidget(disclosure)
        consent_layout.addWidget(change_ticket)

        wireless = self.add_section("Wireless Three-Domain Plan")
        cast(QVBoxLayout, wireless.layout()).addWidget(
            _table(
                ["Device", "Domain Action", "Filter", "Reason"],
                [
                    [row.device_id, row.action, row.filter_expression, row.reason]
                    for row in wireless_plan_rows(state.wireless_plan)
                ],
                "wirelessPlanTable",
            )
        )
        redirect = QLabel(
            "Coverage / Redirect: flex-local WLAN bypasses WLC data plane; capture wired uplink edge-sw-3f.",
            self,
        )
        redirect.setObjectName("wirelessRedirectBanner")
        redirect.setAccessibleName("Wireless redirect banner")
        self.root.addWidget(redirect)
        wireless_status = QLabel(wireless_safety_summary(state.wireless_safety), self)
        wireless_status.setObjectName("wirelessSafetySummary")
        wireless_status.setAccessibleName("Wireless safety summary")
        self.root.addWidget(wireless_status)


class JobsScreen(ScreenBase):
    def __init__(self, state: DemoUiState, parent: QWidget | None = None) -> None:
        super().__init__(
            "jobs",
            "Jobs",
            "Active and historical capture jobs with searchable intent, phase, and verdict state.",
            parent,
        )
        filters = self.add_section("Filters")
        filters_layout = cast(QVBoxLayout, filters.layout())
        filters_layout.addWidget(
            QLabel(
                "Status filters: ARMED ACTIVE STOPPED COLLECTED CORRELATED VERIFIED DONE FAILED",
                filters,
            )
        )
        filters_layout.addWidget(
            QLabel("Search: change-ticket, intent, device, client MAC", filters)
        )
        jobs = self.add_section("Jobs")
        cast(QVBoxLayout, jobs.layout()).addWidget(
            _table(
                ["Job", "Intent", "Phase", "Duration", "Verdict", "Action"],
                [
                    [
                        state.plan.job_id,
                        "Path cat-1 → cat-2",
                        "DONE",
                        "2m14s",
                        state.verdict.severity,
                        "Open Report",
                    ],
                    [
                        "wireless-demo",
                        "Client aa:bb:cc:11:22:33",
                        "ACTIVE",
                        "6m10s",
                        "collecting",
                        "Open Live Run",
                    ],
                    [
                        "job-pruned",
                        "Path retired",
                        "DONE",
                        "retention-pruned",
                        "tombstone",
                        "Audit",
                    ],
                ],
                "jobsTable",
            )
        )
        self.root.addStretch(1)


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
        timeline_layout.addWidget(
            QLabel(
                "IDLE → ARMED → ACTIVE → STOPPED → COLLECTED → CORRELATED → VERIFIED → DONE",
                timeline,
            )
        )
        timeline_layout.addWidget(QLabel("Arming skew ruler: 84.0 ms ✓", timeline))
        status = self.add_section("Status & Actions")
        status_layout = cast(QVBoxLayout, status.layout())
        status_layout.addWidget(QLabel("Phase: ACTIVE", status))
        status_layout.addWidget(QLabel("Coverage: no gaps", status))
        status_layout.addWidget(QLabel(ntp_degraded_banner(state.precision), status))
        status_layout.addWidget(QLabel("Radioactive Trace: 2m11 assoc-req → 2m14 dhcp ack", status))
        abort = QPushButton("Abort Job", status)
        abort.setObjectName("abortJobButton")
        abort.setAccessibleName("Abort Job")
        status_layout.addWidget(abort)

        ap_diff = self.add_section("AP State Diff")
        diff = ap_state_diff_row(state.ap_state_diff)
        cast(QVBoxLayout, ap_diff.layout()).addWidget(
            _table(
                ["AP", "Restored", "Differences"],
                [[diff.ap_name, "yes" if diff.restored else "no", diff.differences or "none"]],
                "apStateDiffTable",
            )
        )


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
        ladder_text = "\n".join(
            [
                "Overlays: drops, 802.11-auth, radioactive-trace",
                "OTA (AP) → CAPWAP (WLC) → Wired (EdgeSw)",
                "2m11 assoc-req → 2m11 assoc-resp → 2m12 DHCP ack",
            ]
        )
        _ = tabs.addTab(_label_panel(ladder_text), "Ladder")
        _ = tabs.addTab(
            _table(
                ["Device", "Mechanism", "Latency", "Counters", "802.11 State"],
                timeline_rows,
                "packetTimelineTable",
            ),
            "Timeline",
        )
        _ = tabs.addTab(
            _table(
                ["Device", "Mechanism", "Latency", "Counters", "802.11 State"],
                timeline_rows,
                "reportTimelineTable",
            ),
            "Packet Drill-down",
        )
        _ = tabs.addTab(
            _label_panel("Drops: 2\nTruncated: 1\nCoverage gaps: none"), "Coverage & Drops"
        )
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


class FirstRunConsentScreen(ScreenBase):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            "firstRunConsent",
            "First-Run Lawful Capture Consent",
            "One-time acknowledgement before packet-capture features are enabled.",
            parent,
        )
        consent = self.add_section("Capture Authorization")
        layout = cast(QVBoxLayout, consent.layout())
        body_text = (
            "I confirm I am authorized to collect packet captures on the selected infrastructure, "
            "will follow local data-handling policy, and understand payload capture may expose sensitive data."
        )
        body = QLabel(body_text, consent)
        body.setWordWrap(True)
        body.setAccessibleName("First-run consent copy")
        layout.addWidget(body)
        checkbox = QCheckBox("I acknowledge lawful-capture responsibilities", consent)
        checkbox.setObjectName("firstRunConsentCheck")
        checkbox.setAccessibleName("First-run consent acknowledgement")
        layout.addWidget(checkbox)
        self.root.addStretch(1)


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
            (
                "Inventory Adapters",
                "Catalyst Center first-class; Prime, NSO, Nexus Dashboard, APIC feature-flagged.",
            ),
            (
                "Enforcement Mode",
                "ENFORCED: change-ticket and consent gates block execution until satisfied.",
            ),
            ("NTP Status", "Recently discovered devices feed Plan Review degraded banners."),
            ("Telemetry", "Crash reports only, opt-in, off by default."),
            (
                "About",
                "Version 0.0.0 • SBOM link available in release artifacts • license/signature verified at release time.",
            ),
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
            [
                str(record.id),
                record.ts,
                record.job_id,
                record.event,
                str(record.payload),
                record.entry_hash[:12],
            ]
            for record in state.audit_records()
        ]
        self.root.addWidget(
            _table(["ID", "Timestamp", "Job", "Event", "Payload", "Hash"], rows, "auditTable")
        )


class SearchPalette(QDialog):
    def __init__(self, screens: Sequence[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setModal(False)
        self.setObjectName("searchPalette")
        self.setAccessibleName("Search palette")
        self.setWindowTitle("Search MultiCap")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        prompt = QLineEdit(self)
        prompt.setObjectName("searchPaletteInput")
        prompt.setAccessibleName("Search palette input")
        prompt.setPlaceholderText("Jump to Job / Device / Intent / Report / Audit / Settings")
        results = QListWidget(self)
        results.setObjectName("searchPaletteResults")
        results.setAccessibleName("Search palette results")
        for screen in screens:
            results.addItem(QListWidgetItem(screen))
        layout.addWidget(prompt)
        layout.addWidget(results)


class TopologyGraph(QWidget):
    def __init__(self, state: DemoUiState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topologyGraph")
        self.setAccessibleName("Topology graph")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel("Topology graph: " + " · ".join(state.topology.devices), self))


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
