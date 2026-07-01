from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    timezone: Mapped[str] = mapped_column(String, default="Europe/Moscow")
    digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    digest_time: Mapped[str] = mapped_column(String, default="09:00")
    default_lead_minutes: Mapped[int] = mapped_column(Integer, default=15)
    # --- монетизация ---
    plan: Mapped[str] = mapped_column(String, default="free")  # free | premium
    premium_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ai_requests_used: Mapped[int] = mapped_column(Integer, default=0)
    ai_requests_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    tasks: Mapped[list["Task"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String)
    raw_text: Mapped[str] = mapped_column(String)
    due_at_utc: Mapped[datetime] = mapped_column(DateTime)
    # none | daily | weekly | monthly
    recurrence: Mapped[str] = mapped_column(String, default="none")
    recurrence_weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lead_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_reminded_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="tasks")
