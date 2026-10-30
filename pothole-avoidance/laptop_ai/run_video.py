"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  User Video Pothole Detection & Actuation Runner
FILE:    run_video.py
======================================================================================

DESCRIPTION:
Executes the complete system using your real-world road video (pothole_video.mp4):
1. Starts the Mock ESP8266 controller simulator in the background (http://127.0.0.1:8080).
2. Streams frames from 'pothole_video.mp4' into the AI detection engine at natural playback speed.
3. Automatically loops the video upon reaching the end.
4. Renders the interactive Heads-Up Display (HUD):
   - Road surface inspection ROI (lower half)
   - Real-time bounding boxes around detected road defects/potholes with confidence scores
   - Dynamic vehicle state banner: GREEN (CRUISE) <-> RED (SLOW DOWN)
   - Live HTTP REST command dispatching to the vehicle controller.

CONTROLS IN PREVIEW WINDOW:
   'q' or ESC : Exit cleanly
   'd'        : Toggle dark crater contour mask overlay
   'f'        : Toggle Classical OpenCV / YOLOv8
   's'        : Query mock vehicle status
======================================================================================
"""

import os
import sys
import time
import threading
from mock_esp8266 import run_mock_server
from detect_stream import main as run_detector


def start_mock_in_background():
    server_thread = threading.Thread(
        target=run_mock_server,
        kwargs={"host": "127.0.0.1", "port": 8080},
        daemon=True
    )
    server_thread.start()
    time.sleep(0.5)


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    video_path = os.path.join(base_dir, "pothole_video.mp4")

    if not os.path.exists(video_path):
        print(f"[ERROR] Video file not found at: {video_path}")
        sys.exit(1)

    print("=" * 75)
    print("      REAL-WORLD ROAD VIDEO POTHOLE DETECTION & VEHICLE SAFETY        ")
    print("=" * 75)
    print(f"[VIDEO] Loading user video: {video_path}")
    print("[1/2] Starting Mock ESP8266 vehicle controller on port 8080...")
    start_mock_in_background()

    print("[2/2] Launching real-time AI detection engine on video stream...")
    print("[INFO] Press 'q' or ESC in the preview window to exit cleanly.\n")

    # Pass command-line arguments to use video file and mock controller
    sys.argv = [
        "detect_stream.py",
        "--stream", video_path,
        "--mock"
    ]
    run_detector()
