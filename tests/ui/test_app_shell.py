from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from multicap.app.main_window import SCREEN_SPECS, MainWindow


@pytest.mark.ui
def test_app_shell_exposes_sidebar_toolbar_and_placeholder_pages(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.navigation.count() == len(SCREEN_SPECS)
    assert window.pages.count() == len(SCREEN_SPECS)
    assert window.findChild(QLabel, "statusPill") is not None
    assert window.findChild(QLabel, "badge") is not None
    assert window.pages.currentWidget().objectName() == "homeScreen"


@pytest.mark.ui
def test_sidebar_navigation_switches_content_stack(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.navigation.setCurrentRow(6)

    assert window.navigation.currentItem().data(Qt.ItemDataRole.UserRole) == "reports"
    assert window.pages.currentWidget().objectName() == "reportsScreen"
