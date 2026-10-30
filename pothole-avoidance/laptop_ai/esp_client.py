"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  ESP8266 Asynchronous REST Client
FILE:    esp_client.py
======================================================================================

DESCRIPTION:
Thread-safe, non-blocking HTTP REST client that communicates with the ESP8266
vehicle motion controller.
Features:
- State-change filtering: Only transmits HTTP requests when the state actually changes.
- Asynchronous dispatch: Dispatches requests in background worker threads with short
  timeouts so video ingestion and GUI rendering never freeze.
- Provides diagnostic helpers to query vehicle status and send manual drive commands.
======================================================================================
"""

import threading
import logging
import requests
from typing import Optional, Dict, Any
from config import (
    ESP8266_BASE_URL,
    POTHOLE_ENDPOINT,
    STATUS_ENDPOINT,
    MODE_ENDPOINT,
    DRIVE_ENDPOINT,
    HTTP_CONNECT_TIMEOUT_SEC,
    HTTP_READ_TIMEOUT_SEC
)

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("ESPClient")


class ESP8266Client:
    """Thread-safe non-blocking HTTP client for communicating with the ESP8266 controller."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url.rstrip("/") if base_url else ESP8266_BASE_URL
        self._last_pothole_state: Optional[int] = None
        self._lock = threading.Lock()
        self._session = requests.Session()

    def set_pothole_state(self, state: int, force: bool = False) -> None:
        """
        Signals the ESP8266 whether a pothole is detected (1) or road is clear (0).
        Transmits ONLY on state transitions unless forced.
        Executes asynchronously in a background thread to prevent blocking video frames.
        """
        with self._lock:
            if not force and self._last_pothole_state == state:
                return  # State unchanged; suppress redundant network transmission
            self._last_pothole_state = state

        # Spawn non-blocking background daemon thread
        dispatch_thread = threading.Thread(
            target=self._dispatch_pothole_request,
            args=(state,),
            daemon=True
        )
        dispatch_thread.start()

    def _dispatch_pothole_request(self, state: int) -> None:
        """Internal worker function executed in background thread."""
        params = {"state": state}
        endpoint = f"{self.base_url}/pothole"
        try:
            response = self._session.get(
                endpoint,
                params=params,
                timeout=(HTTP_CONNECT_TIMEOUT_SEC, HTTP_READ_TIMEOUT_SEC)
            )
            if response.status_code == 200:
                logger.info("Sent %s?state=%d -> ESP8266 acknowledged (200 OK)", endpoint, state)
            else:
                logger.warning("ESP8266 returned HTTP %d for state %d", response.status_code, state)
        except requests.exceptions.Timeout:
            logger.warning("HTTP Timeout sending pothole state %d to ESP8266", state)
        except requests.exceptions.RequestException as exc:
            logger.error("Failed to connect to ESP8266 controller: %s", exc)

    def get_status(self) -> Optional[Dict[str, Any]]:
        """
        Synchronously queries the current vehicle telemetry from GET /status.
        Returns a dictionary or None on failure.
        """
        try:
            response = self._session.get(
                f"{self.base_url}/status",
                timeout=(HTTP_CONNECT_TIMEOUT_SEC, HTTP_READ_TIMEOUT_SEC)
            )
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException:
            pass
        return None

    def set_mode(self, is_auto: bool) -> bool:
        """Toggles between Autonomous (1) and Manual (0) mode."""
        try:
            response = self._session.get(
                f"{self.base_url}/mode",
                params={"auto": 1 if is_auto else 0},
                timeout=(HTTP_CONNECT_TIMEOUT_SEC, HTTP_READ_TIMEOUT_SEC)
            )
            return response.status_code == 200
        except requests.exceptions.RequestException as exc:
            logger.error("Failed to set mode: %s", exc)
            return False

    def send_drive_command(self, cmd: str) -> bool:
        """Sends manual drive command (F, B, L, R, S) in manual mode."""
        try:
            response = self._session.get(
                f"{self.base_url}/drive",
                params={"cmd": cmd.upper()},
                timeout=(HTTP_CONNECT_TIMEOUT_SEC, HTTP_READ_TIMEOUT_SEC)
            )
            return response.status_code == 200
        except requests.exceptions.RequestException as exc:
            logger.error("Failed to send drive command: %s", exc)
            return False

    def reset_state_tracker(self) -> None:
        """Resets cached state to force transmission on the next cycle."""
        with self._lock:
            self._last_pothole_state = None
