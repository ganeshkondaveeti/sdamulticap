# MultiCap — Edge Cases & Corner Scenarios

> **Corner-Case Catalog**

| Field | Value |
|---|---|
| **Project** | MultiCap — Cisco Multi-Platform Synchronized Packet Capture Orchestrator |
| **Document** | edge-cases.md |
| **Version** | 1.0 (DRAFT) |
| **Date** | 2026-09-10 |
| **Owner** | Lakshmi Ganesh Kondaveeti — Technical Consulting Engineering Technical Leader |
| **Derived from** | [architecture.md](./architecture.md) v1.0, [implementation-plan.md](./implementation-plan.md) v1.1 |

---

## Purpose

This document catalogs corner scenarios the orchestrator must handle *by design*, not by accident. Each edge case is tagged with:

- **Phase** it lands in (per implementation-plan §4)
- **Component(s)** that own it (per architecture §6)
- **Detection** — how the system notices
- **Behavior** — what MultiCap does
- **Failure mode if unhandled** — the bad outcome we are preventing
- **Test hook** — where regression coverage lives

Categories:

1. [Discovery & Topology](#1-discovery--topology)
2. [Capability & CLI Drift](#2-capability--cli-drift)
3. [Transport / Session](#3-transport--session)
4. [Authentication, Authorization, Consent](#4-authentication-authorization-consent)
5. [Path Solver & Plan Generation](#5-path-solver--plan-generation)
6. [Safety Gate](#6-safety-gate)
7. [Synchronizer & Trigger](#7-synchronizer--trigger)
8. [Capture Runtime (Wired)](#8-capture-runtime-wired)
9. [Wireless — Controllers (Cat 9800 / HA)](#9-wireless--controllers-cat-9800--ha)
10. [Wireless — APs & Sniffer Mode](#10-wireless--aps--sniffer-mode)
11. [CAPWAP & Over-the-Air Correlation](#11-capwap--over-the-air-correlation)
12. [Clock, NTP & Alignment](#12-clock-ntp--alignment)
13. [Collectors (ERSPAN / PEEKREMOTE / Local NIC)](#13-collectors-erspan--peekremote--local-nic)
14. [Persistence, Journal & Crash Recovery](#14-persistence-journal--crash-recovery)
15. [Cleanup & Compensation](#15-cleanup--compensation)
16. [Correlator & Reporter](#16-correlator--reporter)
17. [Retention, Privacy & Audit](#17-retention-privacy--audit)
18. [UI / IPC / Cross-Platform](#18-ui--ipc--cross-platform)
19. [Packaging, Signing, Update](#19-packaging-signing-update)
20. [Concurrency & Multi-Job](#20-concurrency--multi-job)

---

## 1. Discovery & Topology

### 1.1 CDP and LLDP both administratively disabled
- **Phase**: 3 · **Component**: Discovery & Topology (arch §6.1)
- **Detection**: Seed device returns empty neighbor tables on both protocols.
- **Behavior**: Fall back to subnet-sweep + SSH/NETCONF/RESTCONF capability probe (impl §8, G3). Emit a `discovery-mode: sweep` marker on every device found this way so downstream planning knows the topology edges are inferred, not observed.
- **Failure mode if unhandled**: Silent partial topology → path solver produces plans that miss hops.
- **Test hook**: CML topology with CDP/LLDP disabled globally.

### 1.2 Seed device unreachable but subnet is reachable
- **Detection**: SSH to seed times out; ICMP/ARP on the CIDR succeeds.
- **Behavior**: Surface the seed failure explicitly; proceed with sweep only if the operator confirms — **never** silently substitute.

### 1.3 Duplicate management IPs across VRFs
- **Detection**: Two `Device` records collide on `mgmtAddress` but differ on `sysObjectID` fingerprint.
- **Behavior**: Namespace by `(vrf, mgmtAddress)`; force operator disambiguation before either device can be planned against.

### 1.4 Device advertises CDP/LLDP neighbor that is not reachable
- **Behavior**: Record as `Link{state: 'unverified'}`; do not include in path unless independently reachable.

### 1.5 Mixed IPv4/IPv6 management planes
- **Behavior**: Transport pool selects family per-device; discovery graph stores both when present.

### 1.6 Hop-limit reached mid-crawl
- **Behavior**: Terminate crawl at limit; mark boundary nodes with `crawl-boundary: hop-limit` so plans can flag "topology beyond this point is unknown".

### 1.7 CIDR allow-list excludes a critical hop
- **Detection**: Path solver needs a device that was never crawled.
- **Behavior**: Refuse plan; surface the missing CIDR range for operator to authorize. Never crawl outside allow-list.

### 1.8 Inventory adapter (DNAC/Prime/NSO/ND/APIC) returns stale data
- **Detection**: Inventory says AP X is on WLC A; live probe says WLC B.
- **Behavior**: Live probe wins; inventory disagreement logged and shown as a warning banner in Plan Review.

### 1.9 Client MAC not currently associated
- **Component**: `ClientLocation` resolver
- **Behavior**: Return `ClientLocation.state = 'not-associated'`; job runner refuses wireless-client intent until reassociation observed. Never guess.

### 1.10 Client MAC associated on multiple radios (band-steering race)
- **Behavior**: Resolver returns all locations; plan generator produces a multi-AP plan **iff** operator confirms; otherwise pick the most-recent per controller state.

### 1.11 FlexConnect local-switching, fabric-enabled wireless, or mesh
- **Behavior**: Path solver **redirects** capture to the correct enforcement point (R-6). Never produce a WLC-only plan for FlexConnect local traffic — it would show nothing and mislead.

### 1.12 AP in "join in progress" / not-yet-registered
- **Behavior**: AP capability probe (C-8) marks it `join-pending`; unavailable for sniffer strategies until `Registered`.

---

## 2. Capability & CLI Drift

### 2.1 Release train not in Capability Registry
- **Detection**: `{platform, release_train}` key miss.
- **Behavior**: Refuse to plan on that device; surface exact release string and a "capture golden output" workflow for driver authors. Never guess syntax.

### 2.2 CLI output format changes within a patch release
- **Detection**: Golden-CLI regression test diff.
- **Behavior**: CI blocks release; driver author updates fixture. Runtime falls back to `coverage-gap` for that release until fixed.

### 2.3 EPC exists on parent platform but not on requested interface type (e.g., EPC on SVI unsupported on this train)
- **Behavior**: Rank next strategy (ERSPAN → SPAN → coverage-gap). Log downgrade in plan.

### 2.4 NX-OS `ethanalyzer` invoked without filter
- **Behavior**: Driver refuses at the boundary (Phase 2 exit criterion). UI's Filter/ACL builder blocks empty filter for NX-OS.

### 2.5 IOS classic without EPC and without SPAN destination
- **Behavior**: Emit `coverage-gap{reason: 'no-onbox-capture-available'}`. Never silent no-op.

### 2.6 IOS-XR dead-man parity gap (open item #4)
- **Behavior**: Fall back to shorter capture windows + orchestrator-side watchdog. Document degraded guarantee in plan.

---

## 3. Transport / Session

### 3.1 SSH session lost mid-arm
- **Behavior**: Journal marks device `ARMED-STALE`; on reconnect run compensation to remove staged capture config. Do not proceed to trigger with a stale arm.

### 3.2 SSH session lost mid-capture
- **Behavior**: Device-side dead-man timer fires (EEM/scheduler); orchestrator observes on reconnect and moves state to `COMPENSATING`.

### 3.3 SSH library returns success but device rejected command (silent failure)
- **Detection**: Post-command `show` verification mismatches expected state.
- **Behavior**: Treat as failure; enter `COMPENSATING`.

### 3.4 NETCONF/RESTCONF disabled on device
- **Behavior**: Downgrade to CLI transport; log capability limitation. Structured-config features (e.g., filter builder emitting YANG) fall back to CLI equivalents.

### 3.5 Per-host concurrency cap exceeded
- **Behavior**: Queue with backoff; never open unbounded channels. Surface queue depth in Live Run UI.

### 3.6 SNMP community/v3 creds wrong but SSH works
- **Behavior**: Fingerprint via SSH `show version`; SNMP-derived facts marked `unavailable`. Do not block on SNMP.

### 3.7 SCP pull fails midway (disk full on device or client)
- **Behavior**: Retry with resume if supported; on final failure mark artifact `partial`, keep bytes captured, flag in report.

### 3.8 Device clock jumps during session (manual set, NTP step)
- **Detection**: RTT-compensated pre/post reads disagree beyond a threshold.
- **Behavior**: Invalidate linear offset; mark packets in that window `alignment: coarse`; surface in report.

### 3.9 Management-plane ACL blocks orchestrator mid-job
- **Behavior**: Same as 3.2; dead-man timer is the safety net.

---

## 4. Authentication, Authorization, Consent

### 4.1 TACACS/RADIUS session mid-timeout during capture
- **Behavior**: Persistent channels retain auth; re-auth attempts use stored creds via secure store, never prompt during a live job. If re-auth fails, dead-man timer runs.

### 4.2 Privilege escalation required for a subset of commands
- **Behavior**: Driver declares required privilege in `probeCapabilities`; Safety Gate blocks plan if any device is under-privileged.

### 4.3 Operator revokes consent mid-flight (window closed, dialog dismissed)
- **Behavior**: Job aborts; enter `COMPENSATING`. Consent revocation is journaled.

### 4.4 Change-ticket ID field empty in enforced-mode deployment
- **Phase**: 5 (C-12)
- **Behavior**: UI blocks execution; audit log will show attempted-run + block reason.

### 4.5 Full-payload consent conflated with sniffer consent
- **Behavior**: Two distinct, separately logged consent records (C-11). One does not imply the other.

### 4.6 Key material for 802.11 data decryption not available
- **Behavior**: Pre-capture disclosure modal (C-5) states which frames will be unreadable; operator acknowledges before AP enters sniffer.

---

## 5. Path Solver & Plan Generation

### 5.1 No path exists (src/dst in disjoint L3 domains)
- **Behavior**: Return plan with `coverageGaps` populated; no strategies emitted. UI surfaces "no path" prominently, not as an empty success.

### 5.2 ECMP / multi-path — which physical hop to capture?
- **Behavior**: Enumerate candidate paths; plan captures on all hops within budget or asks operator to pick. Never silently pick one and hide the others.

### 5.3 Asymmetric routing (forward and return differ)
- **Behavior**: Plan produces two path branches; correlator preserves direction annotation.

### 5.4 Path goes through a device the operator has no credentials for
- **Behavior**: Emit `coverage-gap{reason: 'no-credentials'}` for that hop; adjacent hops still captured.

### 5.5 Path crosses a fabric/overlay (VXLAN, SD-Access)
- **Behavior**: Path solver includes fabric edge devices; strategy selection considers inner vs outer view. Coverage gap declared if inner-view mechanism absent.

### 5.6 Duplicate strategy proposals on the same device (path re-enters a device)
- **Behavior**: Deduplicate to a single ArmToken with merged filter; UI shows a "device appears N times on path" note.

### 5.7 Filter cannot express operator's intent on target platform
- **Behavior**: Filter builder refuses emit; suggests closest expressible superset with operator confirmation. Never silently widen.

### 5.8 Plan preview exceeds blast-radius budget
- **Behavior**: Plan Review blocks execution until operator either narrows filter or explicitly acknowledges elevated impact.

---

## 6. Safety Gate

### 6.1 Device CPU already elevated before capture
- **Behavior**: Refuse per hard threshold; operator may override only with second confirmation, logged.

### 6.2 SPAN session table full
- **Behavior**: Refuse SPAN strategy; fall through ranking (ERSPAN → coverage-gap).

### 6.3 WLC in HA standby state selected by mistake
- **Behavior**: Reject; auto-retarget to `active`; log the correction.

### 6.4 Existing user-owned SPAN/EPC session on device
- **Behavior**: Refuse to co-opt or replace it; surface the existing session ID.

### 6.5 Flash low — cannot land pcap
- **Behavior**: Force ring-buffer or refuse; never fill flash to failure.

### 6.6 Sniffer AP has active clients above threshold
- **Behavior**: Recommend a less-loaded AP; require explicit override to proceed.

---

## 7. Synchronizer & Trigger

### 7.1 One of N pre-armed sessions disconnected before trigger
- **Behavior**: Abort the trigger phase; all armed devices roll back via journal. Partial captures are worse than none for correlation.

### 7.2 NTP-anchored EEM start time already passed
- **Behavior**: Re-anchor to next safe epoch, re-arm; never fire "immediately" as a fallback.

### 7.3 Arming skew exceeds SC-3 threshold at trigger observation
- **Behavior**: Plan continues but report flags skew violation; correlator uses actual observed start per device.

### 7.4 Precision mode requested on WAN
- **Behavior**: Warn; downgrade to coordinated-trigger mode unless operator overrides.

### 7.5 A device rejects the trigger command (auth window closed, disk full)
- **Behavior**: Abort remaining devices; enter `COMPENSATING` for all previously armed.

---

## 8. Capture Runtime (Wired)

### 8.1 EPC buffer wraps before stop
- **Detection**: Device reports wrap counter > 0.
- **Behavior**: Surface prominently in the report (R-2); do not hide.

### 8.2 Punt-path drops (device drop counter increments)
- **Behavior**: Read counters at stop; annotate report; do not silently omit.

### 8.3 ERSPAN destination unreachable mid-capture
- **Behavior**: Collector marks stream `stale`; report flags the gap window.

### 8.4 SPAN destination port oversubscribed
- **Behavior**: Warn at plan time using link-utilization pre-flight; if drops observed at stop, surface as gap window.

### 8.5 ACL filter matches zero packets
- **Behavior**: Not an error; report explicitly states "0 matched" with the filter text so operator can verify intent.

### 8.6 Sub-interface / SVI / L3 loopback interface capture attempt
- **Behavior**: Driver validates platform+release supports it (from Capability Registry) or downgrades strategy.

---

## 9. Wireless — Controllers (Cat 9800 / HA)

### 9.1 HA SSO switchover mid-job
- **Detection**: Active/standby role change event.
- **Behavior**: Session-invalidating (C-7); job aborts cleanly; user surface explains what happened; audit records the event.

### 9.2 Standby controller selected by discovery
- **Behavior**: Rejected at Safety Gate (§6.3).

### 9.3 Controller reload during capture
- **Behavior**: Dead-man timer + journal recovery; on next launch the state machine drives compensation.

### 9.4 Radioactive-trace output exceeds size cap
- **Behavior**: Truncate with explicit marker; correlator preserves what it has; report flags truncation.

### 9.5 CAPWAP inner filter cannot be expressed on this train
- **Behavior**: Downgrade to outer capture + post-capture filter in correlator; label the strategy in the plan.

---

## 10. Wireless — APs & Sniffer Mode

### 10.1 AP model does not support sniffer mode
- **Detection**: Capability probe at discovery (C-8).
- **Behavior**: Excluded from sniffer strategy at plan time; never surprises at capture time.

### 10.2 AP joined controller but not yet fully provisioned
- **Behavior**: `join-pending`; unavailable for sniffer (see 1.12).

### 10.3 Client roams between APs mid-capture
- **Behavior**: Correlator handles as multiple `ClientLocation` epochs. If only single-AP sniffer was armed, the report flags roam-out-of-scope and recommends multi-AP.

### 10.4 Channel/width mismatch — client on 6 GHz PSC, sniffer AP on 5 GHz
- **Detection**: Pre-capture channel confirmation from live client state (R-7).
- **Behavior**: Refuse to arm sniffer on wrong band/channel; prompt operator to pick another AP or wait for reassoc.

### 10.5 DFS radar event forces channel change mid-capture
- **Behavior**: Capture window annotated with DFS event; correlator marks packets post-change with new channel; report flags interruption.

### 10.6 AP power-cycled during capture
- **Behavior**: Journal detects; dead-man timer redundant; on rejoin state manager verifies mode restoration.

### 10.7 AP mode NOT restored at end (would leave it stranded)
- **Detection**: Post-run diff assertion.
- **Behavior**: Block `VERIFIED`; retry restoration; escalate to operator if it persists.

### 10.8 AP band/channel/width NOT restored to pre-capture values
- **Behavior**: Same as 10.7. Restoration is a strict superset requirement of R-4.

### 10.9 Multiple sniffer APs on overlapping channels
- **Behavior**: Correlator de-duplicates by BSSID+seq; report notes overlap.

---

## 11. CAPWAP & Over-the-Air Correlation

### 11.1 CAPWAP DTLS enabled on data plane
- **Behavior**: Inner-view unavailable without keys; report clearly states this; capture retained for outer-view analysis.

### 11.2 Non-standard CAPWAP ports (customized)
- **Behavior**: Pull WLC config to learn ports; do not hard-code 5246/5247 blindly.

### 11.3 PEEKREMOTE stream duplicated across two collectors
- **Behavior**: Correlator de-dup by radiotap+timestamp; log dup rate.

### 11.4 802.11 protected frames when key material absent (C-5)
- **Behavior**: Capture retained; management/EAP frames analyzable; protected data frames marked opaque in report.

### 11.5 Fragmented CAPWAP (large payload + MTU)
- **Behavior**: Correlator reassembles; unreassembled fragments annotated, not dropped silently.

---

## 12. Clock, NTP & Alignment

### 12.1 One device not NTP-synchronized
- **Phase**: 9 (C-10)
- **Behavior**: Banner in Plan Review, Live Run, and report; degraded alignment bound recorded. Job may proceed with operator ack.

### 12.2 NTP stratum drifts during capture
- **Behavior**: Pre/post device clock reads catch it; per-device linear offset function annotates uncertainty.

### 12.3 Beacon injection fails on one capture point
- **Behavior**: That capture aligns to next-best beacon or falls back to device-clock-only offset with wider error bar in report.

### 12.4 Devices in different timezones with DST transitions
- **Behavior**: All internal timestamps in UTC; UI renders local. DST transition mid-capture is a no-op internally.

### 12.5 Clock offset exceeds SC-4 (< 10 ms) threshold
- **Behavior**: Report flags SLO breach; correlator still produces merged pcapng.

---

## 13. Collectors (ERSPAN / PEEKREMOTE / Local NIC)

### 13.1 Firewall drops GRE 0x88BE
- **Detection**: No ERSPAN packets observed after arm.
- **Behavior**: Coverage-gap with reason `erspan-not-received`; suggest local SPAN + capture host.

### 13.2 PEEKREMOTE UDP port blocked
- **Behavior**: Same shape as 13.1 with `peekremote-not-received`.

### 13.3 Local NIC in promiscuous mode not permitted (OS/policy)
- **Behavior**: Refuse local-collector strategy; surface OS-level remediation. macOS may need ChmodBPF; Linux CAP_NET_RAW.

### 13.4 IPv6-only environment for ERSPAN
- **Behavior**: Bind listener to v6 address; validate GRE-over-IPv6 support in kernel; fall back cleanly if unsupported.

### 13.5 Duplicate ERSPAN session IDs across devices
- **Behavior**: Orchestrator allocates a unique session-ID pool; refuses collisions.

### 13.6 Collector host clock skewed from device clock
- **Behavior**: Clock aligner also probes local host; local-only skew corrected the same way.

---

## 14. Persistence, Journal & Crash Recovery

### 14.1 App killed during `ARMED`
- **Behavior**: On next launch, journal replays revert; devices back to pre-arm state.

### 14.2 App killed during `ACTIVE`
- **Behavior**: Device dead-man fires; journal replays stop + revert; any pcap collected is optionally recoverable via SCP pull on next launch.

### 14.3 SQLite journal file corrupted
- **Detection**: WAL checksum failure at open.
- **Behavior**: Refuse to accept new jobs; enter "recovery-only" mode; log forensic snapshot; require operator to trigger last-good compensation from a backup snapshot.

### 14.4 Disk full during journal write
- **Behavior**: Journal write path is fsync-checked; on failure the mutation is treated as unattempted; caller retries or aborts.

### 14.5 Concurrent app instances (user double-launched)
- **Behavior**: Second instance detects lockfile + journal owner PID; refuses to run OR attaches read-only. Never two writers.

### 14.6 Retention pruner runs during active capture
- **Behavior**: Pruner skips artifacts referenced by any non-terminal job; never deletes live evidence.

### 14.7 Audit log hash chain broken
- **Detection**: Startup verification.
- **Behavior**: Enter recovery mode; refuse new consent operations until an operator acknowledges the audit event; original entries retained.

---

## 15. Cleanup & Compensation

### 15.1 Compensation itself fails (device unreachable)
- **Behavior**: Retain `COMPENSATING` state; retry on connectivity; alert operator; dead-man is backup.

### 15.2 Compensation partially succeeds (removed capture, failed to remove EEM)
- **Behavior**: Item-level journal; `VERIFIED` requires *every* item green. Post-run diff assertion catches residuals.

### 15.3 Device rebooted before compensation ran
- **Behavior**: Staged capture config typically didn't persist (not written to startup). Verify via diff; if written by mistake, revert.

### 15.4 Operator manually cleaned up a device out-of-band
- **Detection**: Diff shows nothing to compensate.
- **Behavior**: Mark item `already-clean`; still record in audit.

### 15.5 Post-run diff reports unexpected changes unrelated to MultiCap
- **Behavior**: Do NOT auto-revert those. Surface diff to operator; block `VERIFIED` until acknowledged.

---

## 16. Correlator & Reporter

### 16.1 Merged pcapng exceeds Wireshark practical open size
- **Behavior**: Emit sharded pcapng set with index; report links each shard.

### 16.2 Zero packets across all captures
- **Behavior**: Report explicitly says "0 packets"; enumerates filter, duration, and coverage gaps that likely explain it. Never appears "successful and empty".

### 16.3 Ladder diagram spans thousands of hops
- **Behavior**: Auto-collapse by device group; expandable in UI; PDF paginates.

### 16.4 Fault-verdict engine confidence low
- **Behavior**: Report states "no confident verdict"; lists top-N candidate hypotheses; never fabricates a definitive verdict.

### 16.5 Radioactive-trace timeline earlier/later than packet window
- **Behavior**: Correlator clips to job window; annotates external events.

---

## 17. Retention, Privacy & Audit

### 17.1 Retention window shrinks below existing artifact ages
- **Behavior**: Pruner runs on next boundary; audit records the deletions.

### 17.2 Operator attempts to export a full-payload capture off-box
- **Behavior**: Export flow re-checks consent; if headers-only consent was given, refuse full-payload export.

### 17.3 Audit log export includes any credential material
- **Behavior**: **Never.** CI test scans audit exports for secret patterns (impl §17 new row).

### 17.4 Consent revoked after capture stored on disk
- **Behavior**: Pruner immediately purges affected artifacts; audit records purge.

---

## 18. UI / IPC / Cross-Platform

### 18.1 pyo3 native-module ABI mismatch (Python ↔ `correlator_rs`)
- **Behavior**: Refuse to launch; show upgrade dialog. The Python-side facade (`core/correlator_facade.py`) verifies `correlator_rs.__abi_version__` against a bundled constant at startup. No best-effort field skipping.

### 18.2 Qt main thread stalls mid-job (long synchronous work leaks into GUI thread)
- **Behavior**: `QThreadPool` workers own all Netmiko I/O and pyo3 correlator calls; a watchdog on the main-thread event loop (`QTimer` heartbeat) flags stalls > 500 ms into the audit log. Job continues (workers unaffected); Live Run banner surfaces the stall so operators know UI lag is not job failure.

### 18.3 OS DPI / accessibility settings truncate consent modal
- **Behavior**: Modal is scrollable + minimum-height enforced; accept-button is only enabled after scroll-to-bottom.

### 18.4 Linux without libsecret / macOS without Keychain access
- **Behavior**: Refuse to store creds in-memory-only "mode"; guide user to install/enable. Never fall back to plaintext.

### 18.5 macOS "Full Disk Access" not granted for pcapng path
- **Behavior**: Prompt; block start until granted.

### 18.6 Windows SmartScreen warning on first launch of signed binary
- **Behavior**: Signing chain validated at build; release notes include SmartScreen guidance.

### 18.7 High-contrast / dark-mode rendering of ladder diagram
- **Behavior**: Diagram uses palette-aware colors and pattern fills (colorblind-safe).

---

## 19. Packaging, Signing, Update

### 19.1 Notarization stapling fails on macOS
- **Behavior**: CI blocks release; never ship un-notarized.

### 19.2 Reproducible-build check diverges
- **Behavior**: Release gate fails until root-caused.

### 19.3 Rust native addon fails to load on a distro (glibc mismatch)
- **Behavior**: Detect at startup; show actionable message with the required glibc.

### 19.4 In-place upgrade while a job is `ACTIVE`
- **Behavior**: Installer refuses; requires job to reach terminal state first, or offers safe abort → compensate.

---

## 20. Concurrency & Multi-Job

### 20.1 Two jobs target the same device
- **Behavior**: Second job blocked at Safety Gate; queue with visible reason.

### 20.2 Two jobs share a collector port (ERSPAN session ID / PEEKREMOTE UDP)
- **Behavior**: Orchestrator's port/session allocator refuses collisions.

### 20.3 Job scheduled for future NTP epoch while another job is running
- **Behavior**: Allowed if devices disjoint; else queued.

### 20.4 Global cancel-all invoked
- **Behavior**: Each job independently transitions through `COMPENSATING`; the cancel does not skip cleanup.

---

## Cross-Cutting Invariants

The following invariants MUST hold across every edge case above. If any is violated, that is a bug regardless of scenario:

1. **No silent success.** Empty result → explicit "empty and why".
2. **No silent gap.** Missing coverage → declared `coverage-gap` with reason.
3. **No silent revert.** Every compensation is journaled + auditable.
4. **No stranded AP.** Mode/band/channel/width restored, verified by diff.
5. **No plaintext credentials.** Ever. In any surface.
6. **No unfiltered `ethanalyzer`.** Refused at driver boundary.
7. **No `DONE` without `VERIFIED`.** Diff-clean is a hard gate.
8. **No skew hidden.** Skew exceeding SC-3/SC-4 is reported, not smoothed away.
9. **No consent implied.** Sniffer, full-payload, and change-ticket are separate, explicit records.
10. **No unversioned IPC.** Schema mismatch is fatal, not best-effort.

---

*End of document — traceable to [architecture.md](./architecture.md) v1.0 and [implementation-plan.md](./implementation-plan.md) v1.1.*
