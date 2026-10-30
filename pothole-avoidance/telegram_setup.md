# Telegram Bot Setup Guide

This guide walks through creating a Telegram Bot, obtaining your API authentication credentials, retrieving your personal `CHAT_ID`, and verifying notifications from the command line.

---

## 1. Create a New Bot via BotFather

1. Open the Telegram app on your phone, desktop, or web ([web.telegram.org](https://web.telegram.org)).
2. In the global search bar, type `@BotFather` and select the verified account with the blue checkmark.
3. Click **Start** or send the command:
   ```text
   /start
   ```
4. Create a new bot by sending:
   ```text
   /newbot
   ```
5. Follow the interactive prompts:
   - **Bot Name**: Choose a friendly display name (e.g. `Pothole Safety Robot`).
   - **Bot Username**: Choose a unique handle ending in `bot` (e.g. `pothole_safety_car_bot`).
6. BotFather will reply with your **HTTP API Token**. It looks similar to:
   ```text
   7182948291:AAHkLmN98qWzx0_P8qwerTYUiOpASD12345
   ```
   Save this token securely. This is your `TELEGRAM_BOT_TOKEN`.

---

## 2. Obtain Your Personal Chat ID

To allow the bot to send you messages, you must initiate the conversation first (Telegram security prevents bots from sending unsolicited messages to users):

1. Search for your bot's username (e.g. `@pothole_safety_car_bot`) in Telegram.
2. Click **Start** or send any test message, such as `Hello`.
3. Open a web browser or terminal and access the `getUpdates` API endpoint (replace `<YOUR_BOT_TOKEN>` with your actual token):
   ```text
   https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates
   ```
4. You will receive a JSON response formatted like this:
   ```json
   {
     "ok": true,
     "result": [
       {
         "update_id": 987654321,
         "message": {
           "message_id": 1,
           "from": {
             "id": 123456789,
             "is_bot": false,
             "first_name": "John"
           },
           "chat": {
             "id": 123456789,
             "first_name": "John",
             "type": "private"
           },
           "text": "Hello"
         }
       }
     ]
   }
   ```
5. Find the `"chat": { "id": 123456789 }` field. This number (e.g., `123456789`) is your `TELEGRAM_CHAT_ID`.

---

## 3. Verify Message Sending with cURL

Before embedding the credentials in firmware, verify that your bot can successfully deliver messages to your device.

Run the following command in PowerShell, Bash, or Command Prompt (substituting your actual token and chat ID):

### On Linux / macOS / Git Bash:
```bash
curl -s -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/sendMessage" \
     -d "chat_id=<YOUR_CHAT_ID>" \
     -d "text=🚗 Test message: Pothole Avoidance Bot is active!"
```

### On Windows PowerShell:
```powershell
$token = "<YOUR_BOT_TOKEN>"
$chatId = "<YOUR_CHAT_ID>"
$url = "https://api.telegram.org/bot$token/sendMessage"
$body = @{ chat_id = $chatId; text = "🚗 Test message: Pothole Avoidance Bot is active!" }
Invoke-RestMethod -Uri $url -Method Post -Body $body
```

If your bot delivers the notification instantly to your Telegram app, your credentials are confirmed working.

---

## 4. Where to Insert Credentials in the Project

### A) In ESP8266 Firmware (`esp8266_controller/config.h`)
```cpp
// Telegram Bot Credentials
#define TELEGRAM_BOT_TOKEN  "7182948291:AAHkLmN98qWzx0_P8qwerTYUiOpASD12345"
#define TELEGRAM_CHAT_ID    "123456789"
```

### B) In Laptop AI Configuration (`laptop_ai/config.py`)
```python
# Optional secondary Telegram dispatcher from the Python AI server
TELEGRAM_BOT_TOKEN = "7182948291:AAHkLmN98qWzx0_P8qwerTYUiOpASD12345"
TELEGRAM_CHAT_ID = "123456789"
```

> [!CAUTION]
> **Security Notice**: Never commit your real Telegram Bot token to public GitHub or version control repositories. If your token is ever compromised, use `@BotFather` and run `/revoke` to generate a fresh token immediately.
