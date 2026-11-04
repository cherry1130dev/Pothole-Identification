@echo off
title AI Pothole Detection - Live Web Dashboard
cd /d "%~dp0laptop_ai"
echo ======================================================================
echo    AI Pothole Identification Web Dashboard
echo    ESP8266 Onboard Dashboard: http://10.135.210.9
echo    Laptop Secondary Web HUD:  http://localhost:5000
echo    Camera Stream Source:      http://10.135.210.5:81/stream
echo ======================================================================
echo Make sure laptop and ESPs are connected to Wi-Fi router (Easitronics).
echo.
start http://localhost:5000
python web_server.py --port 5000 --stream http://10.135.210.5:81/stream
pause
