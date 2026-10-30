@echo off
title Link Telegram Bot (@vsm_pothole_bot)
cd /d "%~dp0laptop_ai"
echo ======================================================================
echo             Linking Telegram Bot (@vsm_pothole_bot)
echo ======================================================================
echo Make sure you have opened https://t.me/vsm_pothole_bot in Telegram
echo and tapped 'START' or sent any message (e.g. 'hello').
echo.
python register_telegram_bot.py
pause
