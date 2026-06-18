# Деплой на сервер (Oracle Cloud / любой Ubuntu) через systemd

Бот работает как `systemd`-сервис: запускается при загрузке, перезапускается при
падении, живёт 24/7. Ниже — для Ubuntu (Oracle Always Free). Пользователь — `ubuntu`.

> ⚠️ Один экземпляр на токен! Перед деплоем останови локальный бот (закрой `run_bot.bat`),
> иначе сервер и ПК будут конфликтовать (`getUpdates Conflict`).

## 1. Подключиться к серверу
```bash
ssh ubuntu@<IP_СЕРВЕРА>
```

## 2. Поставить системные пакеты
```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git
```

## 3. Склонировать репозиторий
```bash
cd ~
git clone https://github.com/diffary/BOT_telegram_scheduler.git
cd BOT_telegram_scheduler
```

## 4. Виртуальное окружение и зависимости
```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

## 5. Создать .env с реальными ключами (НЕ коммитится)
```bash
cp .env.example .env
nano .env          # вписать BOT_TOKEN, GEMINI_API_KEY, при желании GEMINI_MODEL/DEFAULT_TZ
```

## 6. Проверить запуск вручную (опционально)
```bash
.venv/bin/python -u bot.py    # должно появиться "Run polling for bot @..."; Ctrl+C для выхода
```

## 7. Установить как systemd-сервис
```bash
sudo cp deploy/diary-bot.service /etc/systemd/system/diary-bot.service
# если путь/пользователь другие — поправь WorkingDirectory/ExecStart/User в файле
sudo systemctl daemon-reload
sudo systemctl enable --now diary-bot
```

## 8. Управление и логи
```bash
sudo systemctl status diary-bot      # статус
journalctl -u diary-bot -f           # живые логи
sudo systemctl restart diary-bot     # перезапуск
sudo systemctl stop diary-bot        # остановить
```

## 9. Обновление после нового пуша
```bash
cd ~/BOT_telegram_scheduler
git pull
.venv/bin/pip install -r requirements.txt   # если менялись зависимости
sudo systemctl restart diary-bot
```

## Заметки
- БД `diary.db` создаётся рядом с ботом и переживает рестарты (постоянный диск VM).
- Бэкап данных = просто скопировать файл `diary.db`.
- При смене модели Gemini правишь `GEMINI_MODEL` в `.env` и `systemctl restart diary-bot`.
- Логи polling видно в `journalctl`; глобальный обработчик ошибок не даёт боту падать.
