from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QLineEdit, QProgressBar, QPushButton, QTableWidget, QTabWidget
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
    assert window.findChild(QPushButton, "newPathIntentButton") is not None


@pytest.mark.ui
def test_sidebar_navigation_switches_content_stack(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.navigation.setCurrentRow(6)

    assert window.navigation.currentItem().data(Qt.ItemDataRole.UserRole) == "reports"
    assert window.pages.currentWidget().objectName() == "reportsScreen"


@pytest.mark.ui
def test_plan_review_screen_binds_plan_safety_and_consent_rows(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.navigation.setCurrentRow(3)

    assert window.findChild(QTableWidget, "planStrategyTable").rowCount() == 3
    assert window.findChild(QTableWidget, "safetyGateTable").rowCount() >= 8
    assert window.findChild(QLabel, "ntpDegradedBanner").text().startswith("NTP degraded")
    assert window.findChild(QLineEdit, "changeTicketField").text() == "CHG-0004421"


@pytest.mark.ui
def test_live_run_screen_binds_status_rows(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.navigation.setCurrentRow(5)

    assert window.findChild(QTableWidget, "liveRunTable").rowCount() == 3
    assert window.findChild(QPushButton, "abortJobButton") is not None


@pytest.mark.ui
def test_reports_settings_and_audit_screens_bind_backend_rows(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.navigation.setCurrentRow(6)
    assert window.findChild(QTabWidget, "reportTabs").count() == 6
    assert window.findChild(QTableWidget, "exportsTable").rowCount() == 1

    window.navigation.setCurrentRow(8)
    assert window.findChild(QProgressBar, "retentionUsageBar") is not None
    assert window.findChild(QTableWidget, "retentionTable").rowCount() == 1

    window.navigation.setCurrentRow(7)
    assert window.findChild(QLabel, "auditChainStatus").text() == "Hash chain: OK"
    assert window.findChild(QTableWidget, "auditTable").rowCount() == 2
