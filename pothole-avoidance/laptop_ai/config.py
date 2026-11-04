"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  Laptop AI Central Configuration
FILE:    config.py
======================================================================================

DESCRIPTION:
Centralized configuration parameters for the Python computer vision server.
Controls network endpoints, camera streaming, AI inference models, classical
OpenCV fallback parameters, and temporal debouncing filters.
======================================================================================
"""

import os

# ======================================================================================
# 1. NETWORK & HARDWARE ENDPOINTS
# ======================================================================================

# IP of the ESP32-CAM video streamer node
# IP of the ESP32-CAM video streamer (Connected to ESP8266 AP)
ESP32_CAM_IP = "10.135.210.5"
STREAM_PORT = 81
STREAM_URL = f"http://{ESP32_CAM_IP}:{STREAM_PORT}/stream"

# IP of the ESP8266 AP Server vehicle controller
ESP8266_IP = "10.135.210.9"
ESP8266_PORT = 80
ESP8266_BASE_URL = f"http://{ESP8266_IP}:{ESP8266_PORT}"

# REST API Endpoints on the ESP8266
POTHOLE_ENDPOINT = f"{ESP8266_BASE_URL}/pothole"
STATUS_ENDPOINT  = f"{ESP8266_BASE_URL}/status"
MODE_ENDPOINT    = f"{ESP8266_BASE_URL}/mode"
DRIVE_ENDPOINT   = f"{ESP8266_BASE_URL}/drive"

# HTTP Client timeouts (dispatched asynchronously in background worker threads)
HTTP_CONNECT_TIMEOUT_SEC = 1.00   # 1.0 s connection timeout
HTTP_READ_TIMEOUT_SEC    = 1.50   # 1.5 s response read timeout

# Optional Secondary Telegram Dispatcher from Laptop
TELEGRAM_BOT_TOKEN = "9138292752:AAFdtNKDLzFQVDEwx8mSyhJ1kMcRNApC0xg"
TELEGRAM_CHAT_ID   = "2022474265"
TELEGRAM_ALERT_COOLDOWN_SEC = 15.0

# ======================================================================================
# HIGH-PRECISION ACCURATE GPS & GEOLOCATION CONFIGURATION
# ======================================================================================

# Method 1: Native Windows Wi-Fi Positioning (High Accuracy ~100m, No API Key Required)
# Uses Windows 10/11 native location service triangulating Wi-Fi access points
USE_WINDOWS_GEOLOCATION = True

# Method 2: Live Mobile Phone Satellite GPS Receiver (Sub-3 Meter Accuracy)
# Any smartphone connected to the same Wi-Fi can open http://<LAPTOP_IP>:8080/gps.html
# and stream sub-3 meter satellite GPS coordinates in real-time.
ENABLE_PHONE_GPS_STREAM = True
PHONE_GPS_ENDPOINT = "http://127.0.0.1:8080/api/gps"

# Method 3: Google Geolocation API Key (Triangulates visible Wi-Fi APs for ~15m accuracy)
# Paste your Google Cloud Geolocation API key here (leave empty if not using):
GOOGLE_GEOLOCATION_API_KEY = ""

# Reverse Geocoding via OpenStreetMap Nominatim (Auto-resolves Street/Town/District names)
ENABLE_REVERSE_GEOCODING = True

# Method 4: Exact Physical Street Coordinates Override (Meter-Level Calibration)
# Set to True and specify exact street coordinates for 100% pinpoint accuracy
EXACT_GPS_OVERRIDE_ENABLED = False
EXACT_GPS_LATITUDE  = 16.839701
EXACT_GPS_LONGITUDE = 82.029669
EXACT_GPS_SITE_NAME = "Ramachandrapuram Road"


# ======================================================================================
# 2. AI MODEL CONFIGURATION (YOLOv8n / ONNX)
# ======================================================================================

# Path to trained YOLOv8n weights or ONNX model
# Set to 'models/pothole_yolov8n.onnx' or 'models/best.pt'
MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "pothole_yolov8n.onnx")
PYTORCH_MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "best.pt")

# Target model input resolution for CPU real-time inference (320x320)
MODEL_INPUT_WIDTH  = 320
MODEL_INPUT_HEIGHT = 320

# AI Confidence threshold for detecting a pothole
CONFIDENCE_THRESHOLD = 0.45

# Class index for pothole in the dataset (typically 0)
POTHOLE_CLASS_ID = 0

# Allow automatic fallback to classical OpenCV if model weights file is missing
AUTO_FALLBACK_TO_OPENCV = True

# ======================================================================================
# 3. FALSE ALARM REDUCTION & TEMPORAL DEBOUNCING
# ======================================================================================

# Region of Interest (ROI) Constraints
# Ignore the upper half of the video (sky, horizon, buildings)
# Potholes can only physically exist in the road surface (lower half)
ROI_Y_MIN_RATIO = 0.50   # Only inspect pixels where y >= 50% of frame height
ROI_Y_MAX_RATIO = 1.00   # Inspect down to the bottom bumper edge
ROI_X_MIN_RATIO = 0.05   # Margin from left border
ROI_X_MAX_RATIO = 0.95   # Margin from right border

# Minimum and maximum bounding box area (in pixels) for a valid pothole
MIN_POTHOLE_AREA_PX = 450
MAX_POTHOLE_AREA_PX = 45000

# Temporal Confirmation Filters:
# Require N consecutive frames with detections before sending state=1 (slow down)
CONFIRM_FRAMES_N = 3

# Require M consecutive clear frames before sending state=0 (resume normal speed)
CLEAR_FRAMES_M = 10

# ======================================================================================
# 4. CLASSICAL OPENCV FALLBACK PARAMETERS
# ======================================================================================

# Bilateral / Gaussian filter kernel size for noise reduction
OPENCV_BLUR_KERNEL = (7, 7)

# Canny edge detector thresholds
CANNY_THRESH_LOW  = 50
CANNY_THRESH_HIGH = 150

# Dark-region intensity threshold (relative to median road luminance)
DARK_REGION_INTENSITY_FACTOR = 0.70

# Minimum contour circularity / solidity for defect filtering
MIN_CONTOUR_SOLIDITY = 0.40

# ======================================================================================
# 5. VIDEO DISPLAY & STREAMING SETTINGS
# ======================================================================================

WINDOW_TITLE = "AI Pothole Vision & Safety System [ESP32-CAM Stream]"
DISPLAY_SCALE = 2.0      # Upscale QVGA (320x240) to 640x480 for comfortable laptop viewing
TARGET_FPS = 25
RECONNECT_DELAY_SEC = 2.0
