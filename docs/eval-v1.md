# MultiCap — Implementation Plan Evaluation

> **Evaluation of `implementation-plan.md` v1.1 (DRAFT)**

> ⚠️ **Historical document.** This eval was written against `implementation-plan.md` **v1.1** (pre-pivot: Electron / TypeScript / Node / pnpm / N-API). The plan has since been superseded by **v1.2** per [ADR-001](./stack-decision.md), which switches the stack to **PySide6 / Python / uv / pyo3 + maturin**. Findings that concern the pre-pivot stack (§2 `packages/security` split, §3 Electron/N-API version pins, §6 `ssh2` vs libssh2 blocker, recommendations R6/R7) are **overtaken by events (OBE)** and closed by ADR-001. Findings on delivery structure, phase sequencing, driver contract, safety gate, correlator sequencing, and success-criterion coverage remain **applicable to v1.2** and should still be actioned. This file is retained for historical traceability; a v2.0 eval against v1.2 is a separate work item.

| Field | Value |
|---|---|
| **Project** | MultiCap — Cisco Multi-Platform Synchronized Packet Capture Orchestrator |
| **Document** | eval.md |
| **Version** | 1.0 (historical — evaluates pre-pivot plan) |
| **Date** | 2026-09-10 |
| **Evaluates** | [implementation-plan.md](./implementation-plan.md) **v1.1** (superseded by v1.2 per [ADR-001](./stack-decision.md)) |
| **Cross-refs** | [architecture.md](./architecture.md) v1.0 (superseded by v1.1), [problemStatement.md](./problemStatement.md) v2.0, [stack-decision.md](./stack-decision.md) ADR-001 |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Scoring Rubric](#2-scoring-rubric)
3. [Section-by-Section Evaluation](#3-section-by-section-evaluation)
4. [Gap Closure Assessment (v1.0 → v1.1)](#4-gap-closure-assessment-v10--v11)
5. [Risk-to-Phase Coverage Check](#5-risk-to-phase-coverage-check)
6. [Success-Criteria Traceability](#6-success-criteria-traceability)
7. [Schedule & Critical-Path Analysis](#7-schedule--critical-path-analysis)
8. [Strengths](#8-strengths)
9. [Weaknesses & Gaps](#9-weaknesses--gaps)
10. [Recommendations](#10-recommendations)
11. [Verdict](#11-verdict)

---

## 1. Executive Summary

The v1.1 implementation plan is a **well-structured, risk-first delivery plan** that maps cleanly to the architecture and problem statement. The v1.0 → v1.1 revision demonstrably closes the gap report: every G-item in §21 traces to a concrete deliverable in a specific phase.

**Overall score: 4.3 / 5 — Approve with minor revisions.**

Key strengths: safety-before-capture sequencing (Phase 5 lands before Phase 6), vertical-slice discipline, explicit coverage-gap semantics, and monotonically rising CI gates. Key weaknesses: Phase 2b parallelism assumptions are optimistic, Phase 8 is overloaded (5 weeks for 8+ major deliverables), and several open items (§20) block phases they gate.

---

## 2. Scoring Rubric

| Dimension | Weight | Score (1-5) | Weighted |
|---|---:|---:|---:|
| Alignment with architecture | 15% | 5 | 0.75 |
| Alignment with problem statement / success criteria | 15% | 5 | 0.75 |
| Risk coverage & mitigation sequencing | 15% | 5 | 0.75 |
| Phase decomposition & vertical-slice discipline | 10% | 5 | 0.50 |
| Schedule realism | 15% | 3 | 0.45 |
| Testability & exit-criteria rigor | 10% | 4 | 0.40 |
| Cross-cutting & security workstreams | 5% | 4 | 0.20 |
| Open-item / decision hygiene | 5% | 3 | 0.15 |
| Gap closure vs v1.0 report | 10% | 5 | 0.50 |
| **Total** | 100% | | **4.45 / 5** |

---

## 3. Section-by-Section Evaluation

### §1 Delivery Strategy — **Strong**
- Vertical slices + wired-first-wireless-second is the right sequencing for the risk profile.
- "Safety and cleanup are Phase-0 concerns" is stated but Phase 0 only lands the audit-log *skeleton*; the safety gate itself is Phase 5. This is defensible (skeleton ≠ full gate) but the wording could be tightened.

### §2 Repo Layout — **Strong**
- Monorepo + pnpm workspaces + native Rust addon in a dedicated package is the correct shape.
- Missing: `packages/security` or equivalent for the credential store adapters — currently folded into `packages/persistence`, which mixes concerns (persistence + secrets).

### §3 Toolchain — **Strong**
- All the right pins. `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` show real TS discipline.
- Missing: explicit N-API version pin and electron version pin. Electron churn breaks native addons.

### §4 Phase Overview — **Strong with caveat**
- Duration totals to ~37 weeks; the "Phase 2b partially parallel with 3–4" claim is credible only if driver-authoring capacity ≥ 2 engineers. Not stated.
- Phase 8 at 5 weeks is aggressive (see §7 below).

### §5 Phase 0 Foundations — **Strong**
- Signed-shell-first proves the delivery pipeline before product code — exactly right.
- Missing exit criterion: SBOM baseline. Deferred to Phase 10, but a Phase-0 SBOM smoke would surface tooling issues earlier.

### §6 Phase 1 Transport & Persistence — **Strong**
- SSH pool + NETCONF + RESTCONF + SNMP + SCP + journal in one phase is dense but coherent.
- Open item #7 (ssh2 vs libssh2) is a **phase-entry blocker** — should be resolved *before* Phase 1 kickoff, not "at kickoff."

### §7 Phase 2 Driver Contract — **Strong**
- Contract tests + golden-CLI fixtures + two initial drivers (IOS-XE SW, NX-OS) is the correct minimum viable driver surface.
- NX-OS unfiltered refusal at driver boundary (not just safety gate) is excellent defense-in-depth.

### §7b Phase 2b Remaining Wired Drivers — **Strong**
- Correctly closes G1 and unblocks SC-1.
- **Concern**: 3 weeks for 3 driver families with per-driver golden fixtures across 2+ release trains each is tight. Realistic only with parallel driver authors + a mature capability-registry harness from Phase 2.

### §8 Phase 3 Discovery — **Strong**
- Subnet sweep + RESTCONF probe closes G3.
- Inventory-adapter deferral (open item #5) is honest — Catalyst Center first-class, others as thin adapters behind a common interface.

### §9 Phase 4 Intent & Plan — **Strong**
- Filter/ACL builder UI closes G4.
- Coverage-gap declarations "never silently dropped" is the right invariant.

### §10 Phase 5 Safety Gate — **Very Strong**
- Full-payload consent gate + change-ticket capture + retention limits + dead-man timers + chaos suite is the most load-bearing phase in the plan, and it is well specified.
- Open item #4 (IOS-XR EEM parity) is a real blocker for this phase's IOS-XR path. Should be a Phase-2b or Phase-5 entry condition.

### §11 Phase 6 Synchronizer — **Strong**
- SC-3 thresholds (< 500 ms, < 100 ms precision) are aggressive but architecturally supported by persistent pre-armed channels.
- HA SSO plumbing landing here (even though it's wireless-relevant) is the right early investment.

### §12 Phase 7 Correlator — **Strong**
- Rust N-API addon for the hot path is defensible.
- Open item #1 (correlator language benchmark checkpoint at end of Phase 7) is **too late** — a language switch after Phase 7 would invalidate Phase 8 CAPWAP work. Should be a Phase-6 checkpoint.

### §13 Phase 8 Wireless — **Overloaded**
- Deliverables include: wireless discovery, path solver extension, 9800 driver (with 5 sub-features), AP driver (with 4 sub-features), wireless safety gate, HA SSO surfacing, correlator wireless features, post-run assertion extension.
- 5 weeks for this scope is optimistic by ~30-40%. Recommend split into Phase 8a (9800 + discovery) and Phase 8b (AP sniffer + correlator wireless).

### §14 Phase 9 Reporter — **Strong**
- SC-9 wall-clock verification harness closes G5.
- Ladder diagram + fault-verdict engine + NTP-degraded UX in 3 weeks is realistic given Phase 7 laid the correlator groundwork.

### §15 Phase 10 Release — **Strong**
- Reproducible-build verification is the right bar.
- Open item #8 (Rust addon reproducibility across OSes) should be validated in Phase 7, not Phase 10.

### §16 Cross-Cutting — **Adequate**
- Golden-CLI workstream covers all 7 driver families — correct.
- **Missing**: performance/scale workstream. SC-3 (20 devices) and Phase 8 (4+ concurrent sniffer APs) need a dedicated harness that runs continuously, not just at exit-criteria checkpoints.

### §17 Testing — **Strong**
- Audit-log secret scan (C-9/C-11 enforcement) is excellent.
- SC-9 harness as a release gate is the right lever.
- **Missing**: fuzz testing on pcap/pcapng parsers (Rust addon attack surface) and on CLI-output parsers (drivers).

### §18 Milestones — **Strong**
- M2b added correctly.
- M6 (three-domain wireless) as a single milestone hides the Phase 8 overload risk.

### §19 Risk-to-Phase — **Strong** — full R-1..R-8 coverage.

### §20 Open Items — **Weak sequencing**
- Items 4, 7 are phase-entry blockers presented as "decisions at kickoff." Should be resolved *before* kickoff.
- Items 1, 8 are surfaced too late for the phases they affect.

### §21 Gap Traceability — **Excellent** — every G-item closed with phase citation.

---

## 4. Gap Closure Assessment (v1.0 → v1.1)

| Gap | Status | Notes |
|---|---|---|
| G1 (missing drivers) | **Closed** | Phase 2b + M2b milestone |
| G2 — C-5 (key-material) | **Closed** | Phase 8 consent modal |
| G2 — C-8 (AP capability probe) | **Closed** | Phase 8 AP driver |
| G2 — C-10 (NTP-degraded UX) | **Closed** | Phase 9 banner |
| G2 — C-11 / R-8 (full-payload consent) | **Closed** | Phase 5 safety gate |
| G2 — R-8 (retention limits) | **Closed** | Phase 5 enforcement + Phase 9 UI |
| G2 — C-12 (change-ticket) | **Closed** | Phase 5 |
| G3 (subnet sweep + RESTCONF probe) | **Closed** | Phase 3 |
| G3 (inventory adapters) | **Partial** | Common interface in Phase 3; parity deferred (open item #5) — acceptable |
| G4 (RESTCONF) | **Closed** | Phase 1 |
| G4 (filter/ACL builder UI) | **Closed** | Phase 4 |
| G5 — SC-1 all families | **Closed** | Phase 2b unblocks |
| G5 — SC-9 harness | **Closed** | Phase 9 |
| G6 (golden-CLI 7 families) | **Closed** | §16 workstream |
| G6 (audit-log secret scan) | **Closed** | §17 |
| G6 (AP restore assertion) | **Closed** | Phase 8 post-run assertion |

**Verdict: 15/16 fully closed, 1/16 acceptably deferred. Gap-report remediation is complete.**

---

## 5. Risk-to-Phase Coverage Check

All 8 architecture risks (R-1..R-8) have a "first mitigation" phase and a "fully mitigated by" phase. Cross-checked against architecture §20 — no risk is orphaned. **Pass.**

Highest-blast-radius risk (R-4, stranded AP in sniffer mode) is mitigated in two layers: state-machine in Phase 5, and mode-diff assertion in Phase 8. Correct defense-in-depth.

---

## 6. Success-Criteria Traceability

| SC | First reachable in | Verified in |
|---|---|---|
| SC-1 (≥95% classification) | Phase 3 (wired subset) → Phase 2b (all families) | M2b, M3 |
| SC-2 (client location) | Phase 8 | M6 |
| SC-3 (skew <500ms / <100ms) | Phase 6 | M4 |
| SC-4 (alignment <10ms) | Phase 7 | M5 |
| SC-5 (CAPWAP association) | Phase 8 | M6 |
| SC-6 (cleanup) | Phase 5 (wired) → Phase 8 (wireless) | M4, M6 |
| SC-7 (audit) | Phase 5 / Phase 6 | M4, M6 |
| SC-8 (fault verdict) | Phase 9 | M7 |
| SC-9 (wall-clock) | Phase 9 harness | M7 |
| SC-10 (signed release) | Phase 10 | M8 |

**All 10 SCs traceable. Pass.**

---

## 7. Schedule & Critical-Path Analysis

Stated total: ~37 weeks.

**Critical path** (assuming single-thread driver authoring):
Phase 0 (2) → 1 (2) → 2 (3) → 2b (3) → 3 (3) → 4 (3) → 5 (3) → 6 (4) → 7 (4) → 8 (5) → 9 (3) → 10 (2) = **37 weeks**.

**With claimed Phase 2b parallelism** (2b overlaps 3+4): saves ~3 weeks → **34 weeks**. Realistic only with ≥2 driver engineers.

**Risk-adjusted estimate**: Phase 8 realistic scope is 7 weeks, not 5. Recommend replanning Phase 8 as 8a (3 wks) + 8b (4 wks) = **39–42 weeks total risk-adjusted**.

**Schedule score: 3/5** — phase count and sequencing are correct; individual estimates are optimistic for Phase 2b and Phase 8.

---

## 8. Strengths

1. **Safety-before-capture sequencing** — Phase 5 lands before Phase 6. Non-negotiable, and honored.
2. **Coverage-gap-as-first-class** — classic IOS without EPC returns explicit `coverage-gap`, never silent no-op. Prevents entire class of misleading "empty capture" bugs.
3. **NX-OS unfiltered refusal at driver boundary** — defense-in-depth over the safety gate.
4. **Golden-CLI fixtures with a capture tool** — R-1 (CLI drift) is the highest-frequency ongoing risk in Cisco tooling, and the plan treats it as a workstream, not a one-off.
5. **Chaos suite lands with the state machine, not after** — Phase 5 chaos suite proves the invariants before any live capture.
6. **Immutable, hash-chained audit log from Phase 0** — audit integrity is a foundational property, not a bolt-on.
7. **Explicit gap traceability section (§21)** — v1.0 → v1.1 delta is auditable.

---

## 9. Weaknesses & Gaps

1. **Phase 8 overload** — 8+ major deliverables in 5 weeks. Highest-risk phase, tightest schedule. Recommend split.
2. **Open items #1, #4, #7, #8 mis-sequenced** — decisions surface at or after the phase they gate. Should resolve at *entry*, not kickoff.
3. **No dedicated performance/scale workstream** — SC-3 (20 devices) and Phase 8 (4+ APs) need continuous benchmarking, not exit-criteria-only checks.
4. **Missing fuzz testing** — pcap/pcapng parsers (Rust addon) and CLI-output parsers (drivers) are both untrusted-input surfaces.
5. **Staffing assumption implicit** — "Phase 2b partially parallel" requires ≥2 driver engineers; not stated.
6. **`packages/persistence` conflates persistence + secrets** — split into `packages/security` (or similar) for clearer credential-adapter boundary.
7. **Electron + N-API version pins missing** — Electron churn breaks native addons; should be explicit.
8. **Phase 0 SBOM baseline deferred** — deferring to Phase 10 delays tooling shakeout.
9. **M6 single-milestone hides Phase 8 sub-risk** — split M6 → M6a (9800 + discovery) + M6b (AP sniffer + correlator wireless) matches recommended Phase 8 split.
10. **No explicit rollback plan for a failed release** — Phase 10 covers forward release; a rollback / recall procedure is absent.

---

## 10. Recommendations

**Must-fix before approval:**
- **R1.** Split Phase 8 into 8a (9800 + discovery + path solver extension, ~3 wks) and 8b (AP sniffer + correlator wireless + post-run assertion, ~4 wks). Split M6 accordingly.
- **R2.** Move open items #1 (correlator language), #4 (IOS-XR EEM parity), #7 (SSH library), #8 (Rust reproducibility) to a "Phase Entry Gates" table with a **resolve-by-phase-entry** column, not kickoff.
- **R3.** State the staffing assumption for Phase 2b parallelism explicitly.

**Should-fix (v1.2):**
- **R4.** Add a cross-cutting performance/scale workstream (§16) with a nightly harness from Phase 6 onward.
- **R5.** Add fuzz testing rows to §17 for the Rust pcap/pcapng parser and CLI-output parsers.
- **R6.** Split `packages/persistence` → `packages/persistence` + `packages/security`.
- **R7.** Pin Electron and N-API versions in §3.
- **R8.** Add a Phase-0 SBOM baseline exit criterion.
- **R9.** Add a Phase-10 rollback/recall procedure deliverable.

**Nice-to-have:**
- **R10.** Add a "capacity plan" table (engineers per phase) to §4.
- **R11.** Add explicit dependency arrows between phases (Mermaid) rather than a linear numbered list.

---

## 11. Verdict

**APPROVE WITH MINOR REVISIONS.**

The plan is architecturally sound, risk-aware, and demonstrably closes the v1.0 gap report. It reflects deep familiarity with the platform-specific hazards (CLI drift, stranded AP mode, silent coverage gaps, CAPWAP inner-vs-outer confusion) and sequences mitigations before the mechanisms that create the hazard.

The primary risks to on-time delivery are **Phase 8 scope density** and **late-resolving open items** (#1, #4, #7, #8). Addressing recommendations R1–R3 before Phase 1 kickoff removes the schedule and technical-debt risk without disturbing the delivery strategy.

**Recommended next actions:**
1. Apply R1–R3 to produce v1.2.
2. Schedule Phase 1 kickoff only after open items #4 and #7 are resolved.
3. Stand up the golden-CLI capture tool (§16 workstream) in Phase 0, not Phase 2 — it is a delivery-pipeline dependency, not a driver dependency.

---

*End of evaluation — traceable to [implementation-plan.md](./implementation-plan.md) v1.1, [architecture.md](./architecture.md) v1.0, and [problemStatement.md](./problemStatement.md) v2.0.*
