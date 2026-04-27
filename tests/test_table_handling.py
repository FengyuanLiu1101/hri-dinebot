from __future__ import annotations

import unittest

from agent_a.simple_agent import SimpleAgent
from ui.floor_map import render_floor_map_html
from ui.robot_animation import compute_state, target_table_from_text


class TableHandlingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agent = SimpleAgent()

    def _agent_response(self, query: str) -> str:
        intent = self.agent.classify_intent(query)
        context = self.agent.retrieve(query, k=3)
        return self.agent.generate_response(query, intent, context)

    def test_table_parser_does_not_truncate_three_digit_tables(self) -> None:
        self.assertEqual(target_table_from_text("deliver to table 7"), 7)
        self.assertEqual(target_table_from_text("deliver to table 20"), 20)
        self.assertIsNone(target_table_from_text("deliver to table 100"))
        self.assertIsNone(target_table_from_text("deliver to table 21"))

    def test_agent_refuses_terrace_tables(self) -> None:
        response = self._agent_response("please deliver dessert to table 12")
        self.assertIn("outdoor terrace", response)
        self.assertIn("human staff", response)

    def test_agent_refuses_unknown_tables_without_substring_match(self) -> None:
        response = self._agent_response("please deliver dessert to table 112")
        self.assertIn("cannot deliver to table 112", response)
        self.assertNotIn("outdoor terrace", response)

    def test_compute_state_ignores_restricted_or_invalid_table_targets(self) -> None:
        self.assertEqual(
            compute_state("IDLE", "please deliver to table 7", "", 100),
            "DELIVERING",
        )
        self.assertEqual(
            compute_state("IDLE", "please deliver to table 12", "", 100),
            "IDLE",
        )
        self.assertEqual(
            compute_state("IDLE", "please deliver to table 100", "", 100),
            "IDLE",
        )

    def test_floor_map_tolerates_invalid_targets(self) -> None:
        html = render_floor_map_html("IDLE", 100)
        self.assertIn("Idle at dock", html)
        self.assertIn("const animate = false", html)


if __name__ == "__main__":
    unittest.main()
