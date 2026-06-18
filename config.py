from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Путь к .env считаем относительно этого файла, а не текущей рабочей директории,
# чтобы запуск из любого места (F5 в VS Code, корень воркспейса) находил .env.
_ENV_FILE = Path(__file__).resolve().parent / ".env"


class Settings(BaseSettings):
    """Настройки приложения, читаются из .env (или переменных окружения).

    Имена полей сопоставляются с переменными окружения без учёта регистра:
    поле ``bot_token`` читает ``BOT_TOKEN`` и т.д.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"
    db_path: str = "diary.db"
    default_tz: str = "Europe/Moscow"
    tick_interval: int = 60
