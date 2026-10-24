"""Storage clarification preserves user choices and delegates implementation wiring."""

from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills/vibelens/scripts"))
from bo_observer.data.guidance import storage_questions


class GuidanceTests(unittest.TestCase):
    def test_no_storage_requirement_adds_no_question(self):
        self.assertEqual(storage_questions(), {"user": [], "coding": []})

    def test_required_choice_is_one_question_and_blocks_wiring(self):
        result = storage_questions(required=True)
        self.assertEqual(len(result["user"]), 1)
        self.assertEqual(result["coding"][0]["depends_on"], [result["user"][0]["id"]])
        self.assertEqual(
            {o["id"] for o in result["user"][0]["options"]},
            {"sqlite", "postgresql", "mongodb", "redis", "neo4j"},
        )

    def test_confirmed_choice_reused_without_recommending_new_business(self):
        config = {
            "stores": [
                {
                    "id": "images",
                    "engine": "mongodb",
                    "selection": {
                        "source": "user",
                        "answer": "Keep our existing MongoDB",
                        "locator": "dialogue:turn-2",
                    },
                }
            ]
        }
        before = deepcopy(config)
        result = storage_questions(config)
        self.assertEqual(result["user"], [])
        self.assertEqual(result["coding"][0]["depends_on"], [])
        self.assertEqual(config, before)
        self.assertTrue(any("actual runtime cases" in t for t in result["coding"][0]["tasks"]))

    def test_silence_or_agent_guess_is_not_a_choice(self):
        for selection in (
            {},
            {"source": "agent", "answer": "SQLite", "locator": "guess"},
            {"source": "user", "answer": " ", "locator": "dialogue"},
        ):
            self.assertEqual(
                len(storage_questions({"stores": [{"id": "app", "selection": selection}]})["user"]),
                1,
            )


if __name__ == "__main__":
    unittest.main()
