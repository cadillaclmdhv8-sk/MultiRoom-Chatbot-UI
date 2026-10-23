"""Light and dark color palettes plus the app stylesheet built from them."""
from __future__ import annotations

from string import Template

PALETTES = {
    "dark": {
        "bg": "#313338", "bg2": "#2b2d31", "bg3": "#1e1f22", "hover": "#35373c",
        "selected": "#404249", "border": "#26282c", "chat_input": "#383a40",
        "text": "#dbdee1", "strong": "#ffffff", "muted": "#949ba4", "hint": "#80848e",
        "desc": "#b5bac1", "secondary": "#4e5058", "secondary_hover": "#6d6f78",
        "secondary_text": "#ffffff", "scroll": "#1a1b1e", "popup": "#111214",
        "disabled_bg": "#3c3f87", "disabled_text": "#9a9cc4", "system": "#f0b232",
        "dashed": "#4e5058", "action": "#a3a6aa", "dot_on": "#ffffff", "dot_off": "#6d6f78",
        "accent": "#5865f2", "accent_hover": "#4752c4",
    },
    "light": {
        "bg": "#ffffff", "bg2": "#f2f3f5", "bg3": "#e3e5e8", "hover": "#e8e9ec",
        "selected": "#d7d9dd", "border": "#e1e2e4", "chat_input": "#ebedef",
        "text": "#313338", "strong": "#060607", "muted": "#5c5e66", "hint": "#6d6f78",
        "desc": "#4e5058", "secondary": "#d4d7dc", "secondary_hover": "#c4c9ce",
        "secondary_text": "#313338", "scroll": "#c1c3c7", "popup": "#ffffff",
        "disabled_bg": "#a5abf4", "disabled_text": "#ffffff", "system": "#a8650a",
        "dashed": "#c4c9ce", "action": "#6d6f78", "dot_on": "#313338", "dot_off": "#b5bac1",
        "accent": "#5865f2", "accent_hover": "#4752c4",
    },
}

NAME_COLORS = {
    "dark": ["#f47fff", "#5865f2", "#57f287", "#fee75c", "#eb459e", "#ed4245",
             "#3ba55c", "#faa61a", "#00b0f4", "#9b84ee", "#e67e22", "#1abc9c"],
    "light": ["#b02fc0", "#4752c4", "#1f8b4c", "#a8790a", "#c2185b", "#c62828",
              "#2e7d32", "#c26a00", "#0077b6", "#6a4fc9", "#b35400", "#11806a"],
}

_current = "dark"


def current() -> str:
    return _current


def set_current(name: str) -> None:
    global _current
    _current = name if name in PALETTES else "dark"


def color(token: str) -> str:
    return PALETTES[_current][token]


def name_colors() -> list[str]:
    return NAME_COLORS[_current]


_STYLE = Template("""
* { font-family: "Segoe UI", sans-serif; font-size: 14px; color: $text; }
QMainWindow, QDialog, #messageArea, #messageScroll, #botsArea, #botsScroll { background: $bg; }
QScrollArea { border: none; }
#topBar { background: $bg3; }
#appName { font-size: 16px; font-weight: 700; color: $strong; }
#status { color: $desc; }

QTabWidget::pane { border: none; top: 0; }
QTabWidget::tab-bar { left: 0; }
#mainTabs { background: $bg3; }
QTabBar { background: transparent; }
QTabBar::tab { background: transparent; padding: 8px 22px; color: $muted; font-weight: 600;
               border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: $strong; border-bottom: 2px solid $accent; }
QTabBar::tab:hover { color: $text; }

#sidebar { background: $bg2; }
#sectionLabel { color: $muted; font-size: 12px; font-weight: 700; padding: 4px 2px; }
#hint { color: $hint; font-size: 12px; }
#emptyState { color: $hint; font-size: 16px; background: $bg; }
#chatList { background: transparent; border: none; outline: none; }
#chatList::item { padding: 8px 6px; border-radius: 6px; margin: 1px 0; }
#chatList::item:hover { background: $hover; }
#chatList::item:selected { background: $selected; color: $strong; }
QSplitter::handle { background: $bg3; }

#chatHeader { background: $bg; border-bottom: 1px solid $border; }
#chatTitle { font-size: 16px; font-weight: 700; color: $strong; }
#chatFlags { color: $hint; font-size: 12px; }
#msgName { font-weight: 700; font-size: 13px; }
#bubbleBot, #bubbleUser { padding: 8px 12px; border-radius: 12px; }
#bubbleBot { background: $bg2; }
#bubbleUser { background: $accent; color: #ffffff; }
#systemLine { color: $system; font-size: 12px; padding: 6px; }
#typingDots { background: $bg2; border-radius: 12px; padding: 8px 12px; font-size: 11px; }
#typingLabel { color: $muted; font-size: 12px; }
#inputBar { background: $bg; }
#chatInput { background: $chat_input; border: none; border-radius: 10px; padding: 8px; }

QPushButton { background: $accent; color: #ffffff; border: none; border-radius: 6px;
              padding: 8px 16px; font-weight: 600; }
QPushButton:hover { background: $accent_hover; }
QPushButton:disabled { background: $disabled_bg; color: $disabled_text; }
QPushButton#secondary { background: $secondary; color: $secondary_text; }
QPushButton#secondary:hover { background: $secondary_hover; }
QPushButton#danger { background: #da373c; }
QPushButton#danger:hover { background: #a12828; }

QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox, QListWidget {
    background: $bg3; border: 1px solid $bg3; border-radius: 6px; padding: 6px; }
QLineEdit:focus, QPlainTextEdit:focus { border: 1px solid $accent; }
QComboBox QAbstractItemView { background: $bg2; selection-background-color: $selected; }
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled { color: $hint; }
QListWidget::item { padding: 4px; }

#pageTitle { font-size: 20px; font-weight: 700; color: $strong; }
#botCard, #addCard { background: $bg2; border-radius: 14px; border: 1px solid $bg2; }
#botCard:hover, #addCard:hover { background: $hover; border: 1px solid $accent; }
#addCard { border: 2px dashed $dashed; }
#addPlus { font-size: 48px; color: $muted; }
#cardName { font-weight: 700; font-size: 15px; color: $strong; }
#cardDesc { color: $desc; font-size: 12px; }

#cropHint { color: $hint; font-size: 12px; }
#botsPage { background: $bg; }
#rolesScroll, #rolesArea { background: transparent; }
#profileName { font-size: 20px; font-weight: 700; color: $strong; }
#profileRole { background: $bg2; border-left: 3px solid $accent; border-radius: 4px; padding: 8px 10px; }
#savedBanner { color: $hint; font-size: 12px; }
#savedArea { background: $bg; }
#dangerLabel { color: #da373c; font-weight: 700; }

QCheckBox { spacing: 8px; }
QCheckBox::indicator, QListWidget::indicator { width: 16px; height: 16px; border-radius: 4px;
    border: 2px solid $muted; background: transparent; }
QCheckBox::indicator:checked, QListWidget::indicator:checked { background: $accent;
    border: 2px solid $accent; }
QCheckBox::indicator:hover, QListWidget::indicator:hover { border: 2px solid $accent; }

QScrollBar:vertical { background: transparent; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }
QToolTip { background: $popup; color: $text; border: 1px solid $border; padding: 6px; }
QMenu { background: $popup; padding: 4px; border: 1px solid $border; }
QMenu::item { padding: 6px 18px; border-radius: 4px; }
QMenu::item:selected { background: $accent; color: #ffffff; }
""")


def build_style(name: str | None = None) -> str:
    return _STYLE.substitute(PALETTES[name or _current])
