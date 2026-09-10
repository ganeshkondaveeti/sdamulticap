#!/usr/bin/env bash
# Regenerate SBOM baselines for §5 Phase 0 exit + §15 Phase 10 release attestation.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p ref

uv run cyclonedx-py environment ../../.venv/bin/python --output-format JSON --output-file ref/multicap.python.cdx.json

pushd ../../src/multicap/correlator_rs >/dev/null
cargo cyclonedx --format json --override-filename correlator_rs.rust.cdx
mv correlator_rs.rust.cdx.json ../../../packaging/sbom/ref/correlator_rs.rust.cdx.json
popd >/dev/null

uv run python - <<'PY'
from __future__ import annotations

import json
import uuid
from pathlib import Path

for path in sorted(Path("ref").glob("*.cdx.json")):
    document = json.loads(path.read_text())
    document["serialNumber"] = f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, path.name)}"
    metadata = document.setdefault("metadata", {})
    metadata["timestamp"] = "1970-01-01T00:00:00+00:00"
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
PY

echo "SBOM baselines written to packaging/sbom/ref/"
