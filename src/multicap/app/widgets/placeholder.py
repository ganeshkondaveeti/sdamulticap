from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


@dataclass(frozen=True, slots=True)
class ScreenSpec:
    key: str
    title: str
    summary: str


class PlaceholderScreen(QWidget):
    def __init__(self, spec: ScreenSpec, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.spec: ScreenSpec = spec
        self.setObjectName(f"{spec.key}Screen")
        self.setAccessibleName(spec.title)
        self.setAccessibleDescription(spec.summary)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 32, 32, 32)
        root.setSpacing(16)

        card = QFrame(self)
        card.setObjectName("placeholderCard")
        card.setAccessibleName(f"{spec.title} placeholder card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(12)

        title = QLabel(spec.title, card)
        title.setObjectName("screenTitle")
        title.setAccessibleName(f"{spec.title} title")

        summary = QLabel(spec.summary, card)
        summary.setWordWrap(True)
        summary.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        summary.setAccessibleName(f"{spec.title} summary")

        card_layout.addWidget(title)
        card_layout.addWidget(summary)
        card_layout.addStretch(1)
        root.addWidget(card)
        root.addStretch(1)
