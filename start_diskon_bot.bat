@echo off
title DiskonBot - Master Launcher
echo ========================================================
echo   STARTING DISKON-BOT: ALL SERVICES ACTIVE
echo ========================================================
echo   [1/2] Membuka Frontend Web Dashboard (Port 8000)...
start "DiskonBot - Frontend Dashboard" cmd /k "title DiskonBot Frontend && python server.py"

echo   [2/2] Membuka Telegram Bot Service...
start "DiskonBot - Telegram Bot" cmd /k "title DiskonBot Telegram Bot && python bot.py"

echo.
echo ========================================================
echo   SEMUA SERVICE AKTIF!
echo   - Web Dashboard : http://localhost:8000
echo   - Telegram Bot  : Aktif (Polling)
echo.
echo   Kedua service berjalan di jendela CMD masing-masing.
echo ========================================================
echo.
pause
