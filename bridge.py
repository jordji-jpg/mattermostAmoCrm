import json
import os
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
    if not chat_id or not message:
        raise ValueError("'chat_id' and 'message' must be non-empty strings")
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
