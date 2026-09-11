from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from multicap.app.viewmodels import (
    EvidenceBundleRow,
    LiveRunRow,
    PlanReviewRow,
    RetentionSettingsRow,
    SafetyGateRow,
    TimelineRow,
    evidence_bundle_row,
    live_rows,
    retention_settings_row,
    rows_for_plan,
    safety_rows,
    timeline_rows,
)
from multicap.core.correlator_facade import CorrelationSummary
from multicap.core.filters import FilterSpec
from multicap.core.planner import CapturePlan, CaptureStrategy, PlanImpact
from multicap.core.reporter import (
    EvidenceBundle,
    FaultVerdict,
    FaultVerdictEngine,
    LadderDiagramBuilder,
    LadderHop,
    PrecisionStatus,
)
from multicap.core.safety import DeviceHealth, SafetyGate
from multicap.core.synchronizer import StatusEvent
from multicap.core.topology import Device, Link, TopologyGraph
from multicap.core.wireless import (
    AccessPoint,
    ApRestorationAssertion,
    ApStateDiff,
    ApStateSnapshot,
    ClientLocation,
    ClientLocationResolver,
    SnifferApSelector,
    SnifferCandidate,
    SnifferConsentRecord,
    WirelessCapturePlan,
    WirelessController,
    WirelessInventory,
    WirelessPathSolver,
    WirelessSafetyGate,
    WirelessSafetyReport,
    WlanProfile,
)
from multicap.drivers.base import CaptureFilter
from multicap.persistence.audit import AuditLog, AuditRecord
from multicap.persistence.settings import RetentionPruner, RetentionSettings


class DemoUiState:
    def __init__(self) -> None:
        self._tempdir: TemporaryDirectory[str] = TemporaryDirectory(prefix="multicap-ui-")
        self.root: Path = Path(self._tempdir.name)
        self.topology: TopologyGraph = _demo_topology()
        self.plan: CapturePlan = _demo_plan()
        self.inventory: WirelessInventory = _demo_wireless_inventory()
        self.client_location: ClientLocation = ClientLocationResolver(self.inventory).resolve(
            "aa:bb:cc:11:22:33"
        )
        self.wireless_plan: WirelessCapturePlan = WirelessPathSolver(
            self.inventory, self.topology
        ).solve_client_capture(
            job_id="wireless-demo",
            client_mac=self.client_location.client_mac,
            filter_spec=FilterSpec(protocol="tcp", dst_port=443),
        )
        self.sniffer_candidates: list[SnifferCandidate] = SnifferApSelector().candidates(
            self.inventory, self.client_location.controller_id
        )
        self.wireless_safety: WirelessSafetyReport = WirelessSafetyGate().evaluate(
            self.client_location,
            self.sniffer_candidates,
            SnifferConsentRecord("wireless-demo", self.client_location.ap_name, "operator", True),
            live_channel=self.client_location.channel,
        )
        self.ap_state_diff: ApStateDiff = ApRestorationAssertion().compare(
            ApStateSnapshot(self.client_location.ap_name, "local", "5 GHz", 36, 80),
            ApStateSnapshot(self.client_location.ap_name, "local", "5 GHz", 36, 80),
        )
        self.precision: PrecisionStatus = PrecisionStatus(False, ("nx-1",), 500)
        self.health: dict[str, DeviceHealth] = {
            strategy.device.id: DeviceHealth(strategy.device.id, 18.0, 34.0, 4096, 0)
            for strategy in self.plan.per_device
        }
        self.status_events: tuple[StatusEvent, ...] = (
            StatusEvent(self.plan.job_id, "cat-1", "ARMED", 0.4, self.health["cat-1"], "EPC armed"),
            StatusEvent(
                self.plan.job_id, "nx-1", "ACTIVE", 1.1, self.health["nx-1"], "ethanalyzer active"
            ),
            StatusEvent(
                self.plan.job_id, "cat-2", "COLLECTED", 5.6, self.health["cat-2"], "pcap pulled"
            ),
        )
        self.audit: AuditLog = AuditLog(self.root / "audit.sqlite3")
        _ = self.audit.append(
            job_id=self.plan.job_id, event="change-ticket", payload={"ticket": "CHG-0004421"}
        )
        _ = self.audit.append(
            job_id=self.plan.job_id, event="consent", payload={"type": "full-payload"}
        )
        self.pcapng_path: Path = self.root / "merged.pcapng"
        _ = self.pcapng_path.write_text("packet\n", encoding="utf-8")
        self.correlation: CorrelationSummary = CorrelationSummary(self.pcapng_path, 42, 2, 1)
        self.hops: list[LadderHop] = LadderDiagramBuilder().build(
            self.plan, self.status_events, self.correlation
        )
        self.verdict: FaultVerdict = FaultVerdictEngine().evaluate(self.hops, self.plan)
        self.bundle: EvidenceBundle = EvidenceBundle(
            self.plan.job_id,
            self.root / "phase-ui-evidence.html",
            self.root / "phase-ui-evidence.pdf",
            self.pcapng_path,
            self.root / "phase-ui-audit.json",
            self.verdict,
            self.precision,
        )

    def plan_rows(self) -> list[PlanReviewRow]:
        return rows_for_plan(self.plan)

    def safety_rows(self) -> list[SafetyGateRow]:
        return safety_rows(SafetyGate().evaluate(self.plan, self.health))

    def live_rows(self) -> list[LiveRunRow]:
        return live_rows(self.status_events)

    def timeline_rows(self) -> list[TimelineRow]:
        return timeline_rows(self.hops)

    def evidence_row(self) -> EvidenceBundleRow:
        return evidence_bundle_row(self.bundle)

    def retention_row(self) -> RetentionSettingsRow:
        return retention_settings_row(
            RetentionPruner(
                self.root / "pcaps", RetentionSettings(days=30, max_bytes=50 * 1024**3)
            ).usage()
        )

    def audit_records(self) -> list[AuditRecord]:
        return self.audit.records()


def _demo_plan() -> CapturePlan:
    topology = _demo_topology()
    capture_filter = CaptureFilter("tcp and dst port 443")
    return CapturePlan(
        job_id="phase-ui-demo",
        path=("cat-1", "nx-1", "cat-2"),
        per_device=(
            CaptureStrategy("epc", topology.devices["cat-1"], "source", capture_filter),
            CaptureStrategy("ethanalyzer", topology.devices["nx-1"], "midpoint", capture_filter),
            CaptureStrategy("epc", topology.devices["cat-2"], "destination", capture_filter),
        ),
        impact=PlanImpact("low", "Native filtered on-box capture only."),
    )


def _demo_topology() -> TopologyGraph:
    topology = TopologyGraph()
    topology.add_device(Device("cat-1", "cat-1", "iosxe-switch", "ios-xe", "17.9", "192.0.2.1"))
    topology.add_device(Device("nx-1", "nx-1", "nxos", "nx-os", "10.2", "192.0.2.2"))
    topology.add_device(Device("cat-2", "cat-2", "iosxe-switch", "ios-xe", "17.9", "192.0.2.3"))
    topology.add_device(
        Device("wlc-9800-a", "WLC-9800-A", "iosxe-wlc", "ios-xe-wireless", "17.9", "192.0.2.10")
    )
    topology.add_device(
        Device("edge-sw-3f", "EdgeSw-3F", "iosxe-switch", "ios-xe", "17.9", "192.0.2.11")
    )
    topology.add_link(Link("cat-1", "Gi1/0/1", "nx-1", "Eth1/1", "cdp"))
    topology.add_link(Link("nx-1", "Eth1/2", "cat-2", "Gi1/0/1", "cdp"))
    topology.add_link(Link("edge-sw-3f", "Gi1/0/24", "wlc-9800-a", "Te0/0/0", "lldp"))
    return topology


def _demo_wireless_inventory() -> WirelessInventory:
    return WirelessInventory(
        controllers={
            "wlc-9800-a": WirelessController(
                "wlc-9800-a", "WLC-9800-A", "192.0.2.10", "active", "17.9"
            )
        },
        aps={
            "AP-3F-North": AccessPoint(
                "AP-3F-North",
                "wlc-9800-a",
                True,
                "edge-sw-3f",
                "Gi1/0/24",
                1,
                "5 GHz",
                36,
                80,
                client_count=4,
            ),
            "AP-3F-South": AccessPoint(
                "AP-3F-South",
                "wlc-9800-a",
                True,
                "edge-sw-3f",
                "Gi1/0/23",
                1,
                "5 GHz",
                40,
                80,
                client_count=11,
            ),
        },
        wlans={"corp-secure": WlanProfile("corp-secure", "corp-policy", 120, "flex-local")},
        client_bindings={"aa:bb:cc:11:22:33": ("AP-3F-North", "corp-secure")},
    )
