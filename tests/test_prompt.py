import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Bot, Message  # noqa: E402
from app.prompt import build_prompt, parse_reply, INSTRUCT_PRESETS  # noqa: E402

NAMES = ["Ashley", "Victor", "Mara"]


class BuildPromptTests(unittest.TestCase):
    def setUp(self):
        self.bots = [Bot(n, context=f"{n} personality") for n in NAMES]

    def test_layout(self):
        msgs = [Message("Sam", "hi all", is_user=True), Message("Ashley", "hey!")]
        p = build_prompt(self.bots, "Sam", msgs)
        self.assertTrue(p.startswith("### Characters"))
        self.assertIn("[Victor]\nVictor personality", p)
        self.assertIn("never Sam's", p)
        self.assertNotIn("{{user_name}}", p)
        self.assertNotIn("### Example", p)
        self.assertTrue(p.endswith("[Sam]: hi all\n[Ashley]: hey!\n"))
        self.assertLess(p.index("### Instructions"), p.index("### Chat"))

    def test_instruct_wrapping(self):
        p = build_prompt(self.bots, "Sam", [Message("Sam", "yo", is_user=True)],
                         instruct=INSTRUCT_PRESETS["Mistral"])
        self.assertTrue(p.startswith("[INST] ### Characters"))
        self.assertTrue(p.endswith("[Sam]: yo [/INST]\n"))

    def test_history_trimmed_oldest_first(self):
        msgs = [Message("Sam", f"message number {i}", is_user=True) for i in range(500)]
        p = build_prompt(self.bots, "Sam", msgs, max_chars=3000)
        self.assertLessEqual(len(p), 3000)
        self.assertIn("message number 499", p)
        self.assertNotIn("message number 0\n", p)

    def test_default_turn_rule(self):
        p = build_prompt(self.bots, "Sam", [])
        self.assertIn("Write 1 to 3 short replies", p)
        self.assertNotIn("All bots must respond", p)
        self.assertNotIn("### Chat Context", p)

    def test_complete_response(self):
        p = build_prompt(self.bots, "Sam", [], complete_response=True)
        self.assertIn("- All bots must respond within the output.", p)
        self.assertIn("talk to each other across several lines", p)
        self.assertIn("not just answering Sam.", p)
        self.assertNotIn("1 to 3", p)

    def test_chat_context(self):
        p = build_prompt(self.bots, "Sam", [], chat_context="  They are at a beach party.  ")
        self.assertIn("### Chat Context\n\nThey are at a beach party.\n", p)
        self.assertLess(p.index("Mara personality"), p.index("### Chat Context"))
        self.assertLess(p.index("### Chat Context"), p.index("### Instructions"))
        self.assertNotIn("### Chat Context", build_prompt(self.bots, "Sam", [], chat_context="   "))

    def test_bot_notes(self):
        victor = self.bots[1]
        p = build_prompt(self.bots, "Sam", [], bot_notes={victor.id: "{{user_name}}'s overprotective mom."})
        self.assertIn("[Victor]\nVictor personality\nIn this chat, Victor's role: Sam's overprotective mom.\n", p)
        self.assertEqual(p.count("In this chat,"), 1)
        self.assertIn("role in this chat comes first", p)

    def test_no_role_rule_without_notes(self):
        p = build_prompt(self.bots, "Sam", [], bot_notes={self.bots[0].id: "   "})
        self.assertNotIn("In this chat,", p)
        self.assertNotIn("role in this chat comes first", p)

    def test_previous_context_present(self):
        p = build_prompt(self.bots, "Sam", [], previous_context="[Sam]: we met yesterday")
        self.assertIn("### Earlier conversation (previous session)\n\n[Sam]: we met yesterday\n", p)

    def test_previous_context_position(self):
        p = build_prompt(self.bots, "Sam", [], chat_context="beach",
                         previous_context="[Sam]: we met yesterday")
        self.assertLess(p.index("### Chat Context"), p.index("### Earlier conversation"))
        self.assertLess(p.index("### Earlier conversation"), p.index("### Instructions"))

    def test_previous_context_absent_when_empty(self):
        self.assertNotIn("### Earlier conversation", build_prompt(self.bots, "Sam", [], previous_context="  "))

    def test_system_messages_skipped(self):
        msgs = [Message("", "error!", is_system=True), Message("Sam", "hi", is_user=True)]
        self.assertNotIn("error!", build_prompt(self.bots, "Sam", msgs))


class ParseReplyTests(unittest.TestCase):
    def parse(self, text, names=NAMES):
        return [(p.name, p.text) for p in parse_reply(text, names, "Sam")]

    def test_multi_speaker(self):
        out = self.parse("[Ashley]: Wait, really?? *gasps*\n[Victor]: Right? dude.\n[Mara]: nice.")
        self.assertEqual(out, [("Ashley", "Wait, really?? *gasps*"),
                               ("Victor", "Right? dude."), ("Mara", "nice.")])

    def test_case_insensitive_and_spacing(self):
        self.assertEqual(self.parse("  [ashley] : hi"), [("Ashley", "hi")])

    def test_continuation_lines(self):
        out = self.parse("[Victor]: first\nsecond line\n\n[Mara]: ok")
        self.assertEqual(out, [("Victor", "first\nsecond line"), ("Mara", "ok")])

    def test_stops_at_user(self):
        out = self.parse("[Ashley]: hi\n[Sam]: I say stuff\n[Victor]: later")
        self.assertEqual(out, [("Ashley", "hi")])

    def test_stops_at_unknown_speaker(self):
        out = self.parse("[Ashley]: hi\n[Narrator]: Meanwhile...\n[Victor]: x")
        self.assertEqual(out, [("Ashley", "hi")])

    def test_midline_tag_with_action_prefix(self):
        out = self.parse("[Victor]: road trips!\n*Mara types slowly* [Mara]: good for u")
        self.assertEqual(out, [("Victor", "road trips!"), ("Mara", "*Mara types slowly* good for u")])

    def test_midline_tag_after_dialogue(self):
        out = self.parse("[Victor]: nice one [Mara]: whatever")
        self.assertEqual(out, [("Victor", "nice one"), ("Mara", "whatever")])

    def test_empty_dropped(self):
        self.assertEqual(self.parse("[Ashley]:\n[Victor]: yo"), [("Victor", "yo")])

    def test_single_bot_fallback(self):
        self.assertEqual(self.parse("Hello there!", ["Ashley"]), [("Ashley", "Hello there!")])

    def test_no_fallback_for_groups(self):
        self.assertEqual(self.parse("Hello there!"), [])


if __name__ == "__main__":
    unittest.main()
