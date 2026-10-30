"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  High-Precision Multi-Tier Geolocation Service
FILE:    location_service.py
======================================================================================

DESCRIPTION:
Resolves high-accuracy, meter-level roadway GPS coordinates using multi-tier priority:

  [TIER 1] Exact Physical Calibration:
           If EXACT_GPS_OVERRIDE_ENABLED = True in config.py, uses exact measured
           street coordinates.

  [TIER 2] Live Smartphone Satellite GNSS Gateway (Sub-3 Meter Accuracy):
           Connects to the local GPS receiver (http://127.0.0.1:8080/api/gps).
           When any smartphone opens http://<LAPTOP_IP>:8080/gps.html, real-time
           satellite coordinates are streamed directly from the phone's GPS chip!

  [TIER 3] Windows 10/11 Native Wi-Fi Positioning Service (~50-150m Accuracy):
           Queries Windows WinRT Geolocator via Wi-Fi BSSID database triangulation.
           No API key required; native OS location service.

  [TIER 4] Google Geolocation API (Nearby Wi-Fi AP Triangulation ~15 Meter Accuracy):
           Scans all visible Wi-Fi BSSIDs via 'netsh' and queries Google's database.

  [TIER 5] Wi-Fi Regional Gateway Geo-IP Fallback:
           Queries multi-provider fallback endpoints (ipinfo.io, ipapi.co).
======================================================================================
"""

import os
import re
import time
import json
import subprocess
import threading
import requests
from typing import Dict, Any, Optional

# Import configuration settings
from config import (
    USE_WINDOWS_GEOLOCATION,
    ENABLE_PHONE_GPS_STREAM,
    PHONE_GPS_ENDPOINT,
    GOOGLE_GEOLOCATION_API_KEY,
    ENABLE_REVERSE_GEOCODING,
    EXACT_GPS_OVERRIDE_ENABLED,
    EXACT_GPS_LATITUDE,
    EXACT_GPS_LONGITUDE,
    EXACT_GPS_SITE_NAME
)

_cached_location: Optional[Dict[str, Any]] = None
_last_fetch_time: float = 0
_CACHE_TTL_SEC: float = 60.0  # Cache for 60 seconds
_lock = threading.Lock()
_reverse_geocode_cache: Dict[str, Dict[str, str]] = {}


def get_local_wifi_details() -> Dict[str, str]:
    """Extracts active connected Wi-Fi SSID and BSSID."""
    wifi_info = {
        "ssid": "Unknown Wi-Fi",
        "bssid": "N/A",
        "signal": "N/A"
    }
    try:
        out = subprocess.check_output(
            "netsh wlan show interfaces",
            shell=True,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=2.0
        )
        ssid_m = re.search(r"^\s*SSID\s*:\s*(.+)$", out, re.M)
        bssid_m = re.search(r"^\s*AP BSSID\s*:\s*(.+)$", out, re.M)
        sig_m = re.search(r"^\s*Signal\s*:\s*(.+)$", out, re.M)

        if ssid_m: wifi_info["ssid"] = ssid_m.group(1).strip()
        if bssid_m: wifi_info["bssid"] = bssid_m.group(1).strip()
        if sig_m: wifi_info["signal"] = sig_m.group(1).strip()
    except Exception:
        pass
    return wifi_info


def scan_nearby_wifi_access_points() -> list:
    """Scans all visible Wi-Fi access points and signal levels for triangulation."""
    aps = []
    try:
        out = subprocess.check_output(
            "netsh wlan show networks mode=bssid",
            shell=True,
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3.0
        )
        bssids = re.findall(r"BSSID\s+\d+\s*:\s*([0-9a-fA-F:]+)", out)
        signals = re.findall(r"Signal\s*:\s*(\d+)%", out)
        channels = re.findall(r"Channel\s*:\s*(\d+)", out)

        for b, s, c in zip(bssids, signals, channels):
            dbm = int(int(s) / 2.0 - 100)
            aps.append({
                "macAddress": b,
                "signalStrength": dbm,
                "channel": int(c)
            })
    except Exception:
        pass
    return aps


def check_phone_satellite_gps() -> Optional[Dict[str, Any]]:
    """Checks if a smartphone is actively streaming satellite GPS via /api/gps."""
    if not ENABLE_PHONE_GPS_STREAM:
        return None

    try:
        resp = requests.get(PHONE_GPS_ENDPOINT, timeout=1.0)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("is_fresh") and data.get("lat") and data.get("lon"):
                acc = data.get("accuracy", 3.0)
                return {
                    "lat": float(data["lat"]),
                    "lon": float(data["lon"]),
                    "accuracy_str": f"±{acc:.1f} meters (Live Phone Satellite GPS)",
                    "source": "Smartphone Satellite GNSS (High Accuracy)",
                    "is_precise": True
                }
    except Exception:
        pass
    return None


def query_windows_native_location() -> Optional[Dict[str, Any]]:
    """Queries Windows 10/11 native location service (WinRT Geolocator)."""
    if not USE_WINDOWS_GEOLOCATION:
        return None

    try:
        script_path = os.path.join(os.path.dirname(__file__), "get_win_location.ps1")
        if not os.path.exists(script_path):
            return None

        res = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script_path],
            capture_output=True,
            text=True,
            timeout=10.0
        )

        if res.returncode == 0 and res.stdout.strip():
            # Find JSON payload in output
            out = res.stdout.strip()
            # If there's any surrounding text, extract between first { and last }
            start = out.find("{")
            end = out.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(out[start:end + 1])
                if data.get("Success") and data.get("Latitude") and data.get("Longitude"):
                    acc = data.get("AccuracyMeters", 100.0)
                    return {
                        "lat": float(data["Latitude"]),
                        "lon": float(data["Longitude"]),
                        "accuracy_str": f"±{acc:.0f} meters (Windows Wi-Fi Triangulation)",
                        "source": "Windows Native Location Service (Accurate)",
                        "is_precise": True
                    }
    except Exception:
        pass
    return None


def query_google_geolocation_api() -> Optional[Dict[str, Any]]:
    """Triangulates nearby visible Wi-Fi BSSIDs using Google Geolocation API."""
    if not GOOGLE_GEOLOCATION_API_KEY:
        return None

    aps = scan_nearby_wifi_access_points()
    if not aps:
        return None

    url = f"https://www.googleapis.com/geolocation/v1/geolocate?key={GOOGLE_GEOLOCATION_API_KEY}"
    payload = {
        "considerIp": True,
        "wifiAccessPoints": aps
    }

    try:
        resp = requests.post(url, json=payload, timeout=4.0)
        if resp.status_code == 200:
            res = resp.json()
            loc = res.get("location", {})
            acc = res.get("accuracy", 15.0)
            if loc.get("lat") and loc.get("lng"):
                return {
                    "lat": float(loc["lat"]),
                    "lon": float(loc["lng"]),
                    "accuracy_str": f"±{acc:.1f} meters (Google Wi-Fi Triangulation)",
                    "source": "Google Geolocation API (Multi-AP Triangulation)",
                    "is_precise": True
                }
    except Exception:
        pass
    return None


def reverse_geocode(lat: float, lon: float) -> Dict[str, str]:
    """Resolves roadway, town, district, and state from coordinates using OpenStreetMap Nominatim."""
    key = f"{lat:.3f},{lon:.3f}"
    if key in _reverse_geocode_cache:
        return _reverse_geocode_cache[key]

    result = {
        "address": "Local Roadway",
        "town": "Local Area",
        "district": "",
        "state": "Andhra Pradesh",
        "postcode": "",
        "country": "India"
    }

    if not ENABLE_REVERSE_GEOCODING:
        return result

    try:
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat:.6f}&lon={lon:.6f}&format=json"
        headers = {"User-Agent": "PotholeAvoidanceSystem/2.0 (research-prototype)"}
        r = requests.get(url, headers=headers, timeout=4.0)
        if r.status_code == 200:
            d = r.json()
            addr = d.get("address", {})
            town = (
                addr.get("town") or
                addr.get("city") or
                addr.get("residential") or
                addr.get("suburb") or
                addr.get("village") or
                "Local Area"
            )
            district = addr.get("state_district") or addr.get("county") or ""
            state = addr.get("state") or "Andhra Pradesh"
            postcode = addr.get("postcode") or ""
            disp = d.get("display_name", "")

            result = {
                "address": disp,
                "town": town,
                "district": district,
                "state": state,
                "postcode": postcode,
                "country": addr.get("country", "India")
            }
            _reverse_geocode_cache[key] = result
    except Exception:
        pass
    return result


def fetch_fallback_geo_ip() -> Dict[str, Any]:
    """Fallback IP regional gateway locator."""
    providers = [
        ("https://ipinfo.io/json", lambda d: (float(d["loc"].split(",")[0]), float(d["loc"].split(",")[1]), d.get("city"), d.get("region"), d.get("country"))),
        ("https://ipapi.co/json/", lambda d: (float(d["latitude"]), float(d["longitude"]), d.get("city"), d.get("region"), d.get("country_name")))
    ]
    for url, parser in providers:
        try:
            r = requests.get(url, timeout=3.0)
            if r.status_code == 200:
                lat, lon, city, region, country = parser(r.json())
                if lat != 0.0 and lon != 0.0:
                    return {
                        "lat": lat,
                        "lon": lon,
                        "city": city or "Local City",
                        "region": region or "State",
                        "country": country or "IN",
                        "accuracy_str": "Regional Wi-Fi Gateway (~5 km)",
                        "source": "Wi-Fi Geo-IP Provider",
                        "is_precise": False
                    }
        except Exception:
            continue

    return {
        "lat": 16.839701,
        "lon": 82.029669,
        "city": "Ramachandrapuram",
        "region": "Andhra Pradesh",
        "country": "IN",
        "accuracy_str": "Default Baseline",
        "source": "Default Baseline",
        "is_precise": False
    }


def get_wifi_location(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Returns the most accurate available GPS coordinate and metadata.
    Prioritizes:
    1. Exact Manual Calibration (if enabled in config.py)
    2. Real-Time Smartphone Satellite GPS (sub-3 meter accuracy)
    3. Windows Native Location Service (Wi-Fi Triangulation ~100m accuracy)
    4. Google Wi-Fi Triangulation API (~15 meter accuracy)
    5. Wi-Fi Regional Geo-IP Fallback
    """
    global _cached_location, _last_fetch_time

    with _lock:
        now = time.time()
        if not force_refresh and _cached_location is not None:
            if _cached_location.get("is_precise") and (now - _last_fetch_time < _CACHE_TTL_SEC):
                return dict(_cached_location)

    wifi = get_local_wifi_details()
    city = "Local Area"
    region = "Andhra Pradesh"
    country = "IN"
    district = ""
    postcode = ""
    full_address = ""

    # 1. Tier 1: Exact Manual Calibration
    if EXACT_GPS_OVERRIDE_ENABLED:
        lat = EXACT_GPS_LATITUDE
        lon = EXACT_GPS_LONGITUDE
        accuracy_str = "Meter-Level Precision (Calibrated Reference)"
        source = f"Manual Calibration ({EXACT_GPS_SITE_NAME})"
        is_precise = True

    else:
        # 2. Tier 2: Live Smartphone Satellite GPS
        phone_gps = check_phone_satellite_gps()
        if phone_gps:
            lat = phone_gps["lat"]
            lon = phone_gps["lon"]
            accuracy_str = phone_gps["accuracy_str"]
            source = phone_gps["source"]
            is_precise = True

        else:
            # 3. Tier 3: Windows Native Location Service (Wi-Fi Positioning)
            win_loc = query_windows_native_location()
            if win_loc:
                lat = win_loc["lat"]
                lon = win_loc["lon"]
                accuracy_str = win_loc["accuracy_str"]
                source = win_loc["source"]
                is_precise = True
            else:
                # 4. Tier 4: Google Geolocation Wi-Fi Triangulation
                google_geo = query_google_geolocation_api()
                if google_geo:
                    lat = google_geo["lat"]
                    lon = google_geo["lon"]
                    accuracy_str = google_geo["accuracy_str"]
                    source = google_geo["source"]
                    is_precise = True
                else:
                    # 5. Tier 5: Regional Gateway Fallback
                    fallback = fetch_fallback_geo_ip()
                    lat = fallback["lat"]
                    lon = fallback["lon"]
                    city = fallback["city"]
                    region = fallback["region"]
                    country = fallback["country"]
                    accuracy_str = fallback["accuracy_str"]
                    source = fallback["source"]
                    is_precise = False

    # Reverse geocode to get human-readable street/town/district
    if is_precise:
        rev = reverse_geocode(lat, lon)
        city = rev.get("town", city)
        district = rev.get("district", "")
        region = f"{district}, {rev.get('state', region)}" if district else rev.get("state", region)
        country = rev.get("country", country)
        postcode = rev.get("postcode", "")
        full_address = rev.get("address", "")

    maps_url = f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"

    loc_dict = {
        "latitude": round(lat, 6),
        "longitude": round(lon, 6),
        "city": city,
        "district": district,
        "region": region,
        "country": country,
        "postcode": postcode,
        "address": full_address,
        "accuracy": accuracy_str,
        "source": source,
        "is_precise": is_precise,
        "wifi_ssid": wifi["ssid"],
        "wifi_bssid": wifi["bssid"],
        "wifi_signal": wifi["signal"],
        "maps_url": maps_url,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    with _lock:
        _cached_location = loc_dict
        _last_fetch_time = time.time()

    return dict(loc_dict)


def preload_location_async():
    """Warms up the location resolver in a background thread at startup."""
    t = threading.Thread(target=get_wifi_location, daemon=True)
    t.start()
