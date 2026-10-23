"""One chat row (avatar + name + bubble) and the typing indicator."""
from __future__ import annotations

import html
import os
import re

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QTextDocument
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from . import theme
from .avatar import avatar, color_for

DEFAULT_AVATAR_SIZE = 56
_ACTION_RE = re.compile(r"\*([^*\n]+)\*")


def format_text(text: str) -> str:
    t = html.escape(text)
    t = _ACTION_RE.sub(rf'<i style="color:{theme.color("action")}">\1</i>', t)
    return t.replace("\n", "<br>")


class ClickableLabel(QLabel):
    clicked = Signal()

    def __init__(self, *args):
        super().__init__(*args)
        self.setCursor(Qt.PointingHandCursor)

    def mouseReleaseEvent(self, e):
        hit = e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint())
        super().mouseReleaseEvent(e)
        if hit:
            self.clicked.emit()   # last: the handler may rebuild/delete this label


class MessageRow(QWidget):
    avatar_clicked = Signal()   # bot rows only
    def __init__(self, sender: str, text: str, image_path: str = "", is_user: bool = False,
                 avatar_size: int = DEFAULT_AVATAR_SIZE):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 4, 12, 4)
        row.setSpacing(10)

        if is_user:
            pic = QLabel()
        else:
            pic = ClickableLabel()
            pic.setToolTip(f"View {sender}'s profile")
            pic.clicked.connect(self.avatar_clicked)
        pic.setPixmap(avatar(image_path, sender, avatar_size))
        pic.setFixedSize(avatar_size, avatar_size)

        col = QVBoxLayout()
        col.setSpacing(3)
        name = QLabel(html.escape(sender))
        name.setObjectName("msgName")
        name.setStyleSheet(f"color: {color_for(sender) if not is_user else theme.color('text')};")
        self.bubble = QLabel(format_text(text))
        self.bubble.setObjectName("bubbleUser" if is_user else "bubbleBot")
        self.bubble.setTextFormat(Qt.RichText)
        self.bubble.setWordWrap(True)
        self.bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)

        align = Qt.AlignRight if is_user else Qt.AlignLeft
        col.addWidget(name, 0, align)
        col.addWidget(self.bubble, 0, align)

        if is_user:
            row.addStretch(1)
            row.addLayout(col)
            # Your avatar only shows when you've set an image in Settings
            if image_path and os.path.isfile(image_path):
                row.addWidget(pic, 0, Qt.AlignTop)
            else:
                pic.deleteLater()
        else:
            row.addWidget(pic, 0, Qt.AlignTop)
            row.addLayout(col)
            row.addStretch(1)

    def set_max_bubble_width(self, w: int) -> None:
        # Size the bubble to its text (like a chat app), wrapping only past w.
        w = max(200, w)
        self.bubble.ensurePolished()  # pick up the stylesheet font first
        doc = QTextDocument()
        doc.setDefaultFont(self.bubble.font())
        doc.setHtml(self.bubble.text())
        doc.setTextWidth(w - 24)
        self.bubble.setFixedWidth(min(w, int(doc.idealWidth()) + 24 + 8))


class SystemRow(QLabel):
    def __init__(self, text: str):
        super().__init__(html.escape(text))
        self.setObjectName("systemLine")
        self.setAlignment(Qt.AlignCenter)
        self.setWordWrap(True)


class TypingIndicator(QFrame):
    """'● ● ●' bubble with pulsing dots, optionally with the bot's avatar and name."""

    def __init__(self):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 4, 12, 8)
        row.setSpacing(10)
        self.pic = QLabel()
        self.dots = QLabel()
        self.dots.setObjectName("typingDots")
        self.dots.setTextFormat(Qt.RichText)
        self.label = QLabel()
        self.label.setObjectName("typingLabel")
        row.addWidget(self.pic)
        row.addWidget(self.dots)
        row.addWidget(self.label)
        row.addStretch(1)
        self._step = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self.hide()

    def show_for(self, name: str, image_path: str = "", size: int = DEFAULT_AVATAR_SIZE) -> None:
        if name:
            self.pic.setFixedSize(size, size)
            self.pic.setPixmap(avatar(image_path, name, size))
            self.pic.show()
            self.label.setText(f"<b>{html.escape(name)}</b> is typing…")
        else:
            self.pic.hide()
            self.label.setText("typing…")
        self._tick()
        self._timer.start(350)
        self.show()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def _tick(self) -> None:
        self._step = (self._step + 1) % 3
        parts = []
        for i in range(3):
            color = theme.color("dot_on" if i == self._step else "dot_off")
            parts.append(f'<span style="color:{color}">●</span>')
        self.dots.setText("&nbsp;".join(parts))
