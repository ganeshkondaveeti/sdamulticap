# MultiCap — Cisco Multi-Platform Synchronized Packet Capture Orchestrator

> **Problem Statement (Detailed, Step-by-Step)**

| Field | Value |
|---|---|
| **Project** | MultiCap — Cisco Multi-Platform Synchronized Packet Capture Orchestrator |
| **Document** | problemStatement.md |
| **Version** | 2.0 (DRAFT) — adds Catalyst 9800 Wireless LAN Controller scope |
| **Date** | 2026-09-09 |
| **Owner** | Lakshmi Ganesh Kondaveeti — Technical Consulting Engineering Technical Leader |
| **Supersedes** | v1.0 |
| **Source** | [problemStatement.txt](./problemStatement.txt) |

---

## Table of Contents

1. [Problem Statement](#1-problem-statement)
2. [Impact of the Problem](#2-impact-of-the-problem)
3. [Objective](#3-objective)
4. [Scope — In Scope](#4-scope--in-scope)
5. [Scope — Out of Scope](#5-scope--out-of-scope)
6. [Target Users](#6-target-users)
7. [Success Criteria](#7-success-criteria)
8. [Key Constraints and Assumptions](#8-key-constraints-and-assumptions)
9. [Primary Risks](#9-primary-risks)
10. [Definition of Done (Initial Release)](#10-definition-of-done-initial-release)

---

## 1. Problem Statement

Network engineers troubleshooting **packet loss, latency, misrouting, onboarding failures, or protocol errors** across enterprise and service-provider networks built from Cisco **IOS-XE Catalyst 9000 switches**, **Catalyst 9800 Wireless LAN Controllers**, **classic Cisco IOS devices**, **ASR/ISR routers**, and **Nexus (NX-OS) switches** have **no unified way to capture traffic at multiple points in the network at the same time**.

### 1.1 Why the platforms cannot be treated uniformly

Each Cisco operating system exposes a **different, mutually incompatible capture mechanism**:

| Platform Family | On-box Capture Mechanism | Data-Plane Visibility |
|---|---|---|
| IOS-XE / IOS-XR | Embedded Packet Capture (EPC) | Native |
| Classic Catalyst L2 | *None* | Requires SPAN / RSPAN |
| NX-OS (Nexus) | `ethanalyzer` — **control-plane only** (CPU-punted) | Requires SPAN / ERSPAN |

> ⚠️ `ethanalyzer` without a capture filter is a **supervisor-CPU risk** and must never be run unfiltered against production Nexus devices.

### 1.2 Three capture domains that must be reconciled

Adding wireless makes the problem **qualitatively harder**, not merely broader. Three distinct capture domains must be reconciled simultaneously:

1. **Wired domain** — conventional frames on switch and router interfaces.
2. **CAPWAP tunnel domain** — in central-switching mode, wireless client traffic traverses the wired network encapsulated in CAPWAP (**UDP 5246** control, **UDP 5247** data). A capture taken anywhere between the AP and the Catalyst 9800 shows **only the tunnel, not the client traffic**, and is unusable without automated decapsulation and inner-flow correlation.
3. **Over-the-air (802.11) domain** — association, authentication, EAP exchange, key negotiation, retries, roaming, RSSI, and channel behavior are **invisible to every wired capture**. Observing them requires placing an AP into **sniffer mode**, which **removes that AP from service and disconnects its clients**, and which streams 802.11 frames to a remote listener using **PEEKREMOTE encapsulation** rather than writing a file.

### 1.3 Deployment modes break the "single wired path" assumption

Under **FlexConnect local switching** or **SD-Access fabric-enabled wireless**, client data traffic does **not traverse the Catalyst 9800 at all** — it is switched locally at the AP or VXLAN-tunneled to the fabric edge.

> A tool that captures on the controller and reports *"no traffic observed"* in these modes is **not merely unhelpful — it is actively misleading.**

### 1.4 The current manual workflow (step-by-step)

As a result, engineers today must:

1. **Manually determine** the switching mode and traffic path.
2. **Log in to each device individually.**
3. **Recall five or more different command syntaxes** across wired and wireless platforms.
4. **Start captures sequentially** — guaranteeing that no two captures cover the same instant of the same transient event.
5. **Manually transfer** capture files off each device.
6. **Manually decapsulate CAPWAP.**
7. **Manually correlate** an over-the-air capture against a wired capture against controller-side client debug output.
8. **Manually reconcile** capture files whose device clocks are not aligned.

This is **slow, error prone, frequently fails on the first attempt** because the event does not reoccur, and **leaves residual capture configuration**, ACLs, monitor sessions, and out-of-service sniffer-mode APs on production infrastructure when sessions are interrupted.

### 1.5 What no existing tool provides

No tool exists that:

- **(a)** Discovers the relevant Cisco wired and wireless devices and their switching modes.
- **(b)** Automatically selects the correct capture mechanism per platform and per capture domain.
- **(c)** Arms and triggers all captures near-simultaneously.
- **(d)** Enforces safety guardrails to protect production control planes and wireless service availability.
- **(e)** Guarantees removal of all temporary device configuration and restoration of all AP operating modes.
- **(f)** Returns a **single time-aligned, cross-domain correlated packet set** that localizes the fault to a specific device, interface, radio, or protocol exchange.

---

## 2. Impact of the Problem

- **Mean time to resolution (MTTR)** for intermittent, path-dependent, and client-specific faults is measured in **days**, because each capture attempt is a fresh manual coordination exercise.
- **Wireless client onboarding failures** are especially costly to diagnose because the failure evidence is split across **three capture domains that no engineer can currently capture simultaneously**.
- **Transient faults are routinely missed entirely** due to non-simultaneous capture.
- **Evidence quality is low**: unaligned timestamps and undecapsulated CAPWAP make merged captures unusable or actively misleading.
- **Production risk** is introduced by:
  - Unfiltered captures (Nexus supervisor CPU spikes),
  - Exhausted control-plane memory,
  - Oversubscribed SPAN destinations,
  - APs left in sniffer mode after a failed capture attempt.
- **Deep, per-platform expertise across both wired and wireless domains is required**, so the work **cannot be delegated to first-line operations staff**.

---

## 3. Objective

Deliver a **cross-platform desktop application** — distributed as:

| Operating System | Artifact |
|---|---|
| Microsoft Windows | Signed `.exe` |
| macOS | Signed **and notarized** `.dmg` |
| Ubuntu Linux | `.deb` **and** AppImage |

…that **discovers Cisco wired and wireless network devices** and **orchestrates safe, synchronized, multi-device, multi-domain packet captures**, returning a **single correlated, time-aligned capture set** with an **automated fault-localization verdict**.

### 3.1 Flagship capability

> **Given one wireless client MAC address**, the tool simultaneously captures:
> 1. Over-the-air 802.11 frames,
> 2. CAPWAP tunnel traffic,
> 3. Controller-side client state,
> 4. The wired forwarding path,
>
> …and presents them as **one correlated timeline**.

---

## 4. Scope — In Scope

### 4.1 Supported platform families

| Category | Platforms |
|---|---|
| **IOS-XE switching** | Catalyst 9200, 9300, 9400, 9500, 9600 |
| **IOS-XE wireless** | Catalyst 9800-L, 9800-40, 9800-80, 9800-CL, Embedded Wireless Controller on Catalyst 9000 switches (**including HA SSO pairs**) |
| **IOS-XE routing** | ASR 1000, ISR 4000, Catalyst 8000, CSR 1000v |
| **Classic Cisco IOS** | ISR G2, legacy Catalyst platforms |
| **IOS-XR** | ASR 9000 |
| **NX-OS** | Nexus 3000, 5000, 7000, 9000 |
| **Access points** | Cisco APs operating with a Catalyst 9800 controller, including **local, FlexConnect, fabric, and sniffer** modes |

### 4.2 Device and topology discovery (step-by-step)

1. **Seed-based CDP/LLDP topology crawl** with hop limit and CIDR allow-list.
2. **SNMP fingerprinting** (`sysObjectID`, `ENTITY-MIB`, `LLDP-MIB`).
3. **Inventory ingest** from Cisco Catalyst Center / DNA Center, Prime Infrastructure, NSO, Nexus Dashboard, and APIC where available.
4. **Subnet sweep** with SSH/NETCONF capability probing.
5. **Platform, OS family, and software release classification.**
6. **Wireless topology discovery:**
   - Controllers and HA role (active/standby),
   - AP inventory,
   - AP-to-switch attachment point,
   - Radio and channel assignment,
   - WLAN and policy profiles,
   - **Per-WLAN switching mode** (central switching, FlexConnect local switching, fabric-enabled).
7. **Client location resolution**: given a client MAC or IP, identify the associated AP, radio, band, controller, WLAN, VLAN, and wired uplink.
8. **L2/L3 path computation** between a source and destination, extended to include the wireless segment and CAPWAP tunnel endpoints.

### 4.3 Capture capability abstraction

- **Per-platform driver plugins** with a common contract.
- **Ranked strategy selection per device** (fallback order):
  1. Native on-box capture,
  2. ERSPAN to a built-in local collector,
  3. Local SPAN to a designated capture host,
  4. **Explicit declaration of a coverage gap.**
- **Catalyst 9800-specific mechanisms:**
  - Embedded Packet Capture on wired and wireless interfaces,
  - Control-plane capture,
  - **CAPWAP inner-filter capture** to match encapsulated client traffic directly,
  - AP packet capture profiles,
  - **Radioactive tracing** for per-client control-plane narrative.
- **Over-the-air capture:**
  - Orchestrated conversion of a selected AP to **sniffer mode** with explicit band, channel, and channel-width selection,
  - Built-in **PEEKREMOTE listener** to receive and store the 802.11 stream.
- **Explicit, prominent reporting of reduced coverage** wherever a device, domain, or switching mode cannot be captured.

### 4.4 Synchronized capture execution

- **Parallel pre-arming** of all capture points across persistent SSH sessions.
- **Single-instant trigger** with a target arming skew:
  - **< 500 ms** across all wired and wireless capture points,
  - **< 100 ms** on a local LAN.
- **Optional high-precision mode** using device-side EEM or scheduled tasks triggered at an absolute NTP-synchronized epoch.
- **Coordinated start of stream-based captures** (PEEKREMOTE, ERSPAN) alongside **file-based captures** (EPC, ethanalyzer) within the same capture window.

### 4.5 Safety, guardrails, and hygiene

- **Mandatory capture filters** — unfiltered NX-OS `ethanalyzer` captures **refused**.
- **Pre-flight health checks**: CPU, memory, flash space, existing SPAN session count, controller redundancy state, AP client count.
- **Service-impact gate for over-the-air capture**: converting an AP to sniffer mode requires a **separate, explicit, logged acknowledgement** that the AP will leave service and disconnect its clients; the tool must report the current client count and recommend the **least-impactful candidate AP**.
- **Hard caps** on duration, buffer size, and packet count; **headers-only snap length by default**.
- **Device-side dead-man timer** to force-stop captures and remove capture state if the controlling session is lost.
- **Guaranteed AP mode restoration**, including recovery on application restart after a crash, with verification that the AP has rejoined the controller and returned to service.
- **Detection of Catalyst 9800 HA SSO switchover during a capture**, treated as a **session-invalidating event** with clear user notification.
- **Post-run configuration and state diff** to verify zero residual configuration and zero residual sniffer-mode APs.
- **Change-ticket capture, lawful-capture consent acknowledgement, and an immutable local audit log.**

### 4.6 Collection, correlation, and output (step-by-step)

1. **Secure retrieval** of capture artifacts (**SCP pull**) with checksum verification and on-device cleanup.
2. **Built-in collectors**: ERSPAN (**GRE 0x88BE**), PEEKREMOTE, and optional local NIC capture.
3. **Normalization to pcapng** with per-interface metadata recording:
   - Device,
   - Interface or radio,
   - Capture domain,
   - Mechanism,
   - Computed clock offset.
4. **Automatic CAPWAP decapsulation** and correlation of inner client flows to their outer tunnel, with **both views retained**.
5. **Clock alignment** using injected beacon frames plus RTT-compensated device clock reads.
6. **Merge, de-duplication, and hop-by-hop packet correlation** across wired, CAPWAP, and over-the-air domains.
7. **Ladder-diagram timeline** showing the full client journey, per-hop latency, and drop-point localization, including 802.11 association and authentication exchange state.
8. **Correlation of radioactive trace output** against captured packets on a single timeline.
9. **Exportable evidence report** and **Wireshark-compatible artifacts**.

---

## 5. Scope — Out of Scope

- ❌ Continuous or always-on monitoring — this is an **on-demand diagnostic tool**.
- ❌ Intrusion detection, NDR, wireless intrusion prevention, or security analytics.
- ❌ Replacement for a dedicated packet broker or TAP aggregation infrastructure.
- ❌ Spectrum analysis, RF interference classification, or radio resource management tuning.
- ❌ Wireless site survey, coverage prediction, or capacity planning.
- ❌ Guaranteed line-rate, lossless capture — on-box mechanisms are **punt-path rate limited by design** and this limitation must be surfaced.
- ❌ Legacy **AireOS** wireless controllers in the initial releases.
- ❌ Non-Cisco network operating systems in the initial releases.
- ❌ Replacement of **Wireshark** as an analysis front end.

---

## 6. Target Users

| User | Primary Use Case |
|---|---|
| Network operations / NOC engineers | Live fault isolation |
| Wireless engineers | Diagnosing client onboarding, roaming, and performance complaints |
| TAC and Technical Consulting engineers | Gathering evidence for escalation |
| Network architects / validation engineers | Verifying designs and changes |
| Security and compliance teams | Authorized traffic inspection |

---

## 7. Success Criteria

| ID | Criterion |
|---|---|
| **SC-1** | Discover and correctly classify at least **95%** of reachable devices across all supported Cisco platform families, including controllers and APs, in a reference topology. |
| **SC-2** | Given a wireless client MAC, correctly resolve the associated AP, radio, band, controller, WLAN, switching mode, VLAN, and wired uplink in **≥ 95%** of cases. |
| **SC-3** | Arm and trigger simultaneous captures on **≥ 20 devices** spanning **≥ 2 capture domains**, with measured arming skew **< 500 ms**. |
| **SC-4** | Produce a single merged, time-aligned pcapng whose cross-device timestamp alignment error is **< 10 ms** after beacon-based correction, including alignment between over-the-air and wired captures. |
| **SC-5** | Automatically decapsulate CAPWAP and correctly associate **≥ 99%** of inner client flows with their outer tunnel. |
| **SC-6** | **Zero residual capture configuration** on any device, and **zero APs remaining in sniffer mode**, after normal completion, user abort, application crash, or network disconnection — verified by automated configuration and state diff. |
| **SC-7** | No device control-plane CPU sustained above an operator-defined threshold as a direct result of a tool-initiated capture. |
| **SC-8** | Correctly identify the fault location in **≥ 90%** of seeded fault scenarios in the validation lab, including **≥ 10 wireless onboarding and roaming failure scenarios**. |
| **SC-9** | Reduce end-to-end time from "problem reported" to "correlated evidence in hand" from **hours** to: **< 15 minutes** for a 10-device path; **< 20 minutes** for a full three-domain wireless client capture. |
| **SC-10** | Signed and installable artifacts for **Windows (.exe)**, **macOS (notarized .dmg)**, and **Ubuntu (.deb + AppImage)** produced from a **single CI pipeline**. |

---

## 8. Key Constraints and Assumptions

| ID | Constraint / Assumption |
|---|---|
| **C-1** | Capture command syntax, buffer limits, and feature availability vary by platform **AND** software release; capability data must be **release-aware and regression-tested** against captured golden CLI output. |
| **C-2** | NX-OS has **no data-plane equivalent of EPC**; ERSPAN or SPAN plumbing is mandatory for Nexus data-plane visibility and may be **restricted by customer security policy**. |
| **C-3** | Several classic Catalyst L2 platforms **do not support EPC at all**. |
| **C-4** | Over-the-air 802.11 capture is **inherently service-affecting**: an AP placed in sniffer mode leaves service and disconnects its clients. This is the **highest-impact action the tool can take** and must be gated, consented, logged, and automatically reverted. |
| **C-5** | Over-the-air capture is **band-, channel- and key-limited**: a sniffer-mode AP observes only the channel it is tuned to and cannot decrypt protected client data frames without the relevant key material. These limitations must be stated to the user **before** capture, not after. |
| **C-6** | Under **FlexConnect local switching** and **SD-Access fabric-enabled wireless**, client data traffic does not traverse the Catalyst 9800. The tool must detect the switching mode and **redirect the capture plan** to the correct enforcement point rather than reporting an empty capture. |
| **C-7** | Catalyst 9800 controllers may operate as **HA SSO pairs**. Captures are valid **only on the active chassis**, and a switchover mid-capture invalidates the session. |
| **C-8** | AP capture behavior depends on AP model, join state, and controller release; unsupported combinations must be detected during capability probing **rather than failing at capture time**. |
| **C-9** | The tool requires authenticated management access with sufficient privilege and **must never store credentials in plaintext**. OS-native secure storage is required: **Windows DPAPI**, **macOS Keychain**, **Linux libsecret**. |
| **C-10** | Devices are assumed to be **NTP-synchronized**; the tool must still function, with **degraded and clearly disclosed precision**, when they are not. |
| **C-11** | Packet payloads may contain sensitive or personal data. Over-the-air capture additionally collects frames from clients and devices that are **not the intended target** and that may not belong to the operator. **Headers-only capture is the default**; full-payload and over-the-air capture must be **explicit, logged, and authorized actions**. |
| **C-12** | Packet capture, and any change to an AP operating mode, constitute **configuration changes on production infrastructure** and must be treated as such by change management. |

---

## 9. Primary Risks

| ID | Risk | Mitigation |
|---|---|---|
| **R-1** | Cisco CLI drift across releases breaking drivers or parsers. | **Version-pinned capability registry** plus **golden-output regression suite in CI**. |
| **R-2** | Punt-path rate limiting causing incomplete captures to be misread as network packet loss. | **Read and prominently display device-side drop and truncation counters** alongside every capture. |
| **R-3** | Guardrail failure impacting a production control plane. | Mandatory filters, pre-flight health gates, hard caps, device-side dead-man timers, and **staged lab-then-pilot rollout**. |
| **R-4** | **Residual configuration** left on production devices, or an AP left out of service in sniffer mode — a direct, visible user-facing outage. | Journaled state machine, device-side auto-cleanup, crash-time recovery of pending mode restorations, and a **mandatory post-run configuration and state diff assertion** before a job is marked complete. |
| **R-5** | Customer security policy blocking the ERSPAN or PEEKREMOTE stream paths required for Nexus data-plane and over-the-air capture. | Explicit **degraded-coverage mode** with clear disclosure of what was not captured and why. |
| **R-6** | Misleading results in **FlexConnect or fabric-enabled wireless** deployments where the controller is not in the data path. | **Mandatory switching-mode detection** before plan generation, and refusal to present an empty controller capture as evidence of packet loss. |
| **R-7** | Over-the-air capture on the wrong channel or during a client roam yielding no useful frames while still having taken an AP out of service. | Pre-capture **channel confirmation from live client state**, multi-AP or multi-channel capture option, and a clear **pre-flight summary** of exactly what will and will not be observable. |
| **R-8** | Legal and privacy exposure from collecting third-party wireless traffic. | Explicit **lawful-capture consent**, headers-only default, immutable audit log, and configurable retention limits on stored captures. |

---

## 10. Definition of Done (Initial Release)

A network engineer can complete the following **end-to-end workflow** without leaving the tool:

1. **Enter** one or more seed devices or a controller and credentials.
2. **Have the wired and wireless topology discovered**, including per-WLAN switching mode and AP placement.
3. **Express a capture intent** either as:
   - A **path** (source, destination, protocol, port, duration), **or**
   - A **single wireless client MAC address**.
4. **Review an automatically generated per-device capture plan** that states:
   - The mechanism chosen for each capture domain,
   - The estimated **blast radius**,
   - The explicit **service impact** of any over-the-air capture,
   - Any **coverage gaps**.
5. **Execute a single synchronized capture** across all selected devices and domains.
6. **Receive** a merged, time-aligned pcapng with CAPWAP already decapsulated, plus a report that states **where in the wireless or wired path the traffic was lost, delayed, rejected, or altered**.
7. **Verify** — with a guaranteed assertion — that:
   - **No configuration was left behind on any device**, and
   - **Every AP has returned to service.**

---

*End of document — see [problemStatement.txt](./problemStatement.txt) for the canonical source.*
