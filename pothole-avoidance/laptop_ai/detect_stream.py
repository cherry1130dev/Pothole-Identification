"""
======================================================================================
PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
MODULE:  Real-Time Video Ingestion, AI Inference & Control Engine
FILE:    detect_stream.py
======================================================================================

DESCRIPTION:
Main application running on the laptop:
1. FreshFrameCapture: Threaded video reader that discards stale frames and guarantees
   zero-latency video ingestion from the ESP32-CAM MJPEG stream.
2. Inference Engine: Executes YOLOv8n (ONNX or PyTorch weights) or seamlessly falls
   back to the Classical OpenCV detector when weights are not present.
3. False-Alarm Rejection:
   - Evaluates only the lower-half road surface ROI (y >= 50% height).
   - N-frame hysteresis: Requires N (default: 3) consecutive detection frames to signal SLOW.
   - M-frame hysteresis: Requires M (default: 10) consecutive clear frames to resume CRUISE.
4. Non-Blocking Control: Dispatches HTTP state transitions to the ESP8266 controller.
5. Interactive Heads-Up Display (HUD): Visualizes bounding boxes, confidence, FPS,
   ROI grid, and current vehicle driving state.

KEYBOARD SHORTCUTS:
    'q' or ESC : Quit application
    'f'        : Toggle between AI Model and Classical OpenCV Fallback
    'd'        : Toggle debug mask overlay
    's'        : Query and log ESP8266 status in terminal
======================================================================================
"""

import os
import sys
import time
import queue
import threading
import argparse
import cv2
import numpy as np

# Import system configuration & submodules
from config import (
    STREAM_URL,
    MODEL_PATH,
    PYTORCH_MODEL_PATH,
    MODEL_INPUT_WIDTH,
    MODEL_INPUT_HEIGHT,
    CONFIDENCE_THRESHOLD,
    AUTO_FALLBACK_TO_OPENCV,
    ROI_Y_MIN_RATIO,
    ROI_Y_MAX_RATIO,
    ROI_X_MIN_RATIO,
    ROI_X_MAX_RATIO,
    CONFIRM_FRAMES_N,
    CLEAR_FRAMES_M,
    WINDOW_TITLE,
    DISPLAY_SCALE,
    RECONNECT_DELAY_SEC
)
from esp_client import ESP8266Client
from pothole_fallback import ClassicalPotholeDetector
from location_service import get_wifi_location, preload_location_async
from telegram_notifier import TelegramNotifier


# ======================================================================================
# THREADED ZERO-LAG FRAME GRABBER
# ======================================================================================

class FreshFrameCapture:
    """
    Spawns a dedicated background thread that continuously pulls frames from the
    OpenCV VideoCapture buffer, always keeping only the single newest frame.
    Supports:
      - HTTP / MJPEG URLs (e.g. http://192.168.1.50:81/stream)
      - Webcams (passing '0', '1', etc.)
      - Built-in Road Simulation (passing 'sim')
      - Video file paths (e.g. test.mp4)
    """

    def __init__(self, src_url: str):
        self.src_url = src_url
        self.is_sim = str(src_url).lower() == "sim"
        self.is_video_file = os.path.isfile(str(src_url))
        self.cap = None
        self.latest_frame = None
        self.lock = threading.Lock()
        self.running = True
        self.last_frame_timestamp = time.time()
        self.frame_delay = 0.033

        if self.is_sim:
            self.connected = True
            print("[STREAM] Running in Road Simulation mode ('sim').")
        else:
            if isinstance(src_url, str) and src_url.isdigit():
                idx = int(src_url)
                self.cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                if not self.cap.isOpened():
                    self.cap = cv2.VideoCapture(idx)
            else:
                self.cap = cv2.VideoCapture(self.src_url)
            self.connected = self.cap.isOpened()
            if self.is_video_file and self.connected:
                fps = self.cap.get(cv2.CAP_PROP_FPS)
                if fps and fps > 0:
                    self.frame_delay = 1.0 / fps
                print(f"[STREAM] Video file detected ({self.src_url}) at {fps:.1f} FPS (auto-loop enabled).")

        self.thread = threading.Thread(target=self._capture_worker, daemon=True)
        self.thread.start()

    def _generate_sim_frame(self, frame_idx: int) -> np.ndarray:
        """Generates a realistic animated roadway with perspective lines and potholes."""
        h, w = 240, 320
        frame = np.full((h, w, 3), 115, dtype=np.uint8)  # Gray asphalt

        # Add road texture
        noise = np.random.randint(-10, 10, (h, w), dtype=np.int16)
        frame_gray = np.clip(frame[:, :, 0].astype(np.int16) + noise, 0, 255).astype(np.uint8)
        frame[:, :, 0] = frame_gray
        frame[:, :, 1] = frame_gray
        frame[:, :, 2] = frame_gray

        # Horizon / Sky upper 40%
        frame[0:95, :] = [180, 160, 130]
        cv2.line(frame, (0, 95), (w, 95), (100, 90, 80), 2)

        # Perspective road boundaries
        cv2.line(frame, (80, 95), (10, h), (220, 220, 220), 3)   # Left shoulder
        cv2.line(frame, (240, 95), (310, h), (220, 220, 220), 3) # Right shoulder

        # Moving dashed centerline
        speed = 5
        offset = (frame_idx * speed) % 50
        for y_dash in range(95 + offset, h, 40):
            # Calculate perspective width and x position
            t = (y_dash - 95) / (h - 95)
            x_center = int(160 + (t * 0))
            dash_len = int(8 + t * 14)
            cv2.line(frame, (x_center, y_dash), (x_center, min(h, y_dash + dash_len)), (0, 220, 255), 2)

        # Periodic Pothole: Appears every 110 frames (~4.5s)
        cycle_len = 110
        cycle_pos = frame_idx % cycle_len
        if 20 <= cycle_pos <= 85:
            # Pothole moves down screen from horizon into ROI
            p_progress = (cycle_pos - 20) / 65.0
            p_y = int(98 + p_progress * 135)
            p_x = int(140 + np.sin(p_progress * 3.14) * 20)
            p_radius_x = int(10 + p_progress * 24)
            p_radius_y = int(6 + p_progress * 16)

            # Draw dark crater with subtle edge shadow
            cv2.ellipse(frame, (p_x, p_y), (p_radius_x + 3, p_radius_y + 2), 0, 0, 360, (50, 50, 50), -1)
            cv2.ellipse(frame, (p_x, p_y), (p_radius_x, p_radius_y), 0, 0, 360, (25, 25, 25), -1)
            cv2.ellipse(frame, (p_x - 2, p_y - 1), (max(2, p_radius_x - 6), max(2, p_radius_y - 4)), 0, 0, 360, (15, 15, 15), -1)

        return frame

    def _capture_worker(self):
        sim_frame_idx = 0
        while self.running:
            if self.is_sim:
                frame = self._generate_sim_frame(sim_frame_idx)
                sim_frame_idx += 1
                self.connected = True
                with self.lock:
                    self.latest_frame = frame
                    self.last_frame_timestamp = time.time()
                time.sleep(0.04)  # ~25 FPS
                continue

            if not self.cap or not self.cap.isOpened():
                self.connected = False
                time.sleep(RECONNECT_DELAY_SEC)
                print(f"[STREAM] Attempting reconnection to {self.src_url}...")
                if isinstance(self.src_url, str) and self.src_url.isdigit():
                    idx = int(self.src_url)
                    self.cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
                    if not self.cap.isOpened():
                        self.cap = cv2.VideoCapture(idx)
                else:
                    self.cap.open(self.src_url)
                if self.cap.isOpened():
                    self.connected = True
                    print("[STREAM] Reconnected to video stream successfully!")
                continue

            ret, frame = self.cap.read()
            if not ret or frame is None:
                if self.is_video_file:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    time.sleep(self.frame_delay)
                    continue
                self.connected = False
                time.sleep(0.5)
                self.cap.release()
                continue

            self.connected = True
            with self.lock:
                self.latest_frame = frame
                self.last_frame_timestamp = time.time()

            if self.is_video_file:
                time.sleep(self.frame_delay)

    def read(self):
        """Returns (connected, frame). If frame is stale (> 2s), marks disconnected."""
        with self.lock:
            if self.latest_frame is None or (time.time() - self.last_frame_timestamp > 2.0):
                return self.connected, None
            return self.connected, self.latest_frame.copy()

    def stop(self):
        self.running = False
        if self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cap and self.cap.isOpened():
            self.cap.release()


# ======================================================================================
# YOLO / ONNX INFERENCE WRAPPER
# ======================================================================================

class PotholeAIModel:
    """Encapsulates loading and inference for YOLOv8n (ONNX or PyTorch)."""

    def __init__(self, onnx_path: str, pt_path: str):
        self.backend = None
        self.model = None
        self.onnx_session = None

        # 1. Try ONNX Runtime first (Fastest on CPU)
        if os.path.exists(onnx_path):
            try:
                import onnxruntime as ort
                self.onnx_session = ort.InferenceSession(onnx_path, providers=['CPUExecutionProvider'])
                self.input_name = self.onnx_session.get_inputs()[0].name
                self.backend = "ONNX_CPU"
                print(f"[MODEL] Loaded ONNX Runtime engine: {onnx_path}")
                return
            except Exception as exc:
                print(f"[MODEL] Failed to initialize ONNX Runtime: {exc}")

        # 2. Try PyTorch Ultralytics model
        if os.path.exists(pt_path):
            try:
                from ultralytics import YOLO
                self.model = YOLO(pt_path)
                self.backend = "PYTORCH_YOLO"
                print(f"[MODEL] Loaded PyTorch YOLOv8 model: {pt_path}")
                return
            except Exception as exc:
                print(f"[MODEL] Failed to load PyTorch model: {exc}")

        print("[MODEL] No custom model weights found. Defaulting to Classical OpenCV Fallback.")
        self.backend = None

    def is_available(self) -> bool:
        return self.backend is not None

    def predict(self, frame: np.ndarray, conf_thresh: float) -> list:
        """Runs inference and returns list of detection dicts."""
        if self.backend == "ONNX_CPU":
            return self._predict_onnx(frame, conf_thresh)
        elif self.backend == "PYTORCH_YOLO":
            return self._predict_pytorch(frame, conf_thresh)
        return []

    def _predict_pytorch(self, frame: np.ndarray, conf_thresh: float) -> list:
        results = self.model(frame, imgsz=MODEL_INPUT_WIDTH, conf=conf_thresh, verbose=False, device='cpu')
        detections = []
        for r in results:
            boxes = r.boxes
            for b in boxes:
                xyxy = b.xyxy[0].cpu().numpy()
                x1, y1, x2, y2 = map(int, xyxy)
                conf = float(b.conf[0])
                w = x2 - x1
                h = y2 - y1
                detections.append({
                    "bbox": (x1, y1, w, h),
                    "confidence": round(conf, 2),
                    "area": w * h,
                    "centroid": (x1 + w // 2, y1 + h // 2)
                })
        return detections

    def _predict_onnx(self, frame: np.ndarray, conf_thresh: float) -> list:
        # Preprocess: Resize, BGR->RGB, Normalize to 0-1, NCHW shape
        orig_h, orig_w = frame.shape[:2]
        resized = cv2.resize(frame, (MODEL_INPUT_WIDTH, MODEL_INPUT_HEIGHT))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        input_tensor = (rgb.astype(np.float32) / 255.0).transpose(2, 0, 1)[np.newaxis, ...]

        # Run inference
        outputs = self.onnx_session.run(None, {self.input_name: input_tensor})
        predictions = outputs[0]  # Shape: (1, 5, 2100) or (1, 84, 2100)

        # Post-process YOLOv8 output
        predictions = np.squeeze(predictions).T  # Transpose to (2100, 5)
        boxes_list, confs_list = [], []

        x_factor = orig_w / float(MODEL_INPUT_WIDTH)
        y_factor = orig_h / float(MODEL_INPUT_HEIGHT)

        for row in predictions:
            confidence = row[4] if len(row) == 5 else np.max(row[4:])
            if confidence >= conf_thresh:
                cx, cy, w, h = row[0:4]
                x1 = int((cx - w / 2) * x_factor)
                y1 = int((cy - h / 2) * y_factor)
                box_w = int(w * x_factor)
                box_h = int(h * y_factor)

                boxes_list.append([x1, y1, box_w, box_h])
                confs_list.append(float(confidence))

        indices = cv2.dnn.NMSBoxes(boxes_list, confs_list, conf_thresh, 0.45)
        detections = []
        if len(indices) > 0:
            for i in indices.flatten():
                bx, by, bw, bh = boxes_list[i]
                detections.append({
                    "bbox": (bx, by, bw, bh),
                    "confidence": round(confs_list[i], 2),
                    "area": bw * bh,
                    "centroid": (bx + bw // 2, by + bh // 2)
                })
        return detections


# ======================================================================================
# MAIN VISION & CONTROL LOOP
# ======================================================================================

def main():
    parser = argparse.ArgumentParser(description="AI Pothole Identification & Safety Stream Engine")
    parser.add_argument("--stream", type=str, default=STREAM_URL, help=f"ESP32-CAM MJPEG URL, '0' for webcam, or 'sim' for simulated road (default: {STREAM_URL})")
    parser.add_argument("--force-fallback", action="store_true", help="Force classical OpenCV detector even if weights exist")
    parser.add_argument("--mock", action="store_true", help="Connect to local Mock ESP8266 controller simulator (http://127.0.0.1:8080)")
    parser.add_argument("--esp-url", type=str, default=None, help="Custom ESP8266 controller base URL")
    parser.add_argument("--headless", action="store_true", help="Run without opening GUI window (ideal for background services / CI)")
    parser.add_argument("--max-frames", type=int, default=None, help="Exit after processing N frames (useful for automated testing)")
    args = parser.parse_args()

    print("=" * 75)
    print("      AI-DRIVEN POTHOLE IDENTIFICATION & OBSTACLE AVOIDANCE SYSTEM      ")
    print("                         LAPTOP AI ENGINE                               ")
    print("=" * 75)

    # 1. Initialize Threaded Video Grabber
    print(f"[INIT] Video source: {args.stream}")
    grabber = FreshFrameCapture(args.stream)

    # 2. Initialize ESP8266 REST Client
    esp_base = "http://127.0.0.1:8080" if args.mock else args.esp_url
    esp_client = ESP8266Client(base_url=esp_base)
    print(f"[INIT] ESP8266 REST Target: {esp_client.base_url}")

    # 3. Initialize AI Model and Fallback Detector
    ai_model = PotholeAIModel(MODEL_PATH, PYTORCH_MODEL_PATH)
    fallback_detector = ClassicalPotholeDetector()

    # 4. Initialize Wi-Fi Geolocation & Telegram Alert Service
    preload_location_async()
    telegram_notifier = TelegramNotifier()
    current_location = get_wifi_location()
    print(f"[LOCATION] Active Wi-Fi Geolocation: {current_location.get('city')}, {current_location.get('region')} ({current_location.get('latitude'):.4f}, {current_location.get('longitude'):.4f})")
    print(f"[LOCATION] Connected Wi-Fi AP: {current_location.get('wifi_ssid')} [{current_location.get('wifi_bssid')}]")

    # Determine initial active detection mode
    use_ai = ai_model.is_available() and not args.force_fallback
    print(f"[MODE] Active vision detector: {'YOLOv8n (' + ai_model.backend + ')' if use_ai else 'Classical OpenCV Fallback'}")

    # Debounce State Tracking
    consecutive_detection_frames = 0
    consecutive_clear_frames = 0
    pothole_active_state = 0  # 0 = CRUISE, 1 = SLOW

    # Display & Timing
    show_debug_mask = False
    fps_start_time = time.time()
    frame_counter = 0
    total_processed_frames = 0
    fps_display = 0.0

    if not args.headless:
        cv2.namedWindow(WINDOW_TITLE, cv2.WINDOW_AUTOSIZE)

    try:
        while True:
            cycle_start = time.time()
            connected, frame = grabber.read()

            if not connected or frame is None:
                # Render Connection Waiting Screen
                blank_screen = np.zeros((240, 320, 3), dtype=np.uint8)
                cv2.putText(blank_screen, "Connecting to ESP32-CAM...", (20, 110),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 165, 255), 1, cv2.LINE_AA)
                cv2.putText(blank_screen, f"{args.stream}", (20, 140),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1, cv2.LINE_AA)
                upscaled = cv2.resize(blank_screen, (int(320 * DISPLAY_SCALE), int(240 * DISPLAY_SCALE)))
                cv2.imshow(WINDOW_TITLE, upscaled)
                if cv2.waitKey(100) & 0xFF == ord('q'):
                    break
                continue

            frame_counter += 1
            frame_h, frame_w = frame.shape[:2]

            # Calculate FPS
            if time.time() - fps_start_time >= 1.0:
                fps_display = frame_counter / (time.time() - fps_start_time)
                frame_counter = 0
                fps_start_time = time.time()

            # Execute Detection (AI Model or Classical Fallback)
            detections = []
            debug_mask = None

            if use_ai:
                raw_detections = ai_model.predict(frame, CONFIDENCE_THRESHOLD)
                # Filter through Road ROI constraint (only lower half)
                roi_y_min = int(frame_h * ROI_Y_MIN_RATIO)
                for det in raw_detections:
                    _, cy = det["centroid"]
                    if cy >= roi_y_min:
                        detections.append(det)
            else:
                detections, debug_mask = fallback_detector.detect(frame)

            # --------------------------------------------------------------------------
            # TEMPORAL DEBOUNCING FILTER (Hysteresis)
            # --------------------------------------------------------------------------
            has_pothole_in_frame = len(detections) > 0

            if has_pothole_in_frame:
                consecutive_detection_frames += 1
                consecutive_clear_frames = 0
                if consecutive_detection_frames >= CONFIRM_FRAMES_N:
                    if pothole_active_state == 0:
                        pothole_active_state = 1
                        print(f"\n[ALERT] Pothole confirmed over {CONFIRM_FRAMES_N} consecutive frames! -> Command: SLOW")
                        esp_client.set_pothole_state(1)

                        # Trigger Telegram Bot Alert with Wi-Fi Geolocation
                        loc = get_wifi_location()
                        best_conf = max([d.get("confidence", 0.70) for d in detections], default=0.75)
                        telegram_notifier.notify_pothole(loc, confidence=best_conf)
            else:
                consecutive_clear_frames += 1
                consecutive_detection_frames = 0
                if consecutive_clear_frames >= CLEAR_FRAMES_M:
                    if pothole_active_state == 1:
                        pothole_active_state = 0
                        print(f"\n[CLEAR] Road cleared over {CLEAR_FRAMES_M} frames. -> Command: CRUISE")
                        esp_client.set_pothole_state(0)

            # --------------------------------------------------------------------------
            # VISUAL ANNOTATIONS & HEADS-UP DISPLAY (HUD)
            # --------------------------------------------------------------------------
            annotated_frame = frame.copy()

            # 1. Draw Road ROI Boundary Box (dashed style or semi-transparent)
            roi_y = int(frame_h * ROI_Y_MIN_RATIO)
            cv2.line(annotated_frame, (0, roi_y), (frame_w, roi_y), (0, 255, 255), 1, cv2.LINE_AA)
            cv2.putText(annotated_frame, "ROAD ROI (Inspection Zone)", (8, roi_y - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.38, (0, 255, 255), 1, cv2.LINE_AA)

            # 2. Draw Detected Pothole Bounding Boxes
            for det in detections:
                x, y, w, h = det["bbox"]
                conf = det["confidence"]
                # Box color: Red when confirmed slow, Orange when confirming
                box_color = (0, 0, 255) if pothole_active_state == 1 else (0, 140, 255)

                cv2.rectangle(annotated_frame, (x, y), (x + w, y + h), box_color, 2)
                label = f"POTHOLE {int(conf * 100)}%"
                (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
                cv2.rectangle(annotated_frame, (x, max(0, y - lh - 6)), (x + lw + 4, y), box_color, -1)
                cv2.putText(annotated_frame, label, (x + 2, max(lh + 2, y - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.circle(annotated_frame, det["centroid"], 3, (0, 255, 0), -1)

            # 3. Optional Debug Mask Overlay
            if show_debug_mask and debug_mask is not None:
                mask_colored = cv2.cvtColor(debug_mask, cv2.COLOR_GRAY2BGR)
                annotated_frame = cv2.addWeighted(annotated_frame, 0.7, mask_colored, 0.3, 0)

            # 4. Scale for comfortable screen viewing (fits large or vertical videos)
            target_display_h = 600
            display_scale = target_display_h / float(frame_h) if frame_h > 400 else DISPLAY_SCALE
            disp_w = max(380, int(frame_w * display_scale))
            disp_h = int(frame_h * display_scale)
            display_frame = cv2.resize(annotated_frame, (disp_w, disp_h), interpolation=cv2.INTER_LINEAR)

            # 5. Top Status Banner (HUD)
            banner_bg_color = (0, 0, 180) if pothole_active_state == 1 else (30, 120, 30)
            cv2.rectangle(display_frame, (0, 0), (display_frame.shape[1], 44), banner_bg_color, -1)

            status_text = "STATE: SLOW (POTHOLE HAZARD)" if pothole_active_state == 1 else "STATE: CRUISE (ROAD CLEAR)"
            cv2.putText(display_frame, status_text, (14, 28),
                        cv2.FONT_HERSHEY_DUPLEX, 0.75, (255, 255, 255), 2, cv2.LINE_AA)

            # Location & Wi-Fi Network Badge
            loc_str = f"Loc: {current_location.get('city')}, {current_location.get('country')} ({current_location.get('latitude'):.2f}, {current_location.get('longitude'):.2f}) | AP: {current_location.get('wifi_ssid')}"
            cv2.putText(display_frame, loc_str, (14, display_frame.shape[0] - 28),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.40, (180, 220, 255), 1, cv2.LINE_AA)

            # Engine & FPS Subtitle
            engine_str = f"Detector: {'YOLOv8n' if use_ai else 'Classical OpenCV'} | FPS: {fps_display:.1f}"
            cv2.putText(display_frame, engine_str, (14, display_frame.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (220, 220, 220), 1, cv2.LINE_AA)

            # Debounce Progress Indicators
            debounce_str = f"Detect Hist: {consecutive_detection_frames}/{CONFIRM_FRAMES_N} | Clear Hist: {consecutive_clear_frames}/{CLEAR_FRAMES_M}"
            cv2.putText(display_frame, debounce_str, (display_frame.shape[1] - 310, display_frame.shape[0] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.42, (180, 255, 180), 1, cv2.LINE_AA)

            total_processed_frames += 1

            if not args.headless:
                cv2.imshow(WINDOW_TITLE, display_frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q') or key == 27:
                    print("\n[USER] Stopping detection engine...")
                    break
                elif key == ord('f'):
                    if ai_model.is_available():
                        use_ai = not use_ai
                        print(f"\n[TOGGLE] Switched detector to: {'YOLOv8n' if use_ai else 'Classical OpenCV'}")
                    else:
                        print("\n[INFO] AI weights unavailable. Running in Classical OpenCV mode.")
                elif key == ord('d'):
                    show_debug_mask = not show_debug_mask
                    print(f"\n[TOGGLE] Debug mask overlay: {'ON' if show_debug_mask else 'OFF'}")
                elif key == ord('s'):
                    status = esp_client.get_status()
                    print("\n[ESP8266 STATUS QUERY]:", status)
            else:
                if total_processed_frames % 20 == 0:
                    print(f"[HEADLESS] Frame {total_processed_frames}: Detections={len(detections)} | State={'SLOW' if pothole_active_state else 'CRUISE'} | FPS={fps_display:.1f}", flush=True)
                time.sleep(0.01)

            if args.max_frames and total_processed_frames >= args.max_frames:
                print(f"\n[INFO] Reached requested limit of {args.max_frames} frames. Exiting.")
                break

    finally:
        # Cleanup and ensure vehicle returns to safe cruise state before closing
        print("[SHUTDOWN] Resetting vehicle controller state...")
        esp_client.set_pothole_state(0, force=True)
        grabber.stop()
        cv2.destroyAllWindows()
        print("[SHUTDOWN] Finished cleanly.")


if __name__ == "__main__":
    main()
