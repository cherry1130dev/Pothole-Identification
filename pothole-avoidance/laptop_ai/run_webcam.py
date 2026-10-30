"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  Laptop Webcam Interactive Live Demo
FILE:    run_webcam.py
======================================================================================

DESCRIPTION:
Launches the real-time AI pothole detection engine using your LAPTOP WEBCAM:
1. Spawns the Mock ESP8266 controller server in the background (http://127.0.0.1:8080).
2. Connects to your laptop camera (Webcam Index 0) with DirectShow acceleration.
3. Renders the interactive Heads-Up Display (HUD) on your screen:
   - Green bounding boxes around potholes in the Road ROI (lower half of screen)
   - Real-time confidence score and FPS
   - Top banner indicating vehicle state (CRUISE vs SLOW)
   - Dispatches state updates (SLOW down / resume CRUISE) to the controller!

TESTING TIP:
   Point your webcam towards the floor or hold a dark circular object / black coaster /
   printed black circle in the lower half of your webcam view to trigger pothole detection!

CONTROLS IN PREVIEW WINDOW:
   'q' or ESC : Exit cleanly
   'd'        : Toggle dark-crater contour mask overlay
   'f'        : Toggle Classical OpenCV / YOLOv8
   's'        : Query mock vehicle status
======================================================================================
"""

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
    print("=" * 75)
    print("      STARTING LIVE POTHOLE DETECTION ON LAPTOP WEBCAM                 ")
    print("=" * 75)
    print("[1/2] Starting Mock ESP8266 vehicle controller on port 8080...")
    start_mock_in_background()

    print("[2/2] Opening laptop webcam (Index 0) and launching AI Engine...")
    print("[TIP] Hold a dark circular object in the lower half of your camera view.")
    print("[TIP] Press 'q' in the camera window to quit.\n")

    # Pass command-line arguments to use webcam '0' and mock controller
    sys.argv = [
        "detect_stream.py",
        "--stream", "0",
        "--mock"
    ]
    run_detector()
