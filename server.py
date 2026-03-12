import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from bridge import Settings, post_to_mattermost, validate_payload


class Handler(BaseHTTPRequestHandler):
    server_version = "AmoMmBridge/1.0"

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

        for key in ("chat_id", "message", "api_key"):
            bracket_key = f"data[{key}]"
            if bracket_key in payload and payload[bracket_key] not in (None, ""):
                extracted[key] = str(payload[bracket_key])

            found = Handler._pick_first_non_empty(payload, key)
            if found is not None:
                extracted[key] = found

        return extracted

    def _parse_payload(self, raw_body: bytes, content_type: str, query: dict[str, list[str]]) -> dict[str, str]:
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

        payload = self._extract_nested_payload(payload)

        if "chat_id" not in payload and "chat_id" in query:
            payload["chat_id"] = query["chat_id"][0]
        if "message" not in payload and "message" in query:
            payload["message"] = query["message"][0]
        if "api_key" not in payload and "api_key" in query:
            payload["api_key"] = query["api_key"][0]

        return payload


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
