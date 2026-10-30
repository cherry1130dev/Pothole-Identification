/**
 * ======================================================================================
 * PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
 * MODULE:  ESP32-CAM Video Streamer Firmware
 * FILE:    esp32cam_stream.ino
 * ======================================================================================
 * 
 * DESCRIPTION:
 * Ultra-lightweight, low-latency MJPEG video streamer running on the AI-Thinker ESP32-CAM.
 * - Streams video exclusively on port 81 at URI: http://<ESP32CAM_IP>:81/stream
 * - Resolution: QVGA (320x240) for < 80ms latency target
 * - JPEG Quality: 12 (high compression, excellent edge sharpness)
 * - Automatic Wi-Fi reconnection watchdog in background
 * 
 * FTDI PROGRAMMING CONNECTION GUIDE:
 * --------------------------------------------------------------------------------------
 * FTDI Programmer (Set to 5V or 3.3V)         ESP32-CAM AI-Thinker
 * --------------------------------------------------------------------------------------
 * VCC (5V recommended for stable current) ---> 5V pin
 * GND -------------------------------------> GND pin
 * TX --------------------------------------> U0R (GPIO 3)
 * RX --------------------------------------> U0T (GPIO 1)
 * 
 * FLASHING PROCEDURE:
 * 1. Connect a jumper wire between GPIO 0 and GND on the ESP32-CAM.
 * 2. Press the onboard RST button once to enter Flash/Bootloader mode.
 * 3. In Arduino IDE:
 *    - Board: "AI Thinker ESP32-CAM"
 *    - CPU Frequency: "240MHz (WiFi/BT)"
 *    - Flash Frequency: "80MHz"
 *    - Flash Mode: "QIO"
 *    - Partition Scheme: "Huge APP (3MB No OTA/1MB SPIFFS)"
 * 4. Click Upload.
 * 5. When upload finishes: REMOVE the jumper wire between GPIO 0 and GND!
 * 6. Press the RST button again to run normal firmware.
 * 7. Open Serial Monitor (115200 baud) to view the assigned IP address.
 * ======================================================================================
 */

#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"
#include "esp_timer.h"
#include "img_converters.h"
#include "fb_gfx.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

// ======================================================================================
// USER NETWORK CONFIGURATION (UPDATE WITH YOUR LOCAL WI-FI DETAILS)
// ======================================================================================
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// Optional Static IP Configuration (set to false to use DHCP)
const bool  USE_STATIC_IP = false;
IPAddress   local_IP(192, 168, 1, 50);
IPAddress   gateway(192, 168, 1, 1);
IPAddress   subnet(255, 255, 255, 0);
IPAddress   primaryDNS(8, 8, 8, 8);

// ======================================================================================
// AI-THINKER ESP32-CAM PIN DEFINITIONS
// ======================================================================================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

#define FLASH_LED_PIN      4

// ======================================================================================
// MJPEG HTTP STREAM HEADERS
// ======================================================================================
#define PART_BOUNDARY "123456789000000000000987654321"
static const char* _STREAM_CONTENT_TYPE = "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* _STREAM_BOUNDARY     = "\r\n--" PART_BOUNDARY "\r\n";
static const char* _STREAM_PART         = "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

httpd_handle_t stream_httpd = NULL;

// Wi-Fi Reconnect Watchdog Timing
unsigned long last_wifi_check_ms = 0;
const unsigned long WIFI_CHECK_INTERVAL_MS = 5000;

// ======================================================================================
// MJPEG STREAM HANDLER (Serves live video at port 81 /stream)
// ======================================================================================
static esp_err_t stream_handler(httpd_req_t *req) {
    camera_fb_t * fb = NULL;
    esp_err_t res = ESP_OK;
    size_t _jpg_buf_len = 0;
    uint8_t * _jpg_buf = NULL;
    char part_buf[64];

    res = httpd_resp_set_type(req, _STREAM_CONTENT_TYPE);
    if (res != ESP_OK) {
        return res;
    }

    // Set CORS headers so web browsers and scripts can access seamlessly
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    while (true) {
        fb = esp_camera_fb_get();
        if (!fb) {
            Serial.println("[ERROR] Camera frame capture failed");
            res = ESP_FAIL;
        } else {
            if (fb->format != PIXFORMAT_JPEG) {
                bool jpeg_converted = frame2jpg(fb, 80, &_jpg_buf, &_jpg_buf_len);
                esp_camera_fb_return(fb);
                fb = NULL;
                if (!jpeg_converted) {
                    Serial.println("[ERROR] JPEG conversion failed");
                    res = ESP_FAIL;
                }
            } else {
                _jpg_buf_len = fb->len;
                _jpg_buf = fb->buf;
            }
        }

        if (res == ESP_OK) {
            size_t hlen = snprintf((char *)part_buf, 64, _STREAM_PART, _jpg_buf_len);
            res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
        }
        if (res == ESP_OK) {
            res = httpd_resp_send_chunk(req, (const char *)_jpg_buf, _jpg_buf_len);
        }
        if (res == ESP_OK) {
            res = httpd_resp_send_chunk(req, _STREAM_BOUNDARY, strlen(_STREAM_BOUNDARY));
        }

        if (fb) {
            esp_camera_fb_return(fb);
            fb = NULL;
            _jpg_buf = NULL;
        } else if (_jpg_buf) {
            free(_jpg_buf);
            _jpg_buf = NULL;
        }

        if (res != ESP_OK) {
            break;
        }
    }
    return res;
}

// ======================================================================================
// START HTTP STREAM SERVER ON PORT 81
// ======================================================================================
void startCameraServer() {
    httpd_config_t config = HTTPD_DEFAULT_CONFIG();
    config.server_port = 81;
    config.ctrl_port = 32768;

    httpd_uri_t stream_uri = {
        .uri       = "/stream",
        .method    = HTTP_GET,
        .handler   = stream_handler,
        .user_ctx  = NULL
    };

    Serial.printf("[HTTP] Starting stream server on port %d...\n", config.server_port);
    if (httpd_start(&stream_httpd, &config) == ESP_OK) {
        httpd_register_uri_handler(stream_httpd, &stream_uri);
        Serial.println("[HTTP] Stream server started successfully!");
    } else {
        Serial.println("[ERROR] Failed to start HTTP stream server!");
    }
}

// ======================================================================================
// INITIALIZE CAMERA HARDWARE
// ======================================================================================
bool initCamera() {
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer   = LEDC_TIMER_0;
    config.pin_d0       = Y2_GPIO_NUM;
    config.pin_d1       = Y3_GPIO_NUM;
    config.pin_d2       = Y4_GPIO_NUM;
    config.pin_d3       = Y5_GPIO_NUM;
    config.pin_d4       = Y6_GPIO_NUM;
    config.pin_d5       = Y7_GPIO_NUM;
    config.pin_d6       = Y8_GPIO_NUM;
    config.pin_d7       = Y9_GPIO_NUM;
    config.pin_xclk     = XCLK_GPIO_NUM;
    config.pin_pclk     = PCLK_GPIO_NUM;
    config.pin_vsync    = VSYNC_GPIO_NUM;
    config.pin_href     = HREF_GPIO_NUM;
    config.pin_sscb_sda = SIOD_GPIO_NUM;
    config.pin_sscb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn     = PWDN_GPIO_NUM;
    config.pin_reset    = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;

    // Use PSRAM if available for higher frame buffering
    if (psramFound()) {
        Serial.println("[CAM] PSRAM detected! Enabling dual frame buffers.");
        config.frame_size   = FRAMESIZE_QVGA;  // 320x240 for minimum latency
        config.jpeg_quality = 12;              // 10-14 gives optimal speed & quality
        config.fb_count     = 2;
        config.grab_mode    = CAMERA_GRAB_LATEST; // Always keep the freshest frame
    } else {
        Serial.println("[CAM] WARNING: No PSRAM detected. Using internal DRAM.");
        config.frame_size   = FRAMESIZE_QVGA;
        config.jpeg_quality = 14;
        config.fb_count     = 1;
        config.grab_mode    = CAMERA_GRAB_WHEN_EMPTY;
    }

    // Initialize the camera sensor
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("[ERROR] Camera initialization failed with error: 0x%x\n", err);
        return false;
    }

    sensor_t * s = esp_camera_sensor_get();
    if (s != NULL) {
        // Road-oriented sensor tuning: drop shadows / enhance contrast
        s->set_brightness(s, 1);     // -2 to 2
        s->set_contrast(s, 1);       // -2 to 2
        s->set_saturation(s, 0);     // -2 to 2
        s->set_whitebal(s, 1);       // Auto white balance
        s->set_awb_gain(s, 1);       // AWB Gain
        s->set_wb_mode(s, 0);        // Auto WB mode
        s->set_vflip(s, 0);          // Flip vertical if camera mounted upside down
        s->set_hmirror(s, 0);        // Mirror horizontal
    }

    Serial.println("[CAM] Camera sensor initialized successfully.");
    return true;
}

// ======================================================================================
// WI-FI SETUP & WATCHDOG
// ======================================================================================
void connectWiFi() {
    Serial.printf("[WIFI] Connecting to SSID: %s\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);

    if (USE_STATIC_IP) {
        WiFi.config(local_IP, gateway, subnet, primaryDNS);
        Serial.print("[WIFI] Static IP configured: ");
        Serial.println(local_IP);
    }

    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 25) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n[WIFI] Connected successfully!");
        Serial.print("[WIFI] ESP32-CAM IP Address: ");
        Serial.println(WiFi.localIP());
        Serial.printf("[WIFI] MJPEG Stream URL: http://%s:81/stream\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\n[WIFI] Initial connection failed. Background watchdog will retry.");
    }
}

void wifiWatchdog() {
    if (millis() - last_wifi_check_ms > WIFI_CHECK_INTERVAL_MS) {
        last_wifi_check_ms = millis();
        if (WiFi.status() != WL_CONNECTED) {
            Serial.println("[WIFI WATCHDOG] Connection dropped! Attempting reconnect...");
            WiFi.disconnect();
            WiFi.reconnect();
        }
    }
}

// ======================================================================================
// ARDUINO SETUP & MAIN LOOP
// ======================================================================================
void setup() {
    // Disable brownout detector to prevent false reset during Wi-Fi power spikes
    WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);

    Serial.begin(115200);
    delay(1000);
    Serial.println("\n========================================================");
    Serial.println("  AI-Driven Pothole Identification & Obstacle Avoidance ");
    Serial.println("           ESP32-CAM MJPEG Video Streamer               ");
    Serial.println("========================================================");

    // Initialize flash LED pin as output and turn OFF
    pinMode(FLASH_LED_PIN, OUTPUT);
    digitalWrite(FLASH_LED_PIN, LOW);

    // Initialize Camera
    if (!initCamera()) {
        Serial.println("[CRITICAL] Camera init failed! Halting.");
        while (true) {
            digitalWrite(FLASH_LED_PIN, HIGH);
            delay(100);
            digitalWrite(FLASH_LED_PIN, LOW);
            delay(100);
        }
    }

    // Connect to Wi-Fi
    connectWiFi();

    // Start HTTP stream server on port 81
    startCameraServer();

    Serial.println("[SYSTEM] Ready! Point your browser or Python script to the stream URL.");
}

void loop() {
    // Keep Wi-Fi connection alive
    wifiWatchdog();
    delay(100);
}
