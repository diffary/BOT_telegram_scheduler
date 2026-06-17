from aiogram.fsm.state import State, StatesGroup


class EditTask(StatesGroup):
    """Ожидание новой формулировки при редактировании сохранённой задачи."""

    waiting_text = State()


class EditDraft(StatesGroup):
    """Ожидание правки ещё не сохранённого черновика (на превью)."""

    waiting_text = State()


class SetTimezone(StatesGroup):
    """Ручной ввод часового пояса (IANA)."""

    waiting_manual = State()


class SetSettings(StatesGroup):
    """Ввод значений настроек."""

    waiting_digest_time = State()
    waiting_lead = State()
