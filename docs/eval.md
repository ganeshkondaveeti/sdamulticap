# MultiCap — Implementation Plan Evaluation

> **Evaluation of `implementation-plan.md` v1.2 (DRAFT) — post stack pivot**

| Field | Value |
|---|---|
| **Project** | MultiCap — Cisco Multi-Platform Synchronized Packet Capture Orchestrator |
| **Document** | eval.md |
| **Version** | 2.1 (DRAFT) |
| **Date** | 2026-09-10 |
| **Evaluates** | [implementation-plan.md](./implementation-plan.md) **v1.4** (governed by [ADR-001](./stack-decision.md)) — v2.0 body below evaluated v1.2; v2.1 §14 delta re-evaluates v1.4 after full R1–R12 remediation. |
| **Cross-refs** | [architecture.md](./architecture.md) v1.1, [frontend-plan.md](./frontend-plan.md) v1.1, [edge-cases.md](./edge-cases.md), [problemStatement.md](./problemStatement.md) v2.0, [stack-decision.md](./stack-decision.md) ADR-001 |
| **Supersedes** | [eval-v1.md](./eval-v1.md) (historical — evaluated pre-pivot v1.1) |
| **Owner** | Lakshmi Ganesh Kondaveeti — Technical Consulting Engineering Technical Leader |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Scoring Rubric](#2-scoring-rubric)
3. [Delta from v1.1 → v1.2 (Stack Pivot Impact)](#3-delta-from-v11--v12-stack-pivot-impact)
4. [Section-by-Section Evaluation](#4-section-by-section-evaluation)
5. [Carry-Forward Findings from v1 Eval](#5-carry-forward-findings-from-v1-eval)
6. [Risk-to-Phase Coverage Check](#6-risk-to-phase-coverage-check)
7. [Success-Criteria Traceability](#7-success-criteria-traceability)
8. [Schedule & Critical-Path Analysis](#8-schedule--critical-path-analysis)
9. [ADR-001 Cascade Integrity](#9-adr-001-cascade-integrity)
10. [Strengths](#10-strengths)
11. [Weaknesses & Gaps](#11-weaknesses--gaps)
12. [Recommendations](#12-recommendations)
13. [Verdict](#13-verdict)

---

## 1. Executive Summary

The v1.2 implementation plan is the v1.1 plan re-anchored to the PySide6 / Python / uv / pyo3 + maturin stack per [ADR-001](./stack-decision.md). Delivery strategy, phase decomposition, risk sequencing, coverage-gap semantics, and gap-closure traceability all survive the pivot intact. The pivot **resolves four v1-eval weaknesses outright** (W6 packages/security split, W7 Electron+N-API pins, and open-item mis-sequencing on items #1 correlator-language and #7 SSH library) and **preserves three** (Phase 8 overload, missing perf/scale workstream, missing fuzz row).

**Overall score: 4.6 / 5 — Approve with minor revisions.**

The pivot is a net simplification: one language across UI + orchestration + correlator facade, one process, one packaging pipeline, one type-checker (`mypy --strict`), and no IPC schema layer to maintain. The v1-era "IPC surface as attack/complexity vector" is dissolved. Coupled with the retained substrate-first discipline (Phases 0–1 land the journal, transport pool, and audit skeleton before any driver ships), the plan is in a stronger position than v1.1 for the same wall-clock estimate.

Residual concerns are **Phase 8 wireless scope density** (unchanged from v1) and **new-stack-specific open items** — PyInstaller LGPL constraints, `qasync` vs `QThreadPool` reactor choice for PEEKREMOTE, and pyo3 ABI compatibility across CPython patch releases (see [edge-cases §18.1](./edge-cases.md)).

---

## 2. Scoring Rubric

| Dimension | Weight | Score (1-5) | Weighted | Δ vs v1 eval |
|---|---:|---:|---:|---:|
| Alignment with architecture v1.1 | 15% | 5 | 0.75 | — |
| Alignment with problem statement / success criteria | 15% | 5 | 0.75 | — |
| Risk coverage & mitigation sequencing | 15% | 5 | 0.75 | — |
| Phase decomposition & vertical-slice discipline | 10% | 5 | 0.50 | — |
| Schedule realism | 15% | 3 | 0.45 | — |
| Testability & exit-criteria rigor | 10% | 4 | 0.40 | — |
| Cross-cutting & security workstreams | 5% | 4 | 0.20 | — |
| Open-item / decision hygiene | 5% | 4 | 0.20 | **+0.05** (items #1, #7 resolved by ADR-001) |
| Gap closure vs v1.0 report | 10% | 5 | 0.50 | — |
| Stack-pivot cascade integrity | 5% | 5 | 0.25 | **new** |
| **Total** | 105% (renormalized) | | **4.60 / 5** | **+0.15** |

> Note: rubric now includes a "Stack-pivot cascade integrity" dimension (§9) covering
> whether v1.2 is consistent across all sibling docs after ADR-001. Weights renormalized
> against the additional dimension.

---

## 3. Delta from v1.1 → v1.2 (Stack Pivot Impact)

Explicit trace of what changed and what the change buys / costs.

| Area | v1.1 | v1.2 | Net |
|---|---|---|---|
| UI toolkit | Electron + React + TypeScript | PySide6 + Qt Widgets + qt-material | Bundle ↓, single language, no IPC schema |
| Process model | Renderer + Main (IPC boundary) | Single Qt event loop, single Python process | Simpler; §11.2 state machine no longer straddles processes |
| Correlator hot path | Rust via **N-API** | Rust via **pyo3**, built with **maturin** | Same perf envelope; one fewer runtime (no Node); ABI concern shifts to CPython (see [edge-cases §18.1](./edge-cases.md)) |
| Toolchain | Node LTS, pnpm, tsc, vitest, Playwright, ESLint, electron-builder | Python 3.12 + `uv` + `ruff` + `mypy --strict` + `pytest` + `pytest-qt` + PyInstaller | Consolidated; fewer independent version-pin surfaces |
| Repo layout | `apps/desktop/` + `packages/{ipc-schema, ui, core, drivers, persistence, correlator}` | `src/multicap/{app,core,drivers,transport,collectors,parsers,persistence,correlator_rs,testkit}/` | Flat `src/` layout; **eliminates `packages/security` split concern** (v1 W6) |
| Secure store | Keytar + adapters in `packages/persistence` | `keyring` (DPAPI / Keychain / SecretService) under `src/multicap/persistence/` | Same abstraction; native Qt integration |
| Packaging | `electron-builder` per OS | PyInstaller one-folder → `.dmg` / `.msi` / `.deb` / AppImage; codesign / signtool / dpkg-sig | Longer cold-start (0.5–1.5 s vs 0.3–0.6 s), acceptable for session tool; **LGPL one-folder mode mandatory** — new constraint |
| UI test | Playwright | `pytest-qt` | Same test-per-phase cadence |
| i18n | i18next stub | Qt Linguist (`.ts` / `.qm`) from Phase 0 | Native Qt path; en-US only for v1 unchanged |
| Concurrency | Node worker threads | `QThreadPool` + `QSemaphore`; `qasync` for asyncio-in-Qt-loop | Concurrency model is now Qt-native; **PEEKREMOTE reactor choice is a new open item** (§20 #3, revised) |
| Native-module distribution | `prebuildify` per OS | `maturin` per-OS wheels; `cibuildwheel` vs GH runners TBD | New open follow-up (§20 #8 revised) |

**What v1-eval concerns the pivot resolves outright:**
- v1 W6 (`packages/persistence` conflating persistence + secrets) — dissolved. The `src/` flat layout puts credentials, journal, and pcapng store as siblings under `persistence/` with clear file-level separation; the split-package problem does not exist in a single distribution.
- v1 W7 (Electron + N-API version pins missing) — dissolved. No Electron; no N-API. pyo3 ABI pinning is now the concern and is tracked in [edge-cases §18.1](./edge-cases.md).
- v1 open item #1 (correlator language) — **Resolved** by ADR-001 §4 (Rust + pyo3 via maturin). §20 in v1.2 records the resolution.
- v1 open item #7 (SSH library choice) — **Resolved** by ADR-001 (Netmiko + Paramiko). §20 in v1.2 records the resolution.

**What the pivot introduces:**
- **N1.** pyo3 / CPython ABI compatibility across patch releases — mitigated by facade-side `__abi_version__` check ([edge-cases §18.1](./edge-cases.md)); acceptable.
- **N2.** PyInstaller one-folder LGPL constraint — codified in Phase 10 deliverable text and open item #8's follow-up; correct.
- **N3.** Qt main-thread stall watchdog ([edge-cases §18.2](./edge-cases.md)) — replaces the v1-era renderer-crash concern; correct.
- **N4.** `qasync` vs `QThreadPool` reactor choice for PEEKREMOTE ingest at ≥4 concurrent APs (§20 #3) — new open item, benchmark deferred to Phase 8 kickoff. **Recommend elevating to Phase-8-entry gate** (see R2 below).

---

## 4. Section-by-Section Evaluation

### §1 Delivery Strategy — **Strong** (unchanged from v1)

- Vertical slices + wired-first-wireless-second still correct.
- Wording "safety and cleanup are Phase-0 concerns" still describes skeleton-in-Phase-0, gate-in-Phase-5. Defensible; wording could be tightened.

### §2 Repo Layout — **Very Strong** (upgraded)

- Flat `src/multicap/` layout is the correct Python idiom (PEP 517/518 `src/` convention).
- Credential adapters cleanly separated into `persistence/` module without the v1-era "packages boundary" ambiguity.
- `correlator_rs/` embedded with its own `Cargo.toml` + `pyproject.toml` (maturin config) is the canonical pyo3 layout.
- **Improvement over v1**: the "Removed vs v1.1" callout is explicit and traces to ADR-001 §4.3 — no ambiguity about what disappeared.

### §3 Toolchain — **Very Strong** (upgraded)

- All pins in place: uv lockfile, Rust toolchain file, PyInstaller per-OS specs, `mypy --strict`, `ruff`, `pytest-qt`.
- **`qasync` listed** but not scoped to a specific phase or gated on the PEEKREMOTE reactor benchmark. Recommend a note.
- **`keyring` backends** enumerated (DPAPI / Keychain / SecretService) — correct.
- "Removed vs v1.1" callout again traces to ADR-001. Good hygiene.

### §4 Phase Overview — **Strong** (unchanged)

- Duration total ~37 weeks. Phase 2b parallelism claim still depends on ≥2 driver engineers (v1 W5 preserved).
- Phase 8 at 5 weeks still aggressive (v1 W1 preserved).

### §5 Phase 0 Foundations — **Strong**

- pyo3 skeleton via maturin at Phase 0 is the right early-integration point — surfaces ABI + wheel-production issues before Phase 7.
- **Missing**: Phase-0 SBOM smoke (`cyclonedx-py` + `cargo-cyclonedx`) — v1 W8 preserved. Tooling is already listed for Phase 10; running it once at Phase 0 costs little and validates the pipeline.
- pytest-qt smoke on the empty `QMainWindow` is correct.

### §6 Phase 1 Transport & Persistence — **Strong**

- Netmiko + `ncclient` + `httpx` (RESTCONF) + `pysnmp` + Paramiko SCP is the correct Cisco NetDevOps stack.
- v1 open item #7 (ssh2 vs libssh2) is **resolved by ADR-001** — no phase-entry blocker here.
- Journal + audit log on SQLite (WAL mode) with hash-chaining is correct.

### §7 Phase 2 Driver Contract — **Strong** (unchanged from v1)

- Contract tests + golden fixtures + mock transport are the correct minimum viable driver surface.
- NX-OS unfiltered-refusal-at-driver-boundary preserved.

### §7b Phase 2b Remaining Wired Drivers — **Strong** (unchanged from v1)

- Still tight for 3 driver families in 3 weeks with per-driver golden fixtures across ≥2 trains.
- Staffing assumption still implicit (v1 W5).

### §8 Phase 3 Discovery — **Strong** (unchanged)

- Subnet sweep + RESTCONF probe correct.
- Catalyst Center first-class, others behind `InventorySource` interface — deferral is honest.

### §9 Phase 4 Intent & Plan — **Strong** (unchanged)

- Filter/ACL builder UI closes G4.
- Coverage-gap-as-first-class UI object aligns with [frontend-plan.md §11](./frontend-plan.md).

### §10 Phase 5 Safety Gate — **Very Strong** (unchanged)

- Full-payload consent, change-ticket capture, dead-man timers, retention limits, chaos suite — all preserved.
- v1 open item #4 (IOS-XR EEM parity) **still** a Phase-2b/Phase-5 entry concern (v1 W2 preserved).

### §11 Phase 6 Synchronizer — **Strong**

- `QThreadPool` workers for coordinated remote trigger — correct Qt idiom.
- Persistent pre-armed Netmiko channels held in the Phase-1 pool — no cold-connect penalty at trigger time.
- SC-3 thresholds (<500 ms, <100 ms precision) unchanged and still architecturally supported.

### §12 Phase 7 Correlator — **Strong** (upgraded)

- Rust crate via pyo3 + maturin. v1 open item #1 resolved.
- Per-capture drop/truncation counter surfacing via correlator artifacts — correct R-2 mitigation.
- **v1 concern (correlator-language checkpoint too late) is now moot** — ADR-001 fixed the language.
- Benchmark checkpoint at end of Phase 7 (as a perf gate before Phase 8 CAPWAP work) is retained and appropriate.

### §13 Phase 8 Wireless — **Overloaded** (v1 W1 preserved)

- Scope density unchanged from v1.1: wireless discovery + path solver extension + 9800 driver (5 sub-features) + AP driver (4 sub-features) + wireless safety gate + HA SSO surfacing + correlator wireless features + post-run assertion.
- 5 weeks still ~30-40% optimistic. **Recommendation from v1 eval (split into 8a + 8b) still applies.**
- New concern: **PEEKREMOTE reactor benchmark** (§20 #3 revised — `qasync` vs `QThreadPool`) is currently gated at Phase 8 kickoff. Should be a Phase-8-entry gate (see R2).

### §14 Phase 9 Reporter — **Strong**

- Ladder diagram delivered via `QGraphicsScene` items + `QSvgGenerator` — aligns with [frontend-plan.md §11](./frontend-plan.md) inventory.
- NTP-degraded UX (C-10), retention-limits UI, SC-9 wall-clock harness — all present and correctly phase-mapped.
- Fault-verdict engine + evidence bundle (HTML + PDF via `weasyprint` or equivalent — not pinned; minor open item).

### §15 Phase 10 Release — **Strong** (upgraded)

- **PyInstaller one-folder** explicitly required; one-file mode prohibited without LGPL re-review — correct Qt/PySide6 hygiene, now codified in the deliverable text.
- macOS notarytool + Windows signtool + Debian dpkg-sig + AppImage — full 3-OS coverage.
- SBOM via `cyclonedx-py` (Python) + `cargo-cyclonedx` (Rust) — canonical dual-language SBOM path.
- Reproducible-build verification: `uv.lock` + `Cargo.lock` + `rust-toolchain.toml` + PyInstaller determinism flags. Correct.
- **Still missing**: rollback/recall procedure (v1 W10 preserved).

### §16 Cross-Cutting — **Adequate** (v1 W3 preserved)

- Golden-CLI workstream covering all 7 driver families — preserved.
- Localization scaffold via Qt Linguist from Phase 0 — correct upgrade over v1's i18next stub.
- **Still missing**: dedicated performance/scale workstream (v1 W3).

### §17 Testing — **Strong** (v1 W4 preserved)

- pytest-qt UI tests + containerlab/CML nightly + chaos + audit-log secret scan — all present.
- SC-9 harness as release gate — correct lever.
- **Still missing**: fuzz row for pcap/pcapng parsers (Rust) and CLI-output parsers (drivers). v1 W4 preserved.

### §18 Milestones — **Strong** (v1 W9 preserved)

- M2b correctly added.
- M6 single-milestone still hides Phase 8 sub-risk (v1 W9). Split M6 → M6a + M6b if Phase 8 splits (see R1).

### §19 Risk-to-Phase — **Strong** — full R-1..R-8 coverage, unchanged.

### §20 Open Items — **Improved** (v1 W2 partially resolved)

- Items **#1 (correlator language)** and **#7 (SSH library)** now marked **Resolved by ADR-001** — corrects v1 W2 in part.
- Item **#8 (Rust distribution)** partially resolved (maturin), with a residual follow-up on `cibuildwheel` vs per-OS GH runners — appropriate.
- Items **#4 (IOS-XR EEM parity)** and **#3 (PEEKREMOTE reactor sizing)** remain phase-entry blockers presented as "at kickoff" decisions. **Recommend elevating to entry-gates.**

### §21 Gap Traceability — **Excellent** — every G-item still closed with phase citation, unchanged from v1.1.

---

## 5. Carry-Forward Findings from v1 Eval

Explicit disposition of each v1-eval recommendation against the v1.2 plan.

| v1 Rec | Status against v1.2 | Notes |
|---|---|---|
| **R1** — Split Phase 8 into 8a + 8b | **NOT ADOPTED** | Phase 8 is still monolithic in v1.2. Carry forward as R1 of this eval. |
| **R2** — Phase-entry-gate table for items #1/#4/#7/#8 | **PARTIALLY ADOPTED** | #1 and #7 resolved; #4 and #8 residuals still "at kickoff." Carry forward with reduced scope. |
| **R3** — State Phase 2b staffing assumption | **NOT ADOPTED** | No capacity plan in §4 or §7b. Carry forward. |
| **R4** — Performance/scale workstream | **NOT ADOPTED** | No dedicated row in §16. Carry forward. |
| **R5** — Fuzz testing for pcap/pcapng + CLI parsers | **NOT ADOPTED** | No row in §17. Carry forward. |
| **R6** — Split `packages/persistence` → `packages/security` | **OBE** | Dissolved by the flat `src/` layout under ADR-001. |
| **R7** — Pin Electron + N-API versions | **OBE** | Dissolved by ADR-001 (no Electron, no N-API). Replaced by pyo3 ABI check ([edge-cases §18.1](./edge-cases.md)). |
| **R8** — Phase-0 SBOM baseline | **NOT ADOPTED** | Still deferred to Phase 10. Carry forward. |
| **R9** — Phase-10 rollback/recall procedure | **NOT ADOPTED** | Not in §15 deliverables. Carry forward. |
| **R10** — Capacity plan table in §4 | **NOT ADOPTED** | Carry forward (nice-to-have). |
| **R11** — Mermaid dependency graph between phases | **NOT ADOPTED** | Carry forward (nice-to-have). |

**Net**: 2/11 recommendations addressed (R6, R7 by ADR-001); 9/11 still open. See §12 for renumbered active recommendations.

---

## 6. Risk-to-Phase Coverage Check

All 8 architecture risks (R-1..R-8) still have first-mitigation and fully-mitigated phase mappings, unchanged from v1. R-4 (stranded AP) still two-layered (Phase 5 state machine + Phase 8 mode-diff). **Pass.**

---

## 7. Success-Criteria Traceability

All 10 SCs still traceable, unchanged from v1. **Pass.**

---

## 8. Schedule & Critical-Path Analysis

Stated total unchanged at ~37 weeks. Risk-adjusted analysis identical to v1:

- With Phase 2b parallelism: ~34 wks (requires ≥2 driver engineers — still unstated).
- Phase 8 realistic scope: ~7 weeks → risk-adjusted total **39–42 weeks**.

**Pivot-specific adjustment**: pyo3 + maturin at Phase 0 adds a ~2-day integration spike vs the Node/N-API baseline, absorbed by Phase 0's 2-week window. No net schedule impact.

**Schedule score: 3/5** — unchanged.

---

## 9. ADR-001 Cascade Integrity

Verification that the pivot is consistent across the doc set (not just landed in `implementation-plan.md`).

| Doc | ADR-001 alignment | Notes |
|---|---|---|
| [stack-decision.md](./stack-decision.md) | ADR-001 v1.0 Accepted | Source of truth. |
| [architecture.md](./architecture.md) | v1.1 — single Qt process, `keyring`, PyInstaller, Python entry points | §4/§5/§7/§12/§13/§14/§17/§20 rewritten. Cascade complete. |
| [implementation-plan.md](./implementation-plan.md) | v1.2 — this document | §2/§3/§4/§5/§6/§7/§10/§11/§12/§15/§16/§20 rewritten. Cascade complete. |
| [frontend-plan.md](./frontend-plan.md) | v1.1 — PySide6 UI, qt-material, QAccessible, Qt Linguist, pytest-qt | Header, §2, §11 QWidget inventory, §13 a11y/i18n/test, §16 open items closed. Cascade complete. |
| [edge-cases.md](./edge-cases.md) | §18.1 pyo3 ABI, §18.2 Qt main-thread stall watchdog | Electron IPC / renderer-crash items replaced. Cascade complete. |
| [eval-v1.md](./eval-v1.md) | Historical — evaluates pre-pivot v1.1 | Banner tags OBE findings; retained for traceability. |
| [problemStatement.md](./problemStatement.md) | Stack-agnostic (no hits on Electron/TS/Node/pnpm/React) | Zero drift; no edits required. |

**Cascade score: 5/5 — no stale stack references outside the ADR itself, historical eval, and legitimate "removed vs v1.1" callouts.**

---

## 10. Strengths

Carry-forwards from v1 (all preserved in v1.2):

1. Safety-before-capture sequencing (Phase 5 before Phase 6).
2. Coverage-gap-as-first-class object (no silent no-ops).
3. NX-OS unfiltered refusal at driver boundary.
4. Golden-CLI as a workstream, not a one-off.
5. Chaos suite lands with the state machine.
6. Immutable, hash-chained audit log from Phase 0.
7. Explicit gap traceability (§21).

New in v1.2:

8. **Single-language stack** — Python across UI + orchestration + facade eliminates the v1-era TS↔Node↔Rust context switch and the IPC schema layer.
9. **Native Qt integration** — accessibility, i18n, secure store, menus, file dialogs via Qt rather than Electron shims; simpler on all three OSes.
10. **Fewer independent pin surfaces** — one lockfile (`uv.lock`), one Rust toolchain file, one PyInstaller spec set, one type-checker. Materially lower supply-chain surface than v1.1's pnpm + npm + cargo + electron-builder combination.
11. **pyo3 at Phase 0** — early integration surfaces ABI + wheel-production issues before Phase 7; better than the v1.1 deferred N-API validation.

---

## 11. Weaknesses & Gaps

Preserved from v1 eval:

1. **Phase 8 overload** — 8+ major deliverables in 5 weeks (v1 W1).
2. **Items #3, #4 mis-sequenced** — presented as kickoff decisions, are phase-entry blockers (v1 W2, reduced scope).
3. **No dedicated performance/scale workstream** (v1 W3).
4. **Missing fuzz testing** — pcap/pcapng + CLI-output parsers (v1 W4).
5. **Phase 2b staffing assumption implicit** (v1 W5).
6. **Phase 0 SBOM baseline deferred** to Phase 10 (v1 W8).
7. **M6 single-milestone hides Phase 8 sub-risk** (v1 W9).
8. **No release rollback/recall procedure** (v1 W10).

New in v1.2:

9. **PyInstaller cold-start regression** — 0.5–1.5 s vs Electron's 0.3–0.6 s. Acceptable for a long-session desktop tool, but should be measured and reported in the SC-9 harness as informational (not a gate).
10. **`qasync` scope not gated** — listed in §3 without a phase citation. Should be tied to the Phase 8 PEEKREMOTE benchmark or removed from the top-level toolchain table.
11. **Fault-verdict evidence bundle rendering** — HTML + PDF path not pinned to a specific library (`weasyprint`, `reportlab`, or Qt's `QPrinter`+`QTextDocument`). Minor open item.

---

## 12. Recommendations

**Must-fix before approval:**

- **R1** *(carry-forward from v1 R1)* — Split Phase 8 into **8a** (9800 + discovery + path solver extension, ~3 wks) and **8b** (AP sniffer + correlator wireless + post-run assertion, ~4 wks). Split M6 into M6a + M6b accordingly. Highest-risk phase, tightest schedule — same conclusion as v1; the pivot did not change wireless scope.
- **R2** *(carry-forward, reduced)* — Convert §20 items **#3 (PEEKREMOTE reactor)** and **#4 (IOS-XR EEM parity)** into a "Phase-Entry Gates" table with a resolve-by-phase-entry column. Items #1 and #7 are already resolved by ADR-001; #8 residual is acceptable as a Phase-0 spike.
- **R3** *(carry-forward from v1 R3)* — State the Phase 2b parallelism staffing assumption explicitly.

**Should-fix (v1.3):**

- **R4** *(carry-forward from v1 R4)* — Add a cross-cutting performance/scale workstream in §16 with a nightly harness from Phase 6 onward.
- **R5** *(carry-forward from v1 R5)* — Add fuzz-testing rows to §17 for the Rust pcap/pcapng parser (via `cargo-fuzz`) and CLI-output parsers (via `hypothesis`).
- **R6** *(carry-forward from v1 R8)* — Add a Phase-0 SBOM baseline exit criterion (`cyclonedx-py` + `cargo-cyclonedx` smoke).
- **R7** *(carry-forward from v1 R9)* — Add a Phase-10 rollback/recall procedure deliverable.
- **R8** *(new)* — Tie `qasync` to the Phase 8 PEEKREMOTE reactor benchmark or remove from §3 top-level toolchain table until decided.
- **R9** *(new)* — Pin the fault-verdict evidence-bundle rendering library (weasyprint / reportlab / Qt native) as a Phase-9 open item.
- **R10** *(new)* — Add PyInstaller cold-start measurement to the SC-9 harness as informational metric (not gated), to catch regression across releases.

**Nice-to-have:**

- **R11** *(carry-forward from v1 R10)* — Add a "capacity plan" table (engineers per phase) to §4.
- **R12** *(carry-forward from v1 R11)* — Add explicit phase-dependency Mermaid graph rather than a linear numbered list.

---

## 13. Verdict

**APPROVE WITH MINOR REVISIONS.**

The v1.2 plan preserves everything that made v1.1 architecturally sound — safety-before-capture sequencing, coverage-gap-as-first-class, defense-in-depth on NX-OS filtering, chaos-with-state-machine, hash-chained audit from Phase 0 — and inherits a simpler stack, a single delivery pipeline, and a lower supply-chain surface via ADR-001. The pivot resolves four v1-eval weaknesses (packages/security split, Electron+N-API pins, correlator-language open item, SSH library open item) at zero delivery cost.

The residual risks to on-time delivery are unchanged from v1: **Phase 8 scope density**, **late-resolving open items** (now reduced to #3 and #4), and **implicit staffing assumptions**. Applying R1–R3 before Phase 1 kickoff removes the schedule and technical-debt risk without disturbing delivery strategy — identical conclusion to v1 eval, at a higher confidence level because the stack pivot eliminated two of the four originally mis-sequenced items.

**Recommended next actions:**

1. Apply R1–R3 to produce implementation-plan.md **v1.3**.
2. Schedule Phase 1 kickoff only after §20 items #4 (IOS-XR EEM parity) is resolved.
3. Stand up the golden-CLI capture tool (§16 workstream) in Phase 0.
4. Add a Phase-8-entry gate for §20 item #3 (PEEKREMOTE reactor benchmark).

---

---

## 14. v2.1 Re-Evaluation of implementation-plan.md v1.4

> **Delta evaluation.** §§1–13 above evaluated v1.2 and produced R1–R12. The plan has since advanced to **v1.3** (R1–R10 applied) and now **v1.4** (R11 + R12 applied). This section re-scores v1.4 against the same rubric and closes each recommendation.

### 14.1 Recommendation Closure Table

| Rec | v2.0 status | Applied in | Landing site in v1.4 | v2.1 status |
|---|---|---|---|---|
| **R1** Phase 8 split → 8a / 8b | Must-fix | v1.3 | §4 phase overview; §13/§13b full phase bodies; §18 M6a/M6b | ✅ **Closed** |
| **R2** #3/#4 as Phase-Entry Gates | Must-fix | v1.3 | §20.1 gates table (G-P8b-1, G-P8b-2, G-P7-1, G-P0-1) | ✅ **Closed** |
| **R3** Phase 2b staffing assumption explicit | Must-fix | v1.3 | §7b staffing callout + §4.1 capacity table row | ✅ **Closed (twice — narrative + table)** |
| **R4** Perf/scale cross-cutting workstream | Should-fix | v1.3 | §16 new row (nightly harness from Phase 6, PEEKREMOTE ingest from 8b, trend series) | ✅ **Closed** |
| **R5** Fuzz rows (cargo-fuzz + hypothesis) | Should-fix | v1.3 | §17 two new rows | ✅ **Closed** |
| **R6** Phase 0 SBOM baseline | Should-fix | v1.3 | §5 Phase 0 exit criterion + `packaging/sbom/` reference artifact | ✅ **Closed** |
| **R7** Rollback / recall runbook | Should-fix | v1.3 | §15 Phase 10 deliverable (per-OS withdrawal, signed known-bad banner, journal/audit preservation, staging dry-run) | ✅ **Closed** |
| **R8** `qasync` gating | Should-fix | v1.3 | §3 row tagged with G-P8b-1 explicit gate | ✅ **Closed** |
| **R9** Evidence-bundle renderer decision | Should-fix | v1.3 | §20.2 open item #9 (weasyprint / reportlab / QPrinter+QTextDocument, decision at Phase 9 kickoff) | ✅ **Closed** *(tracked open item, not deferred implicitly)* |
| **R10** PyInstaller cold-start informational metric | Should-fix | v1.3 | §17 SC-9 harness row extended | ✅ **Closed** |
| **R11** Capacity plan table | Nice-to-have | v1.4 | §4.1 new subsection (per-phase FTE + overlap peaks + cross-cutting fractional load) | ✅ **Closed** |
| **R12** Phase-dependency Mermaid graph | Nice-to-have | v1.4 | §4.2 new subsection (solid = hard precedence, dashed = feeds, hexagons = §20.1 gates) | ✅ **Closed** |

**All 12 recommendations closed. No open recommendations against v1.4.**

### 14.2 Re-Scored Rubric

| Dimension | Weight | v2.0 Score | v2.1 Score | Δ | Rationale |
|---|---:|---:|---:|---:|---|
| Alignment with architecture v1.1 | 15% | 5 | 5 | — | Unchanged; ADR-001 cascade still intact. |
| Alignment with problem statement / success criteria | 15% | 5 | 5 | — | SC-1..SC-10 traceability preserved through phase splits. |
| Risk coverage & mitigation sequencing | 15% | 5 | 5 | — | R-1..R-8 mappings preserved; 8a/8b split sharpens R-4/R-7 sequencing. |
| Phase decomposition & vertical-slice discipline | 10% | 5 | 5 | — | 8a/8b are each demoable vertical slices. |
| Schedule realism | 15% | 3 | **4** | **+1** | Capacity plan (§4.1) surfaces the 6-FTE peak in Phase 2b‖3‖4; §20.1 gates make late-resolving items visible before slip. Not a 5 because the 6-FTE peak is now visible but not yet resourced. |
| Testability & exit-criteria rigor | 10% | 4 | **5** | **+1** | Fuzz rows (R5), SC-9 wall-clock harness with cold-start metric (R10), audit-log secret scan preserved, chaos coverage extended to AP-restoration diff. |
| Cross-cutting & security workstreams | 5% | 4 | **5** | **+1** | New Perf & Scale row (R4); SBOM at Phase 0 (R6); rollback runbook (R7); consent-copy review already tracked. |
| Open-item / decision hygiene | 5% | 4 | **5** | **+1** | Phase-Entry Gates (§20.1) convert soft items into hard gates; evidence-renderer decision now tracked (R9); #1/#7 already resolved by ADR-001. |
| Gap closure vs v1.0 report | 10% | 5 | 5 | — | §21 traceability intact. |

**Weighted score: v2.0 = 4.6 → v2.1 = 4.9 / 5.**

Rounding aside, the residual 0.1 gap is entirely the schedule-realism dimension: the capacity table makes staffing peaks **visible**, but does not by itself **resource** them. That is a program-management action, not a plan-document action, and is called out as the sole outstanding action in §14.4.

### 14.3 v2.1 Strengths (net-new vs v2.0)

1. **Staffing peaks are no longer hidden.** §4.1 exposes the 6-FTE concurrent window (Phase 2b ‖ 3 ‖ 4) that §7b previously only implied for the driver row. Program managers can now reconcile against real headcount before Phase 2 exit.
2. **Dependency graph replaces linear reading.** §4.2's Mermaid graph makes the 8a→8b gate, the Phase 7 correlator-perf gate, and the Phase 2b parallel branch visually explicit. Cross-cutting workstreams are shown as non-blocking dashed edges — matches §16's "continuous fractional load" framing.
3. **Gate visibility is now three-layered.** §20.1 gates table (narrative) + §4.1 capacity peaks (numeric) + §4.2 graph (visual). A slip in any one dimension is now discoverable from at least two of the three.
4. **Phase-Entry Gates + PyInstaller informational metric + SBOM-at-Phase-0** collectively turn what were previously Phase 10 surprises (recall procedure absent, SBOM ad-hoc, cold-start unknown) into Phase-0 or Phase-8-entry knowns.

### 14.4 v2.1 Residual Weaknesses

Down from 11 in v2.0 to **1** in v2.1:

1. **The 6-FTE Phase 2b ‖ 3 ‖ 4 peak is visible but not committed.** §4.1 makes the demand explicit; the plan cannot itself confirm the supply. Program-management action required before Phase 2 exit: either confirm 6 FTE available, or invoke the §4.1 fallback (serialize 2b after 3–4, adds ~3 wks to critical path, delays M2b → M6a).

All other v2.0 weaknesses (Phase 8 overload, mis-sequenced items #3/#4, missing perf workstream, missing fuzz row, implicit staffing, Phase 0 SBOM, single M6 milestone, no rollback procedure, `qasync` ungated, evidence-bundle renderer unpinned, PyInstaller cold-start unmeasured) are closed by R1–R12 as tabulated in §14.1.

### 14.5 v2.1 Verdict

**APPROVE FOR PHASE 1 KICKOFF.**

Up from v2.0's "Approve with minor revisions." The minor revisions have been applied end-to-end (R1–R12), all 12 recommendations are closed, and the score moved from 4.6 to 4.9. The single residual weakness is a staffing-commitment action outside the plan document's scope.

**Recommended next actions (superseding v2.0 §13):**

1. ~~Apply R1–R3 to produce v1.3.~~ ✅ Done in v1.3.
2. ~~Apply R4–R10.~~ ✅ Done in v1.3.
3. ~~Apply R11–R12.~~ ✅ Done in v1.4.
4. **Confirm 6-FTE staffing for the Phase 2b ‖ 3 ‖ 4 overlap** — or record the fallback (serialize 2b) as a plan amendment before Phase 2 exit.
5. Schedule Phase 1 kickoff only after §20.1 gate **G-P8b-2** (IOS-XR EEM parity) has a written resolution or written mitigation, per its "Resolution required by: End of Phase 5" clause (early confirmation removes the retroactive risk).
6. Stand up the golden-CLI capture tool (§16 workstream) and the Phase-0 SBOM baseline artifact (`packaging/sbom/`) in Phase 0.
7. Schedule the G-P7-1 correlator-perf benchmark and the G-P8b-1 PEEKREMOTE reactor benchmark as concrete tasks in the Phase 7 and Phase 8a exit checklists respectively (they are gates, not aspirations).

---

*End of evaluation — v2.1 traceable to [implementation-plan.md](./implementation-plan.md) v1.4, [architecture.md](./architecture.md) v1.1, [frontend-plan.md](./frontend-plan.md) v1.1, [problemStatement.md](./problemStatement.md) v2.0, and [stack-decision.md](./stack-decision.md) ADR-001. Historical v1 eval preserved as [eval-v1.md](./eval-v1.md); v2.0 body preserved above §14 as the audit trail for R1–R12.*
