"""Right-hand chat panel: header, message list, typing indicator, input."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget, QMessageBox)

from ..models import Message
from ..session import ChatSession
from .avatar import avatar
from .bot_profile import show_profile
from .message_widget import ClickableLabel, MessageRow, SystemRow, TypingIndicator


class InputBox(QPlainTextEdit):
    submitted = Signal()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Return, Qt.Key_Enter) and not (e.modifiers() & Qt.ShiftModifier):
            self.submitted.emit()
            return
        super().keyPressEvent(e)


class ChatView(QWidget):
    def __init__(self, get_settings, edit_bot=None):
        super().__init__()
        self._get_settings = get_settings
        self._edit_bot = edit_bot   # callback(bot) for the profile's "Edit bot…" button
        self.session: ChatSession | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # header
        header = QWidget()
        header.setObjectName("chatHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 10, 12, 10)
        self.title = QLabel()
        self.title.setObjectName("chatTitle")
        self.members = QHBoxLayout()
        self.members.setSpacing(4)
        self.reset_btn = QPushButton("⟳  New session")
        self.reset_btn.setObjectName("secondary")
        self.reset_btn.setToolTip("Stop any reply in progress, clear this chat and start fresh")
        self.reset_btn.clicked.connect(self._reset)
        hl.addWidget(self.title)
        hl.addSpacing(12)
        hl.addLayout(self.members)
        hl.addSpacing(12)
        self.flags = QLabel()
        self.flags.setObjectName("chatFlags")
        hl.addWidget(self.flags)
        hl.addStretch(1)
        hl.addWidget(self.reset_btn)
        root.addWidget(header)

        # messages
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setObjectName("messageScroll")
        self.container = QWidget()
        self.container.setObjectName("messageArea")
        self.msg_layout = QVBoxLayout(self.container)
        self.msg_layout.setContentsMargins(0, 12, 0, 4)
        self.msg_layout.setSpacing(6)
        self.msg_layout.addStretch(1)
        self.typing = TypingIndicator()
        self.msg_layout.addWidget(self.typing)
        self.scroll.setWidget(self.container)
        sb = self.scroll.verticalScrollBar()
        sb.rangeChanged.connect(lambda _mn, mx: sb.setValue(mx))
        root.addWidget(self.scroll, 1)

        # input
        bar = QWidget()
        bar.setObjectName("inputBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 10, 16, 14)
        self.input = InputBox()
        self.input.setObjectName("chatInput")
        self.input.setPlaceholderText("Message the group…  (Enter to send, Shift+Enter for new line)")
        self.input.setFixedHeight(64)
        self.input.submitted.connect(self._send)
        self.send_btn = QPushButton("Send")
        self.send_btn.setFixedSize(90, 64)
        self.send_btn.clicked.connect(self._send)
        bl.addWidget(self.input, 1)
        bl.addWidget(self.send_btn)
        root.addWidget(bar)

    # ---- binding a session ------------------------------------------------
    def set_session(self, session: ChatSession | None) -> None:
        if self.session is not None:
            for sig, slot in self._connections():
                try:
                    sig.disconnect(slot)
                except (RuntimeError, TypeError):
                    pass
        self.session = session
        if session is not None:
            for sig, slot in self._connections():
                sig.connect(slot)
        self.refresh()

    def _connections(self):
        s = self.session
        return [(s.message_added, self._on_message), (s.typing_changed, self._on_typing),
                (s.busy_changed, self._on_busy), (s.cleared, self.refresh)]

    def refresh(self) -> None:
        """Rebuild everything from the current session."""
        self._clear_messages()
        s = self.session
        if s is None:
            return
        self.title.setText(s.chat.title)
        flags = []
        if s.chat.complete_response:
            flags.append("Complete Response")
        if s.chat.chat_context:
            flags.append("Chat context")
        roles = [f"{b.name}: {s.chat.bot_notes[b.id]}" for b in s.chat.bots
                 if s.chat.bot_notes.get(b.id)]
        if roles:
            flags.append("Roles")
        if s.chat.previous_context:
            flags.append("Continued")
        self.flags.setText("  ·  ".join(flags))
        tip = "\n".join(roles)
        if s.chat.chat_context:
            tip = (tip + "\n\n" if tip else "") + "Context: " + s.chat.chat_context
        if s.chat.previous_context:
            tip = (tip + "\n\n" if tip else "") + "Continues an earlier saved chat"
        self.flags.setToolTip(tip)
        while self.members.count():
            w = self.members.takeAt(0).widget()
            if w:
                w.deleteLater()
        for b in s.chat.bots:
            lbl = ClickableLabel()
            lbl.setPixmap(avatar(b.image_path, b.name, 26))
            lbl.setToolTip(f"{b.name} (click for profile)")
            lbl.clicked.connect(lambda b=b: self.open_profile(b))
            self.members.addWidget(lbl)
        for m in s.chat.messages:
            self._on_message(m)
        self._on_typing(s.typing)
        self._on_busy(s.busy)
        self.input.setFocus()

    def refresh_avatars(self) -> None:
        if self.session:
            self.refresh()

    # ---- events -----------------------------------------------------------
    def _clear_messages(self) -> None:
        # keep the top stretch (index 0) and the typing indicator (last)
        while self.msg_layout.count() > 2:
            item = self.msg_layout.takeAt(1)
            if item.widget():
                item.widget().hide()   # deleteLater is deferred; hide now so it never ghosts
                item.widget().deleteLater()

    def _avatar_size(self) -> int:
        return int(self._get_settings().get("avatar_size", 56))

    def _bubble_width(self) -> int:
        return int(self.scroll.viewport().width() * 0.65)

    def _on_message(self, m: Message) -> None:
        if m.is_system:
            w = SystemRow(m.text)
        else:
            img = self._get_settings().get("user_image", "") if m.is_user else ""
            bot = None
            if not m.is_user:
                bot = next((b for b in self.session.chat.bots
                            if b.id == m.bot_id or b.name == m.sender), None)
                img = bot.image_path if bot else ""
            w = MessageRow(m.sender, m.text, img, m.is_user, self._avatar_size())
            if bot is not None:
                w.avatar_clicked.connect(lambda b=bot: self.open_profile(b))
            w.set_max_bubble_width(self._bubble_width())
        self.msg_layout.insertWidget(self.msg_layout.count() - 1, w)

    def _on_typing(self, who) -> None:
        if who is None:
            self.typing.stop()
            return
        img = ""
        if who:
            bot = next((b for b in self.session.chat.bots if b.name == who), None)
            img = bot.image_path if bot else ""
        self.typing.show_for(who, img, self._avatar_size())

    def _on_busy(self, busy: bool) -> None:
        self.send_btn.setEnabled(not busy)
        self.send_btn.setText("…" if busy else "Send")

    def _send(self) -> None:
        if not self.session or self.session.busy:
            return
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.session.send(text)

    def open_profile(self, bot) -> None:
        role = self.session.chat.bot_notes.get(bot.id, "") if self.session else ""
        show_profile(self, bot, role, self._edit_bot)

    def _reset(self) -> None:
        if not self.session:
            return
        if self.session.chat.messages:
            ok = QMessageBox.question(
                self, "New session",
                "Start a new session?\n\nThis conversation will be kept under Saved chats.")
            if ok != QMessageBox.Yes:
                return
        self.session.reset()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        w = self._bubble_width()
        for i in range(self.msg_layout.count()):
            item = self.msg_layout.itemAt(i).widget()
            if isinstance(item, MessageRow):
                item.set_max_bubble_width(w)
