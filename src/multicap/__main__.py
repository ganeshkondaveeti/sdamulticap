"""multicap desktop entrypoint."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from multicap.app.main_window import MainWindow
from multicap.app.theme.qss import apply_multicap_theme


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = tuple(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(description="Launch the MultiCap desktop app.")
    _ = parser.add_argument(
        "--smoke",
        action="store_true",
        help="launch the PySide6 shell briefly and exit; used by local smoke tests",
    )
    _ = parser.parse_args(raw_args)
    smoke = "--smoke" in raw_args

    if smoke:
        _ = os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    app = QApplication.instance()
    owns_app = app is None
    qt_app = QApplication([sys.argv[0], *raw_args]) if app is None else app
    if not isinstance(qt_app, QApplication):
        raise RuntimeError("MultiCap requires a QApplication instance")
    apply_multicap_theme(qt_app)

    window = MainWindow()
    window.show()
    if smoke:
        QTimer.singleShot(100, window.close)
        QTimer.singleShot(120, qt_app.quit)
    result = qt_app.exec() if owns_app else 0
    if smoke:
        print("multicap GUI smoke ok")
    return result


if __name__ == "__main__":
    sys.exit(main())
