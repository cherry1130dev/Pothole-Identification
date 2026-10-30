@echo off
title AI Pothole Detection - Road Video Mode
cd /d "%~dp0laptop_ai"
echo ======================================================================
echo       Running AI Pothole Detection on Recorded Road Video
echo ======================================================================
echo Loading pothole_video.mp4 and mock vehicle controller...
python run_video.py
pause
