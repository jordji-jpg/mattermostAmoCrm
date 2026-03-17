import unittest

from bridge import validate_payload


class ValidatePayloadTests(unittest.TestCase):
    def test_valid_payload(self) -> None:
        chat_id, message = validate_payload({"chat_id": " uryu3hdiy7rc3khmzixdgo5pxr ", "message": " hello "})
        self.assertEqual(chat_id, "uryu3hdiy7rc3khmzixdgo5pxr")
        self.assertEqual(message, "hello")

    def test_invalid_payload(self) -> None:
        with self.assertRaises(ValueError):
            validate_payload({"chat_id": "", "message": "ok"})

    def test_rejects_unresolved_chat_template(self) -> None:
        with self.assertRaisesRegex(ValueError, "unresolved amoCRM template"):
            validate_payload({"chat_id": "{{1139111}}", "message": "ok"})

    def test_rejects_non_mattermost_chat_id(self) -> None:
        with self.assertRaisesRegex(ValueError, "must look like a Mattermost channel ID"):
            validate_payload({"chat_id": "Сделка: 123", "message": "ok"})

    def test_accepts_mattermost_id_with_human_prefix(self) -> None:
        chat_id, _ = validate_payload(
            {"chat_id": "Сделка: uryu3hdiy7rc3khmzixdgo5pxr", "message": "ok"}
        )
        self.assertEqual(chat_id, "uryu3hdiy7rc3khmzixdgo5pxr")

    def test_converts_escaped_newlines_in_message(self) -> None:
        _, message = validate_payload(
            {"chat_id": "uryu3hdiy7rc3khmzixdgo5pxr", "message": "Line1\\n\\nLine2"}
        )
        self.assertEqual(message, "Line1\n\nLine2")


if __name__ == "__main__":
    unittest.main()
