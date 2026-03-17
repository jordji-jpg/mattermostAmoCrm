import json
import re
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from bridge import Settings, continue_salesbot_step, post_to_mattermost, validate_payload


class Handler(BaseHTTPRequestHandler):
    server_version = "AmoMmBridge/1.0"

    @staticmethod
    def _is_resolved_value(value: str) -> bool:
        if not value:
            return False
        return "{{" not in value and "}}" not in value and "[[" not in value and "]]" not in value

    def _send_json(self, code: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, socket.timeout):
            return

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        self._send_json(404, {"status": "fail", "error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path != "/amo/salesbot/message":
            self._send_json(404, {"status": "fail", "error": "Not found"})
            return

        settings = Settings.from_env()
        query = parse_qs(parsed.query)

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            content_type = self.headers.get("Content-Type", "")
            payload = self._parse_payload(raw_body, content_type, query)

            payload["chat_id"] = self._resolve_templates(str(payload.get("chat_id", "")), payload)
            payload["message"] = self._resolve_templates(str(payload.get("message", "")), payload)

            api_key = (
                self.headers.get("X-Api-Key", "")
                or query.get("api_key", [""])[0]
                or str(payload.get("api_key", ""))
            ).strip().strip('"\'')
            if api_key != settings.app_api_key:
                self._send_json(200, {"status": "fail", "error": "Invalid API key"})
                return

            chat_id, message = validate_payload(payload)
            post_id = post_to_mattermost(settings, chat_id, message)

            bot_id = str(payload.get("bot_id", "")).strip()
            continue_id = str(payload.get("continue_id", "")).strip()
            bot_type = str(payload.get("bot_type", "salesbot")).strip() or "salesbot"
            if self._is_resolved_value(bot_id) and self._is_resolved_value(continue_id):
                continue_salesbot_step(settings, bot_id=bot_id, continue_id=continue_id, bot_type=bot_type)
        except ValueError as exc:
            self._send_json(200, {"status": "fail", "error": str(exc)})
            return
        except json.JSONDecodeError:
            self._send_json(200, {"status": "fail", "error": "Body must be valid JSON"})
            return
        except Exception as exc:  # noqa: BLE001
            self._send_json(200, {"status": "fail", "error": f"Mattermost delivery failed: {exc}"})
            return

        self._send_json(200, {"status": "success", "post_id": post_id})

    @staticmethod
    def _pick_first_non_empty(obj: object, key: str) -> str | None:
        if isinstance(obj, dict):
            if key in obj and obj[key] not in (None, ""):
                return str(obj[key])
            for value in obj.values():
                found = Handler._pick_first_non_empty(value, key)
                if found is not None:
                    return found
        elif isinstance(obj, list):
            for item in obj:
                found = Handler._pick_first_non_empty(item, key)
                if found is not None:
                    return found
        elif isinstance(obj, str):
            raw = obj.strip()
            if raw.startswith("{") or raw.startswith("["):
                try:
                    nested = json.loads(raw)
                except json.JSONDecodeError:
                    return None
                return Handler._pick_first_non_empty(nested, key)
        return None

    @staticmethod
    def _extract_nested_payload(payload: dict) -> dict[str, str]:
        extracted: dict[str, str] = {}

        for key in ("chat_id", "message", "api_key", "bot_id", "continue_id", "bot_type"):
            bracket_key = f"data[{key}]"
            if bracket_key in payload and payload[bracket_key] not in (None, ""):
                extracted[key] = str(payload[bracket_key])

            found = Handler._pick_first_non_empty(payload, key)
            if found is not None:
                extracted[key] = found

        return extracted

    @staticmethod
    def _resolve_templates(value: str, payload: dict[str, object]) -> str:
        if not value:
            return value

        def _lookup_token(token: str) -> str | None:
            token = token.strip()
            candidates = [token]
            token_cf_dot = re.match(r"^(lead|contact)\.cf\.(\d+)$", token)
            token_cf_us = re.match(r"^(lead|contact)\.cf_(\d+)$", token)
            if token_cf_dot:
                entity, field_id = token_cf_dot.groups()
                candidates.extend([f"{entity}.cf_{field_id}", field_id])
            elif token_cf_us:
                entity, field_id = token_cf_us.groups()
                candidates.extend([f"{entity}.cf.{field_id}", field_id])

            for candidate in candidates:
                found = Handler._pick_first_non_empty(payload, candidate)
                if found is not None:
                    return found
            return None

        def _replace_match(match: re.Match[str]) -> str:
            token_value = _lookup_token(match.group(1))
            return token_value if token_value is not None else match.group(0)

        value = re.sub(r"\{\{\s*([^{}]+?)\s*\}\}", _replace_match, value)
        value = re.sub(r"\[\[\s*([^\[\]]+?)\s*\]\]", _replace_match, value)
        return value

    def _parse_payload(self, raw_body: bytes, content_type: str, query: dict[str, list[str]]) -> dict[str, object]:
        body_text = raw_body.decode("utf-8") if raw_body else ""

        if "application/json" in content_type:
            payload = json.loads(body_text) if body_text else {}
        elif "application/x-www-form-urlencoded" in content_type:
            form_data = parse_qs(body_text) if body_text else {}
            payload = {k: v[0] for k, v in form_data.items() if v}
        else:
            payload = {}
            if body_text.strip().startswith(("{", "[")):
                try:
                    payload = json.loads(body_text)
                except json.JSONDecodeError:
                    payload = {}
            elif "=" in body_text:
                form_data = parse_qs(body_text)
                payload = {k: v[0] for k, v in form_data.items() if v}

        if not isinstance(payload, dict):
            payload = {"data": payload}

        extracted = self._extract_nested_payload(payload)
        payload = {**payload, **extracted}

        if "chat_id" not in payload and "chat_id" in query:
            payload["chat_id"] = query["chat_id"][0]
        if "message" not in payload and "message" in query:
            payload["message"] = query["message"][0]
        if "api_key" not in payload and "api_key" in query:
            payload["api_key"] = query["api_key"][0]
        if "bot_id" not in payload and "bot_id" in query:
            payload["bot_id"] = query["bot_id"][0]
        if "continue_id" not in payload and "continue_id" in query:
            payload["continue_id"] = query["continue_id"][0]
        if "bot_type" not in payload and "bot_type" in query:
            payload["bot_type"] = query["bot_type"][0]

        return payload


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
