# MultiCap — Architecture

> **Architecture Specification**

| Field | Value |
|---|---|
| **Project** | MultiCap — Cisco Multi-Platform Synchronized Packet Capture Orchestrator |
| **Document** | architecture.md |
| **Version** | 1.1 (DRAFT) |
| **Date** | 2026-09-10 |
| **Changelog** | v1.1 — Stack pivot per [ADR-001](./stack-decision.md): Electron/TS/Node → PySide6/Python. §4 collapses renderer+main into a single Qt process; §5–§7 restated in Python; §12 secure-store via `keyring`; §13 packaging via PyInstaller; §14 stack table replaced; §17 driver contract restated as Python entry points; §20 closes items answered by ADR-001. |
| **Owner** | Lakshmi Ganesh Kondaveeti — Technical Consulting Engineering Technical Leader |
| **Derived from** | [problemStatement.md](./problemStatement.md) v2.0 |
| **Governed by** | [stack-decision.md](./stack-decision.md) (ADR-001) |

---

## Table of Contents

1. [Architectural Goals & Non-Goals](#1-architectural-goals--non-goals)
2. [Guiding Principles](#2-guiding-principles)
3. [System Context](#3-system-context)
4. [High-Level Architecture](#4-high-level-architecture)
5. [Layered View](#5-layered-view)
6. [Component Breakdown](#6-component-breakdown)
7. [Data Model & Domain Objects](#7-data-model--domain-objects)
8. [Key Workflows](#8-key-workflows)
9. [Capture Domain Abstractions](#9-capture-domain-abstractions)
10. [Synchronization & Clock Alignment](#10-synchronization--clock-alignment)
11. [Safety, Guardrails & Cleanup State Machine](#11-safety-guardrails--cleanup-state-machine)
12. [Security Architecture](#12-security-architecture)
13. [Cross-Platform Packaging](#13-cross-platform-packaging)
14. [Technology Stack](#14-technology-stack)
15. [Deployment View](#15-deployment-view)
16. [Observability, Logging & Audit](#16-observability-logging--audit)
17. [Extensibility Model](#17-extensibility-model)
18. [Testing & Validation Strategy](#18-testing--validation-strategy)
19. [Risk-to-Architecture Traceability](#19-risk-to-architecture-traceability)
20. [Open Questions](#20-open-questions)

---

## 1. Architectural Goals & Non-Goals

### 1.1 Goals

- **Uniform orchestration** over heterogeneous Cisco capture mechanisms (EPC, `ethanalyzer`, SPAN/RSPAN, ERSPAN, PEEKREMOTE, AP sniffer mode, radioactive tracing).
- **Deterministic safety**: guarantee zero residual state on any managed device under all termination paths (normal, abort, crash, network loss).
- **Sub-500 ms arming skew** across ≥ 20 heterogeneous endpoints.
- **Three-domain correlation** (wired, CAPWAP, over-the-air) into a single pcapng with < 10 ms alignment error.
- **Cross-platform desktop delivery** (Windows, macOS, Linux) from a single CI pipeline.
- **Release-aware, plugin-driven** platform support that survives Cisco CLI drift.

### 1.2 Non-Goals

- No continuous monitoring, IDS/NDR, spectrum analysis, or site survey capabilities.
- No line-rate lossless capture guarantees — surface punt-path limits, do not hide them.
- No replacement for Wireshark analysis; produce Wireshark-compatible artifacts instead.
- No AireOS controller support in the initial release.

---

## 2. Guiding Principles

1. **Safety over completeness.** Refuse unsafe operations (unfiltered `ethanalyzer`, sniffer-mode without consent).
2. **Explicit coverage reporting.** A gap declared is better than a silent gap.
3. **Reversibility by construction.** Every device-side change carries a compensating action; every action is journaled.
4. **Platform ignorance in the core.** The orchestrator core talks to `CaptureDriver` interfaces only; platform quirks live in plugins.
5. **Time is a first-class citizen.** Every packet carries a device, domain, and computed clock-offset annotation.
6. **Least privilege, least impact.** Headers-only default, minimal filter, minimal blast radius, minimal AP disruption.
7. **Failure is expected.** Session crashes, SSO switchovers, and lost sessions have first-class recovery paths.

---

## 3. System Context

```
┌──────────────────────────────────────────────────────────────────────┐
│                      MultiCap Desktop Application                    │
│                    (Windows / macOS / Linux)                         │
└─────────────┬──────────────────────────────────────┬─────────────────┘
              │                                      │
              │ SSH / NETCONF / SNMP / RESTCONF      │ ERSPAN GRE 0x88BE
              │ SCP (pull)                           │ PEEKREMOTE (UDP)
              ▼                                      ▼
┌──────────────────────────┐              ┌──────────────────────────┐
│  Cisco Managed Devices   │              │  Built-in Collectors     │
│  • Catalyst 9000 (IOS-XE)│              │  • ERSPAN listener       │
│  • Catalyst 9800 WLC     │              │  • PEEKREMOTE listener   │
│  • ASR/ISR/Cat8k         │              │  • Local NIC (libpcap)   │
│  • Classic IOS           │              └──────────────────────────┘
│  • IOS-XR (ASR9k)        │
│  • NX-OS (Nexus)         │              ┌──────────────────────────┐
│  • APs (local/flex/      │              │  Optional Inventory Src  │
│    fabric/sniffer)       │◄────────────►│  • Catalyst Center / DNAC│
└──────────────────────────┘              │  • Prime, NSO            │
              ▲                            │  • Nexus Dashboard, APIC │
              │ NTP                        └──────────────────────────┘
              │
      ┌───────┴───────┐
      │  NTP Source   │
      └───────────────┘
```

---

## 4. High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│              PRESENTATION LAYER (PySide6 / Qt Widgets)                   │
│   Discovery UI │ Intent Builder │ Plan Review │ Live Run │ Timeline UI   │
│              (multicap.app.widgets, multicap.app.viewmodels)             │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │ Qt signals / slots (in-process)
┌──────────────────────────────────▼───────────────────────────────────────┐
│              APPLICATION LAYER (multicap.core, single process)           │
│  ┌────────────────┐ ┌────────────────┐ ┌────────────────┐ ┌───────────┐  │
│  │ Session        │ │ Capture Intent │ │ Plan           │ │ Job       │  │
│  │ Manager        │ │ Compiler       │ │ Generator      │ │ Runner    │  │
│  └────────────────┘ └────────────────┘ └────────────────┘ └───────────┘  │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────────────────┐
│                         ORCHESTRATION CORE                               │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌──────────────┐  │
│  │ Discovery &   │ │ Capability    │ │ Synchronizer  │ │ Cleanup /    │  │
│  │ Topology      │ │ Registry      │ │ (Arm/Trigger) │ │ State Mgr    │  │
│  └───────────────┘ └───────────────┘ └───────────────┘ └──────────────┘  │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌──────────────┐  │
│  │ Path Solver   │ │ Safety Gate   │ │ Clock Aligner │ │ Correlator   │  │
│  │ (Wired+WLAN)  │ │ (Preflight)   │ │ (Beacons+RTT) │ │ (CAPWAP/OTA) │  │
│  └───────────────┘ └───────────────┘ └───────────────┘ └──────────────┘  │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────────────────┐
│                       DEVICE ABSTRACTION LAYER                           │
│  CaptureDriver contract → plugin per {platform × os-family × release}    │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────────┐   │
│  │IOS-XE  │ │IOS-XE  │ │IOS-XR  │ │Classic │ │NX-OS   │ │Cat9800 WLC │   │
│  │Switch  │ │Router  │ │        │ │IOS     │ │        │ │+ AP Driver │   │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────────┘   │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────────────────┐
│                 TRANSPORT & I/O LAYER (multicap.transport)               │
│  Netmiko SSH pool │ ncclient (post-v1) │ PySNMP (post-v1) │ SCP          │
│  ERSPAN listener  │ PEEKREMOTE listener │ QThreadPool + QSemaphore caps  │
└──────────────────────────────────┬───────────────────────────────────────┘
                                   │
┌──────────────────────────────────▼───────────────────────────────────────┐
│              STORAGE / PERSISTENCE LAYER (multicap.persistence)          │
│  Secure Credential Store │ Session Journal │ pcapng Store │ Audit Log    │
│  (Python `keyring`)         (SQLite WAL)      (on-disk)     (append-only)│
└──────────────────────────────────────────────────────────────────────────┘
```

> All layers execute inside **one PySide6 process**. The renderer/main split from
> v1.0 (Electron) is dissolved; UI code and orchestration code share the same
> Python interpreter and communicate via Qt signals/slots. Long-running blocking
> work (Netmiko sessions, file I/O, pyo3 correlator calls) runs on
> `QThreadPool` workers so the Qt event loop stays responsive.

---

## 5. Layered View

| Layer | Python namespace | Responsibility | Isolation |
|---|---|---|---|
| **Presentation** | `multicap.app.widgets`, `multicap.app.viewmodels` | Rendering UI, user input, review, live status. Qt Widgets + qt-material theme. | No device I/O, no crypto keys. |
| **Application** | `multicap.core` | Session lifecycle, intent compilation, job dispatch. | No CLI syntax knowledge. |
| **Orchestration Core** | `multicap.core` (submodules: `discovery`, `planner`, `synchronizer`, `cleanup`, `clock`, `correlator_facade`) | Discovery, planning, safety, timing, correlation. Talks only to `CaptureDriver`. | Platform-agnostic. |
| **Device Abstraction** | `multicap.drivers.<platform>` | Platform plugins implementing `CaptureDriver` (registered via `multicap.drivers` entry-point group). | Owns all CLI/NETCONF quirks. |
| **Transport & I/O** | `multicap.transport`, `multicap.collectors` | Connection pooling (Netmiko), stream listeners (ERSPAN, PEEKREMOTE), SCP file transfer. Concurrency via `QThreadPool` + `QSemaphore`. | No business logic. |
| **Persistence** | `multicap.persistence` | Credentials (`keyring`), journals, artifacts, audit (SQLite WAL). | No network I/O. |
| **Correlator (native)** | `multicap.correlator_rs` (Rust crate via **pyo3**) | CAPWAP decap, clock-offset apply, pcapng merge. | Pure computation; no I/O beyond files. |

---

## 6. Component Breakdown

### 6.1 Discovery & Topology Service
- Executes seed-based CDP/LLDP crawls (bounded by hop-limit + CIDR allow-list).
- SNMP fingerprinting (`sysObjectID`, `ENTITY-MIB`, `LLDP-MIB`).
- Optional inventory ingest adapters: Catalyst Center, Prime, NSO, Nexus Dashboard, APIC.
- Emits typed `Device`, `Link`, `WirelessTopology`, `ClientLocation` records into the graph store.
- **Wireless-specific**: resolves controllers + HA role, AP inventory, AP↔switch attachment, radio/channel, WLAN + policy profile, **per-WLAN switching mode**.

### 6.2 Capability Registry
- Release-aware, version-pinned catalog of platform capabilities.
- Keyed by `{platform, os_family, release_train, feature}`.
- Backed by a **golden-CLI-output regression suite** in CI (mitigates R-1).
- Answers questions like: *"Does Cat 9300 17.9.4 support EPC on a SVI with `match ipv6-acl`?"*

### 6.3 Capture Intent Compiler
Accepts one of:
- **Path intent** `{src, dst, protocol, port, duration}`, or
- **Wireless client intent** `{client_mac, duration}`.

Emits an abstract `CaptureIntent` normalized against topology + capability registry.

### 6.4 Path Solver
- L2/L3 path computation between endpoints.
- Extends the wired path with the wireless segment: AP → CAPWAP tunnel endpoints → WLC → wired uplink.
- Detects **FlexConnect local switching** and **fabric-enabled wireless** and redirects the capture plan to the correct enforcement point (mitigates R-6).

### 6.5 Plan Generator
For each device on the resolved path, selects a `CaptureStrategy` in ranked order:
1. Native on-box (EPC, `ethanalyzer` **with mandatory filter**),
2. ERSPAN → built-in collector,
3. Local SPAN → designated capture host,
4. **Explicit coverage-gap declaration**.

Outputs a `CapturePlan` containing per-device strategy, filters, buffer sizing, blast radius estimate, and service-impact declaration.

### 6.6 Safety Gate
Pre-flight checks executed against every device in the plan:
- CPU / memory / flash headroom,
- Existing SPAN session count,
- Controller redundancy state (HA SSO active/standby),
- AP client count (for sniffer candidacy),
- Filter presence (blocks unfiltered NX-OS).

Blocks plan execution on any failing gate. Records rationale into the session journal.

### 6.7 Synchronizer
- Maintains persistent SSH channels pre-armed for the trigger phase.
- Two trigger modes:
  - **Coordinated remote trigger** — orchestrator sends `start` in parallel across pre-armed sessions.
  - **NTP-anchored EEM / scheduler mode** — device-side scheduled start at an absolute epoch for < 100 ms LAN skew.
- Coordinates stream captures (PEEKREMOTE, ERSPAN) with file captures (EPC, ethanalyzer) into a single window.

### 6.8 Cleanup / State Manager
- Journaled state machine (SQLite WAL) tracking every device-side mutation with a compensating action.
- Device-side **dead-man timer** installed on arm (EEM applet or equivalent) that force-stops captures and reverts config if the controlling session is lost.
- Crash recovery replays the journal on next launch and completes pending compensations before allowing new work.
- **Post-run diff assertion** compares pre-capture and post-capture `show running-config` + AP mode state; a non-empty diff blocks the "complete" state (mitigates R-4).

### 6.9 Job Runner
- Owns end-to-end lifecycle of one `Job`: arm → trigger → observe → stop → collect → correlate → report → cleanup.
- Publishes structured progress events to the UI.
- HA SSO switchover during a job is treated as **session-invalidating** with clear user surface (C-7).

### 6.10 Clock Aligner
- Injects **beacon frames** into each capture stream at known emission times.
- Reads each device's clock with RTT compensation before and after the capture window.
- Computes a per-device offset function and annotates every packet on ingest.

### 6.11 Correlator
- Ingests all pcap/pcapng artifacts + stream captures into a unified pcapng.
- **CAPWAP decapsulation** — retains both outer and inner views, links them via a shared correlation ID.
- Hop-by-hop packet correlation across wired, CAPWAP, and 802.11 domains.
- Fuses **radioactive-trace** output onto the same timeline.
- Emits the **ladder diagram** and fault-localization verdict.

### 6.12 Reporter
- Merged pcapng (Wireshark-compatible).
- Evidence report (HTML + PDF) with ladder diagram, per-hop latency, drop-point, association/auth exchange state.
- Exportable audit bundle.

---

## 7. Data Model & Domain Objects

Core aggregate types. Runtime representation: **pydantic v2** models (external
boundaries — inventory ingest, journal I/O, driver contract payloads) and
**`@dataclass(slots=True, frozen=True)`** value objects (internal orchestration
state). All types live under `multicap.core.models`.

```python
from __future__ import annotations
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal
from pydantic import BaseModel

Platform = Literal[
    "IOS-XE-SW", "IOS-XE-RT", "IOS-XE-WLC",
    "IOS", "IOS-XR", "NX-OS", "AP",
]

class CapabilityMatrix(BaseModel):
    # release-pinned feature flags; populated by Capability Registry
    features: dict[str, bool]
    release_train: str

class Device(BaseModel):
    id: str
    mgmt_address: str
    platform: Platform
    os_release: str
    role: Literal["active", "standby"] | None = None   # HA SSO
    capabilities: CapabilityMatrix

class AccessPoint(BaseModel):
    id: str
    name: str
    mode: Literal["local", "flex", "fabric", "sniffer"]
    controller_id: str

class Wlan(BaseModel):
    ssid: str
    profile: str
    switching_mode: Literal["central", "flex-local", "fabric"]

class WirelessTopology(BaseModel):
    controllers: list[Device]
    aps: list[AccessPoint]
    wlans: list[Wlan]

class ClientLocation(BaseModel):
    client_mac: str
    ap: AccessPoint
    radio: Literal["2.4", "5", "6"]
    band: str
    channel: int
    controller: Device
    wlan: Wlan
    switching_mode: Literal["central", "flex-local", "fabric"]
    vlan: int | None = None
    wired_uplink_port: str | None = None

# CaptureIntent — discriminated union via pydantic
class PathIntent(BaseModel):
    kind: Literal["path"] = "path"
    src: "Endpoint"
    dst: "Endpoint"
    protocol: str | None = None
    port: int | None = None
    duration: timedelta

class ClientIntent(BaseModel):
    kind: Literal["client"] = "client"
    client_mac: str
    duration: timedelta

CaptureIntent = PathIntent | ClientIntent

# CaptureStrategy — one dataclass per kind; discriminated on `.kind`
@dataclass(slots=True, frozen=True)
class EpcStrategy:
    kind: Literal["epc"] = "epc"
    filter: "Acl"; iface: str; snap: int; buf_mb: int

@dataclass(slots=True, frozen=True)
class EthanalyzerStrategy:
    kind: Literal["ethanalyzer"] = "ethanalyzer"
    filter: "Filter"; snap: int          # filter MANDATORY

@dataclass(slots=True, frozen=True)
class SpanStrategy:
    kind: Literal["span"] = "span"
    source: list["Port"]; dest: "Port"

@dataclass(slots=True, frozen=True)
class ErspanStrategy:
    kind: Literal["erspan"] = "erspan"
    source: list["Port"]; collector_id: str

@dataclass(slots=True, frozen=True)
class CapwapInnerStrategy:
    kind: Literal["capwap-inner"] = "capwap-inner"
    inner_filter: "Acl"

@dataclass(slots=True, frozen=True)
class ApSnifferStrategy:
    kind: Literal["ap-sniffer"] = "ap-sniffer"
    ap: AccessPoint; band: str; channel: int; width: int
    consent: "ConsentRecord"

@dataclass(slots=True, frozen=True)
class RadioactiveTraceStrategy:
    kind: Literal["radioactive-trace"] = "radioactive-trace"
    scope: Literal["client", "ap"]

@dataclass(slots=True, frozen=True)
class CoverageGap:
    kind: Literal["coverage-gap"] = "coverage-gap"
    reason: str

CaptureStrategy = (
    EpcStrategy | EthanalyzerStrategy | SpanStrategy | ErspanStrategy
    | CapwapInnerStrategy | ApSnifferStrategy | RadioactiveTraceStrategy
    | CoverageGap
)

class CapturePlan(BaseModel):
    job_id: str
    per_device: list[tuple[Device, CaptureStrategy]]
    blast_radius: "BlastRadius"
    service_impact: "ServiceImpact"
    coverage_gaps: list[CoverageGap]

class JournalEntry(BaseModel):
    ts: str
    job_id: str
    device_id: str
    action: Literal["apply", "revert"]
    payload: dict
    compensating: "JournalEntry | None" = None
```

---

## 8. Key Workflows

### 8.1 Wireless-client capture (flagship, three-domain)

```
User enters client MAC
        │
        ▼
Discovery ── ClientLocation resolved (AP, radio, channel, WLC, switching mode, VLAN, uplink)
        │
        ▼
Path Solver ── produces {AP, CAPWAP endpoints, WLC, wired uplink, wired path to target}
        │
        ▼
Plan Generator ── per-device CaptureStrategy:
    • AP-sniffer (over-the-air)         ── requires explicit consent
    • WLC CAPWAP-inner (encap traffic)  ── EPC with CAPWAP inner filter
    • WLC radioactive-trace (control)
    • Cat9k switch uplink EPC (wired)
        │
        ▼
Safety Gate ── health checks + sniffer AP candidacy + HA state
        │
        ▼
User Review ── shows blast radius, service impact (AP client count!), coverage gaps
        │
        ▼
Synchronizer ── pre-arm all sessions, install dead-man timers
        │
        ▼
Trigger (parallel; NTP-anchored EEM if precision mode)
        │
        ▼
Observe → Stop → SCP pull → local collectors flush
        │
        ▼
Clock Aligner ── beacons + RTT-compensated device clock offsets
        │
        ▼
Correlator ── CAPWAP decap, hop-by-hop merge, radioactive-trace fusion
        │
        ▼
Reporter ── ladder diagram + fault verdict + pcapng
        │
        ▼
Cleanup / State Manager ── revert all changes, restore AP mode, diff assertion
```

### 8.2 Path capture (wired only)

Same shape, minus wireless components: Path Solver returns pure L2/L3 hops; per-device strategies limited to EPC / ethanalyzer / SPAN / ERSPAN.

### 8.3 Crash recovery

On startup:
1. Read journal; identify jobs in state ≠ `terminal`.
2. For each pending mutation, execute the compensating action (revert capture config, restore AP mode).
3. Verify via configuration + AP state diff.
4. Only then accept new jobs.

---

## 9. Capture Domain Abstractions

Three domains, three ingress paths, one output:

| Domain | Ingress | Normalization |
|---|---|---|
| **Wired** | pcap/pcapng SCP-pulled from device (EPC), or ERSPAN GRE 0x88BE / SPAN into local collector | Transcode to pcapng; annotate with device, interface, mechanism, clock offset. |
| **CAPWAP tunnel** | Wired capture that happens to contain CAPWAP outer frames (UDP 5246/5247) | Decapsulate, generate correlated inner view, retain both. |
| **Over-the-air (802.11)** | AP in sniffer mode streaming PEEKREMOTE UDP to built-in listener | Strip PEEKREMOTE header → 802.11 pcapng; annotate with radio, channel, width. |

---

## 10. Synchronization & Clock Alignment

- **Arming skew target**: < 500 ms across ≥ 20 endpoints; < 100 ms on LAN with EEM/scheduler mode.
- **Mechanism**:
  - Persistent SSH channels pre-armed with capture config staged (not started).
  - Trigger phase issues `start` in parallel across the connection pool.
  - Precision mode: install EEM applet or `kron` scheduler on each device targeting an absolute NTP-anchored epoch.
- **Clock alignment**:
  - Inject known **beacon frames** at coordinated moments visible across as many capture points as possible.
  - Read device clock with RTT compensation immediately before and after the capture window.
  - Compute a linear offset function per device; annotate pcapng packet metadata on ingest.
  - Target error < 10 ms post-correction (SC-4).

---

## 11. Safety, Guardrails & Cleanup State Machine

### 11.1 Preventive guardrails

- **Mandatory filters** on `ethanalyzer` (refuse otherwise).
- **Pre-flight health gates** (CPU, memory, flash, SPAN sessions, HA state).
- **Hard caps** on duration, buffer, packet count.
- **Headers-only snap length** by default; full-payload requires explicit consent + audit entry.
- **Sniffer consent modal**: shows current client count on candidate AP, recommends least-impact AP, requires explicit acknowledgement.

### 11.2 Cleanup state machine

```
    ┌───────┐  arm   ┌───────┐ trigger ┌────────┐  stop  ┌──────────┐
    │ IDLE  ├───────►│ ARMED ├────────►│ ACTIVE ├───────►│ STOPPED  │
    └───────┘        └───┬───┘         └───┬────┘        └────┬─────┘
                         │                 │                  │
                    fail │            fail │             collect│
                         ▼                 ▼                  ▼
                    ┌─────────────────────────────┐    ┌──────────────┐
                    │       COMPENSATING          │◄───┤  COLLECTED   │
                    └─────────────┬───────────────┘    └──────┬───────┘
                                  │                           │
                                  ▼                           ▼
                            ┌────────────┐              ┌───────────┐
                            │ VERIFIED   │◄─────────────┤ CORRELATED│
                            │ (diff OK)  │              └───────────┘
                            └─────┬──────┘
                                  ▼
                             ┌─────────┐
                             │ DONE    │
                             └─────────┘
```

- Every transition is journaled.
- **`VERIFIED`** requires a clean config diff + no APs left in sniffer mode.
- **`DONE`** is only reachable through `VERIFIED` (mitigates R-4).

---

## 12. Security Architecture

- **Credential storage**: OS-native secure store via the Python **`keyring`** library.
  - Windows → **DPAPI** (Credential Manager backend)
  - macOS → **Keychain** (`keyring.backends.macOS`)
  - Linux → **Secret Service** / **libsecret** (`keyring.backends.SecretService`)
- No plaintext credentials on disk, in logs, in memory dumps, or in the journal.
  Credentials are read from `keyring` on demand and held only inside Netmiko
  session objects; those objects are destroyed at session end.
- **Least privilege**: each device profile records the minimum privilege level required; escalation requires re-consent.
- **Lawful capture consent**: mandatory at first launch and before every full-payload or over-the-air capture. Consent records are immutable audit entries.
- **Immutable audit log**: append-only, hash-chained; records change ticket ID, consent, plan, results.
- **Retention limits**: user-configurable retention on stored pcapng and reports.
- **Signed binaries**: Windows Authenticode, macOS notarized, Linux `.deb` signed.
- **PySide6 LGPL compliance**: PyInstaller ships in **one-folder mode** so Qt shared libraries remain dynamically linked; one-file mode is prohibited without an LGPL re-review.

---

## 13. Cross-Platform Packaging

| OS | Artifact | Toolchain |
|---|---|---|
| Windows | Signed `.msi` (WiX / Inno Setup) wrapping a PyInstaller one-folder bundle | PyInstaller + `signtool` (Authenticode) |
| macOS | Notarized `.dmg` (universal2: arm64 + x86_64) wrapping a PyInstaller `.app` bundle | PyInstaller + `codesign` + `notarytool` |
| Ubuntu | `.deb` (via `fpm` or `dpkg-deb`) + AppImage | PyInstaller + `dpkg-sig` |

All artifacts produced from a **single CI pipeline** (SC-10). Reproducible builds; artifact SBOM published per release.

---

## 14. Technology Stack

> **Governed by [ADR-001](./stack-decision.md).** The table below is the
> authoritative summary; see the ADR for rationale, alternatives, and
> licensing notes.

| Concern | Choice | Notes |
|---|---|---|
| Shell / UI toolkit | **PySide6 (Qt 6.x, LGPL)** with **Qt Widgets** | Widgets over QML for v1 (density-first). |
| Application language | **Python 3.12+** | Single language across UI, orchestration, drivers. |
| UI theming | **qt-material** | Material Design tokens as pure QSS. |
| Topology rendering | **QGraphicsScene** + **NetworkX** (layout only) | Native scene graph; NetworkX for algorithms. |
| Ladder diagram | **QGraphicsScene** + custom `QGraphicsItem` subclasses | Export SVG via `QSvgGenerator`. |
| SSH transport | **Netmiko** (built on Paramiko) | Cisco-idiomatic; TextFSM/NTC integration. |
| Structured transport | **ncclient** (NETCONF), **PySNMP** (SNMP) — **post-v1** | Deferred; SSH covers v1 scope. |
| CLI parsing | **TextFSM + NTC Templates** | Golden-CLI fixture format. |
| Concurrency | `QThreadPool` + `QSemaphore` for Netmiko; **qasync** where asyncio needed | Netmiko is synchronous; per-platform caps enforced (SC-04). |
| Persistence | **SQLite (WAL mode)** via stdlib `sqlite3` | Journal, session state, audit log. |
| Secure storage | **Python `keyring`** | OS keychain: DPAPI / Keychain / Secret Service. |
| Correlator | **Rust** crate via **pyo3** bindings (built with `maturin`) | CAPWAP decap, clock-offset apply, pcapng merge. |
| Data models | **pydantic v2** + **dataclasses** | External boundaries + internal value objects. |
| Localization | **Qt Linguist** (`.ts` / `.qm`) | en-US only for v1. |
| Accessibility | **QAccessible** interfaces | WCAG 2.1 AA target. |
| UI testing | **pytest-qt** | Replaces Playwright. |
| Unit / property testing | **pytest** + **hypothesis** | Replaces vitest/jest. |
| Integration testing | **containerlab** / **CML** driven from pytest | Unchanged from v1.0. |
| Packaging | **PyInstaller** one-folder + OS installer (`.dmg` / `.msi` / `.deb`) | LGPL requires one-folder (dynamic linking). |
| Env / lockfile | **`uv`** | Fast, reproducible Python environments. |
| Lint / format / type-check | **`ruff`**, **`ruff format`**, **`mypy --strict`** | CI-gated. |

---

## 15. Deployment View

- Single-binary desktop application; no server components.
- Optional inventory adapters reach out to Cisco management systems (DNAC, Prime, NSO, Nexus Dashboard, APIC) over HTTPS with user-provided credentials.
- Built-in collectors bind to local NICs; ERSPAN listener requires a routable IPv4/IPv6 address and firewall permit for GRE 0x88BE; PEEKREMOTE listener requires UDP port permit.
- No telemetry sent off-box by default. Optional anonymized crash reports opt-in only.

---

## 16. Observability, Logging & Audit

- **Structured logs** (JSON) with per-job correlation IDs.
- **Session journal** (SQLite) — every device mutation + compensating action.
- **Immutable audit log** — consent, plans, results, hash-chained.
- **Per-capture drop / truncation counters** captured from devices and rendered prominently in the report (mitigates R-2).
- **Live status stream** to the UI: per-device state, current phase, elapsed time, health.

---

## 17. Extensibility Model

- **`CaptureDriver` protocol** — every platform plugin implements the same Python `Protocol`:
  ```python
  from typing import Protocol
  from multicap.core.models import (
      Device, CapabilityMatrix, CaptureIntent, CaptureStrategy,
      ArmToken, StopResult, Artifact,
  )

  class CaptureDriver(Protocol):
      supported_releases: tuple[str, ...]      # release-train predicates

      def probe_capabilities(self, device: Device) -> CapabilityMatrix: ...
      def build_strategy(
          self, intent: CaptureIntent, device: Device,
      ) -> CaptureStrategy: ...
      def arm(self, strategy: CaptureStrategy, session) -> ArmToken: ...
      def trigger(self, token: ArmToken) -> None: ...
      def stop(self, token: ArmToken) -> StopResult: ...
      def collect(self, result: StopResult) -> Artifact: ...
      def revert(self, token: ArmToken) -> None: ...
  ```
- Plugins are **release-aware** via `supported_releases` predicates; the
  Capability Registry routes calls accordingly.
- Plugins register via the **`multicap.drivers`** setuptools entry-point group,
  so third-party drivers can ship as separate PyPI wheels without forking the
  orchestration core.
- New platforms (e.g., future AireOS support, non-Cisco NOS) are added as new
  drivers without touching the core.

---

## 18. Testing & Validation Strategy

| Layer | Test Type | Environment |
|---|---|---|
| Driver CLI parsers | **Golden-output regression** | Recorded show/debug outputs per release train (R-1 mitigation). |
| Drivers | **Contract tests** against `CaptureDriver` interface | Mock transport. |
| Orchestration core | Unit + property tests | Local. |
| End-to-end wired | Integration | **Cisco Modeling Labs / containerlab** topology. |
| End-to-end wireless | Integration | Physical mini-lab: Cat 9800 + 2 APs + Cat 9300 + client. |
| Fault localization | **Seeded fault scenarios** (SC-8) | Lab; ≥ 10 wireless onboarding/roaming. |
| Cleanup guarantees | **Chaos tests** — kill app mid-capture, cut network | Journal replay assertion. |
| Cross-platform packaging | Smoke install + launch | Windows, macOS, Linux CI runners. |

---

## 19. Risk-to-Architecture Traceability

| Risk | Mitigating Component(s) |
|---|---|
| **R-1** CLI drift | Capability Registry + golden-output regression + release-pinned drivers. |
| **R-2** Punt-path loss misread | Reporter surfaces device drop/truncation counters alongside captures. |
| **R-3** Guardrail failure | Safety Gate + hard caps + device-side dead-man timers + staged rollout. |
| **R-4** Residual config / stranded sniffer AP | Cleanup State Manager + journal + post-run diff assertion + crash-time replay. |
| **R-5** ERSPAN/PEEKREMOTE blocked | Plan Generator emits explicit coverage-gap declarations. |
| **R-6** FlexConnect / fabric mode misleading | Path Solver's switching-mode detection redirects capture plan. |
| **R-7** Wrong channel OTA capture | Pre-capture channel confirmation from live client state + multi-AP/channel option + pre-flight summary. |
| **R-8** Third-party wireless privacy | Consent gates + headers-only default + immutable audit + retention limits. |

---

## 20. Open Questions

Items 1–2 from v1.0 are **closed by [ADR-001](./stack-decision.md)**:

- ~~**Rust vs C++ vs pure-Node** for the correlator hot path~~ — **Closed.**
  Rust via pyo3 (see ADR §3.3).
- ~~**Node runtime baseline / Electron version**~~ — **Closed.** Node/Electron
  removed entirely.

Remaining open questions:

1. **Bundling Wireshark's `editcap`/`mergecap`** vs re-implementing merge natively in the Rust correlator — licensing and update-surface tradeoff.
2. **PEEKREMOTE listener sizing** — thread-per-AP (`QThreadPool` workers) vs shared `asyncio` reactor (via `qasync`) for ≥ 4 concurrent sniffer APs.
3. **EEM applet cleanup on IOS-XR** — confirm applet syntax + revert path parity with IOS-XE.
4. **Inventory adapter authentication** — support token-based (DNAC OAuth) as first-class or defer.
5. **HA SSO switchover UX** — automatic re-plan on the new active vs hard-abort the job.
6. **`maturin` build in CI** — cross-compile the pyo3 wheel for all three OSes on a single runner via `cibuildwheel`, or use per-OS runners; decision pending Phase 0 spike.

---

*End of document — traceable to [problemStatement.md](./problemStatement.md) v2.0.*
