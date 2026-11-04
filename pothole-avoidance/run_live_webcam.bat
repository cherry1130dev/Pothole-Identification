@echo off
title AI Pothole Detection - Webcam + Live ESP8266 (10.135.210.9)
cd /d "%~dp0laptop_ai"
echo ======================================================================
echo    AI Pothole Detection (Webcam -> Live ESP8266 @ 10.135.210.9)
echo ======================================================================
echo Opening webcam and connecting to live vehicle controller...
python detect_stream.py --stream 0
pause

