import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import storage  # noqa: E402
from app.models import Bot, Chat, Message, continuation_text  # noqa: E402


class TempDataDir(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._saved = (storage.DATA_DIR, storage.SETTINGS_FILE, storage.BOTS_FILE,
                       storage.AVATAR_DIR, storage.CHATS_DIR)
        storage.DATA_DIR = self.tmp
        storage.SETTINGS_FILE = self.tmp / "settings.json"
        storage.BOTS_FILE = self.tmp / "bots.json"
        storage.AVATAR_DIR = self.tmp / "avatars"
        storage.CHATS_DIR = self.tmp / "chats"

    def tearDown(self):
        (storage.DATA_DIR, storage.SETTINGS_FILE, storage.BOTS_FILE,
         storage.AVATAR_DIR, storage.CHATS_DIR) = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)


class ChatSaveTests(TempDataDir):
    def make_chat(self):
        self.ash, self.vic = Bot("Ashley"), Bot("Victor")
        chat = Chat("Crew", [self.ash, self.vic], complete_response=True, chat_context="beach",
                    bot_notes={self.vic.id: "Sam's mom"}, previous_context="[Sam]: old")
        chat.messages = [Message("Sam", "hi", is_user=True),
                         Message("Victor", "hey", bot_id=self.vic.id),
                         Message("", "error", is_system=True)]
        return chat

    def test_round_trip(self):
        chat = self.make_chat()
        storage.save_chat(chat)
        [d] = storage.load_chat_dicts()
        back = Chat.from_dict(d, [self.ash, self.vic])
        self.assertEqual(back.title, "Crew")
        self.assertEqual([b.name for b in back.bots], ["Ashley", "Victor"])
        self.assertEqual([(m.sender, m.text, m.is_user, m.is_system) for m in back.messages],
                         [(m.sender, m.text, m.is_user, m.is_system) for m in chat.messages])
        self.assertTrue(back.complete_response)
        self.assertEqual(back.bot_notes, {self.vic.id: "Sam's mom"})
        self.assertEqual(back.previous_context, "[Sam]: old")
        self.assertEqual(back.id, chat.id)

    def test_deleted_bot_left_out(self):
        chat = self.make_chat()
        storage.save_chat(chat)
        [d] = storage.load_chat_dicts()
        back = Chat.from_dict(d, [self.ash])          # Victor was deleted
        self.assertEqual([b.name for b in back.bots], ["Ashley"])
        self.assertEqual(back.bot_notes, {})
        self.assertEqual(d["bot_names"], ["Ashley", "Victor"])

    def test_newest_first_and_delete(self):
        a, b = self.make_chat(), self.make_chat()
        a.updated, b.updated = "2026-01-01T00:00:00", "2026-02-01T00:00:00"
        storage.save_chat(a)
        storage.save_chat(b)
        self.assertEqual([d["id"] for d in storage.load_chat_dicts()], [b.id, a.id])
        storage.delete_chat(b.id)
        self.assertEqual([d["id"] for d in storage.load_chat_dicts()], [a.id])

    def test_clear_data(self):
        storage.save_bots([Bot("x")])
        storage.save_settings({"user_name": "Sam"})
        storage.save_chat(self.make_chat())
        storage.clear_data(bots=True, chats=True, settings=False)
        self.assertEqual(storage.load_bots(), [])
        self.assertEqual(storage.load_chat_dicts(), [])
        self.assertEqual(storage.load_settings()["user_name"], "Sam")
        storage.clear_data(bots=False, chats=False, settings=True)
        self.assertEqual(storage.load_settings()["user_name"], "You")


class ContinuationTests(unittest.TestCase):
    def test_includes_previous_and_skips_system(self):
        chat = Chat("c", [], previous_context="[Sam]: first\n[Ash]: second")
        chat.messages = [Message("Sam", "third", is_user=True), Message("", "err", is_system=True)]
        self.assertEqual(continuation_text(chat), "[Sam]: first\n[Ash]: second\n[Sam]: third")

    def test_cut_at_line_break_keeps_newest(self):
        chat = Chat("c", [])
        chat.messages = [Message("Sam", f"line {i:03d}", is_user=True) for i in range(500)]
        text = continuation_text(chat, max_chars=200)
        self.assertLessEqual(len(text), 200)
        self.assertTrue(text.endswith("[Sam]: line 499"))
        self.assertTrue(text.startswith("[Sam]: line "))   # whole lines only


if __name__ == "__main__":
    unittest.main()
