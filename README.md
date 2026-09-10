# Cisco Multi-Platform Synchronized Packet-Capture Orchestrator (`multicap`)

Phase 8a substrate. This repository now contains the transport/persistence foundation, wired discovery/planning/execution/correlation foundation, and the controller-side wireless foundations described in [`docs/implementation-plan.md`](./docs/implementation-plan.md) §13.

## Read First

| Doc | Purpose |
|---|---|
| [`docs/problemStatement.md`](./docs/problemStatement.md) | Product problem statement |
| [`docs/implementation-plan.md`](./docs/implementation-plan.md) | **v1.6** — 12-phase backend delivery plan |
| [`docs/eval.md`](./docs/eval.md) | **v2.1** — plan evaluation, verdict: APPROVE FOR PHASE 1 KICKOFF |
| [`docs/architecture.md`](./docs/architecture.md) | System architecture |
| [`docs/frontend-plan.md`](./docs/frontend-plan.md) | PySide6 UI plan (sibling doc) |
| [`docs/stack-decision.md`](./docs/stack-decision.md) | ADR-001 — PySide6/Python over Electron/TS |
| [`docs/edge-cases.md`](./docs/edge-cases.md) | Edge cases & failure modes |

## Phase 8a Status

This checkout contains Phase 0 delivery machinery through Phase 7 wired execution/correlation plus Phase 8a wireless foundations: controller/AP/WLAN/client-location models, switching-mode-aware wireless path solver, FlexConnect/fabric wired-uplink redirects, IOS-XE 9800 controller driver stubs for wireless EPC, control-plane/CAPWAP-inner capture, AP capture profile definition, and radioactive tracing control.

## Bootstrapping (Phase 0)

```bash
uv sync --extra dev --extra ui --extra net
uv run ruff check .
uv run mypy
uv run pytest -m "unit or contract"
```

## Phase 1 Demo

```bash
uv run python tools/phase1_demo.py
```

The demo drives the Phase 1 substrate without live devices: mock SSH exec, journal compensation replay, audit-chain verification, and pcapng storage.

## Phase 2 Demo

```bash
uv run golden-capture --platform iosxe-switch --os-family ios-xe --release-train 17.13 --feature epc_physical --output /tmp/iosxe_17_13.json
uv run pytest -m contract
```

The contract tests drive IOS-XE and NX-OS drivers end-to-end against mock transport and prove NX-OS refuses unfiltered `ethanalyzer` before issuing any command.

## Phase 3 Demo

```bash
uv run python tools/phase3_demo.py
```

The demo drives a mock CDP/LLDP crawl into a typed topology graph.

## Phase 4 Demo

```bash
uv run python tools/phase4_demo.py
```

The demo compiles a wired path intent into a per-device capture plan with EPC and `ethanalyzer` strategies plus platform-native filter expressions.

## Phase 5 Demo

```bash
uv run python tools/phase5_demo.py
```

The demo drives a mock plan through safety evaluation, full-payload consent, change-ticket audit, cleanup transitions, config-diff verification, and final `DONE` state.

## Phase 6 Demo

```bash
uv run python tools/phase6_demo.py
```

The demo drives a mock wired job through arm, parallel trigger, stop, collect, placeholder correlate, cleanup, and final `DONE` state.

## Phase 7 Demo

```bash
uv run python tools/phase7_demo.py
```

The demo collects mock ERSPAN/local packets, estimates device clock offset, and writes a merged pcapng-style JSONL artifact with correlation metadata.

## Phase 8a Demo

```bash
uv run python tools/phase8a_demo.py
```

The demo resolves a wireless client location and produces a controller-side wireless plan with a FlexConnect wired-uplink redirect.

## Release Artifacts (per §15, v1.6)

Five signed artifacts from one git tag:

| OS | Artifact | Tool |
|---|---|---|
| macOS | `.dmg` | PyInstaller + `codesign` + `notarytool` |
| Windows | **`.exe`** | Inno Setup + `signtool` |
| Windows | **`.msi`** | WiX + `signtool` |
| Debian / Ubuntu | `.deb` | `dpkg-deb` + `dpkg-sig` |
| Other Linux | AppImage | `appimagetool` + GPG |

## License

TBD — must be resolved before Phase 10 / SC-10 release (see §15).
