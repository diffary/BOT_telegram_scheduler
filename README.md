# Telegram-бот «Ежедневник» 🗓

Многопользовательский Telegram-бот-планировщик. Пользователь пишет задачу
**свободным текстом** («завтра в 15 встреча с врачом»), LLM (Gemini) распознаёт
дату/время/повтор, бот сохраняет задачу, показывает списки и присылает напоминания.

## Возможности
- 📝 **Свободный текст → задача** через Gemini (с подтверждением и кнопками).
- 📅 **Просмотр**: `/today` (с разделением «Предстоит / Прошло»), `/list` на дату или период.
- 🔁 **Повторяющиеся задачи**: ежедневно / еженедельно / ежемесячно.
- 🔔 **Напоминания** за N минут до события + опциональный утренний **дайджест**.
- ✏️🗑 **Редактирование и удаление** задач (`/manage`, инлайн-кнопки).
- 🌍 **Свой часовой пояс** у каждого пользователя (время хранится в UTC).
- ⚙️ **Настройки** из бота: дайджест вкл/выкл и время, lead-время напоминаний.

## Стек
- **aiogram 3** — Telegram Bot API (async, polling)
- **SQLAlchemy 2 (async) + aiosqlite** — ORM поверх SQLite
- **Google Gemini API** — парсинг свободного текста
- **APScheduler** — планировщик напоминаний/дайджеста
- **pytest** — тесты (72 шт.)

## Быстрый старт

```bash
# 1. Виртуальное окружение и зависимости
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate && pip install -r requirements.txt # Linux/Mac

# 2. Конфиг: скопировать шаблон и вписать ключи
copy .env.example .env        # Windows  (cp на Linux/Mac)
#  BOT_TOKEN      — от @BotFather
#  GEMINI_API_KEY — из Google AI Studio

# 3. Запуск
.venv\Scripts\python.exe bot.py
```

На Windows можно просто **двойной клик по `run_bot.bat`** (сам гасит старые
экземпляры и запускает бота). В VS Code — `F5` (конфиг в `.vscode/launch.json`).

> ⚠️ Запускать строго **в одном экземпляре** — иначе Telegram вернёт
> `Conflict: terminated by other getUpdates request`.

## Команды
| Команда | Действие |
|---------|----------|
| `/start` | приветствие + выбор часового пояса |
| свободный текст | создать задачу (через Gemini) |
| `/today` | задачи на сегодня |
| `/list <дата>` | задачи на дату/период: `завтра`, `20.06`, `неделя` |
| `/manage` | изменить/удалить задачи |
| `/timezone` | сменить часовой пояс |
| `/settings` | дайджест и время напоминаний |
| `/help`, `/cancel` | справка / отмена диалога |

## Структура
```
bot.py                 точка входа: роутеры, планировщик, polling
config.py              настройки из .env (pydantic-settings)
app/
  db/        base.py (engine/session), models.py (User, Task), repo.py (CRUD)
  services/  gemini.py (LLM), parser.py (валидация+UTC),
             occurrences.py (вхождения повторов), scheduler.py (тик)
  handlers/  onboarding.py, commands.py, tasks.py, settings.py, errors.py
  keyboards/ inline.py
  utils/     tz.py, dates.py, formatting.py
  states.py  FSM-состояния
tests/                 72 теста (pytest)
```

## Как это работает (кратко)
1. Свободный текст → Gemini (строгий JSON) → `parser` валидирует и переводит
   локальное время в **UTC** → превью с кнопками → сохранение.
2. **Планировщик** раз в минуту опрашивает БД: какие напоминания «созрели»
   (за `lead` минут до события) и кому пора слать дайджест.
3. Время всегда хранится в UTC, в зону пользователя переводится только
   на входе и выводе.

## Тесты
```bash
.venv\Scripts\python.exe -m pytest -q
```

## Заметки по деплою
Нужен **always-on процесс + постоянный диск** (polling + SQLite-файл).
Бесплатно подходит, например, **Oracle Cloud Always Free** (VM + systemd-сервис).
Секреты — через переменные окружения / локальный `.env` на сервере (не коммитить).
```
