import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


APP_PATH = str(Path(__file__).resolve().parents[1] / "interface" / "streamlit.py")


class StreamlitEntryPointTests(unittest.TestCase):
    def test_app_renders_and_accepts_chat_input(self):
        result = {
            "route": "generalinfo",
            "answer": "A grounded answer [1]",
            "sources": [{
                "title": "Example source",
                "organization": "Example organization",
                "text": "Example passage",
                "url": "",
            }],
            "dashboard": {
                "generated_tips": [
                    {
                        "title": f"Tip {index}",
                        "description": "A useful description.",
                        "actionable_tip": "Take a small step.",
                    }
                    for index in range(1, 5)
                ],
            },
        }
        with (
            patch("agents.pipeline.respond", return_value=result),
            patch("retrieval.build_index.search", return_value=[]),
        ):
            at = AppTest.from_file(APP_PATH, default_timeout=180).run(timeout=180)
            self.assertFalse(at.exception)
            self.assertEqual(len(at.chat_input), 1)

            at.chat_input[0].set_value("What is mental health?").run(timeout=180)

        self.assertFalse(at.exception)
        self.assertTrue(at.session_state.history)
        self.assertIn("What is mental health?", at.session_state.history[-1]["prompt"])
        self.assertIn("A grounded answer [1]", [item.value for item in at.markdown])
        rendered = "\n".join(item.value for item in at.markdown)
        self.assertIn("Tip 3", rendered)
        self.assertNotIn("Tip 4", rendered)

    def test_crisis_input_uses_fixed_response_without_dashboard_search(self):
        result = {
            "route": "crisis",
            "answer": "Fixed crisis response",
            "sources": [],
        }
        with (
            patch("agents.pipeline.respond", return_value=result),
            patch("retrieval.build_index.search") as search,
        ):
            at = AppTest.from_file(APP_PATH, default_timeout=180).run(timeout=180)
            at.chat_input[0].set_value("I want to die").run(timeout=180)

        self.assertFalse(at.exception)
        search.assert_not_called()
        self.assertTrue(at.error)


if __name__ == "__main__":
    unittest.main()
