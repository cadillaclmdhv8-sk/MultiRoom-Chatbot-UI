"""MultiRoom Chatbot: a group-chat front end for KoboldAI / KoboldCpp."""
import sys
import traceback
from datetime import datetime

from PySide6.QtWidgets import QApplication

from app import storage
from app.ui import theme
from app.ui.main_window import MainWindow


class _LazyLog:
    """File that is only created on first write (used when there is no console)."""

    def __init__(self, path):
        self.path = path
        self._f = None

    def write(self, text):
        if self._f is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._f = open(self.path, "a", encoding="utf-8", buffering=1)
            self._f.write(f"\n--- {datetime.now():%Y-%m-%d %H:%M:%S} ---\n")
        self._f.write(text)

    def flush(self):
        if self._f:
            self._f.flush()


def _setup_error_log() -> None:
    # Started with pythonw (no console): send errors to data/error.log instead.
    if sys.stderr is None or sys.stdout is None:
        log = _LazyLog(storage.DATA_DIR / "error.log")
        sys.stdout = sys.stderr = log
    sys.excepthook = lambda t, v, tb: traceback.print_exception(t, v, tb)


def main() -> int:
    _setup_error_log()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    theme.set_current(storage.load_settings().get("theme", "dark"))
    app.setStyleSheet(theme.build_style())
    w = MainWindow()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
