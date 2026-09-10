from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from multicap.collectors import (
    ERSPAN_ETHERTYPE,
    ErspanCollector,
    ErspanFrame,
    LocalCaptureCollector,
)
from multicap.core.clock import ClockAligner, ClockSample
from multicap.core.correlator_facade import CorrelatorFacade


def main() -> int:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        erspan = ErspanCollector().collect(
            [ErspanFrame(10.5, ERSPAN_ETHERTYPE, b"wired-packet", 10)],
            device_id="core-a",
            interface="Gi1/0/1",
        )
        local = LocalCaptureCollector().collect([b"local-span"], interface="en0", started_at=10.1)
        offsets = ClockAligner().estimate([ClockSample("core-a", 10.0, 10.5, 10.2)])
        summary = CorrelatorFacade().merge(
            [*erspan.packets, *local.packets],
            offsets,
            {"core-a": erspan.counters, "local-capture-host": local.counters},
            root / "merged.pcapng.jsonl",
        )
        first = json.loads(summary.output_path.read_text().splitlines()[0])
        print(f"packets={summary.packet_count}")
        print(f"dropped={summary.dropped}")
        print(f"first={first['device_id']}:{first['mechanism']}:{first['timestamp']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
