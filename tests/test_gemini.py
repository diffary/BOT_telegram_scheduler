import pytest
from google.genai import errors as genai_errors

from app.services.gemini import (
    GeminiService,
    GeminiUnavailable,
    build_prompt,
    extract_json,
)


# --- чистые функции ---

def test_extract_json_plain():
    text = '{"title": "x", "datetime_local": "2026-06-17 15:00", "recurrence": "none"}'
    assert extract_json(text)["title"] == "x"


def test_extract_json_from_fenced_block():
    text = '```json\n{"title": "врач", "datetime_local": null, "recurrence": "none"}\n```'
    assert extract_json(text)["title"] == "врач"


def test_extract_json_no_json_raises():
    with pytest.raises(ValueError):
        extract_json("совсем не json")


def test_build_prompt_contains_context():
    p = build_prompt("завтра в 15", tz_name="Europe/Moscow", now_local="2026-06-17 13:00")
    assert "Europe/Moscow" in p
    assert "2026-06-17 13:00" in p
    assert "завтра в 15" in p


# --- ретраи на временных ошибках ---

class _FakeAPIError(genai_errors.APIError):
    """Мини-замена APIError с нужным кодом (минуя реальный __init__)."""

    def __init__(self, code):
        self.code = code
        self.message = f"fake {code}"
        self.status = "FAKE"


class _Resp:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, behaviors):
        self.behaviors = behaviors
        self.calls = 0

    async def generate_content(self, **kwargs):
        behavior = self.behaviors[self.calls]
        self.calls += 1
        if isinstance(behavior, Exception):
            raise behavior
        return _Resp(behavior)


class _FakeAio:
    def __init__(self, models):
        self.models = models


class _FakeClient:
    def __init__(self, models):
        self.aio = _FakeAio(models)


def _service_with(behaviors, **kwargs):
    svc = GeminiService("fake-key", retry_base_delay=0, **kwargs)
    models = _FakeModels(behaviors)
    svc._client = _FakeClient(models)
    return svc, models


async def test_retries_then_succeeds():
    ok = '{"title": "врач", "datetime_local": "2026-06-17 15:00", "recurrence": "none"}'
    svc, models = _service_with([_FakeAPIError(503), ok])
    result = await svc.parse_text("завтра в 15 врач", "Europe/Moscow", "2026-06-17 13:00")
    assert result["title"] == "врач"
    assert models.calls == 2  # один ретрай после 503


async def test_gives_up_after_max_retries():
    svc, models = _service_with(
        [_FakeAPIError(503), _FakeAPIError(503), _FakeAPIError(503)]
    )
    with pytest.raises(GeminiUnavailable):
        await svc.parse_text("x", "Europe/Moscow", "2026-06-17 13:00")
    assert models.calls == 3  # max_retries=2 -> всего 3 попытки


async def test_rate_limit_429_is_retried():
    ok = '{"title": "x", "datetime_local": "2026-06-17 15:00", "recurrence": "none"}'
    svc, models = _service_with([_FakeAPIError(429), ok])
    result = await svc.parse_text("x", "Europe/Moscow", "2026-06-17 13:00")
    assert result["title"] == "x"
    assert models.calls == 2


async def test_non_retryable_error_raises_immediately():
    svc, models = _service_with([_FakeAPIError(400)])
    with pytest.raises(GeminiUnavailable):
        await svc.parse_text("x", "Europe/Moscow", "2026-06-17 13:00")
    assert models.calls == 1  # 400 не ретраится
