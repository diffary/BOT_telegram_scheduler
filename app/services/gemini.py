import asyncio
import json
import re

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

_PROMPT_TEMPLATE = """Ты — парсер задач для бота-ежедневника. Преобразуй сообщение
пользователя в СТРОГИЙ JSON. Никакого текста до или после JSON.

Контекст:
- Текущее локальное время пользователя: {now_local}
- Часовой пояс пользователя: {tz_name}

Верни JSON ровно с этими полями:
- "title": краткая суть задачи (строка, без даты/времени внутри)
- "datetime_local": "ГГГГ-ММ-ДД ЧЧ:ММ" в ЛОКАЛЬНОМ времени пользователя
- "recurrence": одно из "none" | "daily" | "weekly" | "monthly"
- "weekday": число 0-6 (понедельник=0 ... воскресенье=6) ТОЛЬКО если recurrence="weekly", иначе null

КРИТИЧЕСКИ ВАЖНО про дату/время:
- Если пользователь НЕ указал дату или время явно — НЕ УГАДЫВАЙ.
  В этом случае верни "datetime_local": null.
- Относительные указания ("завтра", "через час", "в понедельник") разрешено
  вычислять относительно текущего локального времени — это считается явным указанием.
- "каждый день" -> recurrence="daily"; "по понедельникам"/"каждую неделю" -> "weekly"
  с соответствующим weekday; "каждое N число"/"ежемесячно" -> "monthly".

Сообщение пользователя: "{text}"
"""

# Коды ошибок Gemini, при которых имеет смысл повторить запрос.
_RETRYABLE_CODES = {429, 500, 503}


class GeminiUnavailable(Exception):
    """Gemini временно недоступен (перегрузка/лимит) — после исчерпания ретраев."""


def build_prompt(text: str, tz_name: str, now_local: str) -> str:
    """Собрать строгий промпт с контекстом времени и зоны пользователя."""
    return _PROMPT_TEMPLATE.format(text=text, tz_name=tz_name, now_local=now_local)


def extract_json(response_text: str) -> dict:
    """Извлечь JSON-объект из ответа модели (в т.ч. из ```json блока)."""
    if response_text is None:
        raise ValueError("пустой ответ Gemini")
    match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if not match:
        raise ValueError("в ответе Gemini не найден JSON")
    return json.loads(match.group(0))


class GeminiService:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        max_retries: int = 2,
        retry_base_delay: float = 1.5,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay

    async def parse_text(self, text: str, tz_name: str, now_local: str) -> dict:
        """Отправить текст в Gemini и вернуть сырой dict для parser.parse().

        Временные ошибки API (429/500/503) повторяются с нарастающей паузой;
        если они не прошли — поднимается GeminiUnavailable.
        """
        prompt = build_prompt(text, tz_name, now_local)
        attempt = 0
        while True:
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    ),
                )
                return extract_json(response.text)
            except genai_errors.APIError as exc:
                code = getattr(exc, "code", None)
                if code in _RETRYABLE_CODES and attempt < self._max_retries:
                    await asyncio.sleep(self._retry_base_delay * (attempt + 1))
                    attempt += 1
                    continue
                raise GeminiUnavailable(f"{code}: {exc}") from exc
