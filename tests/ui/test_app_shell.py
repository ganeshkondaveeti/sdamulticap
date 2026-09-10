from __future__ import annotations

from typing import TypeVar

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QCheckBox,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTabWidget,
    QWidget,
)
from pytestqt.qtbot import QtBot

from multicap.app.main_window import SCREEN_SPECS, MainWindow

WidgetT = TypeVar("WidgetT", bound=QWidget)


def find_required[WidgetT: QWidget](window: MainWindow, widget_type: type[WidgetT], name: str) -> WidgetT:
    widget = window.findChild(widget_type, name)
    assert widget is not None, name
    return widget


def table_cell(table: QTableWidget, row: int, column: int) -> str:
    item = table.item(row, column)
    assert item is not None
    return item.text()


@pytest.mark.ui
def test_app_window_launches_with_sidebar_toolbar_and_expected_screens(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.waitUntil(window.isVisible)

    assert window.navigation.count() == len(SCREEN_SPECS)
    assert window.pages.count() == len(SCREEN_SPECS)
    assert [window.navigation.item(index).text() for index in range(window.navigation.count())] == [
        spec.title for spec in SCREEN_SPECS
    ]
    assert find_required(window, QLabel, "statusPill") is not None
    assert find_required(window, QLabel, "badge") is not None
    current_widget = window.pages.currentWidget()
    assert current_widget is not None
    assert current_widget.objectName() == "homeScreen"
    assert find_required(window, QPushButton, "newPathIntentButton") is not None


@pytest.mark.ui
def test_sidebar_navigation_switches_content_stack(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.navigation.setCurrentRow(6)

    assert window.navigation.currentItem().data(Qt.ItemDataRole.UserRole) == "reports"
    current_widget = window.pages.currentWidget()
    assert current_widget is not None
    assert current_widget.objectName() == "reportsScreen"

    new_path = find_required(window, QPushButton, "newPathIntentButton")
    new_path.click()
    current_widget = window.pages.currentWidget()
    assert current_widget is not None
    assert current_widget.objectName() == "intentsScreen"


@pytest.mark.ui
def test_plan_review_screen_binds_plan_safety_and_consent_rows(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.navigation.setCurrentRow(3)

    strategy_table = find_required(window, QTableWidget, "planStrategyTable")
    safety_table = find_required(window, QTableWidget, "safetyGateTable")
    assert isinstance(strategy_table, QTableWidget)
    assert isinstance(safety_table, QTableWidget)

    assert strategy_table.rowCount() == 3
    assert table_cell(strategy_table, 0, 0) == "cat-1"
    assert table_cell(strategy_table, 0, 2) == "epc"
    assert table_cell(strategy_table, 1, 2) == "ethanalyzer"
    assert table_cell(strategy_table, 1, 3) == "tcp and dst port 443"
    assert safety_table.rowCount() >= 8
    assert table_cell(safety_table, 0, 2) == "pass"
    ntp = find_required(window, QLabel, "ntpDegradedBanner")
    coverage = find_required(window, QLabel, "coverageGapBanner")
    change_ticket = find_required(window, QLineEdit, "changeTicketField")
    consent = find_required(window, QCheckBox, "fullPayloadConsentCheck")
    assert isinstance(ntp, QLabel)
    assert isinstance(coverage, QLabel)
    assert isinstance(change_ticket, QLineEdit)
    assert ntp.text().startswith("NTP degraded")
    assert coverage.text() == "No coverage gaps in the compiled plan."
    assert change_ticket.text() == "CHG-0004421"
    assert consent.accessibleName() == "Full-payload consent"


@pytest.mark.ui
def test_live_run_screen_binds_status_rows(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.navigation.setCurrentRow(5)

    live_table = find_required(window, QTableWidget, "liveRunTable")
    assert isinstance(live_table, QTableWidget)

    assert live_table.rowCount() == 3
    assert table_cell(live_table, 1, 1) == "ACTIVE"
    assert "cpu=18.0%" in table_cell(live_table, 1, 3)
    assert find_required(window, QPushButton, "abortJobButton") is not None


@pytest.mark.ui
def test_reports_settings_and_audit_screens_bind_backend_rows(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window.navigation.setCurrentRow(6)
    report_tabs = find_required(window, QTabWidget, "reportTabs")
    exports_table = find_required(window, QTableWidget, "exportsTable")
    timeline_table = find_required(window, QTableWidget, "reportTimelineTable")
    assert isinstance(report_tabs, QTabWidget)
    assert isinstance(exports_table, QTableWidget)
    assert isinstance(timeline_table, QTableWidget)
    assert report_tabs.count() == 6
    assert exports_table.rowCount() == 1
    assert table_cell(exports_table, 0, 1) == "packet-loss:cat-2"
    assert table_cell(exports_table, 0, 4).endswith("merged.pcapng")
    assert timeline_table.rowCount() == 3
    assert table_cell(timeline_table, 2, 3) == "drops=2 truncated=1"

    window.navigation.setCurrentRow(8)
    assert find_required(window, QProgressBar, "retentionUsageBar") is not None
    retention_table = find_required(window, QTableWidget, "retentionTable")
    assert isinstance(retention_table, QTableWidget)
    assert retention_table.rowCount() == 1
    assert table_cell(retention_table, 0, 0) == "30"
    assert table_cell(retention_table, 0, 1) == "50.0"

    window.navigation.setCurrentRow(7)
    audit_status = find_required(window, QLabel, "auditChainStatus")
    audit_table = find_required(window, QTableWidget, "auditTable")
    assert isinstance(audit_status, QLabel)
    assert isinstance(audit_table, QTableWidget)
    assert audit_status.text() == "Hash chain: OK"
    assert audit_table.rowCount() == 2
    assert table_cell(audit_table, 0, 3) == "change-ticket"


@pytest.mark.ui
def test_important_widgets_have_accessible_names(qtbot: QtBot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    important_types = (
        QAbstractButton,
        QLineEdit,
        QProgressBar,
        QTableWidget,
        QTabWidget,
    )
    missing: list[str] = []
    for widget in window.findChildren(QWidget):
        if not isinstance(widget, important_types):
            continue
        if widget.objectName().startswith("qt_"):
            continue
        if widget.objectName() and not widget.accessibleName().strip():
            missing.append(widget.objectName())

    assert missing == []
