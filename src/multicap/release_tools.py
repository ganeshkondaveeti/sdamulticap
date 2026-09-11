#!/usr/bin/env python3
"""Release workflow helpers."""

from __future__ import annotations

import argparse
import base64
import binascii
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass(frozen=True)
class DecodeArgs:
    env_name: str
    output: Path
    allow_raw: bool


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    value = os.environ.get(args.env_name)
    if not value:
        raise SystemExit(f"{args.env_name} is required")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    _ = args.output.write_bytes(decode_secret(value, allow_raw=args.allow_raw))
    if args.output.stat().st_size == 0:
        raise SystemExit(f"{args.env_name} decoded to an empty file")
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


def parse_args(argv: Sequence[str] | None) -> DecodeArgs:
    parser = argparse.ArgumentParser(description="Decode a GitHub Actions secret to a file")
    _ = parser.add_argument("env_name")
    _ = parser.add_argument("output")
    _ = parser.add_argument("--allow-raw", action="store_true")
    parsed = cast(dict[str, object], vars(parser.parse_args(argv)))
    return DecodeArgs(
        env_name=str(parsed["env_name"]),
        output=Path(str(parsed["output"])),
        allow_raw=bool(parsed["allow_raw"]),
    )


def decode_secret(value: str, *, allow_raw: bool) -> bytes:
    stripped = "".join(value.split())
    try:
        return base64.b64decode(stripped, validate=True)
    except binascii.Error:
        if allow_raw:
            return value.encode()
        raise SystemExit("secret is not valid base64") from None


if __name__ == "__main__":
    raise SystemExit(main())
