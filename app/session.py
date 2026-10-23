"""Per-chat state: sending, waiting for the LLM, and delivering replies with delays."""
from __future__ import annotations

import random
from typing import Callable

from PySide6.QtCore import QObject, QTimer, Signal

from .kobold import (KoboldClient, describe_error, instruct_from_settings, run_background,
                     sampler_from_settings, stops_from_settings)
from . import storage
from .models import Chat, Message, new_id, now_iso
from .prompt import ParsedLine, build_prompt, parse_reply

MIN_DELAY_MS = 3000
MAX_DELAY_MS = 5000


class ChatSession(QObject):
    message_added = Signal(object)    # Message
    typing_changed = Signal(object)   # None = hidden, "" = generic, "Name" = that bot
    busy_changed = Signal(bool)
    cleared = Signal()

    def __init__(self, chat: Chat, get_settings: Callable[[], dict]):
        super().__init__()
        self.chat = chat
        self._get_settings = get_settings
        self._gen_id = 0
        self._queue: list[ParsedLine] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._deliver_next)
        self.busy = False
        self.typing: str | None = None

    # ---- public -------------------------------------------------------
    def send(self, text: str) -> None:
        text = text.strip()
        if not text or self.busy:
            return
        s = self._get_settings()
        self._add(Message(s["user_name"], text, is_user=True))
        self._generate()

    def stop(self) -> None:
        """Cancel any generation and queued replies, keeping the messages."""
        was_generating = self.busy and not self._queue
        self._gen_id += 1
        self._timer.stop()
        self._queue.clear()
        if was_generating:
            url = self._get_settings()["kobold_url"]
            run_background(lambda: KoboldClient(url).abort())
        self._set_typing(None)
        self._set_busy(False)

    def reset(self) -> None:
        """New session: stop, then start an empty chat with the same bots and settings.

        The old conversation stays in data/chats/ as a saved chat; this chat
        gets a fresh id so it's saved separately from now on.
        """
        self.stop()
        if self.chat.messages:
            self.chat.id = new_id()
            self.chat.created = self.chat.updated = now_iso()
        self.chat.messages.clear()
        self.chat.previous_context = ""
        self.cleared.emit()

    # ---- internals ------------------------------------------------------
    def _add(self, msg: Message) -> None:
        self.chat.messages.append(msg)
        self.chat.updated = now_iso()
        try:
            storage.save_chat(self.chat)   # auto-save after every message
        except OSError as e:
            print(f"Couldn't save chat: {e}")
        self.message_added.emit(msg)

    def _set_busy(self, busy: bool) -> None:
        if busy != self.busy:
            self.busy = busy
            self.busy_changed.emit(busy)

    def _set_typing(self, who: str | None) -> None:
        self.typing = who
        self.typing_changed.emit(who)

    def _generate(self) -> None:
        s = self._get_settings()
        client = KoboldClient(s["kobold_url"])
        user = s["user_name"]
        bots = list(self.chat.bots)
        history = list(self.chat.messages)
        max_length = int(s["max_length"])
        sampler = sampler_from_settings(s)
        stops = stops_from_settings(s)
        instruct = instruct_from_settings(s)
        complete_response = self.chat.complete_response
        chat_context = self.chat.chat_context
        bot_notes = dict(self.chat.bot_notes)
        previous_context = self.chat.previous_context

        def work() -> str:
            ctx = client.max_context()
            # ~3 chars per token, minus room for the reply
            max_chars = max(2000, (ctx - max_length) * 3)
            prompt = build_prompt(bots, user, history, max_chars, instruct,
                                  complete_response, chat_context, bot_notes,
                                  previous_context)
            return client.generate(prompt, max_length, ctx, sampler, stops)

        self._gen_id += 1
        gen_id = self._gen_id
        self._set_busy(True)
        self._set_typing("")
        run_background(
            work,
            on_done=lambda text: self._on_reply(gen_id, text),
            on_error=lambda e: self._on_error(gen_id, describe_error(e, client.base_url)),
        )

    def _on_error(self, gen_id: int, msg: str) -> None:
        if gen_id != self._gen_id:
            return
        self._set_typing(None)
        self._add(Message("", msg, is_system=True))
        self._set_busy(False)

    def _on_reply(self, gen_id: int, text: str) -> None:
        if gen_id != self._gen_id:
            return  # chat was reset while waiting
        s = self._get_settings()
        lines = parse_reply(text or "", [b.name for b in self.chat.bots], s["user_name"])
        if not lines:
            self._set_typing(None)
            self._add(Message("", "No reply came back. Try sending again.", is_system=True))
            self._set_busy(False)
            return
        self._queue = lines
        self._deliver_next()

    def _deliver_next(self) -> None:
        if not self._queue:
            self._set_typing(None)
            self._set_busy(False)
            return
        line = self._queue.pop(0)
        bot = next((b for b in self.chat.bots if b.name == line.name), None)
        self._add(Message(line.name, line.text, bot_id=bot.id if bot else ""))
        if self._queue:
            self._set_typing(self._queue[0].name)
            self._timer.start(random.randint(MIN_DELAY_MS, MAX_DELAY_MS))
        else:
            self._set_typing(None)
            self._set_busy(False)
