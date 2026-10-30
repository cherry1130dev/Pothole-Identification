@echo off
title AI Pothole Detection - Laptop Webcam Mode
cd /d "%~dp0laptop_ai"
echo ======================================================================
echo       Starting Live AI Pothole Detection via Laptop Webcam
echo ======================================================================
echo Opening webcam and mock controller...
python run_webcam.py
pause
