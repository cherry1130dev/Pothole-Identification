"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  Live Web Streaming Dashboard & Telemetry Server
FILE:    web_server.py
======================================================================================

DESCRIPTION:
Provides a modern, high-performance web dashboard accessible from any web browser
on the local network (laptop, mobile phone, tablet):
1. Live HD Video Stream (/video_feed):
   - Real-time video with AI pothole detections, confidence scores, and ROI overlay.
2. Real-Time Telemetry & Radar Gauges (/api/telemetry):
   - Ultrasonic distances (Front, Left, Right in cm)
   - Vehicle driving state (CRUISE, SLOW, AVOID, BLOCKED)
   - Current motor PWM speed and direction
   - Connected Wi-Fi geolocation & map link
3. Interactive Vehicle Controls:
   - Switch between Autonomous (AI) and Manual Drive modes
   - Directional control keypad (WASD / Arrow Keys / Touch buttons)
   - Toggle AI Model vs Classical OpenCV Fallback
======================================================================================
"""

import os
import sys
import time
import json
import socket
import threading
import argparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import cv2
import numpy as np

# System configuration & modules
from config import (
    STREAM_URL,
    ESP8266_IP,
    ESP8266_BASE_URL,
    MODEL_PATH,
    PYTORCH_MODEL_PATH,
    CONFIDENCE_THRESHOLD,
    ROI_Y_MIN_RATIO,
    CONFIRM_FRAMES_N,
    CLEAR_FRAMES_M,
    DISPLAY_SCALE
)
from detect_stream import FreshFrameCapture, PotholeAIModel
from pothole_fallback import ClassicalPotholeDetector
from esp_client import ESP8266Client
from location_service import get_wifi_location, preload_location_async
from telegram_notifier import TelegramNotifier

# Global shared state
state_lock = threading.Lock()
frame_lock = threading.Lock()
global_jpeg = None
global_telemetry = {
    "mode": "AUTO",
    "state": "CRUISE",
    "speed": 180,
    "pothole": 0,
    "front_cm": 60.0,
    "left_cm": 60.0,
    "right_cm": 60.0,
    "fps": 0.0,
    "detector": "Classical OpenCV Fallback",
    "camera_connected": False,
    "camera_url": STREAM_URL,
    "vehicle_url": ESP8266_BASE_URL,
    "location": {
        "city": "Locating...",
        "region": "",
        "lat": 0.0,
        "lon": 0.0,
        "maps_url": "#"
    }
}

ai_control_state = {
    "use_ai": False,
    "stream_url": STREAM_URL,
    "pothole_active_state": 0
}


def get_lan_ip():
    """Detects the primary LAN IP on Wi-Fi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


# ======================================================================================
# BACKGROUND AI INFERENCE PIPELINE
# ======================================================================================

def run_ai_pipeline(stream_url: str, esp_client: ESP8266Client):
    global global_jpeg, global_telemetry

    print(f"[PIPELINE] Initializing video grabber: {stream_url}")
    grabber = FreshFrameCapture(stream_url)

    ai_model = PotholeAIModel(MODEL_PATH, PYTORCH_MODEL_PATH)
    fallback_detector = ClassicalPotholeDetector()
    telegram_notifier = TelegramNotifier()

    use_ai = ai_model.is_available()
    with state_lock:
        ai_control_state["use_ai"] = use_ai
        global_telemetry["detector"] = ("YOLOv8n (" + ai_model.backend + ")") if use_ai else "Classical OpenCV Fallback"
        global_telemetry["camera_url"] = stream_url

    consecutive_detections = 0
    consecutive_clears = 0
    pothole_state = 0

    fps_start = time.time()
    frame_count = 0
    current_fps = 0.0
    last_status_query = 0

    while True:
        connected, frame = grabber.read()

        # Update telemetry from physical ESP8266 every 500 ms
        if time.time() - last_status_query >= 0.5:
            last_status_query = time.time()
            try:
                status = esp_client.get_status()
                if status:
                    with state_lock:
                        global_telemetry["mode"] = status.get("mode", global_telemetry["mode"])
                        global_telemetry["state"] = status.get("state", global_telemetry["state"])
                        global_telemetry["speed"] = status.get("speed", global_telemetry["speed"])
                        global_telemetry["front_cm"] = status.get("front_cm", global_telemetry["front_cm"])
                        global_telemetry["left_cm"] = status.get("left_cm", global_telemetry["left_cm"])
                        global_telemetry["right_cm"] = status.get("right_cm", global_telemetry["right_cm"])
            except Exception:
                pass

        if not connected or frame is None:
            with state_lock:
                global_telemetry["camera_connected"] = False
            # Generate standby placeholder frame
            standby = np.zeros((240, 320, 3), dtype=np.uint8)
            cv2.putText(standby, "Connecting to Video Stream...", (25, 110),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.50, (0, 165, 255), 1, cv2.LINE_AA)
            cv2.putText(standby, f"{stream_url}", (25, 140),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (180, 180, 180), 1, cv2.LINE_AA)
            _, encoded = cv2.imencode('.jpg', standby, [cv2.IMWRITE_JPEG_QUALITY, 75])
            with frame_lock:
                global_jpeg = encoded.tobytes()
            time.sleep(0.1)
            continue

        with state_lock:
            global_telemetry["camera_connected"] = True

        frame_count += 1
        if time.time() - fps_start >= 1.0:
            current_fps = frame_count / (time.time() - fps_start)
            frame_count = 0
            fps_start = time.time()
            with state_lock:
                global_telemetry["fps"] = round(current_fps, 1)

        frame_h, frame_w = frame.shape[:2]
        with state_lock:
            active_use_ai = ai_control_state["use_ai"]

        # Run Detection
        detections = []
        if active_use_ai and ai_model.is_available():
            raw_dets = ai_model.predict(frame, CONFIDENCE_THRESHOLD)
            roi_y_min = int(frame_h * ROI_Y_MIN_RATIO)
            for d in raw_dets:
                _, cy = d["centroid"]
                if cy >= roi_y_min:
                    detections.append(d)
        else:
            detections, _ = fallback_detector.detect(frame)

        # Hysteresis Filter
        if len(detections) > 0:
            consecutive_detections += 1
            consecutive_clears = 0
            if consecutive_detections >= CONFIRM_FRAMES_N:
                if pothole_state == 0:
                    pothole_state = 1
                    print(f"\n[ALERT] Pothole confirmed! Throttling to SLOW on {esp_client.base_url}")
                    esp_client.set_pothole_state(1)
                    loc = get_wifi_location()
                    best_conf = max([d.get("confidence", 0.70) for d in detections], default=0.75)
                    telegram_notifier.notify_pothole(loc, confidence=best_conf)
        else:
            consecutive_clears += 1
            consecutive_detections = 0
            if consecutive_clears >= CLEAR_FRAMES_M:
                if pothole_state == 1:
                    pothole_state = 0
                    print(f"\n[CLEAR] Road cleared. Resuming CRUISE on {esp_client.base_url}")
                    esp_client.set_pothole_state(0)

        with state_lock:
            global_telemetry["pothole"] = pothole_state

        # Annotate HUD Frame
        annotated = frame.copy()

        # ROI Guide
        roi_y = int(frame_h * ROI_Y_MIN_RATIO)
        cv2.line(annotated, (0, roi_y), (frame_w, roi_y), (0, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(annotated, "ROAD ROI (Inspection Zone)", (8, roi_y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1, cv2.LINE_AA)

        # Draw Detected Potholes
        for det in detections:
            x, y, w, h = det["bbox"]
            conf = det["confidence"]
            box_color = (0, 0, 255) if pothole_state == 1 else (0, 140, 255)
            cv2.rectangle(annotated, (x, y), (x + w, y + h), box_color, 2)
            label = f"POTHOLE {int(conf * 100)}%"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
            cv2.rectangle(annotated, (x, max(0, y - lh - 6)), (x + lw + 4, y), box_color, -1)
            cv2.putText(annotated, label, (x + 2, max(lh + 2, y - 4)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
            cv2.circle(annotated, det["centroid"], 3, (0, 255, 0), -1)

        # Top Status HUD
        overlay = annotated.copy()
        cv2.rectangle(overlay, (0, 0), (frame_w, 28), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.65, annotated, 0.35, 0, annotated)

        status_text = "STATE: SLOW (POTHOLE)" if pothole_state == 1 else "STATE: CRUISE (CLEAR)"
        status_color = (0, 60, 255) if pothole_state == 1 else (0, 230, 0)
        cv2.putText(annotated, status_text, (8, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, status_color, 1, cv2.LINE_AA)
        cv2.putText(annotated, f"FPS: {current_fps:.1f}", (frame_w - 70, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1, cv2.LINE_AA)

        # Encode to JPEG
        _, encoded = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        with frame_lock:
            global_jpeg = encoded.tobytes()

        time.sleep(0.01)


# ======================================================================================
# EMBEDDED DASHBOARD HTML & UI
# ======================================================================================

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AI Pothole Identification & Autonomous Vehicle Control</title>
<style>
  :root {
    --bg-dark: #0f141c;
    --card-bg: #18202c;
    --card-border: #243042;
    --accent-cyan: #00e5ff;
    --accent-green: #00e676;
    --accent-red: #ff1744;
    --accent-yellow: #ffab00;
    --text-primary: #f0f4f8;
    --text-muted: #8b9bb4;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background-color: var(--bg-dark);
    color: var(--text-primary);
    padding: 16px;
    min-height: 100vh;
  }
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px;
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    margin-bottom: 16px;
  }
  .brand { display: flex; align-items: center; gap: 12px; }
  .pulse-dot {
    width: 12px; height: 12px; background: var(--accent-green);
    border-radius: 50%; box-shadow: 0 0 10px var(--accent-green);
    animation: pulse 1.8s infinite;
  }
  @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.4; transform: scale(0.85); } }
  h1 { font-size: 1.15rem; font-weight: 700; letter-spacing: 0.5px; }
  .sub-tag { font-size: 0.78rem; color: var(--text-muted); }
  .badge {
    padding: 4px 10px; border-radius: 20px; font-size: 0.75rem;
    font-weight: 600; text-transform: uppercase; background: rgba(0, 229, 255, 0.12);
    color: var(--accent-cyan); border: 1px solid rgba(0, 229, 255, 0.3);
  }

  .main-layout {
    display: grid;
    grid-template-columns: 1.6fr 1fr;
    gap: 16px;
  }
  @media (max-width: 900px) {
    .main-layout { grid-template-columns: 1fr; }
  }

  .card {
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
  }
  .card-title {
    font-size: 0.85rem; font-weight: 700; text-transform: uppercase;
    letter-spacing: 1px; color: var(--text-muted); margin-bottom: 12px;
    display: flex; justify-content: space-between; align-items: center;
  }

  .video-container {
    position: relative;
    width: 100%;
    background: #000;
    border-radius: 8px;
    overflow: hidden;
    border: 1px solid var(--card-border);
    aspect-ratio: 4 / 3;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .video-stream {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .state-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-radius: 8px;
    margin-top: 12px;
    font-weight: 700;
    font-size: 0.95rem;
    background: rgba(0, 230, 118, 0.12);
    border: 1px solid var(--accent-green);
    color: var(--accent-green);
    transition: all 0.3s;
  }
  .state-banner.slow {
    background: rgba(255, 23, 68, 0.15);
    border-color: var(--accent-red);
    color: var(--accent-red);
  }

  .radar-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    text-align: center;
    margin-top: 8px;
  }
  .radar-box {
    background: #111722;
    padding: 10px;
    border-radius: 8px;
    border: 1px solid var(--card-border);
  }
  .radar-label { font-size: 0.72rem; color: var(--text-muted); text-transform: uppercase; }
  .radar-val { font-size: 1.3rem; font-weight: 800; color: var(--accent-cyan); margin: 4px 0; }
  .radar-bar {
    height: 6px; background: #222d3d; border-radius: 3px; overflow: hidden;
  }
  .radar-fill {
    height: 100%; width: 100%; background: var(--accent-cyan);
    transition: width 0.3s, background-color 0.3s;
  }

  .d-pad {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
    max-width: 220px;
    margin: 10px auto;
  }
  .btn-drive {
    background: #202b3a;
    border: 1px solid var(--card-border);
    color: var(--text-primary);
    padding: 14px;
    border-radius: 8px;
    font-size: 1.1rem;
    font-weight: bold;
    cursor: pointer;
    transition: all 0.15s;
    user-select: none;
  }
  .btn-drive:active { background: var(--accent-cyan); color: #000; transform: scale(0.96); }
  .btn-stop { background: rgba(255, 23, 68, 0.2); border-color: var(--accent-red); color: var(--accent-red); }
  .btn-stop:active { background: var(--accent-red); color: #fff; }

  .mode-row { display: flex; gap: 8px; margin-bottom: 12px; }
  .btn-toggle {
    flex: 1; padding: 10px; border-radius: 8px; font-weight: 700;
    cursor: pointer; border: 1px solid var(--card-border); background: #111722;
    color: var(--text-muted); transition: 0.2s;
  }
  .btn-toggle.active {
    background: var(--accent-cyan); color: #000; border-color: var(--accent-cyan);
  }

  .meta-row {
    display: flex; justify-content: space-between; font-size: 0.82rem;
    padding: 6px 0; border-bottom: 1px solid rgba(255,255,255,0.05);
  }
  .meta-row:last-child { border-bottom: none; }
  .meta-label { color: var(--text-muted); }
  .meta-val { font-weight: 600; }
  a { color: var(--accent-cyan); text-decoration: none; }
  a:hover { text-decoration: underline; }
</style>
</head>
<body>

<header>
  <div class="brand">
    <div class="pulse-dot"></div>
    <div>
      <h1>AI POTHOLE IDENTIFICATION & SAFETY SYSTEM</h1>
      <div class="sub-tag">LIVE ROBOTIC TELEMETRY & COMPUTER VISION STREAM</div>
    </div>
  </div>
  <div class="badge" id="net-badge">CONNECTED: 10.135.210.9</div>
</header>

<div class="main-layout">
  <!-- Left Column: Video Stream & State Banner -->
  <div>
    <div class="card">
      <div class="card-title">
        <span>LIVE AI VIDEO STREAM</span>
        <span id="fps-counter" style="color: var(--accent-cyan);">FPS: --</span>
      </div>
      <div class="video-container">
        <img class="video-stream" src="/video_feed" alt="Live Camera Video Stream">
      </div>
      <div class="state-banner" id="state-banner">
        <span id="banner-state-text">VEHICLE STATE: CRUISE (CLEAR ROAD)</span>
        <span id="banner-speed-text">PWM: 180</span>
      </div>
    </div>

    <!-- Geolocation Card -->
    <div class="card">
      <div class="card-title">INCIDENT GEOLOCATION (WIFI POSITIONING)</div>
      <div class="meta-row">
        <span class="meta-label">Location:</span>
        <span class="meta-val" id="geo-location">Detecting...</span>
      </div>
      <div class="meta-row">
        <span class="meta-label">Coordinates:</span>
        <span class="meta-val" id="geo-coords">-- , --</span>
      </div>
      <div class="meta-row">
        <span class="meta-label">Google Maps Pin:</span>
        <span class="meta-val"><a id="geo-link" href="#" target="_blank">Open in Maps &nearr;</a></span>
      </div>
    </div>
  </div>

  <!-- Right Column: Ultrasonic Radar & Driving Controls -->
  <div>
    <!-- Ultrasonic Radar Array -->
    <div class="card">
      <div class="card-title">
        <span>ULTRASONIC RADAR ARRAY</span>
        <span style="font-size: 0.7rem; color: var(--text-muted);">MAX 60 CM</span>
      </div>
      <div class="radar-grid">
        <div class="radar-box">
          <div class="radar-label">Left Sensor</div>
          <div class="radar-val" id="radar-left">-- cm</div>
          <div class="radar-bar"><div class="radar-fill" id="fill-left"></div></div>
        </div>
        <div class="radar-box">
          <div class="radar-label">Front Sensor</div>
          <div class="radar-val" id="radar-front">-- cm</div>
          <div class="radar-bar"><div class="radar-fill" id="fill-front"></div></div>
        </div>
        <div class="radar-box">
          <div class="radar-label">Right Sensor</div>
          <div class="radar-val" id="radar-right">-- cm</div>
          <div class="radar-bar"><div class="radar-fill" id="fill-right"></div></div>
        </div>
      </div>
    </div>

    <!-- Vehicle Mode & Directional Controls -->
    <div class="card">
      <div class="card-title">MOTION & ACTUATION CONTROLLER</div>
      <div class="mode-row">
        <button class="btn-toggle active" id="btn-mode-auto" onclick="setVehicleMode(1)">AUTONOMOUS AI</button>
        <button class="btn-toggle" id="btn-mode-manual" onclick="setVehicleMode(0)">MANUAL PILOT</button>
      </div>

      <div class="d-pad">
        <div></div>
        <button class="btn-drive" onclick="sendDriveCmd('F')">&#9650;<br><span style="font-size:0.6rem">FWD</span></button>
        <div></div>
        <button class="btn-drive" onclick="sendDriveCmd('L')">&#9664;<br><span style="font-size:0.6rem">LEFT</span></button>
        <button class="btn-drive btn-stop" onclick="sendDriveCmd('S')">&#9632;<br><span style="font-size:0.6rem">STOP</span></button>
        <button class="btn-drive" onclick="sendDriveCmd('R')">&#9654;<br><span style="font-size:0.6rem">RIGHT</span></button>
        <div></div>
        <button class="btn-drive" onclick="sendDriveCmd('B')">&#9660;<br><span style="font-size:0.6rem">REV</span></button>
        <div></div>
      </div>
      <div style="text-align: center; font-size: 0.72rem; color: var(--text-muted); margin-top: 6px;">
        Keyboard: [W, A, S, D] or Arrow Keys to steer in manual mode
      </div>
    </div>

    <!-- System Diagnostics -->
    <div class="card">
      <div class="card-title">SYSTEM STATUS</div>
      <div class="meta-row">
        <span class="meta-label">Camera Node:</span>
        <span class="meta-val" id="meta-cam" style="color: var(--accent-cyan)">http://10.135.210.5:81/stream</span>
      </div>
      <div class="meta-row">
        <span class="meta-label">ESP8266 Vehicle:</span>
        <span class="meta-val" id="meta-esp">http://10.135.210.9:80</span>
      </div>
      <div class="meta-row">
        <span class="meta-label">Active Detector:</span>
        <span class="meta-val" id="meta-detector">Classical OpenCV Fallback</span>
      </div>
      <div class="meta-row">
        <span class="meta-label">Pothole Status:</span>
        <span class="meta-val" id="meta-pothole">CLEAR (0)</span>
      </div>
    </div>
  </div>
</div>

<script>
  let isManual = false;

  function updateColor(elem, fillElem, dist) {
    elem.innerText = dist.toFixed(1) + " cm";
    let pct = Math.min(100, Math.max(5, (dist / 60.0) * 100));
    fillElem.style.width = pct + "%";
    if (dist < 20) {
      fillElem.style.backgroundColor = "var(--accent-red)";
      elem.style.color = "var(--accent-red)";
    } else if (dist < 30) {
      fillElem.style.backgroundColor = "var(--accent-yellow)";
      elem.style.color = "var(--accent-yellow)";
    } else {
      fillElem.style.backgroundColor = "var(--accent-cyan)";
      elem.style.color = "var(--accent-cyan)";
    }
  }

  async function pollTelemetry() {
    try {
      let res = await fetch('/api/telemetry');
      let data = await res.json();

      document.getElementById('fps-counter').innerText = 'FPS: ' + data.fps;

      // Radar
      updateColor(document.getElementById('radar-left'), document.getElementById('fill-left'), data.left_cm);
      updateColor(document.getElementById('radar-front'), document.getElementById('fill-front'), data.front_cm);
      updateColor(document.getElementById('radar-right'), document.getElementById('fill-right'), data.right_cm);

      // State banner
      let banner = document.getElementById('state-banner');
      let bText = document.getElementById('banner-state-text');
      let bSpeed = document.getElementById('banner-speed-text');
      bSpeed.innerText = 'PWM: ' + data.speed;

      if (data.pothole === 1 || data.state === 'SLOW') {
        banner.className = 'state-banner slow';
        bText.innerText = 'VEHICLE STATE: SLOW (POTHOLE DETECTED)';
        document.getElementById('meta-pothole').innerText = 'DETECTED (SLOW)';
        document.getElementById('meta-pothole').style.color = 'var(--accent-red)';
      } else {
        banner.className = 'state-banner';
        bText.innerText = 'VEHICLE STATE: ' + data.state + ' (ALL CLEAR)';
        document.getElementById('meta-pothole').innerText = 'CLEAR (0)';
        document.getElementById('meta-pothole').style.color = 'var(--accent-green)';
      }

      // Geolocation
      if (data.location && data.location.city) {
        document.getElementById('geo-location').innerText = data.location.city + ', ' + data.location.region;
        document.getElementById('geo-coords').innerText = data.location.lat.toFixed(4) + ', ' + data.location.lon.toFixed(4);
        document.getElementById('geo-link').href = data.location.maps_url;
      }

      document.getElementById('meta-detector').innerText = data.detector;

      // Mode sync
      if (data.mode === 'MANUAL') {
        document.getElementById('btn-mode-manual').className = 'btn-toggle active';
        document.getElementById('btn-mode-auto').className = 'btn-toggle';
        isManual = true;
      } else {
        document.getElementById('btn-mode-auto').className = 'btn-toggle active';
        document.getElementById('btn-mode-manual').className = 'btn-toggle';
        isManual = false;
      }
    } catch (e) {
      console.warn("Telemetry poll error:", e);
    }
  }

  async function sendDriveCmd(cmd) {
    try {
      await fetch('/api/drive?cmd=' + cmd, { method: 'POST' });
    } catch(e) { console.error(e); }
  }

  async function setVehicleMode(isAuto) {
    try {
      await fetch('/api/mode?auto=' + isAuto, { method: 'POST' });
    } catch(e) { console.error(e); }
  }

  // Keyboard driving controls
  window.addEventListener('keydown', (e) => {
    if (['ArrowUp', 'w', 'W'].includes(e.key)) sendDriveCmd('F');
    else if (['ArrowDown', 's', 'S'].includes(e.key)) sendDriveCmd('B');
    else if (['ArrowLeft', 'a', 'A'].includes(e.key)) sendDriveCmd('L');
    else if (['ArrowRight', 'd', 'D'].includes(e.key)) sendDriveCmd('R');
    else if ([' '].includes(e.key)) sendDriveCmd('S');
  });

  setInterval(pollTelemetry, 300);
  pollTelemetry();
</script>
</body>
</html>
"""


# ======================================================================================
# HTTP SERVER & API REQUEST HANDLER
# ======================================================================================

class DashboardHTTPHandler(BaseHTTPRequestHandler):
    esp_client = None

    def log_message(self, format, *args):
        # Silence routine HTTP access logs for clean console
        return

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/" or parsed.path == "/index.html":
            content = DASHBOARD_HTML.encode('utf-8')
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        elif parsed.path == "/video_feed":
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()

            try:
                while True:
                    with frame_lock:
                        jpeg_bytes = global_jpeg
                    if jpeg_bytes:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_bytes + b"\r\n")
                    time.sleep(0.04)  # ~25 FPS delivery
            except (ConnectionResetError, BrokenPipeError):
                pass
            return

        elif parsed.path == "/api/telemetry":
            with state_lock:
                telemetry_copy = dict(global_telemetry)
            payload = json.dumps(telemetry_copy).encode('utf-8')
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        if parsed.path == "/api/drive":
            cmd = params.get("cmd", ["S"])[0].upper()
            if self.esp_client:
                self.esp_client.send_drive_command(cmd)
            self._send_json({"status": "ok", "cmd": cmd})
            return

        elif parsed.path == "/api/mode":
            auto_val = int(params.get("auto", ["1"])[0])
            if self.esp_client:
                self.esp_client.set_mode(auto_val)
            self._send_json({"status": "ok", "auto": auto_val})
            return

        self.send_response(404)
        self.end_headers()

    def _send_json(self, data: dict):
        payload = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


# ======================================================================================
# MAIN ENTRYPOINT
# ======================================================================================

def main():
    parser = argparse.ArgumentParser(description="Web Dashboard for AI Pothole Detection & Vehicle Control")
    parser.add_argument("--port", type=int, default=5000, help="Web dashboard port (default: 5000)")
    parser.add_argument("--stream", type=str, default=STREAM_URL, help=f"Video stream URL (default: {STREAM_URL})")
    parser.add_argument("--esp-ip", type=str, default=ESP8266_IP, help=f"ESP8266 IP address (default: {ESP8266_IP})")
    args = parser.parse_args()

    esp_base = f"http://{args.esp_ip}:80"
    esp_client = ESP8266Client(base_url=esp_base)
    DashboardHTTPHandler.esp_client = esp_client

    lan_ip = get_lan_ip()

    print("=" * 75)
    print("      AI POTHOLE IDENTIFICATION & SMART ROBOTIC WEB DASHBOARD           ")
    print("=" * 75)
    print(f"[TARGET] ESP8266 Vehicle Controller: {esp_base}")
    print(f"[TARGET] ESP32-CAM Video Stream:    {args.stream}")
    print(f"\n[DASHBOARD READY] Open your browser and navigate to:")
    print(f"   --> Local (This PC):  http://localhost:{args.port}")
    print(f"   --> Mobile / Network: http://{lan_ip}:{args.port}\n")
    print("=" * 75)

    # Initialize Location asynchronously
    def _async_loc():
        try:
            loc = get_wifi_location()
            with state_lock:
                global_telemetry["location"] = loc
        except Exception:
            pass
    threading.Thread(target=_async_loc, daemon=True).start()

    # Spawn AI Vision Pipeline Thread
    ai_thread = threading.Thread(target=run_ai_pipeline, args=(args.stream, esp_client), daemon=True)
    ai_thread.start()

    # Start Multi-threaded Web Server
    server = ThreadingHTTPServer(("0.0.0.0", args.port), DashboardHTTPHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Stopping Web Dashboard...")
        server.server_close()


if __name__ == "__main__":
    main()
