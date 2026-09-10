from __future__ import annotations

import pytest

from multicap.app.viewmodels import ConsentGateViewModel, safety_rows
from multicap.core.safety import DeviceHealth, SafetyGate
from tests.unit.test_safety_cleanup import planned_job


@pytest.mark.unit
def test_consent_gate_viewmodel_blocks_until_required_fields_present() -> None:
    assert not ConsentGateViewModel("", False, False).can_execute()
    assert not ConsentGateViewModel("CHG123", True, False).can_execute()
    assert ConsentGateViewModel("CHG123", True, True).can_execute()


@pytest.mark.unit
def test_safety_rows_render_report_for_plan_review() -> None:
    report = SafetyGate().evaluate(
        planned_job(),
        {
            "core-a": DeviceHealth("core-a", 20.0, 30.0, 1024, 0),
            "dist-b": DeviceHealth("dist-b", 25.0, 35.0, 1024, 0),
        },
    )

    rows = safety_rows(report)

    assert rows[0].device_id == "core-a"
    assert {row.check for row in rows} >= {"cpu-headroom", "filter-present"}
