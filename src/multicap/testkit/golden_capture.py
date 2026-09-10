from __future__ import annotations

import argparse
from pathlib import Path

from multicap.drivers.base import CapabilityMatrix
from multicap.drivers.capabilities import matrix_to_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a golden capability fixture.")
    parser.add_argument("--platform", required=True)
    parser.add_argument("--os-family", required=True)
    parser.add_argument("--release-train", required=True)
    parser.add_argument("--feature", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    matrix = CapabilityMatrix(
        platform=args.platform,
        os_family=args.os_family,
        release_train=args.release_train,
        features={feature: True for feature in args.feature},
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(matrix_to_json(matrix))
    print(f"wrote {args.output}")
    return 0
