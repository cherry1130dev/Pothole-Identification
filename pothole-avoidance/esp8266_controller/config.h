/**
 * ======================================================================================
 * PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
 * MODULE:  ESP8266 Vehicle Controller Configuration
 * FILE:    config.h
 * ======================================================================================
 * 
 * DESCRIPTION:
 * All user credentials, hardware pin mappings, ultrasonic thresholds, motor speeds,
 * and timing parameters are centralized in this header file.
 * ======================================================================================
 */

#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>

// ======================================================================================
// 1. WI-FI & TELEGRAM CREDENTIALS
// ======================================================================================
#define WIFI_SSID               "YOUR_WIFI_SSID"
#define WIFI_PASSWORD           "YOUR_WIFI_PASSWORD"

// Telegram Bot Credentials (Get from @BotFather in Telegram)
#define TELEGRAM_BOT_TOKEN      "9138292752:AAFdtNKDLzFQVDEwx8mSyhJ1kMcRNApC0xg"
#define TELEGRAM_CHAT_ID        "2022474265"        // e.g. "123456789"

// Web Server Port
#define HTTP_SERVER_PORT        80

// ======================================================================================
// 2. HARDWARE PIN DEFINITIONS (NodeMCU ESP8266)
// ======================================================================================

// Motor Driver L298N Direction Pins
#define PIN_MOTOR_IN1           5   // D1 (GPIO 5)  - Left Motor Fwd
#define PIN_MOTOR_IN2           4   // D2 (GPIO 4)  - Left Motor Rev
#define PIN_MOTOR_IN3           0   // D3 (GPIO 0)  - Right Motor Fwd (10k PU required)
#define PIN_MOTOR_IN4           15  // D8 (GPIO 15) - Right Motor Rev (10k PD required)

// Motor Speed PWM (ENA and ENB tied together)
#define PIN_MOTOR_PWM           2   // D4 (GPIO 2)  - Speed PWM (10k PU required)

// Ultrasonic Sensor Array (HC-SR04)
#define PIN_US_TRIG             14  // D5 (GPIO 14) - Shared Trigger line for all 3 sensors
#define PIN_US_ECHO_FRONT       12  // D6 (GPIO 12) - Front Sensor Echo (via 1k/2k divider)
#define PIN_US_ECHO_LEFT        13  // D7 (GPIO 13) - Left Sensor Echo (via 1k/2k divider)
#define PIN_US_ECHO_RIGHT       16  // D0 (GPIO 16) - Right Sensor Echo (via 1k/2k divider)

// Optional Onboard Indicator LED
#define PIN_LED_STATUS          2   // D4 (GPIO 2) is active-low onboard LED (shared with PWM)

// ======================================================================================
// 3. MOTOR SPEED & PWM CALIBRATION (Range: 0 - 255)
// ======================================================================================
#define PWM_CRUISE              180  // Normal cruising speed (~70% duty cycle)
#define PWM_SLOW                110  // Pothole rough-patch speed (~43% duty cycle)
#define PWM_TURN                175  // Pivot turn speed during obstacle evasion
#define PWM_STOP                0    // Dead stop

// Left / Right Motor Speed Balance (trim factor if vehicle drifts slightly)
#define MOTOR_TRIM_LEFT         1.00
#define MOTOR_TRIM_RIGHT        1.00

// ======================================================================================
// 4. ULTRASONIC THRESHOLDS & TIMING
// ======================================================================================
#define OBSTACLE_FRONT_THRESH   25.0f  // Obstacle avoidance trigger distance (cm)
#define OBSTACLE_SIDE_CLEAR     28.0f  // Distance considered "clear" on sides (cm)
#define OBSTACLE_DEADLOCK       15.0f  // All 3 blocked trigger distance (cm)
#define US_TIMEOUT_MICROS       23520  // ~400 cm maximum timeout (round-trip microseconds)
#define US_SAMPLE_INTERVAL_MS   65     // Interval between ultrasonic measurements (~15 Hz)

// ======================================================================================
// 5. OBSTACLE AVOIDANCE STATE TIMING (Milliseconds)
// ======================================================================================
#define TURN_DURATION_MS        450    // Time to pivot ~45 degrees away from obstacle
#define PASS_TIMEOUT_MS         1800   // Max time to drive forward in bypass before return
#define RETURN_DURATION_MS      450    // Counter-steer duration to restore original lane
#define BLOCKED_RETRY_MS        2000   // Retry interval when trapped in BLOCKED state

// ======================================================================================
// 6. FAIL-SAFES & RATE LIMITS
// ======================================================================================
#define LAPTOP_HEARTBEAT_TIMEOUT_MS  5000   // Reset pothole slowdown if laptop is silent for 5s
#define TELEGRAM_COOLDOWN_MS         15000  // Minimum cooldown between repeated alerts
#define TELEGRAM_MAX_QUEUE           6      // Maximum pending alert messages in queue

#endif // CONFIG_H
