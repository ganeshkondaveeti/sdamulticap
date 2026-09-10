from __future__ import annotations

import pytest

from multicap.app.viewmodels import live_rows, skew_label
from multicap.core.synchronizer import StatusEvent, TriggerReport, TriggerResult


@pytest.mark.unit
def test_live_rows_render_status_events() -> None:
    rows = live_rows((StatusEvent("job-1", "cat-1", "ACTIVE", 1.25, message="started"),))

    assert rows[0].device_id == "cat-1"
    assert rows[0].phase == "ACTIVE"
    assert rows[0].message == "started"


@pytest.mark.unit
def test_skew_label_formats_trigger_report() -> None:
    assert (
        skew_label(TriggerReport((TriggerResult("a", 1.0), TriggerResult("b", 1.123))))
        == "123.0 ms"
    )
