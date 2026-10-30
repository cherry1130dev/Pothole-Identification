"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  Telegram Bot Incident Alerting & Map Location Dispatcher
FILE:    telegram_notifier.py
======================================================================================

DESCRIPTION:
Asynchronous Telegram alert client that transmits pothole hazard alerts and live
geographic map pins to your Telegram account or channel:
1. Dispatches rich formatted Markdown alert messages containing:
   - Defect type & vision detection confidence
   - Wi-Fi network AP identifiers (SSID & BSSID)
   - City, Region, Country and exact GPS coordinates
   - Clickable Google Maps URL
   - Vehicle action (speed throttled for safe crossing).
2. Dispatches native interactive Telegram Map Pins via 'sendLocation'.
3. Thread-safe background execution prevents video frame lag.
4. Intelligent cooldown rate-limiting prevents notification flooding.
5. Graceful offline simulation when placeholder tokens are present.
======================================================================================
"""

import time
import logging
import threading
import requests
from typing import Dict, Any, Optional
from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_ALERT_COOLDOWN_SEC
)

logger = logging.getLogger("TelegramNotifier")


class TelegramNotifier:
    """Dispatches asynchronous alerts with Wi-Fi geolocation to the Telegram Bot API."""

    def __init__(
        self,
        token: str = TELEGRAM_BOT_TOKEN,
        chat_id: str = TELEGRAM_CHAT_ID,
        cooldown_sec: float = TELEGRAM_ALERT_COOLDOWN_SEC
    ):
        self.token = token.strip() if token else ""
        self.chat_id = str(chat_id).strip() if chat_id else ""
        self.cooldown_sec = cooldown_sec
        self.last_alert_time = 0.0
        self.lock = threading.Lock()
        self.session = requests.Session()

    def is_configured(self) -> bool:
        """Returns True if user has configured valid non-placeholder credentials."""
        if not self.token or not self.chat_id:
            return False
        if "YOUR_" in self.token or "YOUR_" in self.chat_id:
            return False
        return True

    def notify_pothole(self, location: Dict[str, Any], confidence: float = 0.75, force: bool = False) -> None:
        """
        Dispatches pothole detection alert with location asynchronously.
        Guarded by cooldown rate-limiting.
        """
        with self.lock:
            now = time.time()
            if not force and (now - self.last_alert_time < self.cooldown_sec):
                # Suppress spam within cooldown window
                return
            self.last_alert_time = now

        # Run dispatch in a background daemon thread
        t = threading.Thread(
            target=self._dispatch_alert,
            args=(location, confidence),
            daemon=True
        )
        t.start()

    def _dispatch_alert(self, loc: Dict[str, Any], conf: float) -> None:
        """Background worker that executes the HTTPS POST requests."""
        lat = loc.get("latitude", 0.0)
        lon = loc.get("longitude", 0.0)
        city = loc.get("city", "Unknown City")
        region = loc.get("region", "Unknown Region")
        country = loc.get("country", "")
        ssid = loc.get("wifi_ssid", "Local Wi-Fi")
        bssid = loc.get("wifi_bssid", "N/A")
        maps_url = loc.get("maps_url", f"https://www.google.com/maps?q={lat},{lon}")
        ts = loc.get("timestamp", time.strftime("%Y-%m-%d %H:%M:%S"))

        conf_pct = int(conf * 100)
        accuracy_str = loc.get("accuracy", "N/A")
        source_str = loc.get("source", "Wi-Fi Positioning")
        address_str = loc.get("address", "")
        postcode = loc.get("postcode", "")

        loc_header = f"{city}, {region}"
        if postcode:
            loc_header += f" - {postcode}"

        # Formatted Rich HTML alert message
        message_text = (
            "⚠️ <b>POTHOLE HAZARD DETECTED!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎯 <b>Vision Confidence:</b> <code>{conf_pct}%</code>\n"
            f"📍 <b>Location:</b> {loc_header}\n"
        )
        if address_str and address_str != loc_header:
            # Add shortened street/road info if available
            short_addr = address_str.split(",")[0].strip()
            message_text += f"🛣️ <b>Road/Area:</b> {short_addr}\n"

        message_text += (
            f"🌐 <b>Exact GPS:</b> <code>{lat:.6f}° N, {lon:.6f}° E</code>\n"
            f"🎯 <b>Fix Accuracy:</b> {accuracy_str}\n"
            f"📡 <b>Provider:</b> {source_str}\n"
            f"📶 <b>Wi-Fi Network:</b> {ssid} (<code>{bssid}</code>)\n"
            f"🕒 <b>Detected At:</b> <code>{ts}</code>\n"
            "⚡ <b>Vehicle Action:</b> Deceleration to 110 PWM (Crawl Mode)\n"
            f"🗺️ <a href=\"{maps_url}\">Open Navigation in Google Maps</a>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━"
        )

        if not self.is_configured():
            # Terminal Preview Simulation Mode
            print("\n" + "╔" + "═" * 68 + "╗")
            print("║             TELEGRAM ALERT SIMULATOR (Wi-Fi Location)              ║")
            print("╠" + "═" * 68 + "╣")
            print(f"║ ⚠️  DEFECT: Pothole detected ({conf_pct}% confidence)")
            print(f"║ 📍  LOCATION: {loc_header}")
            print(f"║ 🌐  GPS COORDS: {lat:.6f}, {lon:.6f}")
            print(f"║ 🎯  ACCURACY: {accuracy_str}")
            print(f"║ 📡  PROVIDER: {source_str}")
            print(f"║ 📶  WI-FI AP: {ssid} ({bssid})")
            print(f"║ 🗺️   MAPS URL: {maps_url}")
            print(f"║ ⚡  VEHICLE: Speed throttled to 110 PWM (crawl mode)")
            print("╠" + "═" * 68 + "╣")
            print("║ [TIP] To receive real notifications on your phone, set your        ║")
            print("║       TELEGRAM_BOT_TOKEN and CHAT_ID in laptop_ai/config.py        ║")
            print("╚" + "═" * 68 + "╝\n")
            return

        # 1. Send Rich HTML Message via sendMessage
        send_msg_url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }

        try:
            resp = self.session.post(send_msg_url, json=payload, timeout=4.0)
            if resp.status_code == 200:
                print(f"\n[TELEGRAM] ✅ Pothole notification delivered to Telegram (Chat ID: {self.chat_id})")
            else:
                print(f"[TELEGRAM] Warning: Telegram API returned HTTP {resp.status_code}: {resp.text}")
        except Exception as exc:
            print(f"[TELEGRAM] Connection error sending text alert: {exc}")

        # 2. Send Interactive Map Pin via sendLocation
        if lat != 0.0 and lon != 0.0:
            send_loc_url = f"https://api.telegram.org/bot{self.token}/sendLocation"
            loc_payload = {
                "chat_id": self.chat_id,
                "latitude": lat,
                "longitude": lon
            }
            try:
                self.session.post(send_loc_url, json=loc_payload, timeout=4.0)
            except Exception:
                pass

    def test_connection(self) -> bool:
        """Sends a diagnostic test message to verify Telegram credentials."""
        if not self.is_configured():
            print("[TELEGRAM TEST] Credentials are placeholders. Edit laptop_ai/config.py first.")
            return False

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": "🚗 *Pothole Avoidance System*: Telegram Alert Service Online & Verified!",
            "parse_mode": "Markdown"
        }
        try:
            r = self.session.post(url, json=payload, timeout=5.0)
            return r.status_code == 200
        except Exception as exc:
            print(f"[TELEGRAM TEST] Error: {exc}")
            return False
