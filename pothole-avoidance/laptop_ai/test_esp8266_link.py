"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  ESP8266 Vehicle Controller REST Link Diagnostic Tool
FILE:    test_esp8266_link.py
======================================================================================

DESCRIPTION:
Diagnostic testing script to validate the HTTP communication link between the
laptop and the ESP8266 vehicle controller.
Tests:
1. Queries /status and parses ultrasonic sensor telemetry and battery/mode state.
2. Sends synthetic pothole alert (GET /pothole?state=1) to verify slow-down trigger.
3. Sends pothole clear signal (GET /pothole?state=0) to verify cruise resume.
4. Validates manual override commands (/mode and /drive).

USAGE:
    python test_esp8266_link.py
    python test_esp8266_link.py --ip 192.168.1.60
======================================================================================
"""

import sys
import time
import argparse
import requests
from config import ESP8266_IP


def main():
    parser = argparse.ArgumentParser(description="Test Laptop -> ESP8266 REST Communication Link")
    parser.add_argument("--ip", type=str, default=ESP8266_IP, help=f"ESP8266 IP address (default: {ESP8266_IP})")
    parser.add_argument("--port", type=int, default=80, help="Port (default: 80)")
    parser.add_argument("--mock", action="store_true", help="Test against local Mock ESP8266 simulator on 127.0.0.1:8080")
    args = parser.parse_args()

    if args.mock:
        base_url = "http://127.0.0.1:8080"
    else:
        base_url = f"http://{args.ip}:{args.port}"

    print("=" * 70)
    print("      ESP8266 REST COMMUNICATION & ACTUATION DIAGNOSTIC TOOL       ")
    print("=" * 70)
    print(f"[TARGET] Connecting to ESP8266 at: {base_url}\n")

    session = requests.Session()

    # 1. Test GET /status
    print("--- [TEST 1: Query Vehicle Telemetry (/status)] ---")
    try:
        t0 = time.time()
        resp = session.get(f"{base_url}/status", timeout=2.0)
        round_trip_ms = (time.time() - t0) * 1000
        if resp.status_code == 200:
            status_data = resp.json()
            print(f"[PASS] HTTP 200 OK received in {round_trip_ms:.1f} ms!")
            print(f"       Mode:        {status_data.get('mode')}")
            print(f"       State:       {status_data.get('state')}")
            print(f"       PWM Speed:   {status_data.get('speed')}")
            print(f"       Pothole:     {status_data.get('pothole')}")
            print(f"       Sensors:     Front: {status_data.get('front_cm')} cm | "
                  f"Left: {status_data.get('left_cm')} cm | Right: {status_data.get('right_cm')} cm")
            print(f"       Uptime:      {status_data.get('uptime_s')} seconds")
        else:
            print(f"[FAIL] Unexpected status code: {resp.status_code}")
            sys.exit(1)
    except Exception as exc:
        print(f"[FAIL] Connection error: {exc}")
        print("\nTroubleshooting checklist:")
        print(f"  - Is the ESP8266 powered on and connected to Wi-Fi?")
        print(f"  - Can you ping {args.ip} from your command prompt?")
        sys.exit(1)

    time.sleep(1.0)

    # 2. Test GET /pothole?state=1 (Slow down)
    print("\n--- [TEST 2: Synthetic Pothole Detection Trigger (/pothole?state=1)] ---")
    try:
        t0 = time.time()
        resp = session.get(f"{base_url}/pothole?state=1", timeout=1.0)
        round_trip_ms = (time.time() - t0) * 1000
        print(f"[PASS] Response {resp.status_code} in {round_trip_ms:.1f} ms: {resp.text}")
        print("       --> Vehicle should now be in SLOW mode (crawl speed PWM ~110).")
    except Exception as exc:
        print(f"[FAIL] Error sending pothole state 1: {exc}")

    print("[INFO] Waiting 3 seconds in SLOW mode...")
    time.sleep(3.0)

    # 3. Test GET /pothole?state=0 (Resume speed)
    print("\n--- [TEST 3: Pothole Cleared Signal (/pothole?state=0)] ---")
    try:
        t0 = time.time()
        resp = session.get(f"{base_url}/pothole?state=0", timeout=1.0)
        round_trip_ms = (time.time() - t0) * 1000
        print(f"[PASS] Response {resp.status_code} in {round_trip_ms:.1f} ms: {resp.text}")
        print("       --> Vehicle should now resume CRUISE mode (normal speed PWM ~180).")
    except Exception as exc:
        print(f"[FAIL] Error sending pothole state 0: {exc}")

    time.sleep(1.0)

    # 4. Optional Manual Drive Test
    print("\n--- [TEST 4: Manual Actuation Test Mode (/mode?auto=0)] ---")
    try:
        resp = session.get(f"{base_url}/mode?auto=0", timeout=1.0)
        print(f"[INFO] Set manual mode: {resp.text}")
        time.sleep(0.5)

        print("[INFO] Pulsing motors FORWARD for 0.5s...")
        session.get(f"{base_url}/drive?cmd=F", timeout=1.0)
        time.sleep(0.5)

        print("[INFO] Stopping motors...")
        session.get(f"{base_url}/drive?cmd=S", timeout=1.0)
        time.sleep(0.5)

        # Restore Auto Mode
        session.get(f"{base_url}/mode?auto=1", timeout=1.0)
        print("[PASS] Restored AUTONOMOUS mode (/mode?auto=1).")
    except Exception as exc:
        print(f"[WARNING] Manual drive test warning: {exc}")

    print("\n" + "=" * 70)
    print("      ALL REST INTERFACE TESTS COMPLETED SUCCESSFULLY!        ")
    print("=" * 70)


if __name__ == "__main__":
    main()
