import json
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
        payload = Handler._parse_payload(
            Handler,
            b"",
            "text/plain",
            {"chat_id": ["cq"], "message": ["mq"], "bot_id": ["42"], "continue_id": ["777"]},
        )
        self.assertEqual(payload["chat_id"], "cq")
        self.assertEqual(payload["message"], "mq")
        self.assertEqual(payload["bot_id"], "42")
        self.assertEqual(payload["continue_id"], "777")

    def test_nested_data_payload(self) -> None:
        payload = Handler._parse_payload(
            Handler,
            b'{"data":{"chat_id":"c2","message":"m2","api_key":"k2"}}',
            "application/json",
            {},
        )
        self.assertEqual(payload["chat_id"], "c2")
        self.assertEqual(payload["message"], "m2")
        self.assertEqual(payload["api_key"], "k2")

    def test_form_data_brackets_payload(self) -> None:
        payload = Handler._parse_payload(
            Handler,
            b"data%5Bchat_id%5D=c3&data%5Bmessage%5D=m3&data%5Bapi_key%5D=k3",
            "application/x-www-form-urlencoded",
            {},
        )
        self.assertEqual(payload["chat_id"], "c3")
        self.assertEqual(payload["message"], "m3")
        self.assertEqual(payload["api_key"], "k3")

    def test_plain_content_type_with_form_body(self) -> None:
        payload = Handler._parse_payload(
            Handler,
            b"chat_id=c4&message=m4&api_key=k4",
            "text/plain",
            {},
        )
        self.assertEqual(payload["chat_id"], "c4")
        self.assertEqual(payload["message"], "m4")
        self.assertEqual(payload["api_key"], "k4")

    def test_nested_params_json_string(self) -> None:
        nested = json.dumps({"data": {"chat_id": "c5", "message": "m5", "api_key": "k5"}})
        body = json.dumps({"params": nested}).encode("utf-8")
        payload = Handler._parse_payload(Handler, body, "application/json", {})
        self.assertEqual(payload["chat_id"], "c5")
        self.assertEqual(payload["message"], "m5")
        self.assertEqual(payload["api_key"], "k5")

    def test_payload_keeps_context_fields_for_template_resolution(self) -> None:
        payload = Handler._parse_payload(
            Handler,
            b'{"chat_id":"{{lead.cf.1139111}}","message":"{{lead.cf.1126839}}","1139111":"channel","1126839":"hello"}',
            "application/json",
            {},
        )
        self.assertEqual(payload["1139111"], "channel")
        self.assertEqual(payload["1126839"], "hello")

    def test_resolve_templates_by_field_id(self) -> None:
        payload = {
            "1139111": "uryu3hdiy7rc3khmzixdgo5pxr",
            "1126839": "Text from deal",
        }
        self.assertEqual(
            Handler._resolve_templates("{{lead.cf.1139111}}", payload),
            "uryu3hdiy7rc3khmzixdgo5pxr",
        )
        self.assertEqual(
            Handler._resolve_templates("Message: [[lead.cf_1126839]]", payload),
            "Message: Text from deal",
        )


if __name__ == "__main__":
    unittest.main()
