"""Unit tests for the LEGO rover intent-matching in brain.py — no hardware,
no Bluetooth, no mic needed; pure phrase -> (action, value) logic."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brain import ROBOT_MAP, _match_robot, _strip_prefixes


class TestRobotPhraseMatching(unittest.TestCase):
    def test_every_robot_phrase_resolves_to_its_action(self):
        for (expected_action, expected_value), phrases in ROBOT_MAP.items():
            for phrase in phrases:
                with self.subTest(phrase=phrase):
                    action, value = _match_robot(_strip_prefixes(phrase))
                    self.assertEqual(action, expected_action)
                    self.assertEqual(value, expected_value)

    def test_go_forward_and_go_back_are_not_claimed_by_robot_map(self):
        # These phrases belong to the existing browser/window navigation
        # commands (WINDOW_PHRASES, checked earlier in brain.think()) —
        # ROBOT_MAP must not shadow them.
        action, value = _match_robot("go forward")
        self.assertIsNone(action)
        action, value = _match_robot("go back")
        self.assertIsNone(action)

    def test_unrelated_phrase_does_not_match(self):
        action, value = _match_robot("what's the weather like")
        self.assertIsNone(action)
        self.assertIsNone(value)


if __name__ == "__main__":
    unittest.main()
