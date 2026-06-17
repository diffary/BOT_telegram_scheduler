@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"

echo Stopping any old bot instances (avoids Telegram Conflict)...
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*bot.py*' -and $_.CommandLine -notlike '*Win32_Process*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo Starting bot... (press Ctrl+C to stop)
echo.
".venv\Scripts\python.exe" -u bot.py

echo.
echo === Bot stopped ===
pause
