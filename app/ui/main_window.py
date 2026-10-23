from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMainWindow, QPushButton,
                               QTabWidget, QVBoxLayout, QWidget)

from .. import storage
from . import theme
from ..kobold import KoboldClient, run_background
from .bot_editor import BotEditor
from .bots_tab import BotsTab
from .chat_tab import ChatTab
from .settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MultiRoom Chatbot")
        self.resize(1150, 760)
        self.settings = storage.load_settings()
        self.bots = storage.load_bots()
        if storage.migrate_bot_images(self.bots):   # copy older bots' images into data/avatars
            storage.save_bots(self.bots)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # top bar
        bar = QWidget()
        bar.setObjectName("topBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 8, 12, 8)
        app_name = QLabel("MultiRoom")
        app_name.setObjectName("appName")
        self.status = QLabel()
        self.status.setObjectName("status")
        settings_btn = QPushButton("⚙  Settings")
        settings_btn.setObjectName("secondary")
        settings_btn.clicked.connect(self.open_settings)
        bl.addWidget(app_name)
        bl.addStretch(1)
        self.theme_btn = QPushButton()
        self.theme_btn.setObjectName("secondary")
        self.theme_btn.setToolTip("Switch between light and dark mode")
        self.theme_btn.clicked.connect(self.toggle_theme)
        self._update_theme_btn()
        bl.addWidget(self.status)
        bl.addSpacing(10)
        bl.addWidget(self.theme_btn)
        bl.addWidget(settings_btn)
        root.addWidget(bar)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("mainTabs")
        self.tabs.setAttribute(Qt.WA_StyledBackground, True)
        self.chat_tab = ChatTab(lambda: self.settings, lambda: self.bots, self.edit_bot)
        self.bots_tab = BotsTab()
        self.bots_tab.add_requested.connect(lambda: self.edit_bot(None))
        self.bots_tab.edit_requested.connect(self.edit_bot)
        self.bots_tab.set_bots(self.bots)
        self.tabs.addTab(self.chat_tab, "Chat")
        self.tabs.addTab(self.bots_tab, "BOTS")
        root.addWidget(self.tabs, 1)
        self.setCentralWidget(central)

        self.check_connection()
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self.check_connection)
        self._status_timer.start(20000)

    # ---- connection status -----------------------------------------------------
    def check_connection(self) -> None:
        url = self.settings["kobold_url"]
        run_background(lambda: KoboldClient(url).model_name(timeout=3),
                       on_done=lambda name: self._set_status(True, name),
                       on_error=lambda _e: self._set_status(False, url))

    def _set_status(self, ok: bool, text: str) -> None:
        name = text.split("/")[-1] if ok else text
        color = "#23a55a" if ok else "#f23f43"
        self.status.setText(f'<span style="color:{color}">●</span>  '
                            + (name if ok else f"Not connected ({name})"))
        self.status.setToolTip(text)

    # ---- theme ---------------------------------------------------------------------
    def _update_theme_btn(self) -> None:
        # Shows the mode you'd switch to
        self.theme_btn.setText("☀  Light" if theme.current() == "dark" else "☾  Dark")

    def toggle_theme(self) -> None:
        new = "light" if theme.current() == "dark" else "dark"
        theme.set_current(new)
        self.settings["theme"] = new
        storage.save_settings(self.settings)
        QApplication.instance().setStyleSheet(theme.build_style())
        self._update_theme_btn()
        # Redraw widgets that use theme colors directly
        self.bots_tab.set_bots(self.bots)
        self.chat_tab.bots_changed()
        self.check_connection()

    # ---- settings / bots -------------------------------------------------------
    def open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self)
        result = dlg.exec()
        if dlg.clear_requested:
            self.clear_data(*dlg.clear_requested)
            return
        if result == SettingsDialog.Accepted:
            self.settings = {**self.settings, **dlg.values()}
            storage.save_settings(self.settings)
            self.chat_tab.view.refresh_avatars()   # avatar size may have changed
            self.check_connection()

    def clear_data(self, bots: bool, chats: bool, settings: bool) -> None:
        if bots or chats:
            self.chat_tab.clear_all()   # stop live chats before their files go
        storage.clear_data(bots, chats, settings)
        self.settings = storage.load_settings()
        self.bots = storage.load_bots()
        theme.set_current(self.settings.get("theme", "dark"))
        QApplication.instance().setStyleSheet(theme.build_style())
        self._update_theme_btn()
        self.bots_tab.set_bots(self.bots)
        self.chat_tab.bots_changed()
        self.check_connection()

    def edit_bot(self, bot) -> None:
        taken = {b.name for b in self.bots if b is not bot}
        dlg = BotEditor(bot, taken, self)
        if dlg.exec() != BotEditor.Accepted:
            return
        if dlg.deleted:
            self.bots = [b for b in self.bots if b is not bot]
            storage.delete_bot_images(bot.id)
        elif bot is None:
            self.bots.append(dlg.bot)
        storage.save_bots(self.bots)
        self.bots_tab.set_bots(self.bots)
        self.chat_tab.bots_changed()

