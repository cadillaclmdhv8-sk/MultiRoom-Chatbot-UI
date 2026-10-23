"""Saving settings and bots as JSON in the data/ folder."""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from .models import Bot

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SETTINGS_FILE = DATA_DIR / "settings.json"
BOTS_FILE = DATA_DIR / "bots.json"
AVATAR_DIR = DATA_DIR / "avatars"   # cropped bot images

DEFAULT_SETTINGS = {
    "kobold_url": "http://localhost:5001",
    "user_name": "You",
    "max_length": 220,
    "sampler_preset": "Godlike",
    "temperature": 0.7,          # used when sampler_preset == "Custom"
    "instruct_preset": "Mistral",
    "instruct_start": "",        # used when instruct_preset == "Custom"
    "instruct_end": "",
    "theme": "dark",
    "avatar_size": 56,           # chat image size in px
    "user_image": "",            # your own avatar (data/avatars/user.png); empty = none shown
}


def _read_json(path: Path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError):
        # Keep a copy of a broken file instead of silently overwriting it later
        try:
            path.replace(path.with_suffix(".broken.json"))
        except OSError:
            pass
        return default


def _write_json(path: Path, data) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def load_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    loaded = _read_json(SETTINGS_FILE, {})
    if isinstance(loaded, dict):
        s.update({k: v for k, v in loaded.items() if k in DEFAULT_SETTINGS})
    return s


def save_settings(settings: dict) -> None:
    _write_json(SETTINGS_FILE, settings)


def load_bots() -> list[Bot]:
    data = _read_json(BOTS_FILE, [])
    if not isinstance(data, list):
        return []
    return [Bot.from_dict(d) for d in data if isinstance(d, dict)]


def save_bots(bots: list[Bot]) -> None:
    _write_json(BOTS_FILE, [b.to_dict() for b in bots])


# ---- bot images ---------------------------------------------------------------
# data/avatars/<id>.<ext>           the image shown for the bot (cropped or copied)
# data/avatars/<id>_original.<ext>  copy of the picked file, used for re-cropping

def _stem_matches(path: Path, stem: str) -> bool:
    try:
        return path.resolve().parent == AVATAR_DIR.resolve() and path.stem == stem
    except OSError:
        return False


def clear_variants(stem: str, keep_suffix: str = "") -> None:
    """Remove data/avatars/<stem>.* except the one ending in keep_suffix."""
    if not AVATAR_DIR.is_dir():
        return
    for old in AVATAR_DIR.glob(f"{stem}.*"):
        if old.suffix.lower() != keep_suffix.lower():
            try:
                old.unlink()
            except OSError:
                pass


def import_image(src: str, bot_id: str, suffix: str = "") -> str:
    """Copy src to data/avatars/<bot_id><suffix><ext> and return the new path.

    Returns src unchanged if it doesn't exist or already is that file.
    """
    if not src:
        return src
    srcp = Path(src)
    if not srcp.is_file():
        return src
    stem = f"{bot_id}{suffix}"
    if _stem_matches(srcp, stem):
        return str(srcp)
    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    ext = srcp.suffix.lower() or ".png"
    dest = AVATAR_DIR / f"{stem}{ext}"
    shutil.copy2(srcp, dest)
    clear_variants(stem, ext)
    return str(dest)


def delete_bot_images(bot_id: str) -> None:
    if not AVATAR_DIR.is_dir():
        return
    for f in AVATAR_DIR.glob(f"{bot_id}*"):
        try:
            f.unlink()
        except OSError:
            pass


def migrate_bot_images(bots: list[Bot]) -> bool:
    """Copy images of older bots (pointing elsewhere on disk) into data/avatars."""
    changed = False
    for b in bots:
        try:
            if b.source_image:
                # Cropped bot: the crop already lives in data/avatars; copy the original in too
                new = import_image(b.source_image, b.id, "_original")
                changed |= new != b.source_image
                b.source_image = new
            else:
                new = import_image(b.image_path, b.id)
                changed |= new != b.image_path
                b.image_path = new
        except OSError:
            pass
    return changed


# ---- saved chats ----------------------------------------------------------------
CHATS_DIR = DATA_DIR / "chats"


def save_chat(chat) -> None:
    """Write data/chats/<id>.json (chat is a models.Chat)."""
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(CHATS_DIR / f"{chat.id}.json", chat.to_dict())


def load_chat_dicts() -> list[dict]:
    """All saved chats as dicts, most recently updated first."""
    if not CHATS_DIR.is_dir():
        return []
    out = []
    for f in CHATS_DIR.glob("*.json"):
        if f.name.endswith(".broken.json"):
            continue
        d = _read_json(f, None)
        if isinstance(d, dict) and d.get("id"):
            out.append(d)
    out.sort(key=lambda d: d.get("updated", ""), reverse=True)
    return out


def delete_chat(chat_id: str) -> None:
    try:
        (CHATS_DIR / f"{chat_id}.json").unlink()
    except OSError:
        pass


# ---- clearing --------------------------------------------------------------------
def clear_data(bots: bool, chats: bool, settings: bool) -> None:
    """Delete the chosen parts of data/. error.log is always kept."""
    if bots:
        for p in (BOTS_FILE,):
            try:
                p.unlink()
            except OSError:
                pass
        shutil.rmtree(AVATAR_DIR, ignore_errors=True)
    if chats:
        shutil.rmtree(CHATS_DIR, ignore_errors=True)
    if settings:
        try:
            SETTINGS_FILE.unlink()
        except OSError:
            pass
        # your own image lives in avatars/ too
        delete_bot_images("user")
