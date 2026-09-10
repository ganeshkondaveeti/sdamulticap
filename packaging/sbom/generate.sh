#!/usr/bin/env bash
# Regenerate deterministic SBOM baselines for §5 Phase 0 exit + §15 release attestation.
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p packaging/sbom/ref

uv run python - <<'PY'
from __future__ import annotations

import json
import tomllib
import uuid
from pathlib import Path
from typing import Any


def purl(kind: str, name: str, version: str) -> str:
    return f"pkg:{kind}/{name}@{version}"


def write_bom(path: Path, name: str, components: list[dict[str, Any]], dependencies: list[dict[str, Any]]) -> None:
    document = {
        "$schema": "http://cyclonedx.org/schema/bom-1.6.schema.json",
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, path.name)}",
        "version": 1,
        "metadata": {
            "timestamp": "1970-01-01T00:00:00+00:00",
            "component": {
                "type": "application",
                "name": name,
                "version": "0.0.0",
                "bom-ref": f"{name}==0.0.0",
            },
        },
        "components": sorted(components, key=lambda item: (item["name"].lower(), item["version"])),
        "dependencies": sorted(dependencies, key=lambda item: item["ref"]),
    }
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")


uv_lock = tomllib.loads(Path("uv.lock").read_text())
python_components: list[dict[str, Any]] = []
python_dependencies: list[dict[str, Any]] = []
for package in uv_lock["package"]:
    name = package["name"]
    version = package["version"]
    ref = f"{name}=={version}"
    python_components.append(
        {
            "type": "application" if name == "multicap" else "library",
            "name": name,
            "version": version,
            "bom-ref": ref,
            "purl": purl("pypi", name, version),
        }
    )
    depends_on = sorted({dependency["name"] for dependency in package.get("dependencies", [])})
    python_dependencies.append({"ref": ref, "dependsOn": depends_on})

write_bom(
    Path("packaging/sbom/ref/multicap.python.cdx.json"),
    "multicap-python-lock",
    python_components,
    python_dependencies,
)

cargo_manifest = tomllib.loads(Path("src/multicap/correlator_rs/Cargo.toml").read_text())
rust_components: list[dict[str, Any]] = []
rust_dependencies: list[dict[str, Any]] = []
crate_name = cargo_manifest["package"]["name"]
crate_version = cargo_manifest["package"]["version"]
crate_ref = f"{crate_name}@{crate_version}"
rust_components.append(
    {
        "type": "application",
        "name": crate_name,
        "version": crate_version,
        "bom-ref": crate_ref,
        "purl": purl("cargo", crate_name, crate_version),
    }
)

for name, spec in sorted(cargo_manifest.get("dependencies", {}).items()):
    version = spec["version"] if isinstance(spec, dict) else str(spec)
    ref = f"{name}@{version}"
    rust_components.append(
        {
            "type": "library",
            "name": name,
            "version": version,
            "bom-ref": ref,
            "purl": purl("cargo", name, version),
        }
    )
    rust_dependencies.append({"ref": ref, "dependsOn": []})

rust_dependencies.append(
    {"ref": crate_ref, "dependsOn": sorted(item["bom-ref"] for item in rust_components if item["type"] == "library")}
)

write_bom(
    Path("packaging/sbom/ref/correlator_rs.rust.cdx.json"),
    "correlator-rs-cargo-lock",
    rust_components,
    rust_dependencies,
)
PY

echo "SBOM baselines written to packaging/sbom/ref/"
