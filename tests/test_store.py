"""Check that an update replaces a fact and deleting a chat removes it."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hamc.chatgpt import ChatGPTClient
from hamc.orchestrator import Orchestrator
from hamc.store import Store

GUEST = "test-guest"


class HamcTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "test.db")
        self.hamc = Orchestrator(self.store, ChatGPTClient(api_key=""))

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def _chat(self):
        return self.store.create_chat(guest_id=GUEST)

    def _send(self, chat_id, text):
        return self.hamc.send(chat_id, text, guest_id=GUEST)

    def _facts(self):
        return self.store.active_facts(guest_id=GUEST)

    def test_update_replaces_campus(self):
        chat = self._chat()
        self._send(chat["id"], "I study at Campus North.")
        self._send(chat["id"], "I transferred to Campus South.")
        campuses = [f for f in self._facts() if f["key"] == "campus"]
        self.assertEqual(len(campuses), 1)
        self.assertEqual(campuses[0]["value"], "Campus South")

    def test_delete_chat_removes_fact(self):
        chat = self._chat()
        self._send(chat["id"], "Remember the temporary research ID is BLUE-88.")
        self.assertTrue(any(f["value"] == "BLUE-88" for f in self._facts()))
        self.store.delete_chat(chat["id"])
        self.assertFalse(any(f["value"] == "BLUE-88" for f in self._facts()))

    def test_delete_fact_then_ask_same_chat_does_not_recall(self):
        chat = self._chat()
        self._send(chat["id"], "The project codeword is ORANGE-17.")
        asked = self._send(chat["id"], "What is the project codeword?")
        self.assertIn("ORANGE-17", asked["message"]["content"])
        fact = next(f for f in self._facts() if f["value"] == "ORANGE-17")
        self.store.delete_fact(fact["id"])
        again = self._send(chat["id"], "What is the project codeword?")
        self.assertFalse(again["used_facts"])
        self.assertNotIn("ORANGE-17", again["message"]["content"])
        self.assertIn("do not have", again["message"]["content"].lower())

    def test_name_is_saved_and_recalled(self):
        chat = self._chat()
        self._send(chat["id"], "hi i am Natus")
        facts = [f for f in self._facts() if f["key"] == "name"]
        self.assertEqual(facts[0]["value"], "Natus")
        later = self._chat()
        result = self._send(later["id"], "what is my name?")
        self.assertIn("Natus", result["message"]["content"])

    def test_school_and_location_save_and_update(self):
        chat = self._chat()
        self._send(chat["id"], "I study at kyungdong university")
        self._send(chat["id"], "I live in south korea")
        facts = {f["key"]: f["value"] for f in self._facts()}
        self.assertEqual(facts["school"].lower(), "kyungdong university")
        self.assertEqual(facts["location"].lower(), "south korea")
        self._send(chat["id"], "I study at Yonsei University")
        self._send(chat["id"], "I live in Seoul")
        facts = {f["key"]: f["value"] for f in self._facts()}
        self.assertEqual(len([k for k in facts if k == "school"]), 1)
        self.assertIn("Yonsei", facts["school"])
        self.assertEqual(facts["location"], "Seoul")

    def test_like_and_now_live_update(self):
        chat = self._chat()
        self._send(chat["id"], "I live in south korea")
        self._send(chat["id"], "I like football")
        self._send(chat["id"], "now I live in Seoul")
        self._send(chat["id"], "I like basketball")
        facts = {f["key"]: f["value"] for f in self._facts()}
        self.assertEqual(facts["location"], "Seoul")
        self.assertEqual(facts["like"].lower(), "basketball")

    def test_codeword_is_retrieved(self):
        chat = self._chat()
        self._send(chat["id"], "The project codeword is ORANGE-17.")
        later = self._chat()
        result = self._send(later["id"], "What is the project codeword?")
        self.assertTrue(any(f["value"] == "ORANGE-17" for f in result["used_facts"]))
        self.assertIn("ORANGE-17", result["message"]["content"])

    def test_users_do_not_share_facts(self):
        a = self.store.create_chat(guest_id="guest-a")
        b = self.store.create_chat(guest_id="guest-b")
        self.hamc.send(a["id"], "The project codeword is ORANGE-17.", guest_id="guest-a")
        self.hamc.send(b["id"], "The project codeword is BLUE-99.", guest_id="guest-b")
        self.assertEqual(
            [f["value"] for f in self.store.active_facts(guest_id="guest-a") if f["key"] == "codeword"],
            ["ORANGE-17"],
        )
        self.assertEqual(
            [f["value"] for f in self.store.active_facts(guest_id="guest-b") if f["key"] == "codeword"],
            ["BLUE-99"],
        )


if __name__ == "__main__":
    unittest.main()
