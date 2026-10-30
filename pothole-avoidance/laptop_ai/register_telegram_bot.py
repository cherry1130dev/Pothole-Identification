"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  One-Click Telegram Bot Pair & Chat ID Auto-Registrar
FILE:    register_telegram_bot.py
======================================================================================

DESCRIPTION:
Automatically pairs your Telegram Bot (@vsm_pothole_bot) with your chat:
1. Connects to Telegram API with your bot token.
2. Waits for you to tap 'Start' or send any message to the bot.
3. Automatically captures your unique CHAT_ID.
4. Updates 'laptop_ai/config.py' and 'esp8266_controller/config.h'.
5. Immediately sends a verification welcome alert + live map pin to your phone!
======================================================================================
"""

import sys
import os
import time
import re
import requests
from location_service import get_wifi_location

BOT_TOKEN = "9138292752:AAFdtNKDLzFQVDEwx8mSyhJ1kMcRNApC0xg"
BOT_USERNAME = "vsm_pothole_bot"


def update_config_files(chat_id: str):
    """Saves the detected Chat ID into config.py and config.h automatically."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Update laptop_ai/config.py
    py_config_path = os.path.join(base_dir, "config.py")
    if os.path.exists(py_config_path):
        with open(py_config_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(r'TELEGRAM_CHAT_ID\s*=\s*["\'].*?["\']', f'TELEGRAM_CHAT_ID   = "{chat_id}"', content)
        with open(py_config_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[CONFIG] ✅ Saved Chat ID to: laptop_ai/config.py")

    # 2. Update esp8266_controller/config.h
    h_config_path = os.path.join(base_dir, "..", "esp8266_controller", "config.h")
    if os.path.exists(h_config_path):
        with open(h_config_path, "r", encoding="utf-8") as f:
            content = f.read()
        content = re.sub(r'#define\s+TELEGRAM_CHAT_ID\s+["\'].*?["\']', f'#define TELEGRAM_CHAT_ID        "{chat_id}"', content)
        with open(h_config_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[CONFIG] ✅ Saved Chat ID to: esp8266_controller/config.h")


def send_welcome_verification(chat_id: str, user_name: str):
    """Sends verification alert with current Wi-Fi location and interactive map pin."""
    loc = get_wifi_location()
    lat = loc.get("latitude", 17.0052)
    lon = loc.get("longitude", 81.7778)
    city = loc.get("city", "Local Area")
    region = loc.get("region", "Region")
    country = loc.get("country", "")
    ssid = loc.get("wifi_ssid", "Wi-Fi")
    bssid = loc.get("wifi_bssid", "N/A")
    maps_url = loc.get("maps_url", f"https://www.google.com/maps?q={lat},{lon}")

    msg = (
        f"🚗 *Welcome to Pothole Safety Robot, {user_name}!* 🎉\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ *Telegram Alerts Successfully Linked!*\n\n"
        "📍 *Current Station*: " + city + ", " + region + ", " + country + "\n"
        f"🌐 *Coordinates*: `{lat:.4f}, {lon:.4f}`\n"
        f"📶 *Connected Wi-Fi*: {ssid} (`{bssid}`)\n"
        f"🗺️ [Open Station on Google Maps]({maps_url})\n\n"
        "Whenever a pothole is identified on the road, an instant safety alert with GPS coordinates and an interactive map pin will be sent right here!\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )

    url_msg = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url_msg, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"}, timeout=5.0)

    url_loc = f"https://api.telegram.org/bot{BOT_TOKEN}/sendLocation"
    requests.post(url_loc, json={"chat_id": chat_id, "latitude": lat, "longitude": lon}, timeout=5.0)


def main():
    print("=" * 75)
    print("          TELEGRAM BOT PAIRING & AUTO-REGISTRATION WIZARD              ")
    print("=" * 75)
    print(f"[BOT] Connected to: @{BOT_USERNAME} (Pothole Detector)")
    print("\n👉 ACTION REQUIRED ON YOUR PHONE OR TELEGRAM APP:")
    print(f"   1. Open Telegram and search for:  @{BOT_USERNAME}")
    print(f"      (Direct link: https://t.me/{BOT_USERNAME})")
    print("   2. Click 'START' or send any message (e.g. 'hi') to the bot.")
    print("\n[LISTENER] Waiting for your message...")

    session = requests.Session()
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"

    timeout_seconds = 600  # 10 minutes timeout
    start_time = time.time()

    while time.time() - start_time < timeout_seconds:
        try:
            resp = session.get(url, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("result", [])
                if results:
                    # Found message!
                    last_update = results[-1]
                    msg = last_update.get("message") or last_update.get("channel_post") or {}
                    chat = msg.get("chat", {})
                    chat_id = str(chat.get("id", ""))
                    user_name = chat.get("first_name", "Driver")

                    if chat_id:
                        print("\n" + "═" * 75)
                        print(f"🎉 SUCCESS! Received message from: {user_name} (Chat ID: {chat_id})")
                        print("═" * 75)

                        update_config_files(chat_id)
                        print("[ALERT] Sending welcome verification and location map pin to your Telegram...")
                        send_welcome_verification(chat_id, user_name)
                        print("[SUCCESS] Check your Telegram now! Alert successfully delivered!")
                        print("=" * 75)
                        return
        except Exception:
            pass

        time.sleep(2.0)
        sys.stdout.write(".")
        sys.stdout.flush()

    print("\n[TIMEOUT] No message received within 2 minutes.")
    print(f"Please open https://t.me/{BOT_USERNAME} in Telegram, send 'hi', and run this script again.")


if __name__ == "__main__":
    main()
