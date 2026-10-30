"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  ESP32-CAM Video Stream Diagnostic Tool
FILE:    test_stream.py
======================================================================================

DESCRIPTION:
Standalone diagnostic tool to verify the ESP32-CAM MJPEG video stream.
Features:
- Validates network connectivity and HTTP handshake to port 81 (/stream).
- Measures real-time FPS, frame dimensions, and network transmission jitter.
- Renders a live preview window with an on-screen diagnostics HUD.
- Supports command-line override of stream URL.

USAGE:
    python test_stream.py
    python test_stream.py --url http://192.168.1.50:81/stream
======================================================================================
"""

import sys
import time
import argparse
import cv2
from config import STREAM_URL, DISPLAY_SCALE


def main():
    parser = argparse.ArgumentParser(description="ESP32-CAM MJPEG Video Stream Diagnostic Tool")
    parser.add_argument("--url", type=str, default=STREAM_URL, help=f"Stream URL (default: {STREAM_URL})")
    args = parser.parse_args()

    print("=" * 70)
    print("      ESP32-CAM VIDEO STREAM DIAGNOSTIC & LATENCY BENCHMARK        ")
    print("=" * 70)
    print(f"[CONNECT] Attempting connection to: {args.url}")
    print("[INFO] Press 'q' or ESC in the preview window to exit.\n")

    start_connect_time = time.time()
    cap = cv2.VideoCapture(args.url)
    connect_latency_ms = (time.time() - start_connect_time) * 1000

    if not cap.isOpened():
        print(f"[ERROR] Could not open video stream at {args.url}")
        print("[CHECKLIST]:")
        print(" 1. Is the ESP32-CAM powered on and connected to the same Wi-Fi?")
        print(" 2. Can you ping the camera IP address?")
        print(" 3. Open http://<ESP32CAM_IP>:81/stream directly in your browser.")
        sys.exit(1)

    print(f"[SUCCESS] Stream opened in {connect_latency_ms:.1f} ms!")

    # Performance tracking
    frame_count = 0
    fps_start_time = time.time()
    current_fps = 0.0
    last_frame_time = time.time()

    window_name = "ESP32-CAM Stream Diagnostic"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)

    while True:
        frame_read_start = time.time()
        ret, frame = cap.read()
        frame_read_latency_ms = (time.time() - frame_read_start) * 1000

        if not ret or frame is None:
            print("[WARNING] Frame drop or stream disconnected! Retrying in 1s...")
            time.sleep(1.0)
            cap.open(args.url)
            continue

        frame_count += 1
        now = time.time()

        # Update FPS calculation every 1.0 second
        if now - fps_start_time >= 1.0:
            current_fps = frame_count / (now - fps_start_time)
            frame_count = 0
            fps_start_time = now

        height, width = frame.shape[:2]

        # Draw Diagnostics HUD
        hud_text = [
            f"Resolution: {width}x{height}",
            f"FPS: {current_fps:.1f}",
            f"Frame Read Latency: {frame_read_latency_ms:.1f} ms",
            f"Stream: {args.url}"
        ]

        # Upscale for comfortable viewing on high-res displays
        display_frame = cv2.resize(frame, (int(width * DISPLAY_SCALE), int(height * DISPLAY_SCALE)))

        # Overlay text
        y_pos = 28
        for line in hud_text:
            cv2.putText(display_frame, line, (12, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(display_frame, line, (12, y_pos),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 128), 1, cv2.LINE_AA)
            y_pos += 26

        cv2.imshow(window_name, display_frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or key == 27:  # 'q' or ESC
            print("\n[USER] Exit requested. Closing stream.")
            break

    cap.release()
    cv2.destroyAllWindows()
    print("[DONE] Diagnostic completed.")


if __name__ == "__main__":
    main()
