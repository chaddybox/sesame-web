from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from SesameModernized.ui.main_window import MainWindow


def pick_icon_path() -> str | None:
    root = Path(__file__).resolve().parent
    assets = root / "assets"
    candidates = [
        assets / "sesame_logo.ico",
        assets / "sesame_logo.png",
        root / "sesame_icon_multi.ico",
        root / "sesame_icon_multi.png",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def main():
    app = QApplication(sys.argv)

    icon_path = pick_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow(app_icon_path=icon_path)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()