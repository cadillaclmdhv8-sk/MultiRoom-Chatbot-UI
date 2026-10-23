"""BOTS tab: a grid of rounded-square cards (image, name, description)."""
from __future__ import annotations


from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
                               QVBoxLayout, QWidget)

from ..models import Bot
from .avatar import avatar
from .flow_layout import FlowLayout

CARD_W = 184
IMG = 160


class BotCard(QFrame):
    clicked = Signal()

    def __init__(self, bot: Bot | None):
        super().__init__()
        self.setObjectName("botCard" if bot else "addCard")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(CARD_W, 250)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(6)

        if bot is None:
            plus = QLabel("+")
            plus.setObjectName("addPlus")
            plus.setAlignment(Qt.AlignCenter)
            txt = QLabel("Add bot")
            txt.setAlignment(Qt.AlignCenter)
            lay.addStretch(1)
            lay.addWidget(plus)
            lay.addWidget(txt)
            lay.addStretch(1)
            return

        pic = QLabel()
        pic.setPixmap(avatar(bot.image_path, bot.name, IMG, radius_ratio=0.12))
        pic.setFixedSize(IMG, IMG)
        inner = CARD_W - 24
        name = QLabel()
        name.setObjectName("cardName")
        name.setText(name.fontMetrics().elidedText(bot.name, Qt.ElideRight, inner))
        name.setToolTip(bot.name)
        desc = QLabel()
        desc.setObjectName("cardDesc")
        desc.setTextFormat(Qt.PlainText)
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        fm = desc.fontMetrics()
        # rough 3-line cut: wrapped lines lose some width at word breaks
        desc.setText(fm.elidedText(bot.description or "No description", Qt.ElideRight,
                                   int(inner * 2.6)))
        desc.setMaximumHeight(fm.lineSpacing() * 3 + 2)
        desc.setToolTip(bot.description)
        lay.addWidget(pic, 0, Qt.AlignHCenter)
        lay.addWidget(name)
        lay.addWidget(desc, 1)

    def mouseReleaseEvent(self, e):
        hit = e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint())
        super().mouseReleaseEvent(e)
        if hit:
            # Must be last: saving in the editor rebuilds the grid and deletes this card.
            self.clicked.emit()


class BotsTab(QWidget):
    add_requested = Signal()
    edit_requested = Signal(object)   # Bot

    def __init__(self):
        super().__init__()
        self.setObjectName("botsPage")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        top = QHBoxLayout()
        top.setContentsMargins(24, 16, 24, 0)
        title = QLabel("Bots")
        title.setObjectName("pageTitle")
        add = QPushButton("+  New bot")
        add.clicked.connect(self.add_requested)
        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(add)
        lay.addLayout(top)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setObjectName("botsScroll")
        lay.addWidget(self.scroll, 1)

    def set_bots(self, bots: list[Bot]) -> None:
        holder = QWidget()
        holder.setObjectName("botsArea")
        flow = FlowLayout(holder, spacing=18)
        flow.setContentsMargins(24, 16, 24, 24)
        for b in bots:
            card = BotCard(b)
            card.clicked.connect(lambda b=b: self.edit_requested.emit(b))
            flow.addWidget(card)
        add = BotCard(None)
        add.clicked.connect(self.add_requested)
        flow.addWidget(add)
        self.scroll.setWidget(holder)  # old holder is deleted by Qt
