from __future__ import annotations

import json
from pathlib import Path

import pytest

from multicap.collectors import (
    ERSPAN_ETHERTYPE,
    ErspanCollector,
    ErspanFrame,
    LocalCaptureCollector,
    PeekremoteCollector,
    PeekremoteDatagram,
)
from multicap.collectors.packets import CaptureCounters, PacketRecord
from multicap.core.clock import ClockAligner, ClockOffset, ClockSample
from multicap.core.correlator_facade import CorrelatorFacade, parse_capwap_outer_header


@pytest.mark.unit
def test_erspan_collector_accepts_gre_ethertype_and_counts_drops() -> None:
    result = ErspanCollector().collect(
        [
            ErspanFrame(10.0, ERSPAN_ETHERTYPE, b"packet-a", 7),
            ErspanFrame(10.1, 0x0800, b"not-erspan", 7),
        ],
        device_id="core-a",
        interface="Gi1/0/1",
    )

    assert len(result.packets) == 1
    assert result.packets[0].mechanism == "erspan"
    assert result.counters.dropped == 1


@pytest.mark.unit
def test_peekremote_and_local_collectors_emit_packet_records() -> None:
    peek = PeekremoteCollector().collect([PeekremoteDatagram(1.0, b"wifi", "ap-1")])
    local = LocalCaptureCollector().collect(
        [b"local-a", b"local-b"], interface="en0", started_at=2.0
    )

    assert peek.packets[0].mechanism == "peekremote"
    assert [packet.timestamp for packet in local.packets] == [2.0, 2.001]


@pytest.mark.unit
def test_clock_aligner_uses_lowest_rtt_sample_and_maps_to_local_time() -> None:
    offsets = ClockAligner().estimate(
        [
            ClockSample("core-a", sent_at=10.0, device_time=11.0, received_at=10.2),
            ClockSample("core-a", sent_at=20.0, device_time=20.7, received_at=20.05),
        ]
    )

    assert offsets["core-a"].offset_seconds == pytest.approx(0.675)
    assert offsets["core-a"].to_local(30.675) == pytest.approx(30.0)
    assert ClockAligner().beacon("job-1", 2) == b"multicap-beacon:job-1:2"


@pytest.mark.unit
def test_correlator_merges_dedups_and_surfaces_counters(tmp_path: Path) -> None:
    packets = [
        PacketRecord("p1", 10.5, b"same", "core-a", "Gi1/0/1", "epc"),
        PacketRecord("p2", 10.6, b"same", "core-a", "Gi1/0/1", "epc"),
        PacketRecord("p3", 10.0, b"other", "dist-b", "Eth1/1", "ethanalyzer"),
    ]

    summary = CorrelatorFacade().merge(
        packets,
        {"core-a": ClockOffset("core-a", 0.5)},
        {"core-a": CaptureCounters(dropped=1), "dist-b": CaptureCounters(truncated=2)},
        tmp_path / "merged.pcapng.jsonl",
    )

    rows = [json.loads(line) for line in summary.output_path.read_text().splitlines()]
    assert summary.packet_count == 2
    assert summary.dropped == 1
    assert summary.truncated == 2
    assert rows[1]["timestamp"] == 10.0
    assert rows[1]["offset_seconds"] == 0.5


@pytest.mark.unit
def test_capwap_outer_header_parser_detects_control_and_data_ports() -> None:
    assert parse_capwap_outer_header(
        (12345).to_bytes(2, "big") + (5246).to_bytes(2, "big")
    ).is_capwap
    assert parse_capwap_outer_header(
        (5247).to_bytes(2, "big") + (12345).to_bytes(2, "big")
    ).is_capwap
    assert not parse_capwap_outer_header(
        (1000).to_bytes(2, "big") + (2000).to_bytes(2, "big")
    ).is_capwap

    with pytest.raises(ValueError, match="requires at least four bytes"):
        parse_capwap_outer_header(b"\x00")
