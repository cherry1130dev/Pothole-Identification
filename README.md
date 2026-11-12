# AI-Driven Pothole Identification and Smart Obstacle Avoidance System using ESP32-CAM

Autonomous robotic vehicle featuring real-time pothole detection, ultrasonic obstacle avoidance, an all-in-one ESP8266 web control & AI dashboard, and live Telegram incident alerts over a shared hotspot (`Pothole car`).

---

## Quick Navigation

All firmware, documentation, wiring diagrams, and optional laptop AI tools are located in [`pothole-avoidance/`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/):

- 📖 **[System Manual](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/README.md)**
- ⚡ **[Wiring Diagram & Pinout](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/docs/wiring_diagram.md)**
- 📐 **[System Architecture](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/docs/architecture.md)**

---

## Subsystem Directories

1. **ESP8266 Main Vehicle & Dashboard Controller**:
   [`pothole-avoidance/esp8266_controller/`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/esp8266_controller/)
   - [`config.h`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/esp8266_controller/config.h): Hotspot credentials (`Pothole car`), motor/ultrasonic pins, and avoidance timings.
   - [`dashboard.h`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/esp8266_controller/dashboard.h): Web dashboard with live video, browser-side pothole image processing, ultrasonic radar, manual/autonomous controls, and Telegram photo alerts.
   - [`esp8266_controller.ino`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/esp8266_controller/esp8266_controller.ino): L298N motor driver, 3x HC-SR04 obstacle avoidance, UDP camera auto-discovery, and HTTP/REST server.

2. **ESP32-CAM Video Streamer**:
   [`pothole-avoidance/esp32cam_stream/esp32cam_stream.ino`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/esp32cam_stream/esp32cam_stream.ino)
   - MJPEG stream on port 81 (`/stream`), `/ping` endpoint, 180° hardware orientation fix, and UDP discovery beacon.

3. **Optional Laptop Python AI Engine**:
   [`pothole-avoidance/laptop_ai/`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/)
   - [`detect_stream.py`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/detect_stream.py): Desktop OpenCV/YOLOv8n stream engine and REST controller.
   - [`pothole_fallback.py`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/pothole_fallback.py): Classical OpenCV pothole detector.
   - [`esp_client.py`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/esp_client.py), [`location_service.py`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/location_service.py), [`telegram_notifier.py`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/telegram_notifier.py), [`config.py`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/config.py), [`requirements.txt`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/requirements.txt).
