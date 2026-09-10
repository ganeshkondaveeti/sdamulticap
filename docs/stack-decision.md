# MultiCap — Stack Decision (ADR-001)

> **Architecture Decision Record: Desktop application stack**

| Field | Value |
|---|---|
| **Project** | MultiCap — Cisco Multi-Platform Synchronized Packet Capture Orchestrator |
| **Document** | stack-decision.md |
| **ADR ID** | ADR-001 |
| **Version** | 1.0 |
| **Date** | 2026-09-10 |
| **Status** | **Accepted** |
| **Owner** | Lakshmi Ganesh Kondaveeti — Technical Consulting Engineering Technical Leader |
| **Supersedes** | [architecture.md](./architecture.md) §14 (v1.0), [implementation-plan.md](./implementation-plan.md) §2–§3 (v1.1) |
| **Cascaded into** | architecture.md v1.1, implementation-plan.md v1.2, frontend-plan.md v1.1 |

---

## 1. Context

The v1.0 architecture recommended an **Electron + React + TypeScript** shell with a **Node.js** main process, native N-API addons for packet processing, and Playwright for UI test. Before executing Phase 0, a stack pivot was proposed to reduce delivery risk and align the toolchain with the team's Python-heavy operational tooling, the Cisco NetDevOps ecosystem, and the read-only, single-user, on-box nature of MultiCap.

The pivot candidate: **PySide6 (Qt for Python) + Qt Widgets, on top of a Python core**, with a Rust correlator retained behind a **pyo3** binding boundary.

---

## 2. Decision

MultiCap will be built on the following stack:

| Concern | Choice | Notes |
|---|---|---|
| **Shell / UI toolkit** | **PySide6 (Qt 6.x, LGPL)** with **Qt Widgets** | Not PyQt6 (GPL). Widgets over QML for v1 (density-first, form-heavy UI). |
| **Application language** | **Python 3.12+** | Single language across UI, orchestration, drivers, collectors. |
| **UI theming** | **qt-material** | Material Design tokens delivered as pure QSS; cross-platform light/dark. |
| **Topology rendering** | **QGraphicsScene** + **NetworkX** (layout only) | Native Qt scene graph; NetworkX supplies graph algorithms + layout seeds. |
| **Ladder diagram** | **QGraphicsScene** with custom `QGraphicsItem` subclasses | Native, GPU-accelerated, export to SVG via `QSvgGenerator`. |
| **SSH transport** | **Netmiko** (built on Paramiko) | Cisco-idiomatic; TextFSM/NTC integration; wide platform coverage. |
| **Structured transport (later)** | Evaluate **ncclient** (NETCONF), **PySNMP** (SNMP) | Post-v1; deferred per §17 of implementation-plan. |
| **CLI parsing** | **TextFSM + NTC Templates** | Golden-CLI fixture format. |
| **Concurrency** | `QThreadPool` + `QSemaphore` for blocking Netmiko sessions; **qasync** where an asyncio event loop is required inside the Qt loop | Netmiko is synchronous; concurrency caps enforced per SC-04. |
| **Persistence** | **SQLite (WAL mode)** via `sqlite3` stdlib module | Journal, session state, audit log — unchanged from v1.0. |
| **Secure storage** | **`keyring`** (Python) | OS keychain: Keychain / DPAPI / Secret Service. |
| **Correlator** | **Rust** crate exposed via **pyo3** Python bindings | Retains Rust performance; loses N-API dependency on Node. |
| **Data models** | **pydantic v2** + **dataclasses** | Replaces the TS type surface in architecture.md §7. |
| **Localization** | **Qt Linguist** (`.ts` / `.qm` files) | en-US only for v1; infra ready for future locales. |
| **Accessibility** | **QAccessible** interfaces on custom widgets | WCAG 2.1 AA target retained. |
| **UI testing** | **pytest-qt** | Replaces Playwright. |
| **Unit / property testing** | **pytest** + **hypothesis** | Replaces vitest/jest. |
| **Integration testing** | **containerlab** / **CML** driven from pytest | Unchanged from v1.0. |
| **Packaging** | **PyInstaller** one-folder bundle wrapped by an OS installer (`.dmg` / `.msi` / `.deb`) | Signed manually per §15 of implementation-plan. |
| **Signing** | `codesign` + `notarytool` (macOS), `signtool` (Windows), `dpkg-sig` (Debian) | Manual for v1; CI-driven later. |

---

## 3. Rationale

### 3.1 Why PySide6 over Electron

- **Single language.** Orchestration core, drivers, parsers, collectors, and UI all live in Python. Eliminates the TS ↔ Node ↔ Rust context switch and the IPC schema layer (`packages/ipc-schema`) that v1.0 required to bridge renderer and main.
- **Ecosystem fit.** Netmiko, ncclient, PySNMP, TextFSM/NTC Templates, pyATS, Genie — the Cisco NetDevOps stack is Python. Electron/TS forced re-implementation or FFI wrapping of tools that already exist.
- **Footprint.** PyInstaller one-folder bundles land in the 200–400 MB range vs. Electron's 300–500 MB baseline; RAM at idle is materially lower.
- **Native surfaces.** OS keychain (`keyring`), native menus, native file dialogs, and native accessibility come via Qt directly — no `electron.remote` or `contextBridge` gymnastics.
- **LGPL is compatible** with a distributed desktop application provided dynamic linking is preserved. PyInstaller's runtime does not statically link Qt.

### 3.2 Why Qt Widgets over QML for v1

MultiCap's UI is form-heavy, table-heavy, and density-first (per frontend-plan.md §14 wireframes). Qt Widgets ships mature `QTableView`, `QTreeView`, `QGraphicsView`, `QStackedWidget`, and consent/gate dialogs out of the box. QML's strengths (touch, animation, fluid layouts) do not apply here. QML remains available for future modules (e.g., an operator dashboard) without invalidating the v1 choice.

### 3.3 Why Rust + pyo3 (not pure Python correlator)

- **Correlator hot path** does CAPWAP decap, clock-offset apply, and pcapng merge on potentially GB-scale captures. Python is not viable at this throughput.
- **pyo3** exposes the Rust crate as a native Python module (`correlator_rs`) — same performance envelope as the v1.0 N-API path, one fewer runtime dependency (no Node).
- **Build integration**: `maturin` produces wheels; the Rust crate lives in-tree under `src/multicap/correlator_rs/`.

### 3.4 Why qt-material

- **Pure QSS** — no custom paint code, works with existing Qt Widgets without subclassing.
- **Material Design** tokens (spacing, elevation, colour ramps) provide the design system frontend-plan.md §16 required to close.
- **Cross-platform parity** — identical look on macOS / Windows / Linux, matching NR-13.
- **MIT licensed**, no runtime cost.

### 3.5 Why "thorough cascade" for docs

Partial edits leave `architecture.md` §14 pointing at Electron while `implementation-plan.md` phase specs reference `packages/ui`. The pivot touches phase toolchains, testing strategy, packaging, and repo layout — piecemeal edits produce an unbuildable spec. One coordinated pass eliminates cross-doc drift.

### 3.6 Why rename `packages/ui` → `src/multicap/app/widgets` now

- **Idiomatic Python.** Python packages live under `src/<distribution>/`, not `packages/<name>/`.
- **Single distribution.** MultiCap ships as one Python distribution (`multicap`), not a monorepo of npm packages.
- **Import ergonomics.** `from multicap.app.widgets import PlanReview` is the target import surface — deferring the rename means every phase writes code against a name that must later change.

---

## 4. Consequences

### 4.1 Positive

- Single-language codebase; no IPC schema layer.
- Native OS integration (keychain, accessibility, menus) via Qt.
- Reduced bundle size and idle RAM.
- Reuse of Cisco Python ecosystem (Netmiko, TextFSM/NTC, pyATS).
- Rust correlator performance retained via pyo3.

### 4.2 Negative / Trade-offs

- **Netmiko is synchronous.** Concurrency requires `QThreadPool` + `QSemaphore` discipline; per-platform SSH caps (SC-04) must be enforced in the thread pool submission layer, not in async schedulers.
- **PyInstaller cold-start** is measurably slower than an Electron binary launch (0.5–1.5 s vs. 0.3–0.6 s). Acceptable for a desktop tool that runs a long session.
- **Qt licensing discipline.** PySide6 is LGPL; static linking is prohibited. PyInstaller's default one-folder mode preserves dynamic linking — we must not switch to one-file mode without an LGPL re-review.
- **QML deferred.** Any future touch / mobile companion cannot rely on v1 widget code.

### 4.3 Deferred / Superseded

- `packages/ipc-schema` — **removed**. No renderer/main process boundary; Qt signals/slots replace typed IPC.
- Playwright — **removed** from v1 test matrix; pytest-qt covers UI.
- vitest / jest — **removed**; pytest covers unit tests.
- N-API — **removed**; pyo3 supersedes it for the correlator.
- Node.js runtime — **removed** entirely.

---

## 5. Alternatives Considered

| Alternative | Verdict | Reason |
|---|---|---|
| **Electron + React + TS** (v1.0) | Rejected | Two languages, larger bundle, IPC surface, ecosystem mismatch with Cisco Python tooling. |
| **Tauri + Rust + web frontend** | Rejected | Smaller than Electron but still forces a language boundary and does not solve the Python-ecosystem reuse problem. |
| **PyQt6** | Rejected | GPL licensing conflicts with signed, redistributed desktop binary without commercial licence. |
| **PySide6 + QML** | Deferred | Overkill for form/table-heavy v1; QML remains available for future modules. |
| **wxPython** | Rejected | Weaker accessibility story on macOS; no equivalent to QGraphicsScene for topology / ladder rendering. |
| **Textual (TUI)** | Rejected | NR-13 requires desktop GUI on macOS / Windows / Linux with WCAG 2.1 AA. |
| **Pure-Python correlator** | Rejected | Cannot meet throughput on GB-scale merged captures. |
| **C++ correlator via pybind11** | Rejected | Rust already chosen in v1.0; pyo3 preserves that investment. |

---

## 6. Cascade Plan

This ADR triggers the following edits (tracked in the version bumps of each companion doc):

### 6.1 `docs/architecture.md` → **v1.1**

- **§4 Container diagram** — replace Electron main/renderer nodes with a single PySide6 process; remove IPC arrow; keep correlator as a native module boundary.
- **§5 Layer view** — restate layers in Python terms (`multicap.app`, `multicap.core`, `multicap.drivers`, `multicap.transport`, `multicap.correlator_rs`).
- **§6 Components** — rename `ui` → `app.widgets`; remove `ipc-schema`.
- **§7 Data model** — convert TS interfaces to pydantic v2 / dataclass definitions.
- **§12 Security** — replace Electron-specific hardening with Qt + `keyring` model.
- **§14 Technology stack** — replace table with §2 of this ADR (verbatim).
- **§17 Extensibility** — restate driver-plugin surface as Python entry points (`multicap.drivers` group).
- **§20 Open questions** — remove items closed by this ADR.

### 6.2 `docs/implementation-plan.md` → **v1.2**

- **§2 Repo layout** — replace `apps/` + `packages/` monorepo with `src/multicap/` package tree.
- **§3 Toolchain** — Python 3.12, `uv` for env / lockfile, `ruff` for lint, `mypy --strict` for typing, `maturin` for the Rust wheel, PyInstaller for packaging.
- **§4–§14 Phase specs** — replace TS/Node tooling references; keep phase scope unchanged.
- **§15 Packaging** — PyInstaller one-folder; per-OS installer + signing steps.
- **§16 Cross-cutting** — swap Playwright → pytest-qt; add Qt Linguist workstream.
- **§17 Testing** — restate UI-test approach.
- **§20 Open items** — close items answered by this ADR.

### 6.3 `docs/frontend-plan.md` → **v1.1**

- **§11 Component inventory** — rename `packages/ui/**` paths to `src/multicap/app/widgets/**`; map each React component to its `QWidget` subclass.
- **§13 Tooling** — swap Playwright → pytest-qt; string tables → Qt Linguist; axe-core → QAccessible + manual audit.
- **§16 Open items** — mark design-system, topology-lib, and ladder-approach items **closed** with references to §2 of this ADR.

### 6.4 `docs/problemStatement.md`, `docs/edge-cases.md`, `docs/eval.md`

- Scrub incidental mentions of "Electron", "TypeScript", "Node.js", "N-API"; replace with stack-agnostic wording where the reference was descriptive, or with the new stack where the reference was normative.

---

## 7. Non-Goals

This ADR does **not**:

- Change the phased delivery order in implementation-plan.md §4.
- Change the safety-gate, journal, or cleanup semantics in architecture.md §8–§11.
- Change the wireframes in frontend-plan.md §14 (they are tech-agnostic).
- Commit to structured transport (ncclient / PySNMP) for v1 — those remain post-v1 evaluations.

---

## 8. References

- [architecture.md](./architecture.md) — system architecture (target v1.1).
- [implementation-plan.md](./implementation-plan.md) — phased delivery plan (target v1.2).
- [frontend-plan.md](./frontend-plan.md) — PySide6 UI product surface (v1.1 landed).
- [problemStatement.md](./problemStatement.md) — requirements source of truth.
- Qt for Python licensing: <https://doc.qt.io/qtforpython-6/licenses.html>
- pyo3: <https://pyo3.rs/>
- qt-material: <https://github.com/UN-GCPDS/qt-material>
- Netmiko: <https://github.com/ktbyers/netmiko>
- PyInstaller LGPL notes: <https://pyinstaller.org/en/stable/operating-mode.html>
