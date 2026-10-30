# System Architecture & State Machine Specification

## 1. System Overview

The **AI-Driven Pothole Identification and Smart Obstacle Avoidance System** is a distributed, cyber-physical robotic platform designed for autonomous roadway safety. The architecture separates low-latency physical safety control from high-compute computer vision intelligence across three collaborative computing nodes:

```mermaid
graph LR
    subgraph SENSE ["Vision & Ranging"]
        CAM["ESP32-CAM<br/>(AI-Thinker)"]
        US["3x HC-SR04<br/>(Front, Left, Right)"]
    end

    subgraph COMPUTE ["Distributed Nodes"]
        NODE_CAM["Node A: Video Streamer<br/>Port 81 MJPEG"]
        NODE_LAPTOP["Node B: AI Vision Engine<br/>YOLOv8n / OpenCV Fallback"]
        NODE_MCU["Node C: Motion Controller<br/>ESP8266 NodeMCU"]
    end

    subgraph ACTUATE ["Vehicle Drive & Cloud"]
        MOTORS["L298N + Dual DC Motors"]
        CLOUD["Telegram Bot API<br/>(Incident Alerts)"]
    end

    CAM --> NODE_CAM
    NODE_CAM -->|"MJPEG Stream (HTTP :81/stream)"| NODE_LAPTOP
    US --> NODE_MCU
    NODE_LAPTOP -->|"REST Control (/pothole?state=0|1)"| NODE_MCU
    NODE_MCU --> MOTORS
    NODE_MCU -->|"HTTPS Event Notifications"| CLOUD
```

---

## 2. Distributed Communication Protocols

### A) Video Stream: ESP32-CAM -> Laptop
- **Transport**: HTTP multipart/x-mixed-replace over TCP.
- **Port**: `81` (`http://<ESP32CAM_IP>:81/stream`).
- **Resolution**: `QVGA` (320x240 pixels) optimized for transmission latency ($< 80\text{ ms}$).
- **Compression**: JPEG Quality = `12` (balances image clarity for edge/contour detection with minimal packet fragmentation).
- **Network Resilience**: Embedded watchdog auto-reconnects Wi-Fi within $3000\text{ ms}$ of AP disconnection.

### B) Vehicle Command & Telemetry REST API: Laptop <-> ESP8266
The ESP8266 runs an embedded HTTP web server on port `80`. The endpoints follow a deterministic REST interface:

| Endpoint | Method | Query Parameters | Description | Sample Response |
|---|---|---|---|---|
| `/pothole` | `GET` | `state=1` or `state=0` | Signals pothole detection (`1` = slow down) or road clear (`0` = cruise). Dispatched only on state transitions. | `{"status":"ok","pothole":1}` |
| `/status` | `GET` | None | Returns real-time vehicle telemetry (distances, state, PWM, mode). | `{"mode":"AUTO","state":"CRUISE","speed":180,"pothole":0,"front_cm":45.2,"left_cm":38.1,"right_cm":42.0,"uptime_s":45}` |
| `/mode` | `GET` | `auto=1` or `auto=0` | Toggles between Autonomous mode (`1`) and Manual Drive mode (`0`). | `{"status":"ok","mode":"AUTO"}` |
| `/drive` | `GET` | `cmd=F\|B\|L\|R\|S` | Manual motor control (`F`=Forward, `B`=Backward, `L`=Left, `R`=Right, `S`=Stop). Active only in manual mode. | `{"status":"ok","command":"F"}` |

### C) Cloud Notification Interface: ESP8266 -> Telegram Bot API
- **Transport**: HTTPS POST over TLS 1.2 to `https://api.telegram.org/bot<TOKEN>/sendMessage`.
- **Client Security**: `WiFiClientSecure` with `setInsecure()` to avoid heavy X.509 certificate store overhead on the ESP8266 RAM.
- **Non-blocking Dispatch**: Messages are enqueued into a memory ring buffer. The main execution loop dispatches HTTP transactions asynchronously during idle slices between motor control ticks.

---

## 3. ESP8266 Finite State Machine (FSM)

The vehicle motion controller is strictly non-blocking. It uses `millis()` timestamp tracking without any blocking `delay()` calls.

```mermaid
stateDiagram-v2
    [*] --> CRUISE : Boot & Wi-Fi Init

    CRUISE --> SLOW : Pothole Detected (pothole_flag == 1)
    SLOW --> CRUISE : Road Clear (pothole_flag == 0)

    CRUISE --> AVOID : Front Obstacle < 25 cm
    SLOW --> AVOID : Front Obstacle < 25 cm

    state AVOID {
        [*] --> SelectDirection
        SelectDirection --> TurnLeft : Left Dist > Right Dist
        SelectDirection --> TurnRight : Right Dist >= Left Dist
        SelectDirection --> BLOCKED : Left < 15cm AND Right < 15cm
        TurnLeft --> WaitTurnTimer : Run Motors
        TurnRight --> WaitTurnTimer : Run Motors
    }

    AVOID --> PASS : Turn Duration Elapsed (t_turn)

    state PASS {
        [*] --> DrivePast
        DrivePast --> CheckClear : Side Sensor Reads > 30 cm OR Pass Timeout Elapsed
    }

    PASS --> RETURN : Obstacle Cleared

    state RETURN {
        [*] --> CounterSteer
        CounterSteer --> WaitReturnTimer : Reverse Turn for t_turn
    }

    RETURN --> CRUISE : Heading Restored

    state BLOCKED {
        [*] --> FullHalt
        FullHalt --> AlertTelegram : Enqueue "Path Blocked" Alert
        AlertTelegram --> RetryAssessment : Wait 2000 ms Interval
    }

    BLOCKED --> AVOID : Space Becomes Available
```

### Detailed State Behavioral Specifications

1. **`CRUISE` (Normal Autonomous Drive)**:
   - Left & Right motors drive forward at normal cruise speed (default: `PWM = 180 / 255`, ~70% duty cycle).
   - Ultrasonic sensors polled continuously at $15\text{ Hz}$ using the non-blocking parallel sampler.
   - Pothole state: `0`.

2. **`SLOW` (Pothole Navigation)**:
   - Left & Right motors drive forward at reduced crawl speed (default: `PWM = 110 / 255`, ~43% duty cycle).
   - The vehicle does **NOT** stop abruptly, preventing rear-end collisions from following vehicles.
   - Transitions back to `CRUISE` smoothly when the laptop signals `pothole=0`.

3. **`AVOID` (Obstacle Evasion Maneuver)**:
   - **Trigger**: Front distance drops below `OBSTACLE_FRONT_THRESH` (default: $25\text{ cm}$).
   - **Arbitration**: Immediately preempts `SLOW` or `CRUISE`. Obstacle avoidance takes top safety priority over road surface conditions.
   - **Decision Engine**:
     - Compares `left_cm` vs `right_cm`.
     - If `left_cm > right_cm` and `left_cm > 20 cm`, pivots **LEFT**.
     - If `right_cm >= left_cm` and `right_cm > 20 cm`, pivots **RIGHT**.
     - If both `left_cm < 15 cm` and `right_cm < 15 cm`, transitions to `BLOCKED`.
   - The pivot turn runs for a calibrated time constant `t_turn` (default: $450\text{ ms}$).

4. **`PASS` (Obstacle Overtaking)**:
   - Vehicle drives straight forward along the bypass trajectory.
   - Monitors the side sensor facing the obstacle (e.g. if steered left, monitors the right sensor).
   - State completes when the side distance exceeds $30\text{ cm}$ (obstacle passed) or after a maximum safety timeout `t_pass` ($1800\text{ ms}$).

5. **`RETURN` (Lane Restoration)**:
   - Vehicle executes a counter-steer maneuver in the opposite direction of the initial evasion for exactly `t_return = t_turn` ($450\text{ ms}$).
   - Returns vehicle chassis parallel to original lane heading, then resumes `CRUISE`.

6. **`BLOCKED` (Deadlock Safety Halt)**:
   - All motors instantly forced to $0\text{ PWM}$ (electric brake).
   - Enqueues an urgent alert to Telegram: `"🚨 EMERGENCY: Path completely blocked in all directions. Vehicle halted."`.
   - Re-evaluates distance sensors every $2000\text{ ms}$. If an escape vector opens ($> 20\text{ cm}$), transitions back to `AVOID`.

---

## 4. End-to-End System Interaction Sequence

The following diagram demonstrates concurrent handling of pothole detection and real-time obstacle avoidance:

```mermaid
sequenceDiagram
    autonumber
    participant Road as Road Surface & Obstacle
    participant Cam as ESP32-CAM
    participant Laptop as Laptop AI Engine
    participant MCU as ESP8266 Vehicle Controller
    participant Motors as L298N Drive Motors
    participant TG as Telegram Bot API

    MCU->>Motors: PWM = 180 (CRUISE Forward)
    Cam->>Laptop: MJPEG Stream Frame (320x240 @ 20 FPS)
    
    Note over Laptop: Frame Analysis: Pothole detected in ROI<br/>Confidence = 0.78, Frame 1 of 3
    Cam->>Laptop: Next Frame (Frame 2 of 3)
    Cam->>Laptop: Next Frame (Frame 3 of 3 - Confirmed!)
    
    Laptop->>MCU: HTTP GET /pothole?state=1
    MCU->>Motors: PWM = 110 (SLOW Down smoothly)
    MCU->>TG: Enqueue Alert: "Pothole detected - slowing down"
    TG-->>MCU: 200 OK (Alert Sent)

    Note over Road,MCU: Static Obstacle appears 22 cm ahead!
    MCU->>Motors: STOP forward drive (Front < 25 cm)
    Note over MCU: Compare: Left = 48 cm, Right = 14 cm
    MCU->>Motors: Steer LEFT (AVOID)
    MCU->>TG: Enqueue Alert: "Obstacle ahead - avoiding to LEFT"
    
    Note over MCU: Turn timer t_turn elapsed
    MCU->>Motors: Drive Forward (PASS)
    Note over MCU: Right sensor reads > 30 cm (Obstacle Cleared)
    
    MCU->>Motors: Steer RIGHT (RETURN to Lane)
    Note over MCU: Counter-turn timer elapsed
    MCU->>Motors: PWM = 110 (Resume SLOW - pothole flag still 1)
    
    Note over Laptop: Pothole cleared in camera ROI<br/>10 consecutive clear frames observed
    Laptop->>MCU: HTTP GET /pothole?state=0
    MCU->>Motors: PWM = 180 (CRUISE Resume normal speed)
```

---

## 5. Fault Tolerance & Fail-Safe Mechanisms

| Subsystem Failure | Detection Mechanism | Fail-Safe Autonomous Action |
|---|---|---|
| **Laptop Connection Dropped** | ESP8266 command watchdog timer (`millis() - last_laptop_cmd_ms > 5000`) | Resets `pothole_flag = 0` to prevent getting stuck at slow crawl; maintains full autonomous ultrasonic obstacle avoidance. |
| **Wi-Fi AP Disconnected** | `WiFi.status() != WL_CONNECTED` check | State machine and ultrasonic obstacle avoidance continue running without pause; Wi-Fi reconnection attempts execute asynchronously in background. |
| **ESP32-CAM Stream Hangs** | Laptop frame grabber timeout ($> 3000\text{ ms}$ with no fresh frame) | Laptop re-initializes OpenCV `VideoCapture` object with exponential backoff; logs warning on HUD. |
| **Sensor Echo Timeout** | Parallel ultrasonic sampler timeout ($30\text{ ms}$) | Reports sensor distance as `MAX_DIST` ($400\text{ cm}$), rejecting 0 values to prevent false obstacle triggers. |
| **Telegram API Latency** | HTTPS request timeout or socket block | Alert queue decouples network latency from motor loop; if network blocks, packet is dropped rather than stalling motor PWM. |
