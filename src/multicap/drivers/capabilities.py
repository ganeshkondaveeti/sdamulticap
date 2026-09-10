from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from multicap.drivers.base import CapabilityMatrix, DeviceProfile, FeatureMap


@dataclass(frozen=True, slots=True)
class CapabilityKey:
    platform: str
    os_family: str
    release_train: str


class CapabilityRegistry:
    def __init__(self, matrices: dict[CapabilityKey, CapabilityMatrix]) -> None:
        self._matrices = matrices

    @classmethod
    def from_default_fixtures(cls) -> CapabilityRegistry:
        fixture_root = resources.files("multicap.testkit.golden")
        matrices: dict[CapabilityKey, CapabilityMatrix] = {}
        for fixture in fixture_root.iterdir():
            if fixture.name.endswith(".json"):
                matrix = matrix_from_json(fixture.read_text())
                matrices[CapabilityKey(matrix.platform, matrix.os_family, matrix.release_train)] = (
                    matrix
                )
        return cls(matrices)

    @classmethod
    def from_directory(cls, path: Path) -> CapabilityRegistry:
        matrices: dict[CapabilityKey, CapabilityMatrix] = {}
        for fixture in sorted(path.glob("*.json")):
            matrix = matrix_from_json(fixture.read_text())
            matrices[CapabilityKey(matrix.platform, matrix.os_family, matrix.release_train)] = (
                matrix
            )
        return cls(matrices)

    def probe(self, device: DeviceProfile) -> CapabilityMatrix:
        key = CapabilityKey(device.platform, device.os_family, device.release_train)
        try:
            return self._matrices[key]
        except KeyError as error:
            raise KeyError(
                f"no capability fixture for {device.platform}/{device.os_family}/{device.release_train}"
            ) from error

    def all_matrices(self) -> list[CapabilityMatrix]:
        return sorted(
            self._matrices.values(),
            key=lambda matrix: (matrix.platform, matrix.os_family, matrix.release_train),
        )


def matrix_from_json(content: str) -> CapabilityMatrix:
    data = json.loads(content)
    features = data["features"]
    if not isinstance(features, dict):
        raise ValueError("capability fixture features must be an object")
    return CapabilityMatrix(
        platform=str(data["platform"]),
        os_family=str(data["os_family"]),
        release_train=str(data["release_train"]),
        features={str(key): bool(value) for key, value in features.items()},
    )


def matrix_to_json(matrix: CapabilityMatrix) -> str:
    payload: dict[str, str | FeatureMap] = {
        "platform": matrix.platform,
        "os_family": matrix.os_family,
        "release_train": matrix.release_train,
        "features": dict(sorted(matrix.features.items())),
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"
