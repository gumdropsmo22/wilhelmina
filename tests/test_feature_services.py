import unittest
from unittest import mock

from services import eight_ball, fortune, rolls


class RollServiceTests(unittest.TestCase):
    def test_number_lore_special_case(self):
        self.assertIn("answer", rolls.number_lore(42).lower())

    def test_number_lore_prime(self):
        self.assertIn("prime", rolls.number_lore(11).lower())

    def test_roll_die_bounds(self):
        with mock.patch("services.rolls.random.randint", return_value=4) as randint:
            self.assertEqual(rolls.roll_die(6), 4)
            randint.assert_called_once_with(1, 6)

    def test_roll_die_rejects_invalid_sides(self):
        with self.assertRaises(ValueError):
            rolls.roll_die(1)


class EightBallServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_answer_uses_static_fallback_when_ai_empty(self):
        with mock.patch("services.eight_ball.generate_text_async", return_value=""):
            with mock.patch("services.eight_ball.random.choice", return_value="fallback answer"):
                answer = await eight_ball.generate_answer("yes")

        self.assertEqual(answer, "fallback answer")

    def test_format_question(self):
        self.assertEqual(eight_ball.format_question("Will it work?"), '"Will it work?"')


class FortuneServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_generate_fortune_uses_ai_when_available(self):
        with mock.patch("services.fortune.render_persona_text", return_value="A crisp omen."):
            self.assertEqual(await fortune.generate_fortune(), "A crisp omen.")

    async def test_generate_fortune_uses_fallback_when_ai_empty(self):
        with mock.patch("services.fortune.render_persona_text", return_value=""):
            with mock.patch("services.fortune.random.choice", return_value="fallback fortune"):
                self.assertEqual(await fortune.generate_fortune(), "fallback fortune")


if __name__ == "__main__":
    unittest.main()
