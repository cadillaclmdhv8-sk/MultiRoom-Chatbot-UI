from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QPlainTextEdit,
                               QScrollArea, QVBoxLayout, QWidget)

from ..models import Bot, MAX_BOTS_PER_CHAT
from .avatar import avatar


class NewChatDialog(QDialog):
    def __init__(self, bots: list[Bot], parent=None, user_name: str = "You"):
        super().__init__(parent)
        self.setWindowTitle("New chat")
        self.resize(440, 640)
        self._bots = bots
        self._title_edited = False

        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("Chat name"))
        self.title = QLineEdit()
        self.title.textEdited.connect(lambda _: setattr(self, "_title_edited", True))
        lay.addWidget(self.title)

        lay.addWidget(QLabel(f"Pick up to {MAX_BOTS_PER_CHAT} bots"))
        self.list = QListWidget()
        self.list.setIconSize(QSize(32, 32))
        for b in bots:
            it = QListWidgetItem(QIcon(avatar(b.image_path, b.name, 32)), b.name)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Unchecked)
            it.setData(Qt.UserRole, b.id)
            self.list.addItem(it)
        self.list.itemChanged.connect(self._update)
        self.list.itemClicked.connect(self._toggle)
        lay.addWidget(self.list, 1)

        self.count = QLabel()
        self.count.setObjectName("hint")
        lay.addWidget(self.count)

        # Per-bot role for this chat only: one row per bot, shown while it's ticked
        self.roles_label = QLabel("Roles in this chat (optional)")
        lay.addWidget(self.roles_label)
        self.roles_scroll = QScrollArea()
        self.roles_scroll.setObjectName("rolesScroll")
        self.roles_scroll.setWidgetResizable(True)
        self.roles_scroll.setMaximumHeight(200)
        roles_holder = QWidget()
        roles_holder.setObjectName("rolesArea")
        roles_lay = QVBoxLayout(roles_holder)
        roles_lay.setContentsMargins(0, 0, 4, 0)
        roles_lay.setSpacing(4)
        self._role_rows: dict[str, QWidget] = {}
        self._role_edits: dict[str, QLineEdit] = {}
        for b in bots:
            row = QWidget()
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 0, 0, 0)
            pic = QLabel()
            pic.setPixmap(avatar(b.image_path, b.name, 24))
            name = QLabel(b.name)
            name.setFixedWidth(90)
            edit = QLineEdit()
            edit.setPlaceholderText(f"e.g. {user_name}'s mom, {user_name}'s rival, the teacher…")
            rl.addWidget(pic)
            rl.addWidget(name)
            rl.addWidget(edit, 1)
            row.setVisible(False)
            roles_lay.addWidget(row)
            self._role_rows[b.id] = row
            self._role_edits[b.id] = edit
        roles_lay.addStretch(1)
        self.roles_scroll.setWidget(roles_holder)
        lay.addWidget(self.roles_scroll)

        self.complete = QCheckBox("Complete Response")
        self.complete.setToolTip("Every bot in the chat replies each turn")
        lay.addWidget(self.complete)
        self.use_context = QCheckBox("Chat context")
        self.use_context.setToolTip("Extra scenario/setting text added to the prompt")
        lay.addWidget(self.use_context)
        self.context = QPlainTextEdit()
        self.context.setPlaceholderText("e.g. Everyone is at Ashley's birthday party at the beach…")
        self.context.setFixedHeight(90)
        self.context.setVisible(False)
        self.use_context.toggled.connect(self.context.setVisible)
        lay.addWidget(self.context)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("Create")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        lay.addWidget(self.buttons)
        if not bots:
            self.count.setText("You have no bots yet. Add some in the BOTS tab first.")
        self._update()

    def _toggle(self, it: QListWidgetItem) -> None:
        it.setCheckState(Qt.Unchecked if it.checkState() == Qt.Checked else Qt.Checked)

    def selected_bots(self) -> list[Bot]:
        ids = [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())
               if self.list.item(i).checkState() == Qt.Checked]
        return [b for b in self._bots if b.id in ids]

    def complete_response(self) -> bool:
        return self.complete.isChecked()

    def chat_context(self) -> str:
        return self.context.toPlainText().strip() if self.use_context.isChecked() else ""

    def bot_notes(self) -> dict[str, str]:
        return {b.id: self._role_edits[b.id].text().strip() for b in self.selected_bots()
                if self._role_edits[b.id].text().strip()}

    def chat_title(self) -> str:
        t = self.title.text().strip()
        return t or ", ".join(b.name for b in self.selected_bots())

    def _update(self, *_):
        sel = self.selected_bots()
        n = len(sel)
        ids = {b.id for b in sel}
        for bid, row in self._role_rows.items():
            row.setVisible(bid in ids)  # hidden rows keep their text
        self.roles_label.setVisible(n > 0)
        self.roles_scroll.setVisible(n > 0)
        if self._bots:
            self.count.setText(f"{n} / {MAX_BOTS_PER_CHAT} selected"
                               + ("  (too many)" if n > MAX_BOTS_PER_CHAT else ""))
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(1 <= n <= MAX_BOTS_PER_CHAT)
        if not self._title_edited:
            self.title.setText(", ".join(b.name for b in sel))
