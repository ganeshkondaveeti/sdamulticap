from __future__ import annotations

from typing import cast, override

from PySide6.QtCore import QByteArray, QSettings, Qt
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QDockWidget,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QStackedWidget,
    QToolBar,
    QToolButton,
    QWidget,
)

from multicap.app.demo_data import DemoUiState
from multicap.app.widgets.placeholder import PlaceholderScreen, ScreenSpec
from multicap.app.widgets.screens import (
    AuditScreen,
    DiscoveryScreen,
    FirstRunConsentScreen,
    HomeScreen,
    IntentsScreen,
    JobsScreen,
    LiveRunScreen,
    PlanReviewScreen,
    ReportsScreen,
    SearchPalette,
    SettingsScreen,
)

SCREEN_SPECS: tuple[ScreenSpec, ...] = (
    ScreenSpec(
        "home", "Home / Dashboard", "Recent jobs, active jobs, and quick-start capture actions."
    ),
    ScreenSpec(
        "discovery", "Discovery", "Seed devices, credentials, crawl progress, and topology preview."
    ),
    ScreenSpec(
        "intents", "Intents", "Path and client-MAC capture intents compile into reviewable plans."
    ),
    ScreenSpec(
        "planReview",
        "Plan Review",
        "Safety, consent, strategy, NTP, and coverage checks before execution.",
    ),
    ScreenSpec(
        "jobs", "Jobs", "Active and historical capture jobs with phase, duration, and verdict."
    ),
    ScreenSpec(
        "liveRun", "Live Run", "Per-device state, phase timeline, counters, and recovery actions."
    ),
    ScreenSpec(
        "reports", "Reports", "Evidence bundles, ladder diagrams, pcapng handoff, and exports."
    ),
    ScreenSpec(
        "audit", "Audit", "Hash-chained audit records, consent history, and chain verification."
    ),
    ScreenSpec(
        "settings",
        "Settings",
        "Retention, credentials, inventory adapters, enforcement, NTP, and telemetry.",
    ),
    ScreenSpec(
        "firstRunConsent",
        "First-Run Consent",
        "Lawful-capture acknowledgement captured before packet-capture features are used.",
    ),
)


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings: QSettings = QSettings()
        self._navigation: QListWidget = QListWidget(self)
        self._pages: QStackedWidget = QStackedWidget(self)
        self._state: DemoUiState = DemoUiState()

        self.setWindowTitle("MultiCap")
        self.setObjectName("mainWindow")
        self.setAccessibleName("MultiCap application shell")
        self.resize(1180, 760)

        self._build_toolbar()
        self._build_navigation()
        self._build_pages()
        self._restore_geometry()

    @property
    def navigation(self) -> QListWidget:
        return self._navigation

    @property
    def pages(self) -> QStackedWidget:
        return self._pages

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        self._settings.setValue("mainWindow/geometry", self.saveGeometry())
        super().closeEvent(event)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Global status", self)
        toolbar.setObjectName("globalToolbar")
        toolbar.setMovable(False)
        toolbar.setAccessibleName("Global status toolbar")

        title = QLabel("MultiCap", toolbar)
        title.setAccessibleName("Application title")
        _ = toolbar.addWidget(title)
        _ = toolbar.addSeparator()

        ntp = QLabel("NTP healthy", toolbar)
        ntp.setObjectName("statusPill")
        ntp.setAccessibleName("NTP status")
        _ = toolbar.addWidget(ntp)

        enforcement = QLabel("ENFORCED", toolbar)
        enforcement.setObjectName("badge")
        enforcement.setAccessibleName("Enforcement mode")
        _ = toolbar.addWidget(enforcement)

        active_jobs = QLabel("Active jobs: 0", toolbar)
        active_jobs.setObjectName("activeJobsCounter")
        active_jobs.setAccessibleName("Active job counter")
        _ = toolbar.addWidget(active_jobs)

        notifications = QToolButton(toolbar)
        notifications.setText("Notifications: 2")
        notifications.setObjectName("notificationsTray")
        notifications.setAccessibleName("Notifications tray")
        menu = QMenu(notifications)
        _ = menu.addAction("NTP degraded on nx-1")
        _ = menu.addAction("Wireless redirect planned for flex-local WLAN")
        notifications.setMenu(menu)
        notifications.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        _ = toolbar.addWidget(notifications)

        search = QToolButton(toolbar)
        search.setText("Search")
        search.setObjectName("searchPaletteButton")
        search.setAccessibleName("Search palette button")
        _ = search.clicked.connect(self._show_search_palette)
        _ = toolbar.addWidget(search)

        refresh = QAction("Refresh", self)
        refresh.setObjectName("refreshAction")
        _ = toolbar.addAction(refresh)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, toolbar)

    def _build_navigation(self) -> None:
        self._navigation.setObjectName("sidebarNavigation")
        self._navigation.setAccessibleName("Primary navigation")
        self._navigation.setAccessibleDescription("Select a MultiCap screen")
        for spec in SCREEN_SPECS:
            item = QListWidgetItem(spec.title)
            item.setData(Qt.ItemDataRole.UserRole, spec.key)
            self._navigation.addItem(item)
        self._navigation.setCurrentRow(0)
        _ = self._navigation.currentRowChanged.connect(self._pages.setCurrentIndex)

        dock = QDockWidget("Navigation", self)
        dock.setObjectName("navigationDock")
        dock.setAccessibleName("Navigation dock")
        dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        dock.setWidget(self._navigation)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, dock)

    def _build_pages(self) -> None:
        self._pages.setObjectName("contentStack")
        self._pages.setAccessibleName("Main content")
        for spec in SCREEN_SPECS:
            _ = self._pages.addWidget(self._page_for(spec))
        self.setCentralWidget(self._pages)

        home = cast(HomeScreen, self._pages.widget(0))
        _ = home.new_path_button.clicked.connect(lambda: self._navigation.setCurrentRow(2))
        _ = home.new_client_button.clicked.connect(lambda: self._navigation.setCurrentRow(2))
        intents = cast(IntentsScreen, self._pages.widget(2))
        _ = intents.compile_path_button.clicked.connect(lambda: self._navigation.setCurrentRow(3))
        _ = intents.compile_client_button.clicked.connect(lambda: self._navigation.setCurrentRow(3))

    def _page_for(self, spec: ScreenSpec) -> QWidget:
        if spec.key == "home":
            return HomeScreen(self._state, self._pages)
        if spec.key == "discovery":
            return DiscoveryScreen(self._state, self._pages)
        if spec.key == "intents":
            return IntentsScreen(self._state, self._pages)
        if spec.key == "planReview":
            return PlanReviewScreen(self._state, self._pages)
        if spec.key == "jobs":
            return JobsScreen(self._state, self._pages)
        if spec.key == "liveRun":
            return LiveRunScreen(self._state, self._pages)
        if spec.key == "reports":
            return ReportsScreen(self._state, self._pages)
        if spec.key == "audit":
            return AuditScreen(self._state, self._pages)
        if spec.key == "settings":
            return SettingsScreen(self._state, self._pages)
        if spec.key == "firstRunConsent":
            return FirstRunConsentScreen(self._pages)
        return PlaceholderScreen(spec, self._pages)

    def _show_search_palette(self) -> None:
        palette = SearchPalette(tuple(spec.title for spec in SCREEN_SPECS), self)
        palette.setWindowFlag(Qt.WindowType.Tool, True)
        palette.resize(420, 320)
        palette.show()

    def _restore_geometry(self) -> None:
        geometry = cast(object, self._settings.value("mainWindow/geometry"))
        if isinstance(geometry, QByteArray):
            _ = self.restoreGeometry(geometry)
