from aiogram.fsm.state import State, StatesGroup


class EditTask(StatesGroup):
    """Ожидание новой формулировки при редактировании задачи."""

    waiting_text = State()
