@echo off
title AI Pothole Detection - Live ESP32-CAM and ESP8266
cd /d "%~dp0laptop_ai"
echo ======================================================================
echo    AI Pothole Identification Engine (Wi-Fi Router Mode)
echo    Camera:  http://10.135.210.5:81/stream (ESP32-CAM)
echo    Vehicle: http://10.135.210.9:80 (ESP8266)
echo ======================================================================
echo Laptop connected to Wi-Fi router with internet for Telegram alerts!
echo Connecting to live camera stream and vehicle motion controller...
echo Tip: Press 'r' in video window to flip stream 180 degrees if needed.
python detect_stream.py --stream http://10.135.210.5:81/stream
pause
