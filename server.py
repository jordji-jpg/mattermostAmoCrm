import json
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
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802
        path = urlsplit(self.path).path
        if path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        self._send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path != "/amo/salesbot/message":
            self._send_json(404, {"error": "Not found"})
            return

        settings = Settings.from_env()
        query = parse_qs(parsed.query)
        api_key = self.headers.get("X-Api-Key", "") or query.get("api_key", [""])[0]
        if api_key != settings.app_api_key:
            self._send_json(401, {"error": "Invalid API key"})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            raw_body = self.rfile.read(content_length)
            content_type = self.headers.get("Content-Type", "")
            payload = self._parse_payload(raw_body, content_type, query)
            chat_id, message = validate_payload(payload)
            post_id = post_to_mattermost(settings, chat_id, message)
        except ValueError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except json.JSONDecodeError:
            self._send_json(400, {"error": "Body must be valid JSON"})
            return
        except Exception as exc:  # noqa: BLE001
            self._send_json(502, {"error": f"Mattermost delivery failed: {exc}"})
            return

        self._send_json(200, {"status": "ok", "post_id": post_id})

    def _parse_payload(self, raw_body: bytes, content_type: str, query: dict[str, list[str]]) -> dict[str, str]:
        if "application/json" in content_type:
            payload = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        elif "application/x-www-form-urlencoded" in content_type:
            form_data = parse_qs(raw_body.decode("utf-8")) if raw_body else {}
            payload = {k: v[0] for k, v in form_data.items() if v}
        else:
            payload = {}

        if "chat_id" not in payload and "chat_id" in query:
            payload["chat_id"] = query["chat_id"][0]
        if "message" not in payload and "message" in query:
            payload["message"] = query["message"][0]

        return payload


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", 8080), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
