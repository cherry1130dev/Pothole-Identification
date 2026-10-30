# AI-Driven Pothole Identification and Smart Obstacle Avoidance System using ESP32-CAM

This repository contains the complete, working prototype implementation of an autonomous robotic vehicle featuring distributed vision-based pothole detection and ultrasonic obstacle avoidance.

---

## Quick Navigation

All source code, documentation, wiring diagrams, and AI pipelines are located in the [`pothole-avoidance/`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/) directory:

- 📖 **[Comprehensive System Manual](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/README.md)**
- ⚡ **[Electrical Schematics & Wiring Diagrams](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/docs/wiring_diagram.md)**
- 📐 **[System Architecture & Finite State Machine Spec](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/docs/architecture.md)**
- 🧪 **[7-Stage Bring-Up & Calibration Test Plan](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/docs/test_plan.md)**
- 🤖 **[Telegram Bot Setup Guide](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/telegram_setup.md)**

---

## Subsystem Directories

1. **ESP32-CAM Video Streamer**:
   [`pothole-avoidance/esp32cam_stream/esp32cam_stream.ino`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/esp32cam_stream/esp32cam_stream.ino)
   - Lightweight MJPEG streaming server on port 81 (`/stream`), QVGA resolution, low latency.

2. **ESP8266 Main Vehicle Controller**:
   [`pothole-avoidance/esp8266_controller/`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/esp8266_controller/)
   - [`config.h`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/esp8266_controller/config.h): Pin assignments, Wi-Fi credentials, Telegram secrets, and thresholds.
   - [`esp8266_controller.ino`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/esp8266_controller/esp8266_controller.ino): Cooperative non-blocking state machine, parallel 3-sensor ultrasonic driver, L298N PWM speed control, and asynchronous Telegram queue.

3. **Laptop AI Vision & Control Engine**:
   [`pothole-avoidance/laptop_ai/`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/)
   - [`detect_stream.py`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/detect_stream.py): Zero-lag threaded stream ingestion, YOLOv8n / OpenCV fallback, HUD overlay, and REST control.
   - [`pothole_fallback.py`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/pothole_fallback.py): Out-of-the-box classical OpenCV dark crater and edge detector.
   - [`train_model.py`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/train_model.py): YOLOv8n fine-tuning pipeline and ONNX CPU acceleration exporter.
   - [`test_stream.py`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/test_stream.py): Stream benchmark and latency diagnostic tool.
   - [`test_esp8266_link.py`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/test_esp8266_link.py): REST endpoint and vehicle actuation diagnostic tool.
   - [`requirements.txt`](file:///c:/Users/chara/Desktop/Pothole%20Identification/pothole-avoidance/laptop_ai/requirements.txt): Python dependencies.
