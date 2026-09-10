# Cisco Multi-Platform Synchronized Packet-Capture Orchestrator (`multicap`)

Phase 4 substrate. This repository now contains the transport/persistence foundation, first driver contract slice, wired discovery/topology service, and path-intent plan generator described in [`docs/implementation-plan.md`](./docs/implementation-plan.md) §9.

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

## Phase 4 Status

This checkout contains Phase 0 delivery machinery, Phase 1 transport/persistence substrate, Phase 2 driver contract/capability registry, Phase 3 discovery/topology, and Phase 4 wired intent planning: path-intent compiler, BFS path solver, ranked strategy selection, explicit coverage gaps, blast-radius/service-impact estimates, filter builder, and plan-review view-model rows.

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
