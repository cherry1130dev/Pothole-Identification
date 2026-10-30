"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  Mock ESP8266 Vehicle Controller Simulator & Mobile GPS Gateway (SITL)
FILE:    mock_esp8266.py
======================================================================================

DESCRIPTION:
Software-in-the-Loop (SITL) simulator and Mobile High-Accuracy GPS Receiver:
1. Exposes vehicle HTTP REST endpoints:
    GET /pothole?state=0|1
    GET /status
    GET /mode?auto=0|1
    GET /drive?cmd=F|B|L|R|S
2. Mobile High-Accuracy GPS Gateway:
    GET  /gps.html   -> Serves responsive mobile web application that captures
                        satellite GNSS from any smartphone browser.
    POST /api/gps    -> Ingests live satellite latitude, longitude, and accuracy.
    GET  /api/gps    -> Supplies live coordinates to the AI vision engine.
======================================================================================
"""

import time
import json
import socket
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# Simulated Vehicle State
vehicle_state = {
    "mode": "AUTO",
    "state": "CRUISE",
    "speed": 180,
    "pothole": 0,
    "front_cm": 85.0,
    "left_cm": 65.0,
    "right_cm": 70.0,
    "uptime_s": 0
}

# Live Mobile Phone Satellite GPS Cache
live_phone_gps = {
    "lat": None,
    "lon": None,
    "accuracy": None,
    "speed": None,
    "timestamp": 0
}

start_time = time.time()
state_lock = threading.Lock()
gps_lock = threading.Lock()


def get_local_lan_ip():
    """Detects the primary LAN IP address on the local Wi-Fi network."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


GPS_HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Satellite GPS Transmitter</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
        body { background: #0f172a; color: #f8fafc; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; padding: 20px; }
        .card { background: #1e293b; border: 1px solid #334155; border-radius: 20px; width: 100%; max-width: 420px; padding: 26px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); text-align: center; }
        .badge { display: inline-block; padding: 6px 14px; border-radius: 999px; font-size: 13px; font-weight: 600; margin-bottom: 16px; }
        .badge.active { background: #064e3b; color: #34d399; border: 1px solid #059669; }
        .badge.waiting { background: #78350f; color: #fbbf24; border: 1px solid #d97706; }
        h1 { font-size: 22px; font-weight: 700; margin-bottom: 6px; }
        p.desc { font-size: 14px; color: #94a3b8; margin-bottom: 22px; }
        .metric-box { background: #0f172a; border-radius: 14px; padding: 14px; margin-bottom: 12px; text-align: left; }
        .metric-label { font-size: 12px; color: #64748b; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        .metric-value { font-size: 20px; font-weight: 700; color: #38bdf8; margin-top: 4px; word-break: break-all; }
        .accuracy { color: #4ade80; font-size: 14px; font-weight: 600; }
        .btn { background: #2563eb; color: #fff; border: none; padding: 14px 20px; border-radius: 12px; font-size: 16px; font-weight: 600; width: 100%; cursor: pointer; margin-top: 10px; }
        .btn:active { background: #1d4ed8; }
        .footer { font-size: 12px; color: #64748b; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="card">
        <div id="statusBadge" class="badge waiting">Connecting GPS...</div>
        <h1>Satellite GPS Transmitter</h1>
        <p class="desc">Streaming high-accuracy satellite coordinates directly to the Pothole Identification System.</p>

        <div class="metric-box">
            <div class="metric-label">Latitude</div>
            <div id="latVal" class="metric-value">--.------</div>
        </div>

        <div class="metric-box">
            <div class="metric-label">Longitude</div>
            <div id="lonVal" class="metric-value">--.------</div>
        </div>

        <div class="metric-box">
            <div class="metric-label">GPS Accuracy</div>
            <div id="accVal" class="metric-value accuracy">Acquiring satellites...</div>
        </div>

        <button class="btn" onclick="startTracking()">Force GPS Refresh</button>
        <p class="footer">Keep this screen open while driving to provide meter-level coordinates.</p>
    </div>

    <script>
        let watchId = null;

        function sendCoords(lat, lon, acc, speed) {
            fetch('/api/gps', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ lat: lat, lon: lon, accuracy: acc, speed: speed })
            }).then(() => {
                document.getElementById('statusBadge').className = 'badge active';
                document.getElementById('statusBadge').innerText = 'Transmitting Live GPS 🟢';
            }).catch(e => {
                document.getElementById('statusBadge').className = 'badge waiting';
                document.getElementById('statusBadge').innerText = 'Network Lag 🟠';
            });
        }

        function onPosition(pos) {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            const acc = pos.coords.accuracy;
            const spd = pos.coords.speed || 0;

            document.getElementById('latVal').innerText = lat.toFixed(6);
            document.getElementById('lonVal').innerText = lon.toFixed(6);
            document.getElementById('accVal').innerText = '± ' + acc.toFixed(1) + ' meters';

            sendCoords(lat, lon, acc, spd);
        }

        function onError(err) {
            document.getElementById('statusBadge').className = 'badge waiting';
            document.getElementById('statusBadge').innerText = 'Location Permission Needed ⚠️';
            alert('Please allow Location Access in your browser to transmit satellite coordinates.');
        }

        function startTracking() {
            if ("geolocation" in navigator) {
                if (watchId) navigator.geolocation.clearWatch(watchId);
                watchId = navigator.geolocation.watchPosition(onPosition, onError, {
                    enableHighAccuracy: true,
                    timeout: 8000,
                    maximumAge: 1000
                });
            } else {
                alert('Geolocation is not supported by your browser.');
            }
        }

        window.onload = startTracking;
    </script>
</body>
</html>
"""


class MockESP8266Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        global vehicle_state, live_phone_gps
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        uptime = int(time.time() - start_time)

        if path == "/gps.html":
            resp = GPS_HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        elif path == "/api/gps":
            with gps_lock:
                now = time.time()
                is_fresh = (now - live_phone_gps["timestamp"] < 45.0) if live_phone_gps["timestamp"] else False
                resp_data = dict(live_phone_gps)
                resp_data["is_fresh"] = is_fresh

            resp = json.dumps(resp_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        elif path == "/pothole":
            state_param = query.get("state", [None])[0]
            if state_param in ("0", "1"):
                new_pothole = int(state_param)
                with state_lock:
                    vehicle_state["pothole"] = new_pothole
                    if vehicle_state["mode"] == "AUTO":
                        if new_pothole == 1:
                            vehicle_state["state"] = "SLOW"
                            vehicle_state["speed"] = 110
                            print(f"\n🚗 [MOCK ESP8266] >>> STATE: SLOW (Pothole Detected!) | Motors PWM: 110 (~43%)")
                        else:
                            vehicle_state["state"] = "CRUISE"
                            vehicle_state["speed"] = 180
                            print(f"\n🚗 [MOCK ESP8266] >>> STATE: CRUISE (Road Clear)        | Motors PWM: 180 (~70%)")

                resp = json.dumps({"status": "ok", "pothole": new_pothole}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            else:
                self.send_error(400, "Missing or invalid 'state' parameter")

        elif path == "/status":
            with state_lock:
                vehicle_state["uptime_s"] = uptime
                resp_data = dict(vehicle_state)

            resp = json.dumps(resp_data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        elif path == "/mode":
            auto_param = query.get("auto", [None])[0]
            if auto_param in ("0", "1"):
                mode_str = "AUTO" if auto_param == "1" else "MANUAL"
                with state_lock:
                    vehicle_state["mode"] = mode_str
                    if mode_str == "MANUAL":
                        vehicle_state["speed"] = 0
                print(f"[MOCK ESP8266] Mode changed to: {mode_str}")
                resp = json.dumps({"status": "ok", "mode": mode_str}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            else:
                self.send_error(400, "Invalid 'auto' param")

        elif path == "/drive":
            cmd = query.get("cmd", [None])[0]
            if cmd:
                cmd = cmd.upper()
                print(f"[MOCK ESP8266] Manual drive command: {cmd}")
                resp = json.dumps({"status": "ok", "cmd": cmd}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            else:
                self.send_error(400, "Missing 'cmd' param")

        else:
            self.send_error(404, "Endpoint Not Found")

    def do_POST(self):
        global live_phone_gps
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/api/gps":
            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)
            try:
                gps_json = json.loads(post_data.decode("utf-8"))
                with gps_lock:
                    live_phone_gps["lat"] = float(gps_json.get("lat", 0.0))
                    live_phone_gps["lon"] = float(gps_json.get("lon", 0.0))
                    live_phone_gps["accuracy"] = float(gps_json.get("accuracy", 10.0))
                    live_phone_gps["speed"] = float(gps_json.get("speed", 0.0))
                    live_phone_gps["timestamp"] = time.time()

                resp = json.dumps({"status": "ok"}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            except Exception as e:
                self.send_error(400, f"Malformed JSON: {e}")
        else:
            self.send_error(404, "Endpoint Not Found")

    def do_OPTIONS(self):
        # Handle CORS pre-flight from mobile browsers
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def run_mock_server(host="0.0.0.0", port=8080):
    server_address = (host, port)
    httpd = HTTPServer(server_address, MockESP8266Handler)
    lan_ip = get_local_lan_ip()

    print("=" * 75)
    print("      MOCK ESP8266 VEHICLE CONTROLLER & PRECISION GPS GATEWAY (SITL)   ")
    print("=" * 75)
    print(f"[REST API]   Listening on: http://127.0.0.1:{port}")
    print(f"[MOBILE GPS] Precision GPS Web App: http://{lan_ip}:{port}/gps.html")
    print("             (Open this link on your smartphone for sub-3 meter GPS accuracy!)")
    print("=" * 75 + "\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[MOCK] Server stopping...")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock ESP8266 Vehicle Controller Simulator")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host binding (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port binding (default: 8080)")
    args = parser.parse_args()
    run_mock_server(args.host, args.port)
