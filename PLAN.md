# Telegram-бот «Ежедневник» — план реализации

> **Для агентов-исполнителей:** РЕКОМЕНДУЕМЫЙ СУБ-СКИЛЛ — используйте
> superpowers:subagent-driven-development (рекомендуется) или
> superpowers:executing-plans для выполнения плана задача-за-задачей.
> Шаги размечены чекбоксами (`- [ ]`) для отслеживания.

**Goal:** Многопользовательский Telegram-бот, который парсит свободный текст в задачи
(дата/время/повторы), показывает список на день и шлёт напоминания.

**Architecture:** aiogram 3 (async polling) + SQLAlchemy async поверх SQLite (aiosqlite).
Gemini API превращает свободный текст в JSON. APScheduler запускает один «тик» раз в
минуту, который по данным БД решает, что напомнить и кому слать дайджест. Всё время
хранится в UTC, у каждого пользователя своя IANA-зона.

**Tech Stack:** Python 3.11+, aiogram 3, SQLAlchemy 2 (async) + aiosqlite,
google-genai (Gemini), APScheduler 3, pytest + pytest-asyncio, python-dotenv.

---

## Структура файлов

| Файл | Ответственность |
|------|-----------------|
| `bot.py` | Точка входа: создание `Bot`/`Dispatcher`, регистрация роутеров, старт планировщика, polling |
| `config.py` | Загрузка настроек из `.env` в frozen-dataclass `Settings` |
| `app/db/base.py` | `engine`, `async_session`, `Base`, `init_db()` |
| `app/db/models.py` | ORM-модели `User`, `Task` |
| `app/db/repo.py` | CRUD-функции (единственный слой доступа к данным) |
| `app/utils/tz.py` | Конвертация `local ↔ UTC`, валидация IANA-зоны |
| `app/services/parser.py` | Валидация/нормализация ответа Gemini → `ParsedTask` |
| `app/services/gemini.py` | Промпт + вызов Gemini, отдаёт сырой dict в `parser` |
| `app/services/occurrences.py` | Чистая логика вхождений: «созрело ли напоминание к моменту T» |
| `app/services/scheduler.py` | APScheduler tick: дёргает occurrences/repo, шлёт сообщения |
| `app/utils/formatting.py` | Рендер списков задач и сообщений |
| `app/keyboards/inline.py` | Инлайн-клавиатуры (подтверждение, действия с задачей) |
| `app/states.py` | FSM-состояния (онбординг, редактирование) |
| `app/handlers/commands.py` | `/start /help /today /list /timezone /settings /cancel` |
| `app/handlers/tasks.py` | Свободный текст → парсинг → подтверждение; колбэки edit/delete |
| `app/handlers/onboarding.py` | FSM выбора TZ и настроек |
| `tests/*` | pytest: parser, occurrences, tz, repo |

**Принципы:** DRY, YAGNI, TDD, частые коммиты. `repo` — единственная точка доступа к БД;
хендлеры не пишут SQL. Чистая логика (parser, occurrences, tz) не зависит от aiogram/БД
и покрывается юнит-тестами. Gemini в тестах мокается.

---

## Task 1: Каркас проекта, конфиг, git

**Files:**
- Create: `telegram_bot_scheduler/.gitignore`
- Create: `telegram_bot_scheduler/requirements.txt`
- Create: `telegram_bot_scheduler/.env.example`
- Create: `telegram_bot_scheduler/config.py`
- Create: `telegram_bot_scheduler/app/__init__.py` (пустой), и `__init__.py` в каждом подпакете
- Test: `telegram_bot_scheduler/tests/test_config.py`

- [ ] **Step 1: Инициализировать git и структуру**

```bash
cd telegram_bot_scheduler
git init
mkdir -p app/db app/handlers app/keyboards app/services app/utils tests
touch app/__init__.py app/db/__init__.py app/handlers/__init__.py \
      app/keyboards/__init__.py app/services/__init__.py app/utils/__init__.py \
      tests/__init__.py
```

- [ ] **Step 2: requirements.txt**

```
aiogram==3.13.1
SQLAlchemy==2.0.35
aiosqlite==0.20.0
APScheduler==3.10.4
google-genai==0.3.0
python-dotenv==1.0.1
pytest==8.3.3
pytest-asyncio==0.24.0
```

- [ ] **Step 3: .gitignore**

```
__pycache__/
*.pyc
.env
*.db
*.sqlite3
.pytest_cache/
.venv/
```

- [ ] **Step 4: .env.example**

```
BOT_TOKEN=put-your-telegram-token-here
GEMINI_API_KEY=put-your-gemini-key-here
DB_PATH=diary.db
DEFAULT_TZ=Europe/Moscow
TICK_INTERVAL_SECONDS=60
```

- [ ] **Step 5: Написать падающий тест конфига**

`tests/test_config.py`:
```python
import os
from config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "token123")
    monkeypatch.setenv("GEMINI_API_KEY", "gem123")
    monkeypatch.setenv("DB_PATH", "test.db")
    monkeypatch.setenv("DEFAULT_TZ", "Europe/Moscow")
    monkeypatch.setenv("TICK_INTERVAL_SECONDS", "30")

    s = Settings.from_env()

    assert s.bot_token == "token123"
    assert s.gemini_api_key == "gem123"
    assert s.db_path == "test.db"
    assert s.default_tz == "Europe/Moscow"
    assert s.tick_interval_seconds == 30


def test_settings_requires_bot_token(monkeypatch):
    monkeypatch.delenv("BOT_TOKEN", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "gem123")
    import pytest
    with pytest.raises(ValueError, match="BOT_TOKEN"):
        Settings.from_env()
```

- [ ] **Step 6: Запустить тест — убедиться, что падает**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (модуль `config` или `Settings` ещё нет).

- [ ] **Step 7: Реализовать config.py**

```python
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bot_token: str
    gemini_api_key: str
    db_path: str
    default_tz: str
    tick_interval_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        bot_token = os.getenv("BOT_TOKEN")
        if not bot_token:
            raise ValueError("BOT_TOKEN is required")
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required")
        return cls(
            bot_token=bot_token,
            gemini_api_key=gemini_api_key,
            db_path=os.getenv("DB_PATH", "diary.db"),
            default_tz=os.getenv("DEFAULT_TZ", "Europe/Moscow"),
            tick_interval_seconds=int(os.getenv("TICK_INTERVAL_SECONDS", "60")),
        )
```

- [ ] **Step 8: Запустить тест — убедиться, что проходит**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 9: Добавить pytest.ini для async-режима**

`pytest.ini`:
```ini
[pytest]
asyncio_mode = auto
```

- [ ] **Step 10: Commit**

```bash
git add .
git commit -m "chore: project scaffold, deps, config with tests"
```

---

## Task 2: Слой БД — модели, engine, init

**Files:**
- Create: `app/db/base.py`
- Create: `app/db/models.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Написать падающий тест моделей**

`tests/test_db.py`:
```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.db.base import Base
from app.db.models import User, Task


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_create_user_and_task(session):
    user = User(telegram_id=42, username="bob", timezone="Europe/Moscow")
    session.add(user)
    await session.flush()

    task = Task(user_id=user.id, title="врач", raw_text="завтра врач",
                recurrence="none")
    session.add(task)
    await session.commit()

    assert user.id is not None
    assert task.user_id == user.id
    assert user.default_lead_minutes == 15  # default applied
    assert user.digest_enabled is True
```

- [ ] **Step 2: Запустить тест — убедиться, что падает**

Run: `pytest tests/test_db.py -v`
Expected: FAIL (нет `app.db.base` / `app.db.models`).

- [ ] **Step 3: Реализовать base.py**

```python
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker


class Base(DeclarativeBase):
    pass


_engine = None
_sessionmaker = None


def init_engine(db_path: str):
    global _engine, _sessionmaker
    _engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def init_db():
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_sessionmaker():
    return _sessionmaker
```

- [ ] **Step 4: Реализовать models.py**

```python
from datetime import datetime, date
from sqlalchemy import String, Integer, Boolean, DateTime, Date, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    timezone: Mapped[str] = mapped_column(String, default="Europe/Moscow")
    digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    digest_time: Mapped[str] = mapped_column(String, default="09:00")
    default_lead_minutes: Mapped[int] = mapped_column(Integer, default=15)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    tasks: Mapped[list["Task"]] = relationship(back_populates="user",
                                               cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    raw_text: Mapped[str] = mapped_column(String)
    due_at_utc: Mapped[datetime] = mapped_column(DateTime)
    recurrence: Mapped[str] = mapped_column(String, default="none")  # none|daily|weekly|monthly
    recurrence_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_reminded_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="tasks")
```

Примечание: `due_at_utc` в тесте Step 1 не задан — добавьте в тест значение
(`due_at_utc=datetime(2026,6,17,12,0)`) или сделайте поле nullable. Рекомендуется
задать значение в тесте, поле оставить NOT NULL.

- [ ] **Step 5: Запустить тест — убедиться, что проходит**

Run: `pytest tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/db tests/test_db.py
git commit -m "feat: db models User and Task with async engine"
```

---

## Task 3: Хелперы часовых поясов

**Files:**
- Create: `app/utils/tz.py`
- Test: `tests/test_tz.py`

- [ ] **Step 1: Написать падающий тест**

`tests/test_tz.py`:
```python
from datetime import datetime
from app.utils.tz import to_utc, to_local, is_valid_tz


def test_to_utc_from_moscow():
    # 15:00 MSK (UTC+3) -> 12:00 UTC
    local = datetime(2026, 6, 17, 15, 0)
    result = to_utc(local, "Europe/Moscow")
    assert result.hour == 12
    assert result.tzinfo is None  # naive UTC for storage


def test_to_local_roundtrip():
    utc_naive = datetime(2026, 6, 17, 12, 0)
    local = to_local(utc_naive, "Europe/Moscow")
    assert local.hour == 15


def test_is_valid_tz():
    assert is_valid_tz("Europe/Moscow") is True
    assert is_valid_tz("Mars/Phobos") is False
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_tz.py -v`
Expected: FAIL.

- [ ] **Step 3: Реализовать tz.py**

```python
from datetime import datetime
from zoneinfo import ZoneInfo, available_timezones

_AVAILABLE = available_timezones()


def is_valid_tz(name: str) -> bool:
    return name in _AVAILABLE


def to_utc(local_naive: datetime, tz_name: str) -> datetime:
    """Локальное naive-время -> naive UTC (для хранения)."""
    aware = local_naive.replace(tzinfo=ZoneInfo(tz_name))
    return aware.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)


def to_local(utc_naive: datetime, tz_name: str) -> datetime:
    """naive UTC -> локальное naive-время (для отображения)."""
    aware = utc_naive.replace(tzinfo=ZoneInfo("UTC"))
    return aware.astimezone(ZoneInfo(tz_name)).replace(tzinfo=None)
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/test_tz.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/utils/tz.py tests/test_tz.py
git commit -m "feat: timezone helpers (local<->utc, validation)"
```

---

## Task 4: Парсер ответа Gemini

**Files:**
- Create: `app/services/parser.py`
- Test: `tests/test_parser.py`

Парсер принимает сырой dict (как из Gemini) + TZ пользователя + «сейчас» и возвращает
`ParsedTask` с `due_at_utc`. Чистая функция, без сети.

- [ ] **Step 1: Написать падающие тесты**

`tests/test_parser.py`:
```python
from datetime import datetime
import pytest
from app.services.parser import parse, ParsedTask, ParseError


NOW = datetime(2026, 6, 16, 10, 0)  # UTC


def test_parse_one_off():
    raw = {"title": "встреча с врачом", "datetime_local": "2026-06-17 15:00",
           "recurrence": "none"}
    result = parse(raw, tz_name="Europe/Moscow", raw_text="...", now_utc=NOW)
    assert isinstance(result, ParsedTask)
    assert result.title == "встреча с врачом"
    assert result.recurrence == "none"
    # 15:00 MSK -> 12:00 UTC
    assert result.due_at_utc == datetime(2026, 6, 17, 12, 0)


def test_parse_weekly_with_weekday():
    raw = {"title": "созвон", "datetime_local": "2026-06-17 09:00",
           "recurrence": "weekly", "weekday": 2}
    result = parse(raw, tz_name="Europe/Moscow", raw_text="...", now_utc=NOW)
    assert result.recurrence == "weekly"
    assert result.recurrence_weekday == 2


def test_parse_missing_datetime_raises():
    raw = {"title": "что-то", "recurrence": "none"}
    with pytest.raises(ParseError, match="datetime"):
        parse(raw, tz_name="Europe/Moscow", raw_text="...", now_utc=NOW)


def test_parse_missing_title_raises():
    raw = {"datetime_local": "2026-06-17 15:00", "recurrence": "none"}
    with pytest.raises(ParseError, match="title"):
        parse(raw, tz_name="Europe/Moscow", raw_text="...", now_utc=NOW)


def test_parse_invalid_recurrence_defaults_to_none():
    raw = {"title": "x", "datetime_local": "2026-06-17 15:00",
           "recurrence": "yearly"}
    result = parse(raw, tz_name="Europe/Moscow", raw_text="...", now_utc=NOW)
    assert result.recurrence == "none"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_parser.py -v`
Expected: FAIL.

- [ ] **Step 3: Реализовать parser.py**

```python
from dataclasses import dataclass
from datetime import datetime
from app.utils.tz import to_utc

VALID_RECURRENCE = {"none", "daily", "weekly", "monthly"}


class ParseError(ValueError):
    pass


@dataclass
class ParsedTask:
    title: str
    raw_text: str
    due_at_utc: datetime
    recurrence: str
    recurrence_weekday: int | None


def parse(raw: dict, tz_name: str, raw_text: str, now_utc: datetime) -> ParsedTask:
    title = (raw.get("title") or "").strip()
    if not title:
        raise ParseError("title missing")

    dt_str = raw.get("datetime_local")
    if not dt_str:
        raise ParseError("datetime missing")
    try:
        local_dt = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    except ValueError as e:
        raise ParseError(f"bad datetime format: {dt_str}") from e

    recurrence = raw.get("recurrence", "none")
    if recurrence not in VALID_RECURRENCE:
        recurrence = "none"

    weekday = raw.get("weekday")
    weekday = int(weekday) if (recurrence == "weekly" and weekday is not None) else None

    return ParsedTask(
        title=title,
        raw_text=raw_text,
        due_at_utc=to_utc(local_dt, tz_name),
        recurrence=recurrence,
        recurrence_weekday=weekday,
    )
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/test_parser.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add app/services/parser.py tests/test_parser.py
git commit -m "feat: parse Gemini output into ParsedTask"
```

---

## Task 5: Логика вхождений (что созрело к моменту T)

**Files:**
- Create: `app/services/occurrences.py`
- Test: `tests/test_occurrences.py`

Ядро планировщика — чистые функции: `occurrence_on_date()` (момент вхождения задачи в
конкретный день) и `is_reminder_due()` (пора ли напомнить к моменту `now`).

- [ ] **Step 1: Написать падающие тесты**

`tests/test_occurrences.py`:
```python
from datetime import datetime, date
from app.services.occurrences import occurrence_on_date, is_reminder_due


def make_task(due_at_utc, recurrence="none", weekday=None, lead=15, last=None):
    class T:  # лёгкий стенд вместо ORM-объекта
        pass
    t = T()
    t.due_at_utc = due_at_utc
    t.recurrence = recurrence
    t.recurrence_weekday = weekday
    t.lead_minutes = lead
    t.last_reminded_on = last
    return t


def test_one_off_occurrence_only_on_its_date():
    t = make_task(datetime(2026, 6, 17, 12, 0))
    assert occurrence_on_date(t, date(2026, 6, 17)) == datetime(2026, 6, 17, 12, 0)
    assert occurrence_on_date(t, date(2026, 6, 18)) is None


def test_daily_occurrence_every_day_same_time():
    t = make_task(datetime(2026, 6, 17, 8, 0), recurrence="daily")
    occ = occurrence_on_date(t, date(2026, 6, 20))
    assert occ == datetime(2026, 6, 20, 8, 0)


def test_weekly_occurrence_only_matching_weekday():
    # 2026-06-17 -> Wednesday (weekday=2)
    t = make_task(datetime(2026, 6, 17, 9, 0), recurrence="weekly", weekday=2)
    assert occurrence_on_date(t, date(2026, 6, 24)) == datetime(2026, 6, 24, 9, 0)  # Wed
    assert occurrence_on_date(t, date(2026, 6, 25)) is None  # Thu


def test_monthly_occurrence_same_day_of_month():
    t = make_task(datetime(2026, 6, 17, 9, 0), recurrence="monthly")
    assert occurrence_on_date(t, date(2026, 7, 17)) == datetime(2026, 7, 17, 9, 0)
    assert occurrence_on_date(t, date(2026, 7, 18)) is None


def test_reminder_due_within_lead_window():
    t = make_task(datetime(2026, 6, 17, 12, 0), lead=15)
    # now = 11:46 UTC, lead 15 -> окно открылось в 11:45
    assert is_reminder_due(t, now_utc=datetime(2026, 6, 17, 11, 46),
                           default_lead=15) is True


def test_reminder_not_due_before_window():
    t = make_task(datetime(2026, 6, 17, 12, 0), lead=15)
    assert is_reminder_due(t, now_utc=datetime(2026, 6, 17, 11, 30),
                           default_lead=15) is False


def test_reminder_not_resent_same_day():
    t = make_task(datetime(2026, 6, 17, 12, 0), lead=15,
                  last=date(2026, 6, 17))
    assert is_reminder_due(t, now_utc=datetime(2026, 6, 17, 11, 50),
                           default_lead=15) is False


def test_reminder_uses_default_lead_when_none():
    t = make_task(datetime(2026, 6, 17, 12, 0), lead=None)
    assert is_reminder_due(t, now_utc=datetime(2026, 6, 17, 11, 35),
                           default_lead=30) is True
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_occurrences.py -v`
Expected: FAIL.

- [ ] **Step 3: Реализовать occurrences.py**

```python
from datetime import datetime, date, timedelta


def occurrence_on_date(task, day: date) -> datetime | None:
    """Момент (naive UTC) вхождения задачи в указанный день, либо None."""
    t = task.due_at_utc.time()
    r = task.recurrence

    if r == "none":
        return datetime.combine(day, t) if task.due_at_utc.date() == day else None
    if r == "daily":
        return datetime.combine(day, t) if day >= task.due_at_utc.date() else None
    if r == "weekly":
        if day < task.due_at_utc.date():
            return None
        if day.weekday() == task.recurrence_weekday:
            return datetime.combine(day, t)
        return None
    if r == "monthly":
        if day < task.due_at_utc.date():
            return None
        return datetime.combine(day, t) if day.day == task.due_at_utc.day else None
    return None


def is_reminder_due(task, now_utc: datetime, default_lead: int) -> bool:
    """Пора ли напомнить о ближайшем вхождении к моменту now_utc."""
    if task.last_reminded_on == now_utc.date():
        return False
    occ = occurrence_on_date(task, now_utc.date())
    if occ is None:
        return False
    lead = task.lead_minutes if task.lead_minutes is not None else default_lead
    window_start = occ - timedelta(minutes=lead)
    return window_start <= now_utc <= occ
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/test_occurrences.py -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add app/services/occurrences.py tests/test_occurrences.py
git commit -m "feat: pure occurrence + reminder-due logic"
```

---

## Task 6: Слой repo (CRUD)

**Files:**
- Create: `app/db/repo.py`
- Test: `tests/test_repo.py`

- [ ] **Step 1: Написать падающие тесты**

`tests/test_repo.py`:
```python
from datetime import datetime, date
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.db.base import Base
from app.db import repo


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_get_or_create_user(session):
    u1 = await repo.get_or_create_user(session, telegram_id=1, username="a",
                                       default_tz="Europe/Moscow")
    u2 = await repo.get_or_create_user(session, telegram_id=1, username="a",
                                       default_tz="Europe/Moscow")
    assert u1.id == u2.id


async def test_add_and_list_tasks(session):
    u = await repo.get_or_create_user(session, 1, "a", "Europe/Moscow")
    await repo.add_task(session, user_id=u.id, title="t1", raw_text="r",
                        due_at_utc=datetime(2026, 6, 17, 12, 0), recurrence="none",
                        recurrence_weekday=None, lead_minutes=None)
    tasks = await repo.list_user_tasks(session, u.id)
    assert len(tasks) == 1
    assert tasks[0].title == "t1"


async def test_delete_task(session):
    u = await repo.get_or_create_user(session, 1, "a", "Europe/Moscow")
    t = await repo.add_task(session, u.id, "t1", "r",
                            datetime(2026, 6, 17, 12, 0), "none", None, None)
    await repo.delete_task(session, t.id, u.id)
    assert await repo.list_user_tasks(session, u.id) == []


async def test_mark_reminded(session):
    u = await repo.get_or_create_user(session, 1, "a", "Europe/Moscow")
    t = await repo.add_task(session, u.id, "t1", "r",
                            datetime(2026, 6, 17, 12, 0), "none", None, None)
    await repo.mark_reminded(session, t.id, date(2026, 6, 17))
    refreshed = (await repo.list_user_tasks(session, u.id))[0]
    assert refreshed.last_reminded_on == date(2026, 6, 17)
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_repo.py -v`
Expected: FAIL.

- [ ] **Step 3: Реализовать repo.py**

```python
from datetime import datetime, date
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import User, Task


async def get_or_create_user(session: AsyncSession, telegram_id: int,
                             username: str | None, default_tz: str) -> User:
    res = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = res.scalar_one_or_none()
    if user is None:
        user = User(telegram_id=telegram_id, username=username, timezone=default_tz)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def update_user(session: AsyncSession, user_id: int, **fields) -> None:
    user = await session.get(User, user_id)
    for k, v in fields.items():
        setattr(user, k, v)
    await session.commit()


async def add_task(session: AsyncSession, user_id: int, title: str, raw_text: str,
                   due_at_utc: datetime, recurrence: str,
                   recurrence_weekday: int | None, lead_minutes: int | None) -> Task:
    task = Task(user_id=user_id, title=title, raw_text=raw_text,
                due_at_utc=due_at_utc, recurrence=recurrence,
                recurrence_weekday=recurrence_weekday, lead_minutes=lead_minutes)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task


async def list_user_tasks(session: AsyncSession, user_id: int) -> list[Task]:
    res = await session.execute(
        select(Task).where(Task.user_id == user_id).order_by(Task.due_at_utc))
    return list(res.scalars().all())


async def get_task(session: AsyncSession, task_id: int, user_id: int) -> Task | None:
    res = await session.execute(
        select(Task).where(Task.id == task_id, Task.user_id == user_id))
    return res.scalar_one_or_none()


async def update_task(session: AsyncSession, task_id: int, user_id: int, **fields):
    task = await get_task(session, task_id, user_id)
    if task is None:
        return None
    for k, v in fields.items():
        setattr(task, k, v)
    await session.commit()
    return task


async def delete_task(session: AsyncSession, task_id: int, user_id: int) -> None:
    await session.execute(
        delete(Task).where(Task.id == task_id, Task.user_id == user_id))
    await session.commit()


async def mark_reminded(session: AsyncSession, task_id: int, day: date) -> None:
    task = await session.get(Task, task_id)
    if task:
        task.last_reminded_on = day
        await session.commit()


async def all_active_tasks(session: AsyncSession) -> list[Task]:
    res = await session.execute(select(Task))
    return list(res.scalars().all())


async def all_users(session: AsyncSession) -> list[User]:
    res = await session.execute(select(User))
    return list(res.scalars().all())
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/test_repo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/db/repo.py tests/test_repo.py
git commit -m "feat: repo CRUD layer with tests"
```

---

## Task 7: Форматирование и клавиатуры

**Files:**
- Create: `app/utils/formatting.py`
- Create: `app/keyboards/inline.py`
- Test: `tests/test_formatting.py`

- [ ] **Step 1: Написать падающий тест форматирования**

`tests/test_formatting.py`:
```python
from datetime import datetime
from app.utils.formatting import format_task_line, format_day_list


class T:
    def __init__(self, id, title, due, recurrence="none"):
        self.id, self.title, self.due_at_utc, self.recurrence = id, title, due, recurrence


def test_format_task_line_shows_local_time():
    t = T(1, "врач", datetime(2026, 6, 17, 12, 0))  # 12 UTC -> 15 MSK
    line = format_task_line(t, "Europe/Moscow")
    assert "15:00" in line
    assert "врач" in line


def test_format_day_list_empty():
    assert "пусто" in format_day_list([], "Europe/Moscow").lower()


def test_format_day_list_with_tasks():
    t = T(1, "врач", datetime(2026, 6, 17, 12, 0))
    out = format_day_list([t], "Europe/Moscow")
    assert "врач" in out
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_formatting.py -v`
Expected: FAIL.

- [ ] **Step 3: Реализовать formatting.py**

```python
from app.utils.tz import to_local

_REC_LABEL = {"none": "", "daily": " (ежедневно)", "weekly": " (еженедельно)",
              "monthly": " (ежемесячно)"}


def format_task_line(task, tz_name: str) -> str:
    local = to_local(task.due_at_utc, tz_name)
    rec = _REC_LABEL.get(getattr(task, "recurrence", "none"), "")
    return f"🕒 {local:%H:%M} — {task.title}{rec}"


def format_day_list(tasks, tz_name: str) -> str:
    if not tasks:
        return "На этот день задач нет — пусто 🎉"
    return "\n".join(format_task_line(t, tz_name) for t in tasks)
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/test_formatting.py -v`
Expected: PASS.

- [ ] **Step 5: Реализовать inline.py (без отдельного теста — UI-слой)**

```python
from aiogram.types import (InlineKeyboardMarkup, InlineKeyboardButton)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Сохранить", callback_data="task:save"),
        InlineKeyboardButton(text="✏️ Изменить", callback_data="task:edit"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="task:cancel"),
    ]])


def task_actions_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✏️", callback_data=f"edit:{task_id}"),
        InlineKeyboardButton(text="🗑", callback_data=f"del:{task_id}"),
    ]])
```

- [ ] **Step 6: Commit**

```bash
git add app/utils/formatting.py app/keyboards/inline.py tests/test_formatting.py
git commit -m "feat: task formatting and inline keyboards"
```

---

## Task 8: Gemini-сервис

**Files:**
- Create: `app/services/gemini.py`
- Test: `tests/test_gemini.py` (мок клиента)

Сервис строит промпт (включая TZ и текущее datetime пользователя), вызывает Gemini,
извлекает JSON. Возвращает сырой dict для `parser.parse`. Сеть в тестах мокается.

- [ ] **Step 1: Написать падающий тест с моком**

`tests/test_gemini.py`:
```python
from app.services.gemini import extract_json, build_prompt


def test_extract_json_from_fenced_block():
    text = '```json\n{"title": "врач", "datetime_local": "2026-06-17 15:00", ' \
           '"recurrence": "none"}\n```'
    data = extract_json(text)
    assert data["title"] == "врач"


def test_extract_json_plain():
    text = '{"title": "x", "datetime_local": "2026-06-17 15:00", "recurrence": "none"}'
    assert extract_json(text)["title"] == "x"


def test_build_prompt_contains_context():
    p = build_prompt("завтра в 15 врач", tz_name="Europe/Moscow",
                     now_local="2026-06-16 13:00")
    assert "Europe/Moscow" in p
    assert "2026-06-16 13:00" in p
    assert "завтра в 15 врач" in p
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_gemini.py -v`
Expected: FAIL.

- [ ] **Step 3: Реализовать gemini.py**

```python
import json
import re
from google import genai

_PROMPT_TEMPLATE = """Ты парсер задач ежедневника. Преобразуй сообщение пользователя
в JSON. Сегодня (локальное время пользователя): {now_local}. Часовой пояс: {tz_name}.

Верни СТРОГО JSON без пояснений с полями:
- "title": краткая суть задачи (строка)
- "datetime_local": "YYYY-MM-DD HH:MM" в локальном времени пользователя
- "recurrence": одно из "none" | "daily" | "weekly" | "monthly"
- "weekday": 0-6 (пн=0), только если recurrence == "weekly"

Если время не указано явно — выбери разумное (например 09:00).

Сообщение пользователя: "{text}"
"""


def build_prompt(text: str, tz_name: str, now_local: str) -> str:
    return _PROMPT_TEMPLATE.format(text=text, tz_name=tz_name, now_local=now_local)


def extract_json(response_text: str) -> dict:
    match = re.search(r"\{.*\}", response_text, re.DOTALL)
    if not match:
        raise ValueError("no JSON found in Gemini response")
    return json.loads(match.group(0))


class GeminiService:
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self._client = genai.Client(api_key=api_key)
        self._model = model

    async def parse_text(self, text: str, tz_name: str, now_local: str) -> dict:
        prompt = build_prompt(text, tz_name, now_local)
        # google-genai async API
        resp = await self._client.aio.models.generate_content(
            model=self._model, contents=prompt)
        return extract_json(resp.text)
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/test_gemini.py -v`
Expected: PASS (тестируются чистые `extract_json`/`build_prompt`; сетевой
`parse_text` проверяется вручную на этапе интеграции).

- [ ] **Step 5: Commit**

```bash
git add app/services/gemini.py tests/test_gemini.py
git commit -m "feat: gemini service (prompt build + json extract)"
```

---

## Task 9: FSM-состояния и хендлеры — свободный текст + просмотр

**Files:**
- Create: `app/states.py`
- Create: `app/handlers/tasks.py`
- Create: `app/handlers/commands.py`

Хендлеры тестируются вручную (интеграция с Telegram); юнит-логика уже покрыта в
Task 4–7. Зависимости (session-фабрика, GeminiService) прокидываются через
`dp["..."]`/middleware или импортом из собранного приложения — см. Task 11.

- [ ] **Step 1: states.py**

```python
from aiogram.fsm.state import State, StatesGroup


class Onboarding(StatesGroup):
    waiting_timezone = State()


class TaskFlow(StatesGroup):
    confirming = State()      # показано превью, ждём кнопку
    editing_text = State()    # пользователь присылает новый текст задачи


class Settings(StatesGroup):
    waiting_digest_time = State()
    waiting_lead = State()
```

- [ ] **Step 2: commands.py (роутер базовых команд)**

```python
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from app.db import repo
from app.db.base import get_sessionmaker
from app.utils.tz import to_local
from app.utils.formatting import format_day_list
from app.services.occurrences import occurrence_on_date

router = Router()


@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "Напиши свободным текстом, что запланировано — например:\n"
        "• «завтра в 15 встреча с врачом»\n"
        "• «каждый понедельник в 10 планёрка»\n\n"
        "Команды:\n"
        "/today — задачи на сегодня\n"
        "/list — задачи (с датой: /list 20.06)\n"
        "/timezone — часовой пояс\n"
        "/settings — напоминания и дайджест"
    )


@router.message(Command("today"))
async def today_cmd(message: Message):
    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session, message.from_user.id, message.from_user.username, "Europe/Moscow")
        tasks = await repo.list_user_tasks(session, user.id)
        today_local = to_local(datetime.utcnow(), user.timezone).date()
        todays = [t for t in tasks
                  if occurrence_on_date(t, today_local) is not None]
        await message.answer("📅 Сегодня:\n" + format_day_list(todays, user.timezone))
```

(`/list` реализуется аналогично с парсингом аргумента-даты; `/cancel` —
`await state.clear()`.)

- [ ] **Step 3: tasks.py (свободный текст → превью → сохранение)**

```python
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from app.db import repo
from app.db.base import get_sessionmaker
from app.services.parser import parse, ParseError
from app.utils.tz import to_local
from app.utils.formatting import format_task_line
from app.keyboards.inline import confirm_kb, task_actions_kb
from app.states import TaskFlow

router = Router()


@router.message(F.text & ~F.text.startswith("/"))
async def on_free_text(message: Message, state: FSMContext, gemini):
    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session, message.from_user.id, message.from_user.username, "Europe/Moscow")
        now_local = to_local(datetime.utcnow(), user.timezone).strftime("%Y-%m-%d %H:%M")
    try:
        raw = await gemini.parse_text(message.text, user.timezone, now_local)
        parsed = parse(raw, user.timezone, message.text, datetime.utcnow())
    except (ParseError, ValueError):
        await message.answer("Не смог разобрать 🤔 Переформулируй, "
                             "например: «завтра в 15 встреча».")
        return
    await state.update_data(parsed=parsed.__dict__)
    await state.set_state(TaskFlow.confirming)
    preview = format_task_line(parsed, user.timezone)
    await message.answer(f"Сохранить?\n{preview}", reply_markup=confirm_kb())


@router.callback_query(F.data == "task:save", TaskFlow.confirming)
async def on_save(cb: CallbackQuery, state: FSMContext):
    data = (await state.get_data())["parsed"]
    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session, cb.from_user.id, cb.from_user.username, "Europe/Moscow")
        task = await repo.add_task(
            session, user.id, data["title"], data["raw_text"],
            data["due_at_utc"], data["recurrence"],
            data["recurrence_weekday"], None)
        await cb.message.edit_text(
            "✅ Сохранено:\n" + format_task_line(task, user.timezone),
            reply_markup=task_actions_kb(task.id))
    await state.clear()
    await cb.answer()


@router.callback_query(F.data == "task:cancel", TaskFlow.confirming)
async def on_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("Отменено.")
    await cb.answer()


@router.callback_query(F.data.startswith("del:"))
async def on_delete(cb: CallbackQuery):
    task_id = int(cb.data.split(":")[1])
    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session, cb.from_user.id, cb.from_user.username, "Europe/Moscow")
        await repo.delete_task(session, task_id, user.id)
    await cb.message.edit_text("🗑 Удалено.")
    await cb.answer()
```

- [ ] **Step 4: Запустить весь тест-сьют (регрессия)**

Run: `pytest -v`
Expected: все предыдущие тесты PASS (новый код хендлеров не ломает юнит-тесты).

- [ ] **Step 5: Commit**

```bash
git add app/states.py app/handlers/tasks.py app/handlers/commands.py
git commit -m "feat: free-text task flow, today/list, delete handlers"
```

---

## Task 10: Планировщик (tick)

**Files:**
- Create: `app/services/scheduler.py`
- Test: `tests/test_scheduler.py` (тестируем выборку «кого напомнить», а не APScheduler)

- [ ] **Step 1: Написать падающий тест функции выборки**

`tests/test_scheduler.py`:
```python
from datetime import datetime, date
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.db.base import Base
from app.db import repo
from app.services.scheduler import collect_due_reminders


@pytest.fixture
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        yield s
    await engine.dispose()


async def test_collect_due_reminders(session):
    u = await repo.get_or_create_user(session, 1, "a", "Europe/Moscow")
    await repo.add_task(session, u.id, "врач", "r",
                        datetime(2026, 6, 17, 12, 0), "none", None, None)
    # now = 11:50 UTC, lead default 15 -> окно с 11:45, задача созрела
    due = await collect_due_reminders(session, now_utc=datetime(2026, 6, 17, 11, 50))
    assert len(due) == 1
    user, task, occ = due[0]
    assert task.title == "врач"
```

- [ ] **Step 2: Запустить — убедиться, что падает**

Run: `pytest tests/test_scheduler.py -v`
Expected: FAIL.

- [ ] **Step 3: Реализовать scheduler.py**

```python
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.db import repo
from app.db.base import get_sessionmaker
from app.services.occurrences import occurrence_on_date, is_reminder_due
from app.utils.tz import to_local
from app.utils.formatting import format_day_list

log = logging.getLogger(__name__)


async def collect_due_reminders(session, now_utc: datetime):
    """-> list[(user, task, occurrence_datetime)] для созревших напоминаний."""
    users = {u.id: u for u in await repo.all_users(session)}
    result = []
    for task in await repo.all_active_tasks(session):
        user = users.get(task.user_id)
        if user is None:
            continue
        if is_reminder_due(task, now_utc, user.default_lead_minutes):
            occ = occurrence_on_date(task, now_utc.date())
            result.append((user, task, occ))
    return result


async def collect_digests(session, now_utc: datetime):
    """-> list[(user, [tasks])] для пользователей, у кого настал digest_time."""
    out = []
    for user in await repo.all_users(session):
        if not user.digest_enabled:
            continue
        local_now = to_local(now_utc, user.timezone)
        if local_now.strftime("%H:%M") != user.digest_time:
            continue
        tasks = await repo.list_user_tasks(session, user.id)
        todays = [t for t in tasks
                  if occurrence_on_date(t, local_now.date()) is not None]
        out.append((user, todays))
    return out


def make_tick(bot):
    async def tick():
        now_utc = datetime.utcnow().replace(second=0, microsecond=0)
        maker = get_sessionmaker()
        async with maker() as session:
            try:
                for user, task, occ in await collect_due_reminders(session, now_utc):
                    try:
                        local = to_local(occ, user.timezone)
                        await bot.send_message(
                            user.telegram_id,
                            f"🔔 Напоминание: {task.title} в {local:%H:%M}")
                        await repo.mark_reminded(session, task.id, now_utc.date())
                    except Exception:
                        log.exception("reminder failed for user %s", user.telegram_id)
                for user, tasks in await collect_digests(session, now_utc):
                    try:
                        await bot.send_message(
                            user.telegram_id,
                            "☀️ План на сегодня:\n" + format_day_list(tasks, user.timezone))
                    except Exception:
                        log.exception("digest failed for user %s", user.telegram_id)
            except Exception:
                log.exception("tick failed")
    return tick


def start_scheduler(bot, interval_seconds: int) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(make_tick(bot), "interval", seconds=interval_seconds)
    scheduler.start()
    return scheduler
```

- [ ] **Step 4: Запустить — убедиться, что проходит**

Run: `pytest tests/test_scheduler.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/services/scheduler.py tests/test_scheduler.py
git commit -m "feat: APScheduler tick with reminders and digests"
```

---

## Task 11: Онбординг, настройки, редактирование

**Files:**
- Create: `app/handlers/onboarding.py`
- Modify: `app/handlers/commands.py` (добавить `/start`, `/timezone`, `/settings`, `/cancel`)
- Modify: `app/handlers/tasks.py` (ветка `task:edit` и состояние `editing_text`)

- [ ] **Step 1: onboarding.py — /start и выбор TZ**

```python
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from app.db import repo
from app.db.base import get_sessionmaker
from app.utils.tz import is_valid_tz
from app.states import Onboarding

router = Router()


@router.message(CommandStart())
async def start_cmd(message: Message, state: FSMContext):
    maker = get_sessionmaker()
    async with maker() as session:
        await repo.get_or_create_user(
            session, message.from_user.id, message.from_user.username, "Europe/Moscow")
    await message.answer(
        "Привет! Я ежедневник. Сначала укажи свой часовой пояс "
        "(IANA-формат), например: Europe/Moscow")
    await state.set_state(Onboarding.waiting_timezone)


@router.message(Onboarding.waiting_timezone)
async def set_tz(message: Message, state: FSMContext):
    tz = message.text.strip()
    if not is_valid_tz(tz):
        await message.answer("Не узнал пояс. Примеры: Europe/Moscow, Asia/Almaty, "
                             "Europe/Kyiv. Попробуй ещё раз.")
        return
    maker = get_sessionmaker()
    async with maker() as session:
        user = await repo.get_or_create_user(
            session, message.from_user.id, message.from_user.username, "Europe/Moscow")
        await repo.update_user(session, user.id, timezone=tz)
    await state.clear()
    await message.answer(f"Готово, пояс: {tz}. Пиши задачи свободным текстом! /help")
```

- [ ] **Step 2: commands.py — /timezone, /settings, /cancel**

`/timezone` переводит в `Onboarding.waiting_timezone`; `/settings` показывает текущие
настройки и через FSM (`Settings.waiting_digest_time`, `waiting_lead`) обновляет
`digest_time`/`default_lead_minutes`/`digest_enabled` через `repo.update_user`;
`/cancel` делает `await state.clear()` и отвечает «Отменено».

```python
@router.message(Command("cancel"))
async def cancel_cmd(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.")


@router.message(Command("timezone"))
async def timezone_cmd(message: Message, state: FSMContext):
    await message.answer("Укажи часовой пояс (например Europe/Moscow):")
    await state.set_state(Onboarding.waiting_timezone)
```

- [ ] **Step 3: tasks.py — редактирование задачи**

Колбэк `task:edit` (на превью) и `edit:{id}` (на сохранённой задаче) переводят в
`TaskFlow.editing_text`; следующее текстовое сообщение прогоняется через тот же
парсинг и для `edit:{id}` вызывает `repo.update_task(session, id, user.id, title=...,
due_at_utc=..., recurrence=..., recurrence_weekday=...)`.

- [ ] **Step 4: Регрессия**

Run: `pytest -v`
Expected: все тесты PASS.

- [ ] **Step 5: Commit**

```bash
git add app/handlers/onboarding.py app/handlers/commands.py app/handlers/tasks.py
git commit -m "feat: onboarding, settings, timezone, task editing"
```

---

## Task 12: Сборка приложения (bot.py) и ручная проверка

**Files:**
- Create: `bot.py`

- [ ] **Step 1: Реализовать bot.py**

```python
import asyncio
import logging
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from config import Settings
from app.db.base import init_engine, init_db
from app.services.gemini import GeminiService
from app.services.scheduler import start_scheduler
from app.handlers import commands, tasks, onboarding


async def main():
    logging.basicConfig(level=logging.INFO)
    load_dotenv()
    settings = Settings.from_env()

    init_engine(settings.db_path)
    await init_db()

    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    gemini = GeminiService(settings.gemini_api_key)

    # прокидываем gemini в хендлеры через workflow data
    dp["gemini"] = gemini

    dp.include_router(onboarding.router)
    dp.include_router(commands.router)
    dp.include_router(tasks.router)

    start_scheduler(bot, settings.tick_interval_seconds)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
```

Примечание: для инъекции `gemini` в `tasks.on_free_text` aiogram 3 поддерживает
передачу значений из `dp[...]` как именованных аргументов хендлера — имя параметра
`gemini` совпадает с ключом.

- [ ] **Step 2: Проверить запуск с реальными ключами**

```bash
cp .env.example .env   # заполнить BOT_TOKEN и GEMINI_API_KEY
python bot.py
```

Ручной чек-лист в Telegram:
1. `/start` → задать `Europe/Moscow`.
2. «завтра в 15 встреча с врачом» → превью → ✅ Сохранить.
3. `/today` (если на сегодня) / создать задачу на ближайшие минуты с малым lead → дождаться 🔔.
4. «каждый понедельник в 10 планёрка» → проверить пометку «(еженедельно)».
5. 🗑 удалить — задача исчезает.
6. `/settings` → включить дайджест на ближайшую минуту → дождаться ☀️.

- [ ] **Step 3: Финальная регрессия**

Run: `pytest -v`
Expected: весь сьют PASS.

- [ ] **Step 4: Commit**

```bash
git add bot.py
git commit -m "feat: application wiring (bot entrypoint) + manual verification"
```

---

## Чек-лист готовности

- [ ] Все юнит-тесты зелёные (`pytest -v`).
- [ ] Бот стартует, проходит онбординг, парсит и сохраняет задачи.
- [ ] Напоминания приходят за `N` минут, повторно за день не дублируются.
- [ ] Повторяющиеся задачи показываются на нужные дни.
- [ ] Редактирование и удаление работают.
- [ ] Утренний дайджест приходит в локальное `digest_time`.
- [ ] README и .env.example актуальны.
