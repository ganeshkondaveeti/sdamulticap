from __future__ import annotations

from importlib.metadata import entry_points

from multicap.drivers.base import CaptureDriver


def discover_drivers() -> dict[str, CaptureDriver]:
    discovered: dict[str, CaptureDriver] = {}
    for entry_point in entry_points(group="multicap.drivers"):
        factory = entry_point.load()
        driver = factory()
        if not isinstance(driver, CaptureDriver):
            raise TypeError(f"entry point {entry_point.name} did not return a CaptureDriver")
        discovered[entry_point.name] = driver
    return discovered
