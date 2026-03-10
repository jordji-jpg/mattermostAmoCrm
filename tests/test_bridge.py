import unittest

from bridge import validate_payload


class ValidatePayloadTests(unittest.TestCase):
    def test_valid_payload(self) -> None:
        chat_id, message = validate_payload({"chat_id": " ch1 ", "message": " hello "})
        self.assertEqual(chat_id, "ch1")
        self.assertEqual(message, "hello")

    def test_invalid_payload(self) -> None:
        with self.assertRaises(ValueError):
            validate_payload({"chat_id": "", "message": "ok"})


if __name__ == "__main__":
    unittest.main()
