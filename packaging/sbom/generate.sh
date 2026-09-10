#!/usr/bin/env bash
# Regenerate SBOM baselines for §5 Phase 0 exit + §15 Phase 10 release attestation.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p ref

uv run cyclonedx-py environment --output-format JSON --output-file ref/multicap.python.cdx.json

pushd ../../src/multicap/correlator_rs >/dev/null
cargo cyclonedx --format json --override-filename correlator_rs.rust.cdx
mv correlator_rs.rust.cdx.json ../../../packaging/sbom/ref/correlator_rs.rust.cdx.json
popd >/dev/null

echo "SBOM baselines written to packaging/sbom/ref/"
