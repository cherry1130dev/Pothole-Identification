"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  Wi-Fi Geolocation & Telegram Notification Diagnostic Tool
FILE:    test_telegram_location.py
======================================================================================

DESCRIPTION:
Diagnostic utility to test Wi-Fi geolocation resolution and verify delivery of
Telegram pothole notifications with interactive Google Maps navigation links.

USAGE:
    python test_telegram_location.py
======================================================================================
"""

import sys
from location_service import get_wifi_location
from telegram_notifier import TelegramNotifier


def main():
    print("=" * 75)
    print("      WI-FI GEOLOCATION & TELEGRAM NOTIFICATION DIAGNOSTIC TOOL       ")
    print("=" * 75)

    print("\n[1/2] Resolving current Wi-Fi Geolocation...")
    loc = get_wifi_location(force_refresh=True)

    print(f"  📍 City/Region:  {loc.get('city')}, {loc.get('region')}, {loc.get('country')}")
    print(f"  🌐 Coordinates:  Latitude {loc.get('latitude'):.4f}, Longitude {loc.get('longitude'):.4f}")
    print(f"  📶 Wi-Fi AP:     SSID '{loc.get('wifi_ssid')}' | BSSID '{loc.get('wifi_bssid')}'")
    print(f"  🗺️  Google Maps:  {loc.get('maps_url')}")
    print(f"  📡 Network ISP:  {loc.get('isp')}")

    print("\n[2/2] Testing Telegram Notification Dispatcher...")
    notifier = TelegramNotifier()

    if notifier.is_configured():
        print(f"[STATUS] Bot credentials detected! Dispatching test location alert to Chat ID: {notifier.chat_id}...")
        notifier.notify_pothole(loc, confidence=0.88, force=True)
        print("[SUCCESS] Check your Telegram app for the alert message and interactive map pin!")
    else:
        print("[NOTICE] Running in Simulation Mode (Credentials in config.py are placeholders).")
        print("         Displaying simulated Telegram payload below:")
        notifier.notify_pothole(loc, confidence=0.88, force=True)
        print("\n[TIP] To receive real alerts on your phone:")
        print("  1. Create a bot using @BotFather (see telegram_setup.md)")
        print("  2. Paste your BOT_TOKEN and CHAT_ID into laptop_ai/config.py")

    print("\n" + "=" * 75)
    print("      DIAGNOSTIC TEST COMPLETED SUCCESSFULLY!                         ")
    print("=" * 75)


if __name__ == "__main__":
    main()
