# Cisco Multi-Platform Synchronized Packet-Capture Orchestrator (`multicap`)

Phase 7 substrate. This repository now contains the transport/persistence foundation, first driver contract slice, wired discovery/topology service, path-intent plan generator, safety/cleanup gate, synchronizer/job-runner slice, and collector/correlation foundation described in [`docs/implementation-plan.md`](./docs/implementation-plan.md) §12.

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

## Phase 7 Status

This checkout contains Phase 0 delivery machinery, Phase 1 transport/persistence substrate, Phase 2 driver contract/capability registry, Phase 3 discovery/topology, Phase 4 wired intent planning, Phase 5 safety/cleanup, Phase 6 synchronized job execution, and Phase 7 collector/correlation: ERSPAN, PEEKREMOTE stub, local capture records, RTT-compensated clock offsets, CAPWAP outer-port parsing, merge/dedup, and drop/truncation counter surfacing.

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
