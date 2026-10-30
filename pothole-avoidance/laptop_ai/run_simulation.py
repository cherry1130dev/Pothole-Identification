"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  One-Click Interactive Simulation & Demonstration Runner
FILE:    run_simulation.py
======================================================================================

DESCRIPTION:
Launches the complete end-to-end system in simulated Software-in-the-Loop (SITL) mode:
1. Starts the Mock ESP8266 Vehicle Controller server on http://127.0.0.1:8080 in a background thread.
2. Starts the real-time AI computer vision engine with simulated roadway video feed.
3. Renders the interactive Heads-Up Display (HUD) showing:
   - Road surface with moving lane dividers
   - Potholes approaching and entering the road inspection ROI
   - Bounding boxes, confidence scores, and detection counters
   - Live HTTP control signals (SLOW <-> CRUISE) sent to the controller.

CONTROLS IN PREVIEW WINDOW:
   'q' or ESC : Exit cleanly
   'f'        : Toggle Classical OpenCV / YOLOv8
   'd'        : Toggle crater mask debug overlay
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
    print("     STARTING FULL END-TO-END SYSTEM SIMULATION & DEMO (SITL)          ")
    print("=" * 75)
    print("[1/2] Starting Mock ESP8266 vehicle controller on port 8080...")
    start_mock_in_background()

    print("[2/2] Launching real-time AI detection engine with Road Simulator...")
    # Inject CLI arguments to run against simulation and mock controller
    sys.argv = [
        "detect_stream.py",
        "--stream", "sim",
        "--mock"
    ]
    run_detector()
