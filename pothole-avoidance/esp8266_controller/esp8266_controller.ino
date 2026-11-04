/**
 * ======================================================================================
 * PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
 * MODULE:  ESP8266 Main Vehicle Motion & Safety Controller (Station Mode with Internet)
 * FILE:    esp8266_controller.ino
 * ======================================================================================
 * 
 * DESCRIPTION:
 * 1. Connects to local Wi-Fi Router (Station Mode) so Telegram messages work reliably!
 * 2. Uses proven, rock-solid ultrasonic measurement via getDistance(echoPin) with pulseIn.
 * 3. Obstacle Avoidance Rules:
 *    - Center detected (<= 20 cm): Stop -> Turn LEFT for 1.0 sec -> Continue path
 *    - Left detected (<= 20 cm):   Turn RIGHT for 1.5 sec -> Continue path
 *    - Right detected (<= 20 cm):  Turn LEFT for 1.5 sec -> Continue path
 * 4. Pothole Detection Integration:
 *    - Receives /pothole?state=1 from Laptop AI -> Decelerates to SLOW crawl mode.
 *    - Receives /pothole?state=0 from Laptop AI -> Resumes CRUISE speed.
 * 5. Serves Web Control Dashboard from dashboard.h at http://<ESP8266_IP>/
 * ======================================================================================
 */

#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include "config.h"
#include "dashboard.h"

// ======================================================================================
// FORWARD DECLARATIONS (Prevents compiler scope errors)
// ======================================================================================
void moveForward();
void moveBackward();
void turnLeft();
void turnRight();
void stopMotors();
void setMotorSpeed(uint8_t speed);
long getDistance(uint8_t echoPin);
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
    digitalWrite(PIN_MOTOR_PWM, HIGH);
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
// ULTRASONIC SENSOR MEASUREMENT (HC-SR04)
// ======================================================================================

long getDistance(uint8_t echoPin) {
    // Ensure trigger line is LOW
    digitalWrite(PIN_US_TRIG, LOW);
    delayMicroseconds(2);

    // Send 10us trigger pulse
    digitalWrite(PIN_US_TRIG, HIGH);
    delayMicroseconds(10);
    digitalWrite(PIN_US_TRIG, LOW);

    // Read echo pulse length (timeout at 30ms to prevent blocking too long)
    long duration = pulseIn(echoPin, HIGH, 30000);

    if (duration == 0) return 999; // No echo received, assume clear distance

    // Calculate distance in cm (Speed of sound = 343 m/s)
    return (duration / 2) * 0.0343;
}


// ======================================================================================
// AUTONOMOUS OBSTACLE AVOIDANCE & DRIVING LOGIC
// ======================================================================================

void runAutonomousMode() {
    // 1. Read Front distance
    distFront = getDistance(PIN_US_ECHO_FRONT);
    delay(30); // Prevent acoustic crosstalk between sensor readings

    // Rule 1: Center obstacle detected (<= 20 cm) -> STOP, then turn LEFT for 1.0 sec, continue forward
    if (distFront <= OBSTACLE_THRESH) {
        Serial.printf("[AVOID] Center obstacle (%ld cm) -> STOP & Turn LEFT for 1.0s\n", distFront);
        stopMotors();
        delay(150);

        digitalWrite(PIN_MOTOR_PWM, HIGH);
        turnLeft();
        delay(TURN_CENTER_MS); // 1.0 sec (1000 ms)
        stopMotors();
        delay(100);

        moveForward();
        return;
    }

    // 2. Read Left distance
    distLeft = getDistance(PIN_US_ECHO_LEFT);
    delay(30);

    // Rule 2: Left obstacle detected (<= 20 cm) -> Turn RIGHT for 1.5 sec, continue forward
    if (distLeft <= OBSTACLE_THRESH) {
        Serial.printf("[AVOID] Left obstacle (%ld cm) -> Turn RIGHT for 1.5s\n", distLeft);
        digitalWrite(PIN_MOTOR_PWM, HIGH);
        turnRight();
        delay(TURN_LEFT_MS); // 1.5 sec (1500 ms)
        stopMotors();
        delay(100);

        moveForward();
        return;
    }

    // 3. Read Right distance
    distRight = getDistance(PIN_US_ECHO_RIGHT);
    delay(30);

    // Rule 3: Right obstacle detected (<= 20 cm) -> Turn LEFT for 1.5 sec, continue forward
    if (distRight <= OBSTACLE_THRESH) {
        Serial.printf("[AVOID] Right obstacle (%ld cm) -> Turn LEFT for 1.5s\n", distRight);
        digitalWrite(PIN_MOTOR_PWM, HIGH);
        turnLeft();
        delay(TURN_RIGHT_MS); // 1.5 sec (1500 ms)
        stopMotors();
        delay(100);

        moveForward();
        return;
    }

    // Road Clear -> Drive Forward
    // If Laptop AI signals a pothole, slow down
    if (potholeFlag == 1) {
        analogWrite(PIN_MOTOR_PWM, PWM_SLOW); // Slow crawl for rough road
        moveForward();
    } else {
        digitalWrite(PIN_MOTOR_PWM, HIGH);     // Full cruise power
        moveForward();
    }
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
    json += "\"speed\":" + String(currentSpeed);
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
        digitalWrite(PIN_MOTOR_PWM, HIGH);
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

    // Hold PWM HIGH to keep motors enabled with maximum torque
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

    // Connect to Normal Wi-Fi Router (Station Mode with Internet Access)
    Serial.printf("[WIFI] Connecting to SSID: %s\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int retryCount = 0;
    while (WiFi.status() != WL_CONNECTED && retryCount < 40) {
        delay(300);
        Serial.print(".");
        retryCount++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n[WIFI] Connected to Wi-Fi successfully!");
        Serial.print("[WIFI] Vehicle IP Address: ");
        Serial.println(WiFi.localIP());
        Serial.print("[WIFI] Open Dashboard at: http://");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("\n[WIFI] Wi-Fi connection timed out. Starting fallback AP mode...");
        WiFi.mode(WIFI_AP);
        WiFi.softAP("pothole car", "123456789");
        Serial.print("[WIFI] Fallback AP IP: ");
        Serial.println(WiFi.softAPIP());
    }

    // Setup Web Server Routes (Both API and direct routes)
    server.on("/", HTTP_GET, handleRoot);
    server.on("/status", HTTP_GET, handleStatus);
    server.on("/pothole", HTTP_GET, handlePothole);
    server.on("/drive", HTTP_GET, handleDrive);
    server.on("/mode", HTTP_GET, handleMode);

    // Direct User Test Routes
    server.on("/forward", HTTP_GET, []() {
        if (!isAutoMode) {
            digitalWrite(PIN_MOTOR_PWM, HIGH);
            moveForward();
        }
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "text/plain", "OK");
    });
    server.on("/backward", HTTP_GET, []() {
        if (!isAutoMode) {
            digitalWrite(PIN_MOTOR_PWM, HIGH);
            moveBackward();
        }
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "text/plain", "OK");
    });
    server.on("/left", HTTP_GET, []() {
        if (!isAutoMode) {
            digitalWrite(PIN_MOTOR_PWM, HIGH);
            turnLeft();
        }
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "text/plain", "OK");
    });
    server.on("/right", HTTP_GET, []() {
        if (!isAutoMode) {
            digitalWrite(PIN_MOTOR_PWM, HIGH);
            turnRight();
        }
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "text/plain", "OK");
    });
    server.on("/stop", HTTP_GET, []() {
        if (!isAutoMode) {
            stopMotors();
        }
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

    if (isAutoMode) {
        runAutonomousMode();
    } else {
        // In manual mode, take periodic distance measurements for web dashboard
        static unsigned long lastManualSample = 0;
        if (millis() - lastManualSample >= 250) {
            lastManualSample = millis();
            distFront = getDistance(PIN_US_ECHO_FRONT);
            delay(30);
            distLeft  = getDistance(PIN_US_ECHO_LEFT);
            delay(30);
            distRight = getDistance(PIN_US_ECHO_RIGHT);
        }
    }
}
