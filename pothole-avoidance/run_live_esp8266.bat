@echo off
title AI Pothole Detection - Live ESP8266 (10.135.210.9)
cd /d "%~dp0laptop_ai"
echo ======================================================================
echo    AI Pothole Detection Engine (Connected to ESP8266 @ 10.135.210.9)
echo ======================================================================
echo Loading road video stream and connecting to live vehicle controller...
python detect_stream.py --stream pothole_video.mp4
pause

