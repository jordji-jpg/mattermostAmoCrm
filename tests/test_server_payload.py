import unittest

from server import Handler


class ParsePayloadTests(unittest.TestCase):
    def test_json_payload(self) -> None:
        payload = Handler._parse_payload(Handler, b'{"chat_id":"c1","message":"m1"}', "application/json", {})
        self.assertEqual(payload["chat_id"], "c1")
        self.assertEqual(payload["message"], "m1")

    def test_form_payload(self) -> None:
        payload = Handler._parse_payload(
            Handler,
            b"chat_id=c1&message=hello",
            "application/x-www-form-urlencoded",
            {},
        )
        self.assertEqual(payload["chat_id"], "c1")
        self.assertEqual(payload["message"], "hello")

    def test_query_fallback(self) -> None:
        payload = Handler._parse_payload(Handler, b"", "text/plain", {"chat_id": ["cq"], "message": ["mq"]})
        self.assertEqual(payload["chat_id"], "cq")
        self.assertEqual(payload["message"], "mq")


if __name__ == "__main__":
    unittest.main()
