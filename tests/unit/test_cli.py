from __future__ import annotations

import pytest

from multicap.__main__ import main


@pytest.mark.unit
def test_phase0_cli_smoke(capsys: pytest.CaptureFixture[str]) -> None:
    assert main() == 0

    captured = capsys.readouterr()
    assert "Phase 4 path intent planning and filter builder" in captured.out
