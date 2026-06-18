import asyncio
import json
import re

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

_TIME_RULES = """Правила ВРЕМЕНИ:
- Относительные указания считай от текущего локального времени ("завтра",
  "через час", "в понедельник" — это явное указание времени/даты).
- Час БЕЗ уточнения части суток выбирай по самому вероятному смыслу:
  • 1–6 → день (прибавь 12): "в 3 часа" → 15:00, "в 5" → 17:00, "в 6" → 18:00.
  • 7–11 → утро как есть: "в 8" → 08:00, "в 10" → 10:00, "в 11" → 11:00.
  • 12 → полдень 12:00.
- Явное уточнение части суток ВАЖНЕЕ этого правила:
  • "ночи"/"утра" → утро (0–11): "в 3 ночи" → 03:00, "в 7 утра" → 07:00.
  • "дня"/"вечера" → день/вечер (1–11 +12): "в 3 дня" → 15:00, "в 8 вечера" → 20:00.
- "полночь"/"12 ночи" → 00:00.
- Явный 24-часовой формат бери как есть: "в 15:30" → 15:30, "в 20" → 20:00.

Правила ПОВТОРОВ:
- "каждый день"/"ежедневно"/"каждое утро/вечер" → recurrence="daily".
- "каждый понедельник"/"по понедельникам"/"каждую неделю в пн" →
  recurrence="weekly", weekday=0 (вт=1 … вс=6).
- "каждое N число"/"ежемесячно"/"раз в месяц" → recurrence="monthly".
- Иначе recurrence="none". Для повторов datetime_local — ближайшая дата старта + время."""

_FIELDS = """Поля JSON:
- "title": краткая суть задачи (без даты/времени внутри)
- "datetime_local": "ГГГГ-ММ-ДД ЧЧ:ММ" в локальном времени пользователя
- "recurrence": одно из "none" | "daily" | "weekly" | "monthly"
- "weekday": 0-6 (пн=0 … вс=6) ТОЛЬКО если recurrence="weekly", иначе null"""

_PROMPT_TEMPLATE = """Ты — парсер задач для бота-ежедневника. Преобразуй сообщение
пользователя в СТРОГИЙ JSON. Никакого текста до или после JSON.

Контекст:
- Текущее локальное время пользователя: {now_local}
- Часовой пояс пользователя: {tz_name}

{fields}

{rules}

Если дата/время вообще не указаны — НЕ УГАДЫВАЙ, верни "datetime_local": null.

Сообщение пользователя: "{text}"
"""

_AMEND_TEMPLATE = """Ты редактируешь СУЩЕСТВУЮЩУЮ задачу ежедневника. Верни
ОБНОВЛЁННУЮ задачу СТРОГИМ JSON (те же поля), без текста вокруг.

Контекст:
- Текущее локальное время пользователя: {now_local}
- Часовой пояс пользователя: {tz_name}

Исходная задача:
- title: {cur_title}
- datetime_local: {cur_dt}
- recurrence: {cur_rec}
- weekday: {cur_wd}

Инструкция пользователя по изменению: "{instruction}"

Правила редактирования:
- Сохрани поля исходной задачи; меняй только то, что затронуто инструкцией.
- Если инструкция ДОБАВЛЯЕТ действие ("и ещё помыть собаку") — дополни title,
  время/дату/повтор НЕ трогай.
- Если меняет время/дату/повтор — обнови их по правилам ниже.
- НЕ обнуляй datetime_local, если инструкция не меняет время.

{fields}

{rules}
"""


def build_prompt(text: str, tz_name: str, now_local: str) -> str:
    """Строгий промпт для создания задачи из свободного текста."""
    return _PROMPT_TEMPLATE.format(
        text=text, tz_name=tz_name, now_local=now_local,
        fields=_FIELDS, rules=_TIME_RULES,
    )


def build_amend_prompt(
    instruction: str, current: dict, tz_name: str, now_local: str
) -> str:
    """Промпт для редактирования: исходная задача как контекст + инструкция."""
    return _AMEND_TEMPLATE.format(
        instruction=instruction, tz_name=tz_name, now_local=now_local,
        cur_title=current.get("title"),
        cur_dt=current.get("datetime_local"),
        cur_rec=current.get("recurrence"),
        cur_wd=current.get("weekday"),
        fields=_FIELDS, rules=_TIME_RULES,
    )


def extract_json(response_text: str) -> dict:
    """Извлечь JSON-объект из ответа модели (в т.ч. из ```json блока)."""
    if response_text is None:
        raise ValueError("пустой ответ Gemini")
    match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if not match:
        raise ValueError("в ответе Gemini не найден JSON")
    return json.loads(match.group(0))


_RETRYABLE_CODES = {429, 500, 503}


class GeminiUnavailable(Exception):
    """Gemini временно недоступен (перегрузка/лимит) — после исчерпания ретраев."""


class GeminiService:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.1-flash-lite",
        max_retries: int = 2,
        retry_base_delay: float = 1.5,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._max_retries = max_retries
        self._retry_base_delay = retry_base_delay

    async def _generate(self, prompt: str) -> dict:
        """Один запрос к Gemini с ретраями на временных ошибках (429/500/503)."""
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

    async def parse_text(self, text: str, tz_name: str, now_local: str) -> dict:
        """Свободный текст → сырой dict для parser.parse()."""
        return await self._generate(build_prompt(text, tz_name, now_local))

    async def amend_text(
        self, instruction: str, current: dict, tz_name: str, now_local: str
    ) -> dict:
        """Редактирование: исходная задача + инструкция → обновлённый dict."""
        return await self._generate(
            build_amend_prompt(instruction, current, tz_name, now_local)
        )
