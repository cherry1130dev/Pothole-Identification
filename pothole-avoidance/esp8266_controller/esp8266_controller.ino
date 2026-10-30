/**
 * ======================================================================================
 * PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
 * MODULE:  ESP8266 Main Vehicle Motion & Safety Controller
 * FILE:    esp8266_controller.ino
 * ======================================================================================
 * 
 * DESCRIPTION:
 * Non-blocking cooperative state machine implementing:
 * 1. Parallel 3-sensor ultrasonic acquisition with median filtering.
 * 2. Obstacle avoidance finite state machine (CRUISE, SLOW, AVOID, PASS, RETURN, BLOCKED).
 * 3. Priority arbitration (Obstacle avoidance ALWAYS preempts pothole slowdown).
 * 4. Embedded HTTP REST API (/pothole, /status, /mode, /drive).
 * 5. Asynchronous queued Telegram Bot alerts over HTTPS.
 * 6. Multi-level fail-safes (Laptop heartbeat watchdog, Wi-Fi auto-recovery).
 * ======================================================================================
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include "config.h"

// ======================================================================================
// ENUMERATIONS & DATA STRUCTURES
// ======================================================================================

enum VehicleMode {
    MODE_AUTO,
    MODE_MANUAL
};

enum VehicleState {
    STATE_CRUISE,   // Normal forward speed
    STATE_SLOW,     // Pothole rough-patch crawl
    STATE_AVOID,    // Steering away from detected obstacle
    STATE_PASS,     // Bypassing obstacle in adjacent lane
    STATE_RETURN,   // Counter-steering back to original heading
    STATE_BLOCKED   // Trapped; all directions obstructed
};

enum AvoidDirection {
    AVOID_NONE,
    AVOID_LEFT,
    AVOID_RIGHT
};

enum AlertType {
    ALERT_BOOT,
    ALERT_POTHOLE,
    ALERT_AVOID_LEFT,
    ALERT_AVOID_RIGHT,
    ALERT_BLOCKED
};

// ======================================================================================
// GLOBAL STATE VARIABLES
// ======================================================================================

VehicleMode    currentMode        = MODE_AUTO;
VehicleState   currentState       = STATE_CRUISE;
AvoidDirection avoidDirection     = AVOID_NONE;

int  potholeFlag                  = 0;       // 1 = slow down, 0 = cruise
int  currentSpeedPwm              = PWM_CRUISE;
char manualDriveCmd               = 'S';

// Timers (millis tracking)
unsigned long stateStartTimeMs    = 0;
unsigned long lastUsSampleMs      = 0;
unsigned long lastLaptopCmdMs     = 0;
unsigned long lastBlockedRetryMs  = 0;
unsigned long lastWifiCheckMs     = 0;

// Telegram Alert Queue & Cooldowns
struct TelegramAlert {
    String    message;
    AlertType type;
};

TelegramAlert alertQueue[TELEGRAM_MAX_QUEUE];
int alertQueueHead = 0;
int alertQueueTail = 0;
int alertQueueCount = 0;

unsigned long lastAlertTimeMs[5] = {0, 0, 0, 0, 0}; // Cooldowns for each AlertType

// Ultrasonic Filter Buffers (Median of 3)
float frontHistory[3] = {100.0f, 100.0f, 100.0f};
float leftHistory[3]  = {100.0f, 100.0f, 100.0f};
float rightHistory[3] = {100.0f, 100.0f, 100.0f};
int usHistoryIndex = 0;

float frontDistCm = 100.0f;
float leftDistCm  = 100.0f;
float rightDistCm = 100.0f;

// Web Server
ESP8266WebServer server(HTTP_SERVER_PORT);

// ======================================================================================
// MOTOR ACTUATION SUBSYSTEM (L298N)
// ======================================================================================

void motorsInit() {
    pinMode(PIN_MOTOR_IN1, OUTPUT);
    pinMode(PIN_MOTOR_IN2, OUTPUT);
    pinMode(PIN_MOTOR_IN3, OUTPUT);
    pinMode(PIN_MOTOR_IN4, OUTPUT);
    pinMode(PIN_MOTOR_PWM, OUTPUT);

    // Set ESP8266 PWM range to standard 0-255
    analogWriteRange(255);
    analogWriteFreq(1000); // 1 kHz PWM frequency

    motorsStop();
    Serial.println("[MOTORS] L298N driver initialized.");
}

void motorsSetSpeed(uint8_t speed) {
    currentSpeedPwm = speed;
    analogWrite(PIN_MOTOR_PWM, currentSpeedPwm);
}

void motorsForward() {
    digitalWrite(PIN_MOTOR_IN1, HIGH);
    digitalWrite(PIN_MOTOR_IN2, LOW);
    digitalWrite(PIN_MOTOR_IN3, HIGH);
    digitalWrite(PIN_MOTOR_IN4, LOW);
}

void motorsBackward() {
    digitalWrite(PIN_MOTOR_IN1, LOW);
    digitalWrite(PIN_MOTOR_IN2, HIGH);
    digitalWrite(PIN_MOTOR_IN3, LOW);
    digitalWrite(PIN_MOTOR_IN4, HIGH);
}

void motorsTurnLeft() {
    // Pivot turn: Left motor reverse, Right motor forward
    digitalWrite(PIN_MOTOR_IN1, LOW);
    digitalWrite(PIN_MOTOR_IN2, HIGH);
    digitalWrite(PIN_MOTOR_IN3, HIGH);
    digitalWrite(PIN_MOTOR_IN4, LOW);
}

void motorsTurnRight() {
    // Pivot turn: Left motor forward, Right motor reverse
    digitalWrite(PIN_MOTOR_IN1, HIGH);
    digitalWrite(PIN_MOTOR_IN2, LOW);
    digitalWrite(PIN_MOTOR_IN3, LOW);
    digitalWrite(PIN_MOTOR_IN4, HIGH);
}

void motorsStop() {
    digitalWrite(PIN_MOTOR_IN1, LOW);
    digitalWrite(PIN_MOTOR_IN2, LOW);
    digitalWrite(PIN_MOTOR_IN3, LOW);
    digitalWrite(PIN_MOTOR_IN4, LOW);
    analogWrite(PIN_MOTOR_PWM, 0);
}

// ======================================================================================
// PARALLEL ULTRASONIC ACQUISITION WITH MEDIAN FILTER
// ======================================================================================

void ultrasonicsInit() {
    pinMode(PIN_US_TRIG, OUTPUT);
    pinMode(PIN_US_ECHO_FRONT, INPUT);
    pinMode(PIN_US_ECHO_LEFT, INPUT);
    pinMode(PIN_US_ECHO_RIGHT, INPUT);

    digitalWrite(PIN_US_TRIG, LOW);
    Serial.println("[SENSORS] HC-SR04 parallel ultrasonic array initialized.");
}

float calculateMedian3(float a, float b, float c) {
    if ((a <= b && b <= c) || (c <= b && b <= a)) return b;
    if ((b <= a && a <= c) || (c <= a && a <= b)) return a;
    return c;
}

/**
 * Executes a single parallel pulse on shared TRIG and measures FRONT, LEFT,
 * and RIGHT echo times simultaneously in a high-speed microsecond polling loop.
 */
void sampleUltrasonicsParallel() {
    // 1. Send clean 10 µs trigger pulse
    digitalWrite(PIN_US_TRIG, LOW);
    delayMicroseconds(4);
    digitalWrite(PIN_US_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_US_TRIG, LOW);

    // 2. Wait for echo pulses to start (timeout 2500 µs)
    unsigned long waitStart = micros();
    bool echoStarted = false;
    while (micros() - waitStart < 2500) {
        if (digitalRead(PIN_US_ECHO_FRONT) || digitalRead(PIN_US_ECHO_LEFT) || digitalRead(PIN_US_ECHO_RIGHT)) {
            echoStarted = true;
            break;
        }
    }

    if (!echoStarted) {
        // No echo detected, return max distance
        return;
    }

    unsigned long pulseStartTime = micros();
    unsigned long frontDuration = 0;
    unsigned long leftDuration  = 0;
    unsigned long rightDuration = 0;

    bool frontDone = false;
    bool leftDone  = false;
    bool rightDone = false;

    // 3. Parallel polling loop (runs until all 3 have fallen or timeout reached)
    while (micros() - pulseStartTime < US_TIMEOUT_MICROS) {
        unsigned long now = micros();

        if (!frontDone && digitalRead(PIN_US_ECHO_FRONT) == LOW) {
            frontDuration = now - pulseStartTime;
            frontDone = true;
        }
        if (!leftDone && digitalRead(PIN_US_ECHO_LEFT) == LOW) {
            leftDuration = now - pulseStartTime;
            leftDone = true;
        }
        if (!rightDone && digitalRead(PIN_US_ECHO_RIGHT) == LOW) {
            rightDuration = now - pulseStartTime;
            rightDone = true;
        }

        if (frontDone && leftDone && rightDone) {
            break;
        }
    }

    // Convert microseconds to centimeters (Speed of sound: 343 m/s -> 58.2 µs/cm)
    float rawFront = frontDone ? (frontDuration / 58.2f) : 400.0f;
    float rawLeft  = leftDone  ? (leftDuration  / 58.2f) : 400.0f;
    float rawRight = rightDone ? (rightDuration / 58.2f) : 400.0f;

    // Filter out invalid zero or negative readings
    if (rawFront <= 1.0f || rawFront > 400.0f) rawFront = 400.0f;
    if (rawLeft  <= 1.0f || rawLeft  > 400.0f) rawLeft  = 400.0f;
    if (rawRight <= 1.0f || rawRight > 400.0f) rawRight = 400.0f;

    // Store in circular buffer
    frontHistory[usHistoryIndex] = rawFront;
    leftHistory[usHistoryIndex]  = rawLeft;
    rightHistory[usHistoryIndex] = rawRight;
    usHistoryIndex = (usHistoryIndex + 1) % 3;

    // Compute median of 3 samples to reject stray spikes
    frontDistCm = calculateMedian3(frontHistory[0], frontHistory[1], frontHistory[2]);
    leftDistCm  = calculateMedian3(leftHistory[0], leftHistory[1], leftHistory[2]);
    rightDistCm = calculateMedian3(rightHistory[0], rightHistory[1], rightHistory[2]);
}

// ======================================================================================
// TELEGRAM ALERT QUEUE & DISPATCHER (NON-BLOCKING)
// ======================================================================================

void enqueueTelegramAlert(const String& msg, AlertType type) {
    unsigned long now = millis();
    // Check cooldown for this specific alert type
    if (now - lastAlertTimeMs[type] < TELEGRAM_COOLDOWN_MS && type != ALERT_BOOT) {
        Serial.printf("[TELEGRAM] Alert type %d throttled by cooldown.\n", type);
        return;
    }

    if (alertQueueCount >= TELEGRAM_MAX_QUEUE) {
        Serial.println("[TELEGRAM] Queue full! Dropping oldest alert.");
        alertQueueHead = (alertQueueHead + 1) % TELEGRAM_MAX_QUEUE;
        alertQueueCount--;
    }

    alertQueue[alertQueueTail].message = msg;
    alertQueue[alertQueueTail].type    = type;
    alertQueueTail = (alertQueueTail + 1) % TELEGRAM_MAX_QUEUE;
    alertQueueCount++;

    lastAlertTimeMs[type] = now;
    Serial.printf("[TELEGRAM] Enqueued: %s\n", msg.c_str());
}

void processTelegramQueue() {
    if (alertQueueCount == 0 || WiFi.status() != WL_CONNECTED) {
        return;
    }

    String botToken = TELEGRAM_BOT_TOKEN;
    String chatId   = TELEGRAM_CHAT_ID;

    // Skip if placeholders remain
    if (botToken.startsWith("YOUR_") || chatId.startsWith("YOUR_")) {
        // Discard alert to prevent queue clogging
        alertQueueHead = (alertQueueHead + 1) % TELEGRAM_MAX_QUEUE;
        alertQueueCount--;
        return;
    }

    TelegramAlert currentAlert = alertQueue[alertQueueHead];
    alertQueueHead = (alertQueueHead + 1) % TELEGRAM_MAX_QUEUE;
    alertQueueCount--;

    WiFiClientSecure secureClient;
    secureClient.setInsecure(); // Bypass X.509 cert validation for speed and RAM efficiency
    secureClient.setTimeout(3000); // 3-second hard timeout

    const char* host = "api.telegram.org";
    if (!secureClient.connect(host, 443)) {
        Serial.println("[TELEGRAM] SSL Connection failed to api.telegram.org");
        return;
    }

    // Build URL-encoded POST payload
    StaticJsonDocument<256> doc;
    doc["chat_id"] = chatId;
    doc["text"]    = currentAlert.message;
    String payload;
    serializeJson(doc, payload);

    String request = String("POST /bot") + botToken + "/sendMessage HTTP/1.1\r\n" +
                     "Host: " + host + "\r\n" +
                     "Content-Type: application/json\r\n" +
                     "Content-Length: " + payload.length() + "\r\n" +
                     "Connection: close\r\n\r\n" +
                     payload;

    secureClient.print(request);
    Serial.printf("[TELEGRAM] Alert sent: %s\n", currentAlert.message.c_str());
}

// ======================================================================================
// REST API HTTP REQUEST HANDLERS
// ======================================================================================

void handlePothole() {
    if (server.hasArg("state")) {
        int newState = server.arg("state").toInt();
        potholeFlag = (newState == 1) ? 1 : 0;
        lastLaptopCmdMs = millis();

        if (potholeFlag == 1) {
            enqueueTelegramAlert("⚠️ Pothole detected ahead - slowing down", ALERT_POTHOLE);
        }

        StaticJsonDocument<128> doc;
        doc["status"]  = "ok";
        doc["pothole"] = potholeFlag;
        String resp;
        serializeJson(doc, resp);
        server.send(200, "application/json", resp);

        Serial.printf("[API] Pothole state updated to: %d\n", potholeFlag);
    } else {
        server.send(400, "application/json", "{\"error\":\"Missing 'state' query param\"}");
    }
}

void handleStatus() {
    StaticJsonDocument<300> doc;
    doc["mode"]       = (currentMode == MODE_AUTO) ? "AUTO" : "MANUAL";
    
    switch (currentState) {
        case STATE_CRUISE:  doc["state"] = "CRUISE"; break;
        case STATE_SLOW:    doc["state"] = "SLOW"; break;
        case STATE_AVOID:   doc["state"] = "AVOID"; break;
        case STATE_PASS:    doc["state"] = "PASS"; break;
        case STATE_RETURN:  doc["state"] = "RETURN"; break;
        case STATE_BLOCKED: doc["state"] = "BLOCKED"; break;
    }

    doc["speed"]      = currentSpeedPwm;
    doc["pothole"]    = potholeFlag;
    doc["front_cm"]   = serialized(String(frontDistCm, 1));
    doc["left_cm"]    = serialized(String(leftDistCm, 1));
    doc["right_cm"]   = serialized(String(rightDistCm, 1));
    doc["uptime_s"]   = millis() / 1000;

    String resp;
    serializeJson(doc, resp);
    server.send(200, "application/json", resp);
}

void handleMode() {
    if (server.hasArg("auto")) {
        int isAuto = server.arg("auto").toInt();
        currentMode = (isAuto == 1) ? MODE_AUTO : MODE_MANUAL;
        if (currentMode == MODE_MANUAL) {
            motorsStop();
        }
        server.send(200, "application/json", String("{\"status\":\"ok\",\"mode\":\"") + ((currentMode == MODE_AUTO) ? "AUTO" : "MANUAL") + "\"}");
        Serial.printf("[API] Vehicle Mode set to: %s\n", (currentMode == MODE_AUTO) ? "AUTO" : "MANUAL");
    } else {
        server.send(400, "application/json", "{\"error\":\"Missing 'auto' param\"}");
    }
}

void handleDrive() {
    if (server.hasArg("cmd")) {
        String cmd = server.arg("cmd");
        cmd.toUpperCase();
        manualDriveCmd = cmd.charAt(0);

        if (currentMode == MODE_MANUAL) {
            motorsSetSpeed(PWM_CRUISE);
            switch (manualDriveCmd) {
                case 'F': motorsForward(); break;
                case 'B': motorsBackward(); break;
                case 'L': motorsTurnLeft(); break;
                case 'R': motorsTurnRight(); break;
                case 'S': default: motorsStop(); break;
            }
        }
        server.send(200, "application/json", String("{\"status\":\"ok\",\"cmd\":\"") + manualDriveCmd + "\"}");
        Serial.printf("[API] Manual command: %c\n", manualDriveCmd);
    } else {
        server.send(400, "application/json", "{\"error\":\"Missing 'cmd' param\"}");
    }
}

void handleNotFound() {
    server.send(404, "text/plain", "404: Not Found");
}

void setupHttpServer() {
    server.on("/pothole", HTTP_GET, handlePothole);
    server.on("/status",  HTTP_GET, handleStatus);
    server.on("/mode",    HTTP_GET, handleMode);
    server.on("/drive",   HTTP_GET, handleDrive);
    server.onNotFound(handleNotFound);

    server.begin();
    Serial.println("[HTTP] REST API server started on port 80.");
}

// ======================================================================================
// AUTONOMOUS FINITE STATE MACHINE (COOPERATIVE NON-BLOCKING)
// ======================================================================================

void executeStateMachine() {
    if (currentMode != MODE_AUTO) {
        return; // Manual mode bypasses autonomous FSM
    }

    unsigned long now = millis();

    // ----------------------------------------------------------------------------------
    // TOP SAFETY PRIORITY: OBSTACLE DETECTION ARBITRATION
    // If obstacle is < 25 cm ahead, trigger evasion immediately (preempts CRUISE or SLOW)
    // ----------------------------------------------------------------------------------
    if ((currentState == STATE_CRUISE || currentState == STATE_SLOW) && (frontDistCm < OBSTACLE_FRONT_THRESH)) {
        Serial.printf("[FSM] Front obstacle detected at %.1f cm! Evaluating escape path.\n", frontDistCm);

        // Check for deadlock (blocked on all sides)
        if (leftDistCm < OBSTACLE_DEADLOCK && rightDistCm < OBSTACLE_DEADLOCK) {
            currentState = STATE_BLOCKED;
            stateStartTimeMs = now;
            motorsStop();
            enqueueTelegramAlert("🚨 Emergency: Path blocked in all directions! Vehicle stopped.", ALERT_BLOCKED);
            Serial.println("[FSM] -> Entered STATE_BLOCKED");
            return;
        }

        // Steer toward the side with greater clearance
        if (leftDistCm > rightDistCm) {
            avoidDirection = AVOID_LEFT;
            currentState = STATE_AVOID;
            stateStartTimeMs = now;
            motorsSetSpeed(PWM_TURN);
            motorsTurnLeft();
            enqueueTelegramAlert("🚧 Obstacle ahead - avoiding to LEFT", ALERT_AVOID_LEFT);
            Serial.println("[FSM] -> Entered STATE_AVOID (Turning LEFT)");
        } else {
            avoidDirection = AVOID_RIGHT;
            currentState = STATE_AVOID;
            stateStartTimeMs = now;
            motorsSetSpeed(PWM_TURN);
            motorsTurnRight();
            enqueueTelegramAlert("🚧 Obstacle ahead - avoiding to RIGHT", ALERT_AVOID_RIGHT);
            Serial.println("[FSM] -> Entered STATE_AVOID (Turning RIGHT)");
        }
        return;
    }

    // ----------------------------------------------------------------------------------
    // STATE TRANSITION EXECUTION
    // ----------------------------------------------------------------------------------
    switch (currentState) {

        case STATE_CRUISE:
            if (potholeFlag == 1) {
                currentState = STATE_SLOW;
                motorsSetSpeed(PWM_SLOW);
                motorsForward();
                Serial.println("[FSM] -> Entered STATE_SLOW (Pothole rough patch)");
            } else {
                motorsSetSpeed(PWM_CRUISE);
                motorsForward();
            }
            break;

        case STATE_SLOW:
            if (potholeFlag == 0) {
                currentState = STATE_CRUISE;
                motorsSetSpeed(PWM_CRUISE);
                motorsForward();
                Serial.println("[FSM] -> Entered STATE_CRUISE (Road clear)");
            } else {
                motorsSetSpeed(PWM_SLOW);
                motorsForward();
            }
            break;

        case STATE_AVOID:
            // Pivot turn for calibrated turn duration
            if (now - stateStartTimeMs >= TURN_DURATION_MS) {
                currentState = STATE_PASS;
                stateStartTimeMs = now;
                motorsSetSpeed(potholeFlag ? PWM_SLOW : PWM_CRUISE);
                motorsForward();
                Serial.println("[FSM] -> Entered STATE_PASS (Bypassing obstacle)");
            }
            break;

        case STATE_PASS:
            {
                // Monitor side sensor facing the obstacle
                bool sideClear = false;
                if (avoidDirection == AVOID_LEFT) {
                    // We turned left, so obstacle is to our right
                    if (rightDistCm > OBSTACLE_SIDE_CLEAR) sideClear = true;
                } else {
                    // We turned right, so obstacle is to our left
                    if (leftDistCm > OBSTACLE_SIDE_CLEAR) sideClear = true;
                }

                // If side is clear or maximum pass timeout reached, begin return
                if (sideClear || (now - stateStartTimeMs >= PASS_TIMEOUT_MS)) {
                    currentState = STATE_RETURN;
                    stateStartTimeMs = now;
                    motorsSetSpeed(PWM_TURN);
                    if (avoidDirection == AVOID_LEFT) {
                        motorsTurnRight(); // Counter-steer right
                    } else {
                        motorsTurnLeft();  // Counter-steer left
                    }
                    Serial.println("[FSM] -> Entered STATE_RETURN (Counter-steering to original lane)");
                }
            }
            break;

        case STATE_RETURN:
            // Counter-steer for same turn duration to re-align heading
            if (now - stateStartTimeMs >= RETURN_DURATION_MS) {
                avoidDirection = AVOID_NONE;
                currentState = (potholeFlag == 1) ? STATE_SLOW : STATE_CRUISE;
                motorsSetSpeed(potholeFlag ? PWM_SLOW : PWM_CRUISE);
                motorsForward();
                Serial.println("[FSM] -> Evasion complete. Resuming drive heading.");
            }
            break;

        case STATE_BLOCKED:
            motorsStop();
            if (now - lastBlockedRetryMs >= BLOCKED_RETRY_MS) {
                lastBlockedRetryMs = now;
                Serial.println("[FSM] Retrying assessment from BLOCKED state...");
                if (frontDistCm > OBSTACLE_FRONT_THRESH || leftDistCm > OBSTACLE_DEADLOCK || rightDistCm > OBSTACLE_DEADLOCK) {
                    Serial.println("[FSM] Obstacle cleared! Resuming autonomous drive.");
                    currentState = STATE_CRUISE;
                }
            }
            break;
    }
}

// ======================================================================================
// FAIL-SAFE MONITORS
// ======================================================================================

void checkFailSafes() {
    unsigned long now = millis();

    // 1. Laptop Heartbeat Watchdog: If laptop is silent for > 5s, reset pothole flag
    if (potholeFlag == 1 && (now - lastLaptopCmdMs > LAPTOP_HEARTBEAT_TIMEOUT_MS)) {
        Serial.println("[FAILSAFE] Laptop command heartbeat timeout. Resetting pothole slowdown to cruise.");
        potholeFlag = 0;
    }

    // 2. Wi-Fi Background Auto-Recovery
    if (now - lastWifiCheckMs > 5000) {
        lastWifiCheckMs = now;
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("[WIFI WATCHDOG] Connection lost. Attempting reconnect...");
            WiFi.reconnect();
        }
    }
}

// ======================================================================================
// SETUP & MAIN LOOP
// ======================================================================================

void setup() {
    Serial.begin(115200);
    delay(500);

    Serial.println("\n========================================================");
    Serial.println("  AI-Driven Pothole Identification & Obstacle Avoidance ");
    Serial.println("         ESP8266 Main Vehicle Motion Controller         ");
    Serial.println("========================================================");

    motorsInit();
    ultrasonicsInit();

    // Connect to Wi-Fi
    Serial.printf("[WIFI] Connecting to %s...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int retries = 0;
    while (WiFi.status() != WL_CONNECTED && retries < 25) {
        delay(400);
        Serial.print(".");
        retries++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n[WIFI] Connected!");
        Serial.print("[WIFI] Vehicle Controller IP: ");
        Serial.println(WiFi.localIP());

        // Setup REST Server
        setupHttpServer();

        // Enqueue system online boot message
        String bootMsg = String("🤖 Pothole Avoidance Robot Online!\nIP: ") + WiFi.localIP().toString();
        enqueueTelegramAlert(bootMsg, ALERT_BOOT);
    } else {
        Serial.println("\n[WIFI] Connection failed. Running in autonomous offline mode.");
    }

    lastLaptopCmdMs = millis();
    Serial.println("[SYSTEM] Vehicle state machine active in CRUISE mode.");
}

void loop() {
    unsigned long now = millis();

    // 1. Service HTTP Client Requests
    server.handleClient();

    // 2. Periodic Ultrasonic Acquisition (every 65 ms ~ 15 Hz)
    if (now - lastUsSampleMs >= US_SAMPLE_INTERVAL_MS) {
        lastUsSampleMs = now;
        sampleUltrasonicsParallel();
    }

    // 3. Step Autonomous State Machine
    executeStateMachine();

    // 4. Dispatch Queued Telegram Alerts (between motor ticks)
    processTelegramQueue();

    // 5. Run Safety Watchdogs
    checkFailSafes();
}
