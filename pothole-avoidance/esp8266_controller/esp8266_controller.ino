/**
 * ======================================================================================
 * PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
 * MODULE:  ESP8266 Main Vehicle Motion & Safety Controller
 * FILE:    esp8266_controller.ino
 * ======================================================================================
 * 
 * DESCRIPTION:
 * 1. Connects to Device Hotspot (Station Mode: SSID "Pothole car" / "123456789")
 *    so the dashboard & Telegram alerts have full internet access.
 * 2. Auto-discovers the ESP32-CAM IP via UDP broadcast on port 4210.
 * 3. Uses rock-solid ultrasonic measurement via getDistance(echoPin) with pulseIn.
 * 4. Obstacle Avoidance Rules:
 *    - Center detected (<= 20 cm): Stop -> Turn LEFT for 1.0 sec -> Continue path
 *    - Left detected (<= 20 cm):   Turn RIGHT for 1.5 sec -> Continue path
 *    - Right detected (<= 20 cm):  Turn LEFT for 1.5 sec -> Continue path
 * 5. Pothole Detection Integration (Driven directly by Dashboard Image Processing):
 *    - Receives /pothole?state=1 -> Decelerates to SLOW crawl mode.
 *    - Receives /pothole?state=0 -> Resumes CRUISE speed.
 * 6. Serves All-in-One Web Control + AI Image Processing Dashboard from dashboard.h.
 * ======================================================================================
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <WiFiUdp.h>
#include "config.h"
#include "dashboard.h"

// ======================================================================================
// FORWARD DECLARATIONS
// ======================================================================================
void moveForward();
void moveBackward();
void turnLeft();
void turnRight();
void stopMotors();
void setMotorSpeed(uint8_t speed);
long getDistance(uint8_t echoPin);
void safeDelay(unsigned long ms);
void checkCamDiscovery();
void runAutonomousMode();
void handleRoot();
void handleStatus();
void handlePothole();
void handleDrive();
void handleMode();

// ======================================================================================
// GLOBAL STATE VARIABLES
// ======================================================================================
bool isAutoMode = false;
int potholeFlag = 0; // 0 = Clear road, 1 = Pothole rough patch
uint8_t currentSpeed = PWM_CRUISE;

// Live Distances (cm)
long distFront = 999;
long distLeft  = 999;
long distRight = 999;

// Auto-discovered ESP32-CAM IP on the Hotspot
String discoveredCamIp = "";
WiFiUDP udpDiscovery;

ESP8266WebServer server(HTTP_SERVER_PORT);


// ======================================================================================
// MOTOR ACTUATION SUBSYSTEM (L298N)
// ======================================================================================

void setMotorSpeed(uint8_t speed) {
    currentSpeed = speed;
    if (speed >= 250) {
        digitalWrite(PIN_MOTOR_PWM, HIGH);
    } else {
        analogWrite(PIN_MOTOR_PWM, currentSpeed);
    }
}

void moveForward() {
    if (potholeFlag == 1) {
        analogWrite(PIN_MOTOR_PWM, PWM_SLOW);
    } else {
        digitalWrite(PIN_MOTOR_PWM, HIGH);
    }
    digitalWrite(PIN_MOTOR_IN1, HIGH); digitalWrite(PIN_MOTOR_IN2, LOW);
    digitalWrite(PIN_MOTOR_IN3, HIGH); digitalWrite(PIN_MOTOR_IN4, LOW);
}

void moveBackward() {
    digitalWrite(PIN_MOTOR_PWM, HIGH);
    digitalWrite(PIN_MOTOR_IN1, LOW);  digitalWrite(PIN_MOTOR_IN2, HIGH);
    digitalWrite(PIN_MOTOR_IN3, LOW);  digitalWrite(PIN_MOTOR_IN4, HIGH);
}

void turnLeft() {
    // Pivot turn left: Left reverse, Right forward
    digitalWrite(PIN_MOTOR_PWM, HIGH);
    digitalWrite(PIN_MOTOR_IN1, LOW);  digitalWrite(PIN_MOTOR_IN2, HIGH);
    digitalWrite(PIN_MOTOR_IN3, HIGH); digitalWrite(PIN_MOTOR_IN4, LOW);
}

void turnRight() {
    // Pivot turn right: Left forward, Right reverse
    digitalWrite(PIN_MOTOR_PWM, HIGH);
    digitalWrite(PIN_MOTOR_IN1, HIGH); digitalWrite(PIN_MOTOR_IN2, LOW);
    digitalWrite(PIN_MOTOR_IN3, LOW);  digitalWrite(PIN_MOTOR_IN4, HIGH);
}

void stopMotors() {
    digitalWrite(PIN_MOTOR_IN1, LOW); digitalWrite(PIN_MOTOR_IN2, LOW);
    digitalWrite(PIN_MOTOR_IN3, LOW); digitalWrite(PIN_MOTOR_IN4, LOW);
}


// ======================================================================================
// ULTRASONIC SENSOR MEASUREMENT (HC-SR04) & RESPONSIVE DELAY
// ======================================================================================

long getDistance(uint8_t echoPin) {
    digitalWrite(PIN_US_TRIG, LOW);
    delayMicroseconds(2);

    digitalWrite(PIN_US_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_US_TRIG, LOW);

    long duration = pulseIn(echoPin, HIGH, 30000);
    if (duration == 0) return 999;

    return (duration / 2) * 0.0343;
}

void safeDelay(unsigned long ms) {
    unsigned long start = millis();
    while (millis() - start < ms) {
        server.handleClient();
        if (!isAutoMode) {
            return; // Abort maneuver immediately if switched to manual or stopped
        }
        yield();
        delay(5);
    }
}

void checkCamDiscovery() {
    int packetSize = udpDiscovery.parsePacket();
    if (packetSize > 0) {
        char buf[64];
        int len = udpDiscovery.read(buf, sizeof(buf) - 1);
        if (len > 0) {
            buf[len] = '\0';
            String msg = String(buf);
            if (msg.startsWith("POTHOLE_CAM:")) {
                String newIp = msg.substring(12);
                newIp.trim();
                if (newIp.length() > 6 && newIp != discoveredCamIp) {
                    discoveredCamIp = newIp;
                    Serial.printf("[DISCOVERY] ESP32-CAM found at: http://%s:81/stream\n", discoveredCamIp.c_str());
                }
            }
        }
    }
}


// ======================================================================================
// AUTONOMOUS OBSTACLE AVOIDANCE & DRIVING LOGIC
// ======================================================================================

void runAutonomousMode() {
    // 1. Read Front distance
    distFront = getDistance(PIN_US_ECHO_FRONT);
    safeDelay(30);
    if (!isAutoMode) return;

    // Rule 1: Center obstacle detected (<= 20 cm) -> STOP, then turn LEFT for 1.0 sec, continue forward
    if (distFront <= OBSTACLE_THRESH) {
        Serial.printf("[AVOID] Center obstacle (%ld cm) -> STOP & Turn LEFT for 1.0s\n", distFront);
        stopMotors();
        safeDelay(150);
        if (!isAutoMode) return;

        turnLeft();
        safeDelay(TURN_CENTER_MS); // 1.0 sec (1000 ms)
        if (!isAutoMode) return;
        stopMotors();
        safeDelay(100);
        if (!isAutoMode) return;

        moveForward();
        return;
    }

    // 2. Read Left distance
    distLeft = getDistance(PIN_US_ECHO_LEFT);
    safeDelay(30);
    if (!isAutoMode) return;

    // Rule 2: Left obstacle detected (<= 20 cm) -> Reversed turn call so robot moves away to right
    if (distLeft <= OBSTACLE_THRESH) {
        Serial.printf("[AVOID] Left obstacle (%ld cm) -> Avoid RIGHT (turnLeft) for 1.5s\n", distLeft);
        turnLeft();
        safeDelay(TURN_LEFT_MS); // 1.5 sec (1500 ms)
        if (!isAutoMode) return;
        stopMotors();
        safeDelay(100);
        if (!isAutoMode) return;

        moveForward();
        return;
    }

    // 3. Read Right distance
    distRight = getDistance(PIN_US_ECHO_RIGHT);
    safeDelay(30);
    if (!isAutoMode) return;

    // Rule 3: Right obstacle detected (<= 20 cm) -> Reversed turn call so robot moves away to left
    if (distRight <= OBSTACLE_THRESH) {
        Serial.printf("[AVOID] Right obstacle (%ld cm) -> Avoid LEFT (turnRight) for 1.5s\n", distRight);
        turnRight();
        safeDelay(TURN_RIGHT_MS); // 1.5 sec (1500 ms)
        if (!isAutoMode) return;
        stopMotors();
        safeDelay(100);
        if (!isAutoMode) return;

        moveForward();
        return;
    }

    // Road Clear -> Drive Forward (respecting pothole slowdown flag)
    moveForward();
}


// ======================================================================================
// WEB SERVER ROUTES & REST API
// ======================================================================================

void handleRoot() {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send_P(200, "text/html", INDEX_HTML);
}

void handleStatus() {
    String json = "{";
    json += "\"mode\":\"" + String(isAutoMode ? "AUTO" : "MANUAL") + "\",";
    json += "\"front\":" + String(distFront) + ",";
    json += "\"left\":" + String(distLeft) + ",";
    json += "\"right\":" + String(distRight) + ",";
    json += "\"pothole\":" + String(potholeFlag) + ",";
    json += "\"speed\":" + String(currentSpeed) + ",";
    json += "\"cam_ip\":\"" + discoveredCamIp + "\",";
    json += "\"ip\":\"" + WiFi.localIP().toString() + "\"";
    json += "}";
    server.sendHeader("Access-Control-Allow-Origin", "*");
    server.send(200, "application/json", json);
}

void handlePothole() {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    if (server.hasArg("state")) {
        potholeFlag = server.arg("state").toInt();
        if (potholeFlag == 1) {
            setMotorSpeed(PWM_SLOW);
        } else {
            setMotorSpeed(PWM_CRUISE);
        }
        server.send(200, "application/json", "{\"status\":\"ok\",\"pothole\":" + String(potholeFlag) + "}");
    } else {
        server.send(400, "text/plain", "Missing state parameter");
    }
}

void handleDrive() {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    if (server.hasArg("cmd")) {
        isAutoMode = false;
        String cmd = server.arg("cmd");
        cmd.toUpperCase();
        char c = cmd.charAt(0);

        switch (c) {
            case 'F': moveForward(); break;
            case 'B': moveBackward(); break;
            case 'L': turnLeft(); break;
            case 'R': turnRight(); break;
            case 'S': stopMotors(); break;
            default: break;
        }
        server.send(200, "application/json", "{\"status\":\"ok\",\"cmd\":\"" + cmd + "\"}");
    } else {
        server.send(400, "text/plain", "Missing cmd parameter");
    }
}

void handleMode() {
    server.sendHeader("Access-Control-Allow-Origin", "*");
    if (server.hasArg("auto")) {
        int autoVal = server.arg("auto").toInt();
        isAutoMode = (autoVal == 1);
        if (!isAutoMode) {
            stopMotors();
        }
        server.send(200, "application/json", "{\"status\":\"ok\",\"auto\":" + String(isAutoMode) + "}");
    } else {
        server.send(400, "text/plain", "Missing auto parameter");
    }
}


// ======================================================================================
// ARDUINO SETUP & MAIN LOOP
// ======================================================================================

void setup() {
    Serial.begin(115200);
    delay(200);
    Serial.println("\n\n=======================================================");
    Serial.println("  AI-DRIVEN POTHOLE CAR & SAFETY CONTROLLER            ");
    Serial.println("=======================================================");

    // Initialize Motor Pins
    pinMode(PIN_MOTOR_IN1, OUTPUT);
    pinMode(PIN_MOTOR_IN2, OUTPUT);
    pinMode(PIN_MOTOR_IN3, OUTPUT);
    pinMode(PIN_MOTOR_IN4, OUTPUT);
    pinMode(PIN_MOTOR_PWM, OUTPUT);

    digitalWrite(PIN_MOTOR_PWM, HIGH);
    stopMotors();
    Serial.println("[MOTORS] L298N initialized and stopped.");

    // Initialize Ultrasonic Pins
    pinMode(PIN_US_TRIG, OUTPUT);
    digitalWrite(PIN_US_TRIG, LOW);
    pinMode(PIN_US_ECHO_FRONT, INPUT);
    pinMode(PIN_US_ECHO_LEFT, INPUT);
    pinMode(PIN_US_ECHO_RIGHT, INPUT);
    Serial.println("[ULTRASONICS] Sensors initialized.");

    // Connect to Device Hotspot (Station Mode: "Pothole car")
    Serial.printf("[WIFI] Connecting to Hotspot SSID: %s\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.persistent(true);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int retryCount = 0;
    while (WiFi.status() != WL_CONNECTED && retryCount < 45) {
        delay(400);
        Serial.print(".");
        retryCount++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n[WIFI] Connected to Hotspot successfully!");
        Serial.print("[WIFI] Vehicle IP Address: ");
        Serial.println(WiFi.localIP());
        Serial.print("[WIFI] Open Dashboard at: http://");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("\n[WIFI] Still waiting for Hotspot 'Pothole car' (will auto-connect when available)...");
    }

    // Start UDP Listener for ESP32-CAM Auto-Discovery
    udpDiscovery.begin(CAM_DISCOVERY_UDP_PORT);
    Serial.printf("[DISCOVERY] Listening for ESP32-CAM beacon on UDP port %d\n", CAM_DISCOVERY_UDP_PORT);

    // Setup Web Server Routes
    server.on("/", HTTP_GET, handleRoot);
    server.on("/status", HTTP_GET, handleStatus);
    server.on("/pothole", HTTP_GET, handlePothole);
    server.on("/drive", HTTP_GET, handleDrive);
    server.on("/mode", HTTP_GET, handleMode);

    // Direct Control Routes
    server.on("/forward", HTTP_GET, []() {
        if (!isAutoMode) {
            moveForward();
        }
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "text/plain", "OK");
    });
    server.on("/backward", HTTP_GET, []() {
        if (!isAutoMode) {
            moveBackward();
        }
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "text/plain", "OK");
    });
    server.on("/left", HTTP_GET, []() {
        if (!isAutoMode) {
            turnLeft();
        }
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "text/plain", "OK");
    });
    server.on("/right", HTTP_GET, []() {
        if (!isAutoMode) {
            turnRight();
        }
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "text/plain", "OK");
    });
    server.on("/stop", HTTP_GET, []() {
        isAutoMode = false;
        stopMotors();
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "text/plain", "OK");
    });
    server.on("/auto", HTTP_GET, []() {
        isAutoMode = true;
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "text/plain", "OK");
    });
    server.on("/manual", HTTP_GET, []() {
        isAutoMode = false;
        stopMotors();
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "text/plain", "OK");
    });

    server.begin();
    Serial.println("[HTTP] Web Server started on port 80.\n");
}

void loop() {
    server.handleClient();
    checkCamDiscovery();

    // Wi-Fi IP announcement when reconnected after boot
    static bool wasConnected = (WiFi.status() == WL_CONNECTED);
    bool isConnected = (WiFi.status() == WL_CONNECTED);
    if (isConnected && !wasConnected) {
        Serial.printf("\n[WIFI] Connected! Dashboard: http://%s/\n", WiFi.localIP().toString().c_str());
    }
    wasConnected = isConnected;

    if (isAutoMode) {
        runAutonomousMode();
    } else {
        // Non-blocking round-robin ultrasonic sampling (1 sensor per 90ms cycle)
        static unsigned long lastManualSample = 0;
        static uint8_t sensorIdx = 0;
        if (millis() - lastManualSample >= 90) {
            lastManualSample = millis();
            if (sensorIdx == 0) distFront = getDistance(PIN_US_ECHO_FRONT);
            else if (sensorIdx == 1) distLeft  = getDistance(PIN_US_ECHO_LEFT);
            else distRight = getDistance(PIN_US_ECHO_RIGHT);
            sensorIdx = (sensorIdx + 1) % 3;
        }
    }
}
