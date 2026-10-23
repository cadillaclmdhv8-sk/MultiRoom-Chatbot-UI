"""Read-only profile popup for a bot, opened by clicking its picture in a chat."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                               QVBoxLayout)

from ..models import Bot
from .avatar import avatar


class BotProfileDialog(QDialog):
    """After exec(): .edit_requested is True if 'Edit bot…' was pressed."""

    def __init__(self, bot: Bot, role: str = "", parent=None, can_edit: bool = True):
        super().__init__(parent)
        self.setWindowTitle(bot.name)
        self.resize(460, 600)
        self.edit_requested = False

        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        pic = QLabel()
        pic.setPixmap(avatar(bot.image_path, bot.name, 180, radius_ratio=0.12))
        pic.setAlignment(Qt.AlignHCenter)
        lay.addWidget(pic)

        name = QLabel(html.escape(bot.name))
        name.setObjectName("profileName")
        name.setAlignment(Qt.AlignHCenter)
        lay.addWidget(name)

        if bot.description:
            desc = QLabel(html.escape(bot.description))
            desc.setObjectName("cardDesc")
            desc.setAlignment(Qt.AlignHCenter)
            desc.setWordWrap(True)
            lay.addWidget(desc)

        if role.strip():
            r = QLabel(f"<b>Role in this chat:</b> {html.escape(role.strip())}")
            r.setObjectName("profileRole")
            r.setWordWrap(True)
            lay.addWidget(r)

        lay.addWidget(QLabel("Context"))
        ctx = QPlainTextEdit(bot.context or "(no context)")
        ctx.setReadOnly(True)
        lay.addWidget(ctx, 1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        if can_edit:
            edit = QPushButton("Edit bot…")
            edit.setObjectName("secondary")
            edit.clicked.connect(self._edit)
            btns.addWidget(edit)
        close = QPushButton("Close")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        btns.addWidget(close)
        lay.addLayout(btns)

    def _edit(self):
        self.edit_requested = True
        self.accept()


def show_profile(parent, bot: Bot, role: str = "", edit_bot=None) -> None:
    """Open the profile; if the user picks 'Edit bot…', call edit_bot(bot)."""
    dlg = BotProfileDialog(bot, role, parent, can_edit=edit_bot is not None)
    dlg.exec()
    if dlg.edit_requested and edit_bot is not None:
        edit_bot(bot)
