from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
from typing import cast

from PySide6.QtWidgets import QApplication


def apply_multicap_theme(app: QApplication) -> None:
    app.setApplicationName("MultiCap")
    app.setOrganizationName("MultiCap Contributors")
    try:
        module = import_module("qt_material")
    except ImportError:
        app.setStyleSheet(_fallback_qss())
        return
    apply_stylesheet = cast(Callable[..., None], module.__dict__["apply_stylesheet"])
    apply_stylesheet(app, theme="dark_blue.xml")
    app.setStyleSheet(app.styleSheet() + _fallback_qss())


def _fallback_qss() -> str:
    return """
    QMainWindow, QWidget {
        background: #0b1220;
        color: #dce7f3;
        font-size: 13px;
    }
    QToolBar {
        background: #111c2f;
        border-bottom: 1px solid #22324f;
        spacing: 10px;
        padding: 6px;
    }
    QDockWidget {
        titlebar-close-icon: none;
        titlebar-normal-icon: none;
        border-right: 1px solid #22324f;
    }
    QListWidget {
        background: #0f1a2b;
        border: none;
        padding: 8px;
    }
    QListWidget::item {
        border-radius: 6px;
        padding: 10px 12px;
        margin: 2px 0;
    }
    QListWidget::item:selected {
        background: #1f6feb;
        color: #ffffff;
    }
    QFrame#placeholderCard {
        background: #111c2f;
        border: 1px solid #2d4268;
        border-radius: 14px;
    }
    QLabel#screenTitle {
        font-size: 24px;
        font-weight: 700;
        color: #ffffff;
    }
    QLabel#statusPill {
        background: #132f24;
        color: #8ee6b2;
        border: 1px solid #1d7f4f;
        border-radius: 10px;
        padding: 4px 10px;
    }
    QLabel#badge {
        background: #2b2510;
        color: #ffd166;
        border: 1px solid #8a6d1d;
        border-radius: 10px;
        padding: 4px 10px;
    }
    """
