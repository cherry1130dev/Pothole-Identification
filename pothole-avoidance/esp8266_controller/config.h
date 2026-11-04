/**
 * ======================================================================================
 * PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
 * MODULE:  ESP8266 Vehicle Controller Configuration
 * FILE:    config.h
 * ======================================================================================
 */

#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ======================================================================================
// 1. WI-FI ROUTER CREDENTIALS (Normal Wi-Fi Station Mode with Internet for Telegram)
// ======================================================================================
#define WIFI_SSID               "Easitronics"
#define WIFI_PASSWORD           "123456789"
#define HTTP_SERVER_PORT        80

// ======================================================================================
// 2. HARDWARE PIN DEFINITIONS (NodeMCU ESP8266)
// ======================================================================================
// Motor Driver L298N Direction Pins
#define PIN_MOTOR_IN1           5   // D1 (GPIO 5)  - Left Motor Fwd
#define PIN_MOTOR_IN2           4   // D2 (GPIO 4)  - Left Motor Rev
#define PIN_MOTOR_IN3           0   // D3 (GPIO 0)  - Right Motor Fwd (10k PU)
#define PIN_MOTOR_IN4           15  // D8 (GPIO 15) - Right Motor Rev (10k PD)
#define PIN_MOTOR_PWM           2   // D4 (GPIO 2)  - Speed PWM / Enable

// Ultrasonic Sensor Array (HC-SR04)
#define PIN_US_TRIG             14  // D5 (GPIO 14) - Shared Trigger line
#define PIN_US_ECHO_FRONT       12  // D6 (GPIO 12) - Center (Front) Echo
#define PIN_US_ECHO_LEFT        13  // D7 (GPIO 13) - Left Echo
#define PIN_US_ECHO_RIGHT       16  // D0 (GPIO 16) - Right Echo

// ======================================================================================
// 3. OBSTACLE AVOIDANCE & SPEED PARAMETERS
// ======================================================================================
#define OBSTACLE_THRESH         20   // Distance in cm to trigger avoidance (20 cm)
#define PWM_CRUISE              255  // Normal driving speed (0-255)
#define PWM_SLOW                120  // Pothole rough-patch slowdown speed (0-255)

// Avoidance Timings (Milliseconds)
// 1. Center detected: Stop -> Turn LEFT for 1.0 sec (1000 ms) -> Continue path
#define TURN_CENTER_MS          1000
// 2. Left detected: Turn RIGHT for 1.5 sec (1500 ms) -> Continue path
#define TURN_LEFT_MS            1500
// 3. Right detected: Turn LEFT for 1.5 sec (1500 ms) -> Continue path
#define TURN_RIGHT_MS           1500

#endif // CONFIG_H
