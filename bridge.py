import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_api_key: str
    mattermost_base_url: str
    mattermost_bot_token: str
    request_timeout_seconds: float
    retry_attempts: int

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            app_api_key=os.environ["APP_API_KEY"],
            mattermost_base_url=os.environ["MATTERMOST_BASE_URL"].rstrip("/"),
            mattermost_bot_token=os.environ["MATTERMOST_BOT_TOKEN"],
            request_timeout_seconds=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "5")),
            retry_attempts=int(os.getenv("RETRY_ATTEMPTS", "3")),
        )


def validate_payload(payload: dict) -> tuple[str, str]:
    chat_id = str(payload.get("chat_id", "")).strip()
    message = str(payload.get("message", "")).strip()
    message = message.replace("\\r\\n", "\n").replace("\\n", "\n")
    if not chat_id or not message:
        raise ValueError("'chat_id' and 'message' must be non-empty strings")

    if ":" in chat_id:
        maybe_chat_id = chat_id.split(":", 1)[1].strip()
        if re.fullmatch(r"[a-z0-9]{8,64}", maybe_chat_id):
            chat_id = maybe_chat_id

    if any(token in chat_id for token in ("{{", "}}", "[[", "]]")):
        raise ValueError("'chat_id' contains unresolved amoCRM template; provide resolved channel id value")

    if not re.fullmatch(r"[a-z0-9]{8,64}", chat_id):
        raise ValueError("'chat_id' must look like a Mattermost channel ID (lowercase letters/digits)")

    return chat_id, message


def post_to_mattermost(settings: Settings, chat_id: str, message: str) -> str:
    url = f"{settings.mattermost_base_url}/api/v4/posts"
    body = json.dumps({"channel_id": chat_id, "message": message}).encode("utf-8")

    for attempt in range(1, settings.retry_attempts + 1):
        request = urllib.request.Request(
            url,
            method="POST",
            data=body,
            headers={
                "Authorization": f"Bearer {settings.mattermost_bot_token}",
                "Content-Type": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=settings.request_timeout_seconds) as response:
                data = json.loads(response.read().decode("utf-8"))
                post_id = data.get("id", "").strip()
                if not post_id:
                    raise RuntimeError("Mattermost response has no post id")
                return post_id
        except (urllib.error.HTTPError, urllib.error.URLError, RuntimeError):
            if attempt == settings.retry_attempts:
                raise
            time.sleep(attempt * 0.5)

    raise RuntimeError("Unexpected retry flow exit")
