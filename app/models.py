from __future__ import annotations

import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict

MAX_BOTS_PER_CHAT = 10


def new_id() -> str:
    return uuid.uuid4().hex


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class Bot:
    name: str
    description: str = ""
    context: str = ""
    image_path: str = ""     # what is shown (cropped copy, or the original)
    source_image: str = ""   # original picked file, used for re-cropping
    id: str = field(default_factory=new_id)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Bot":
        return cls(
            name=d.get("name", "Unnamed"),
            description=d.get("description", ""),
            context=d.get("context", ""),
            image_path=d.get("image_path", ""),
            source_image=d.get("source_image", ""),
            id=d.get("id") or new_id(),
        )


@dataclass
class Message:
    sender: str          # display name
    text: str
    is_user: bool = False
    is_system: bool = False
    bot_id: str = ""     # set for bot messages


@dataclass
class Chat:
    title: str
    bots: list[Bot]
    messages: list[Message] = field(default_factory=list)
    complete_response: bool = False   # every bot must reply each turn
    chat_context: str = ""            # extra scenario text for the prompt
    bot_notes: dict[str, str] = field(default_factory=dict)  # bot id -> role in this chat
    previous_context: str = ""        # recent text from an older chat this one continues
    id: str = field(default_factory=new_id)
    created: str = field(default_factory=now_iso)
    updated: str = field(default_factory=now_iso)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "bot_ids": [b.id for b in self.bots],
            "bot_names": [b.name for b in self.bots],   # for showing chats whose bots were deleted
            "messages": [asdict(m) for m in self.messages],
            "complete_response": self.complete_response,
            "chat_context": self.chat_context,
            "bot_notes": dict(self.bot_notes),
            "previous_context": self.previous_context,
            "created": self.created,
            "updated": self.updated,
        }

    @classmethod
    def from_dict(cls, d: dict, all_bots: list[Bot]) -> "Chat":
        """Rebuild a chat; bots that no longer exist are left out."""
        by_id = {b.id: b for b in all_bots}
        bots = [by_id[i] for i in d.get("bot_ids", []) if i in by_id]
        msgs = []
        for m in d.get("messages", []):
            if isinstance(m, dict):
                msgs.append(Message(sender=m.get("sender", ""), text=m.get("text", ""),
                                    is_user=bool(m.get("is_user")), is_system=bool(m.get("is_system")),
                                    bot_id=m.get("bot_id", "")))
        return cls(
            title=d.get("title", "Chat"),
            bots=bots,
            messages=msgs,
            complete_response=bool(d.get("complete_response")),
            chat_context=d.get("chat_context", ""),
            bot_notes={k: v for k, v in (d.get("bot_notes") or {}).items() if k in by_id},
            previous_context=d.get("previous_context", ""),
            id=d.get("id") or new_id(),
            created=d.get("created") or now_iso(),
            updated=d.get("updated") or now_iso(),
        )


CONTINUATION_MAX_CHARS = 4000   # ~1/3 of a 4096-token context at ~3 chars/token


def continuation_text(chat: Chat, max_chars: int = CONTINUATION_MAX_CHARS) -> str:
    """Most recent text of a chat (incl. what it continued from), cut at a line break."""
    lines = [ln for ln in chat.previous_context.split("\n") if ln.strip()]
    lines += [f"[{m.sender}]: {m.text.strip()}" for m in chat.messages if not m.is_system]
    kept: list[str] = []
    used = 0
    for ln in reversed(lines):
        cost = len(ln) + 1
        if used + cost > max_chars:
            break
        kept.append(ln)
        used += cost
    return "\n".join(reversed(kept))
