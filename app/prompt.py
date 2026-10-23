"""Prompt building and reply parsing. Pure functions, no Qt."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import Bot, Message

INSTRUCTIONS = """### Instructions

You are writing a group chat between the characters above and {{user_name}}. Write only the characters' replies, never {{user_name}}'s.

Format rules:
- Every line of dialogue begins with the speaker's name in square brackets, followed by a colon, then what they say: [Name]: dialogue
- Put physical actions and gestures between asterisks, e.g. *she laughs and nudges him*
- Each character speaks in their own voice, per their personality and speech quirks. Never blend voices.
- Characters react to each other and to {{user_name}}, not just to the last line.
{{turn_rule}}
- Keep replies natural and conversational. No narration outside asterisks, no summaries, no out-of-character commentary.
- Never speak or act for {{user_name}}."""

DEFAULT_TURN_RULE = ("- Not everyone has to speak every turn. Write 1 to 3 short replies, "
                     "and only from characters who would plausibly say something.")
COMPLETE_TURN_RULE = (
    "- All bots must respond within the output.\n"
    "- Characters may speak more than once and should talk to each other across several lines "
    "(replying to, teasing, agreeing or arguing with one another), not just answering {{user_name}}.")

# Per-chat role line added to a character's block, and the rule that makes it stick
# (Wording picked by testing against Mistral-Nemo: naming the bot + this rule made roles stick.)
ROLE_PREFIX = "In this chat, {name}'s role:"
ROLE_RULE = ("- Each character's role in this chat comes first: play that role (relationship, "
             "age, attitude), keeping only the personality traits and speech quirks that still fit.")

# name -> (start tag, end tag)
INSTRUCT_PRESETS: dict[str, tuple[str, str]] = {
    "Mistral": ("[INST] ", " [/INST]\n"),
    "ChatML": ("<|im_start|>user\n", "<|im_end|>\n<|im_start|>assistant\n"),
    "Llama 3": (
        "<|start_header_id|>user<|end_header_id|>\n\n",
        "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n",
    ),
    "Alpaca": ("### Instruction:\n", "\n### Response:\n"),
    "None": ("", ""),
}


def _line(name: str, text: str) -> str:
    return f"[{name}]: {text}"


def history_lines(messages: list[Message]) -> list[str]:
    out = []
    for m in messages:
        if m.is_system:
            continue
        out.append(_line(m.sender, m.text.strip()))
    return out


def build_prompt(
    bots: list[Bot],
    user_name: str,
    messages: list[Message],
    max_chars: int = 12000,
    instruct: tuple[str, str] = ("", ""),
    complete_response: bool = False,
    chat_context: str = "",
    bot_notes: dict[str, str] | None = None,
    previous_context: str = "",
) -> str:
    bot_notes = bot_notes or {}
    has_notes = False
    chars = ["### Characters", ""]
    for b in bots:
        chars.append(f"[{b.name}]")
        chars.append((b.context or b.description or "").strip())
        note = bot_notes.get(b.id, "").strip()
        if note:
            chars.append(f"{ROLE_PREFIX.format(name=b.name)} {note}")
            has_notes = True
        chars.append("")
    if chat_context.strip():
        chars += ["### Chat Context", "", chat_context.strip(), ""]
    if previous_context.strip():
        chars += ["### Earlier conversation (previous session)", "", previous_context.strip(), ""]
    instructions = INSTRUCTIONS.replace(
        "{{turn_rule}}", COMPLETE_TURN_RULE if complete_response else DEFAULT_TURN_RULE)
    if has_notes:
        instructions += "\n" + ROLE_RULE
    header = ("\n".join(chars) + "\n" + instructions).replace("{{user_name}}", user_name)
    header += "\n\n### Chat\n\n"
    start, end = instruct

    budget = max_chars - len(header) - len(start) - len(end)
    lines = history_lines(messages)
    kept: list[str] = []
    used = 0
    for ln in reversed(lines):
        cost = len(ln) + 1
        if kept and used + cost > budget:
            break
        kept.append(ln)
        used += cost
    kept.reverse()

    body = header + "\n".join(kept)
    if instruct == ("", ""):
        return body + "\n"
    return start + body.rstrip() + end


_TAG_RE = re.compile(r"\[([^\]\n]{1,40})\]\s*:")
_ACTION_ONLY_RE = re.compile(r"^(\*[^*]+\*\s*)+$")


@dataclass
class ParsedLine:
    name: str   # canonical bot name
    text: str


def parse_reply(text: str, bot_names: list[str], user_name: str) -> list[ParsedLine]:
    """Split LLM output like '[Name]: text' into one message per speaker.

    Stops at the user's tag or a name not in the chat. Speaker tags may also
    appear mid-line ('*she waves* [Mara]: hi'); an action-only prefix like that
    is given to the new speaker.
    """
    lookup = {n.strip().lower(): n for n in bot_names}
    user_key = user_name.strip().lower()
    result: list[ParsedLine] = []
    current: ParsedLine | None = None

    def add_text(s: str, sep: str = "\n") -> None:
        nonlocal current
        s = s.strip()
        if not s:
            return
        if current is None:
            if len(bot_names) != 1 or result:
                return
            # Model skipped the [Name]: prefix on a one-bot chat
            current = ParsedLine(bot_names[0], "")
            result.append(current)
        current.text = f"{current.text}{sep}{s}" if current.text else s

    for raw in text.replace("\r", "").split("\n"):
        pos = 0
        pending_prefix = ""
        stop = False
        for m in _TAG_RE.finditer(raw):
            key = m.group(1).strip().lower()
            if key != user_key and key not in lookup:
                if not raw[:m.start()].strip():
                    stop = True  # a made-up character starting a line: stop here
                    break
                continue  # mid-line, e.g. "[laughs]:" - treat as plain text
            before = raw[pos:m.start()].strip()
            if before and _ACTION_ONLY_RE.match(before):
                pending_prefix = before
            else:
                add_text(before, " " if pos else "\n")
            if key == user_key:
                stop = True
                break
            current = ParsedLine(lookup[key], pending_prefix)
            pending_prefix = ""
            result.append(current)
            pos = m.end()
        if stop:
            break
        add_text(raw[pos:], " " if pos else "\n")

    for p in result:
        p.text = p.text.strip()
    return [p for p in result if p.text]
