"""Chat tab: live and saved chat lists on the left, chat view on the right."""
from __future__ import annotations

import re

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMenu,
                               QMessageBox, QPushButton, QSplitter, QStackedWidget, QVBoxLayout,
                               QWidget)

from .. import storage
from ..models import Chat, continuation_text
from ..session import ChatSession
from .avatar import avatar
from .chat_view import ChatView
from .new_chat_dialog import NewChatDialog
from .saved_chat_view import SavedChatView, nice_date

PAGE_EMPTY, PAGE_LIVE, PAGE_SAVED = 0, 1, 2


class ChatTab(QWidget):
    def __init__(self, get_settings, get_bots, edit_bot=None):
        super().__init__()
        self._get_settings = get_settings
        self._get_bots = get_bots
        self.sessions: list[ChatSession] = []
        self.saved: list[dict] = []

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        split = QSplitter()
        split.setHandleWidth(1)
        lay.addWidget(split)

        # left column
        left = QWidget()
        left.setObjectName("sidebar")
        ll = QVBoxLayout(left)
        ll.setContentsMargins(10, 12, 10, 10)
        head = QLabel("CHATS")
        head.setObjectName("sectionLabel")
        new_btn = QPushButton("+  New chat")
        new_btn.clicked.connect(self.new_chat)
        self.list = QListWidget()
        self.list.setObjectName("chatList")
        self.list.setIconSize(QSize(32, 32))
        self.list.currentRowChanged.connect(self._select_live)
        self.list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list.customContextMenuRequested.connect(self._live_menu)

        saved_head = QLabel("SAVED CHATS")
        saved_head.setObjectName("sectionLabel")
        self.saved_list = QListWidget()
        self.saved_list.setObjectName("chatList")
        self.saved_list.setIconSize(QSize(32, 32))
        self.saved_list.currentRowChanged.connect(self._select_saved)
        self.saved_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.saved_list.customContextMenuRequested.connect(self._saved_menu)

        ll.addWidget(head)
        ll.addWidget(new_btn)
        ll.addWidget(self.list, 1)
        ll.addWidget(saved_head)
        ll.addWidget(self.saved_list, 1)
        hint = QLabel("Chats save automatically.\nRight-click a chat to delete it.")
        hint.setObjectName("hint")
        ll.addWidget(hint)

        # right side
        self.stack = QStackedWidget()
        empty = QLabel("Create a chat to get started  →  “+ New chat”")
        empty.setAlignment(Qt.AlignCenter)
        empty.setObjectName("emptyState")
        self.view = ChatView(get_settings, edit_bot)
        self.saved_view = SavedChatView(get_settings, get_bots, edit_bot)
        self.saved_view.continue_requested.connect(self.continue_saved)
        self.saved_view.delete_requested.connect(self._delete_saved)
        self.stack.addWidget(empty)            # PAGE_EMPTY
        self.stack.addWidget(self.view)        # PAGE_LIVE
        self.stack.addWidget(self.saved_view)  # PAGE_SAVED

        split.addWidget(left)
        split.addWidget(self.stack)
        split.setStretchFactor(1, 1)
        split.setSizes([250, 850])
        left.setMinimumWidth(200)

        self.refresh_saved()

    # ---- live chats ----------------------------------------------------------------
    def new_chat(self) -> None:
        dlg = NewChatDialog(self._get_bots(), self, self._get_settings()["user_name"])
        if dlg.exec() != NewChatDialog.Accepted:
            return
        self._add_session(Chat(title=dlg.chat_title(), bots=dlg.selected_bots(),
                               complete_response=dlg.complete_response(),
                               chat_context=dlg.chat_context(),
                               bot_notes=dlg.bot_notes()))

    def _add_session(self, chat: Chat) -> None:
        session = ChatSession(chat, self._get_settings)
        # "New session" leaves the old conversation in data/chats -> show it under Saved
        session.cleared.connect(self.refresh_saved)
        self.sessions.append(session)
        it = QListWidgetItem(self._icon(chat.bots[0].image_path, chat.bots[0].name), chat.title)
        it.setToolTip(", ".join(b.name for b in chat.bots))
        self.list.addItem(it)
        self.list.setCurrentRow(self.list.count() - 1)

    def _icon(self, image_path: str, name: str) -> QIcon:
        return QIcon(avatar(image_path, name, 32))

    def _select_live(self, row: int) -> None:
        if not 0 <= row < len(self.sessions):
            if self.stack.currentIndex() == PAGE_LIVE:
                self.view.set_session(None)
                self.stack.setCurrentIndex(PAGE_EMPTY)
            return
        self._clear_selection(self.saved_list)
        self.view.set_session(self.sessions[row])
        self.stack.setCurrentIndex(PAGE_LIVE)

    def _live_menu(self, pos) -> None:
        row = self.list.indexAt(pos).row()
        if row < 0:
            return
        m = QMenu(self)
        act = m.addAction("Delete chat")
        if m.exec(self.list.mapToGlobal(pos)) != act:
            return
        session = self.sessions[row]
        if session.chat.messages and QMessageBox.question(
                self, "Delete chat", f"Delete “{session.chat.title}”? "
                "It will also be removed from saved chats.") != QMessageBox.Yes:
            return
        self.sessions.pop(row)
        session.stop()
        storage.delete_chat(session.chat.id)
        if self.view.session is session:
            self.view.set_session(None)
            self.stack.setCurrentIndex(PAGE_EMPTY)
        self.list.takeItem(row)

    # ---- saved chats ----------------------------------------------------------------
    def refresh_saved(self) -> None:
        live_ids = {s.chat.id for s in self.sessions}
        current = self._current_saved_id()
        self.saved = [d for d in storage.load_chat_dicts()
                      if d["id"] not in live_ids and d.get("messages")]
        by_id = {b.id: b for b in self._get_bots()}
        self.saved_list.blockSignals(True)
        self.saved_list.clear()
        for d in self.saved:
            ids = d.get("bot_ids") or []
            names = d.get("bot_names") or ["?"]
            first = next((by_id[i] for i in ids if i in by_id), None)
            icon = self._icon(first.image_path, first.name) if first else self._icon("", names[0])
            when = nice_date(d.get("updated", ""))
            it = QListWidgetItem(icon, f"{d.get('title', 'Chat')}\n{when}")
            missing = sum(1 for i in ids if i not in by_id)
            it.setToolTip(", ".join(names) + (f"\n({missing} deleted)" if missing else ""))
            self.saved_list.addItem(it)
        # keep the same saved chat selected if it's still there
        ids = [d["id"] for d in self.saved]
        if current in ids:
            self.saved_list.setCurrentRow(ids.index(current))
        self.saved_list.blockSignals(False)
        if current and current not in ids and self.stack.currentIndex() == PAGE_SAVED:
            self.stack.setCurrentIndex(PAGE_EMPTY)

    def _current_saved_id(self) -> str:
        row = self.saved_list.currentRow()
        if self.stack.currentIndex() == PAGE_SAVED and 0 <= row < len(self.saved):
            return self.saved[row]["id"]
        return ""

    def _select_saved(self, row: int) -> None:
        if not 0 <= row < len(self.saved):
            return
        self._clear_selection(self.list)
        self.saved_view.show_chat(self.saved[row])
        self.stack.setCurrentIndex(PAGE_SAVED)

    def _saved_menu(self, pos) -> None:
        row = self.saved_list.indexAt(pos).row()
        if row < 0:
            return
        m = QMenu(self)
        cont = m.addAction("Continue this chat")
        delete = m.addAction("Delete")
        picked = m.exec(self.saved_list.mapToGlobal(pos))
        if picked == cont:
            self.continue_saved(self.saved[row])
        elif picked == delete:
            self._delete_saved(self.saved[row])

    def _delete_saved(self, d: dict) -> None:
        if QMessageBox.question(self, "Delete saved chat",
                                f"Delete “{d.get('title', 'Chat')}”? This can't be undone.") \
                != QMessageBox.Yes:
            return
        storage.delete_chat(d["id"])
        if self.stack.currentIndex() == PAGE_SAVED:
            self.stack.setCurrentIndex(PAGE_EMPTY)
        self.saved_list.setCurrentRow(-1)
        self.refresh_saved()

    def continue_saved(self, d: dict) -> None:
        """Start a new live chat with the same bots/settings, remembering recent text."""
        old = Chat.from_dict(d, self._get_bots())
        if not old.bots:
            QMessageBox.information(self, "Can't continue",
                                    "All of this chat's bots have been deleted.")
            return
        title = re.sub(r"(\s*\(cont\.\))+$", "", old.title) + " (cont.)"
        self._add_session(Chat(title=title, bots=old.bots,
                               complete_response=old.complete_response,
                               chat_context=old.chat_context,
                               bot_notes=dict(old.bot_notes),
                               previous_context=continuation_text(old)))

    # ---- shared ------------------------------------------------------------------------
    @staticmethod
    def _clear_selection(lst: QListWidget) -> None:
        lst.blockSignals(True)
        lst.setCurrentRow(-1)
        lst.clearSelection()
        lst.blockSignals(False)

    def bots_changed(self) -> None:
        """Bots were edited: refresh icons and the open views."""
        for i, s in enumerate(self.sessions):
            if s.chat.bots:
                b = s.chat.bots[0]
                self.list.item(i).setIcon(self._icon(b.image_path, b.name))
        self.view.refresh_avatars()
        self.refresh_saved()
        if self.stack.currentIndex() == PAGE_SAVED and self.saved_list.currentRow() >= 0:
            self.saved_view.show_chat(self.saved[self.saved_list.currentRow()])

    def clear_all(self) -> None:
        """Drop every live chat (used by 'Clear all data')."""
        for s in self.sessions:
            s.stop()
        self.sessions.clear()
        self.view.set_session(None)
        self.list.clear()
        self.stack.setCurrentIndex(PAGE_EMPTY)
        self.refresh_saved()
