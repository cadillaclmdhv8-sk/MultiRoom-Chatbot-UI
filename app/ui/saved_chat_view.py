"""Read-only preview of a saved chat, with a 'Continue this chat' button."""
from __future__ import annotations

import html
from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QGraphicsOpacityEffect, QHBoxLayout, QLabel, QPushButton,
                               QScrollArea, QVBoxLayout, QWidget)

from ..models import Chat
from .avatar import avatar
from .bot_profile import show_profile
from .message_widget import ClickableLabel, MessageRow, SystemRow


def nice_date(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        return ""


class SavedChatView(QWidget):
    continue_requested = Signal(object)   # chat dict
    delete_requested = Signal(object)     # chat dict

    def __init__(self, get_settings, get_bots, edit_bot=None):
        super().__init__()
        self._get_settings = get_settings
        self._get_bots = get_bots
        self._edit_bot = edit_bot
        self._data: dict | None = None
        self._chat: Chat | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("chatHeader")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 10, 12, 10)
        self.title = QLabel()
        self.title.setObjectName("chatTitle")
        self.members = QHBoxLayout()
        self.members.setSpacing(4)
        self.info = QLabel()
        self.info.setObjectName("chatFlags")
        hl.addWidget(self.title)
        hl.addSpacing(12)
        hl.addLayout(self.members)
        hl.addSpacing(12)
        hl.addWidget(self.info)
        hl.addStretch(1)
        root.addWidget(header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setObjectName("messageScroll")
        sb = self.scroll.verticalScrollBar()
        sb.rangeChanged.connect(lambda _mn, mx: sb.setValue(mx))   # open at the latest messages
        root.addWidget(self.scroll, 1)

        bar = QWidget()
        bar.setObjectName("inputBar")
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(16, 10, 16, 14)
        self.banner = QLabel("Saved chat (read-only). Continuing starts a new session "
                             "that remembers the most recent part of this one.")
        self.banner.setObjectName("savedBanner")
        self.banner.setWordWrap(True)
        delete = QPushButton("Delete")
        delete.setObjectName("secondary")
        delete.clicked.connect(lambda: self._data and self.delete_requested.emit(self._data))
        self.cont = QPushButton("Continue this chat  →")
        self.cont.setFixedHeight(44)
        self.cont.clicked.connect(lambda: self._data and self.continue_requested.emit(self._data))
        bl.addWidget(self.banner, 1)
        bl.addWidget(delete)
        bl.addWidget(self.cont)
        root.addWidget(bar)

    def show_chat(self, d: dict) -> None:
        self._data = d
        bots = self._get_bots()
        chat = Chat.from_dict(d, bots)
        self._chat = chat
        names = d.get("bot_names") or []
        missing = max(0, len(names) - len(chat.bots))

        self.title.setText(chat.title)
        while self.members.count():
            w = self.members.takeAt(0).widget()
            if w:
                w.hide()
                w.deleteLater()
        for b in chat.bots:
            lbl = ClickableLabel()
            lbl.setPixmap(avatar(b.image_path, b.name, 26))
            lbl.setToolTip(f"{b.name} (click for profile)")
            lbl.clicked.connect(lambda b=b: self._profile(b))
            self.members.addWidget(lbl)
        info = [nice_date(d.get("updated", ""))]
        if missing:
            info.append(f"{missing} bot{'s' if missing > 1 else ''} deleted")
        self.info.setText("  ·  ".join(i for i in info if i))
        self.cont.setEnabled(bool(chat.bots))
        self.cont.setToolTip("" if chat.bots else "All of this chat's bots were deleted")

        # messages (slightly faded to show it's an old chat)
        holder = QWidget()
        holder.setObjectName("savedArea")
        lay = QVBoxLayout(holder)
        lay.setContentsMargins(0, 12, 0, 12)
        lay.setSpacing(6)
        lay.addStretch(1)
        s = self._get_settings()
        size = int(s.get("avatar_size", 56))
        width = int(self.scroll.viewport().width() * 0.65)
        by_id = {b.id: b for b in chat.bots}
        if chat.previous_context:
            lay.addWidget(SystemRow("(continues an earlier chat)"))
        for m in chat.messages:
            if m.is_system:
                lay.addWidget(SystemRow(m.text))
                continue
            bot = None if m.is_user else (by_id.get(m.bot_id)
                                          or next((b for b in chat.bots if b.name == m.sender), None))
            img = s.get("user_image", "") if m.is_user else (bot.image_path if bot else "")
            row = MessageRow(m.sender, m.text, img, m.is_user, size)
            if bot is not None:
                row.avatar_clicked.connect(lambda b=bot: self._profile(b))
            row.set_max_bubble_width(width)
            lay.addWidget(row)
        fade = QGraphicsOpacityEffect(holder)
        fade.setOpacity(0.8)
        holder.setGraphicsEffect(fade)
        self.scroll.setWidget(holder)

    def _profile(self, bot) -> None:
        role = self._chat.bot_notes.get(bot.id, "") if self._chat else ""
        show_profile(self, bot, role, self._edit_bot)
