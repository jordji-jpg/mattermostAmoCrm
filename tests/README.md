# amoCRM -> Mattermost Salesbot Bridge

Простой и надежный HTTP-сервис для отправки уведомлений из сделки amoCRM в конкретный чат/канал Mattermost.

## Как это работает
1. В сделке amoCRM хранится поле `MM_CHANNEL_ID` с `channel_id` Mattermost.
2. Salesbot формирует текст сообщения (с подстановкой полей сделки).
3. Salesbot делает HTTP POST в этот сервис.
4. Сервис отправляет сообщение в Mattermost через `POST /api/v4/posts` с Bot Token.

## Переменные окружения
Скопируйте `.env.example` и заполните:

- `APP_API_KEY` — ключ для защиты входящего endpoint.
- `MATTERMOST_BASE_URL` — например `https://mm.company.ru`.
- `MATTERMOST_BOT_TOKEN` — токен бота Mattermost.
- `REQUEST_TIMEOUT_SECONDS` — таймаут запроса (по умолчанию 5).
- `RETRY_ATTEMPTS` — число попыток (по умолчанию 3).

## Запуск
```bash
export APP_API_KEY='super-secret'
export MATTERMOST_BASE_URL='https://mm.company.ru'
export MATTERMOST_BOT_TOKEN='token'
python server.py
```

Сервис слушает `0.0.0.0:8080`.

## Настройка Salesbot (amoCRM)
HTTP-запрос в salesbot:

- Method: `POST`
- URL: `https://<your-host>/amo/salesbot/message`
- Header: `X-Api-Key: <APP_API_KEY>`
- JSON Body:

```json
{
  "chat_id": "{{lead.cf.MM_CHANNEL_ID}}",
  "message": "Сделка: {{lead.name}}\nСумма: {{lead.price}}\nОтветственный: {{lead.responsible_user.name}}"
}
```

> `message` полностью редактируется в Salesbot и может содержать переменные полей сделки amoCRM.

## Endpoint'ы
- `GET /health` → `{"status":"ok"}`
- `POST /amo/salesbot/message` → `{"status":"ok","post_id":"..."}`

## Почему решение надежное
- Проверка API-ключа.
- Валидация входного JSON и обязательных полей.
- Retry с небольшим backoff при сетевых ошибках Mattermost.
- Явные коды ошибок (`400/401/502`).
