/**
 * ======================================================================================
 * PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
 * MODULE:  ESP8266 Web Dashboard HTML & JavaScript (Separated from .ino to prevent 
 *          Arduino builder prototype injection and syntax errors)
 * FILE:    dashboard.h
 * ======================================================================================
 */

#ifndef DASHBOARD_H
#define DASHBOARD_H

#include <Arduino.h>

const char INDEX_HTML[] PROGMEM = R"rawliteral(<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pothole Car Dashboard</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; }
    body { background: #0b0f17; color: #f0f4f8; padding: 12px; text-align: center; }
    .header { background: #151d2a; padding: 12px; border-radius: 12px; margin-bottom: 12px; border: 1px solid #233145; }
    h1 { font-size: 1.15rem; color: #00e5ff; letter-spacing: 0.5px; }
    .ip-info { font-size: 0.75rem; color: #8b9bb4; margin-top: 4px; }
    .cam-box { width: 100%; max-width: 480px; margin: 0 auto 10px; background: #000; border-radius: 10px; overflow: hidden; border: 2px solid #233145; min-height: 200px; display: flex; align-items: center; justify-content: center; }
    .cam-box img { width: 100%; display: block; aspect-ratio: 4/3; object-fit: contain; background: #000; transition: transform 0.2s ease; }
    .btn-toolbar { display: flex; justify-content: center; gap: 8px; max-width: 480px; margin: 0 auto 10px; }
    .flip-btn { background: #151d2a; border: 1px solid #00e5ff; color: #00e5ff; padding: 6px 14px; border-radius: 6px; font-size: 0.78rem; font-weight: bold; cursor: pointer; }
    .flip-btn:active { background: #00e5ff; color: #000; }
    .badge { padding: 10px; border-radius: 8px; font-weight: bold; font-size: 0.88rem; margin: 0 auto 10px; max-width: 480px; transition: all 0.3s; }
    .badge-clear { background: rgba(0, 230, 118, 0.15); border: 1px solid #00e676; color: #00e676; }
    .badge-pothole { background: rgba(255, 23, 68, 0.25); border: 1px solid #ff1744; color: #ff1744; }
    .radar { display: flex; justify-content: space-around; max-width: 480px; margin: 0 auto 10px; gap: 8px; }
    .sensor-box { flex: 1; background: #151d2a; padding: 10px 6px; border-radius: 8px; border: 1px solid #233145; }
    .sensor-title { font-size: 0.68rem; color: #8b9bb4; text-transform: uppercase; }
    .sensor-val { font-size: 1.25rem; font-weight: 800; color: #00e5ff; margin-top: 4px; }
    .sensor-warn { color: #ff1744 !important; }
    .mode-row { display: flex; max-width: 480px; margin: 0 auto 10px; gap: 8px; }
    .btn-mode { flex: 1; padding: 12px; border-radius: 8px; border: 1px solid #233145; background: #151d2a; color: #8b9bb4; font-weight: bold; cursor: pointer; transition: 0.2s; font-size: 0.9rem; }
    .btn-mode-active { background: #00e5ff; color: #000; border-color: #00e5ff; font-weight: 800; }
    .controls { max-width: 250px; margin: 0 auto 10px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
    .btn { background: #1c2636; border: 1px solid #33445c; color: #fff; padding: 14px 6px; border-radius: 8px; font-size: 1.1rem; font-weight: bold; cursor: pointer; user-select: none; }
    .btn:active { background: #00e5ff; color: #000; }
    .btn-stop { background: rgba(255, 23, 68, 0.25); border-color: #ff1744; color: #ff1744; }
    .btn-stop:active { background: #ff1744; color: #fff; }
  </style>
</head>
<body>

<div class="header">
  <h1>POTHOLE CAR CONTROL CENTER</h1>
  <div class="ip-info" id="ip-info">Connected to Wi-Fi | Robot Online</div>
</div>

<div class="cam-box">
  <img id="cam-feed" src="http://10.135.210.5:81/stream" onerror="this.alt='Connecting to ESP32-CAM stream...';" alt="ESP32-CAM Live Stream">
</div>

<div class="btn-toolbar">
  <button class="flip-btn" onclick="toggleFlip()">&#128260; FLIP VIDEO 180&deg;</button>
  <button class="flip-btn" onclick="changeCamIp()">&#128247; SET CAM IP</button>
</div>

<div class="badge badge-clear" id="pothole-badge">ROAD STATUS: ALL CLEAR (CRUISE)</div>

<div class="radar">
  <div class="sensor-box">
    <div class="sensor-title">Left Sensor</div>
    <div class="sensor-val" id="val-left">-- cm</div>
  </div>
  <div class="sensor-box">
    <div class="sensor-title">Center (Front)</div>
    <div class="sensor-val" id="val-front">-- cm</div>
  </div>
  <div class="sensor-box">
    <div class="sensor-title">Right Sensor</div>
    <div class="sensor-val" id="val-right">-- cm</div>
  </div>
</div>

<div class="mode-row">
  <button class="btn-mode btn-mode-active" id="btn-manual" onclick="setMode('manual')">MANUAL PILOT</button>
  <button class="btn-mode" id="btn-auto" onclick="setMode('auto')">AUTONOMOUS (AI)</button>
</div>

<div class="controls">
  <div></div>
  <button class="btn" onclick="sendCmd('forward')">&#9650;<br><span style="font-size:0.6rem">FWD</span></button>
  <div></div>
  <button class="btn" onclick="sendCmd('left')">&#9664;<br><span style="font-size:0.6rem">LEFT</span></button>
  <button class="btn btn-stop" onclick="sendCmd('stop')">&#9632;<br><span style="font-size:0.6rem">STOP</span></button>
  <button class="btn" onclick="sendCmd('right')">&#9654;<br><span style="font-size:0.6rem">RIGHT</span></button>
  <div></div>
  <button class="btn" onclick="sendCmd('backward')">&#9660;<br><span style="font-size:0.6rem">REV</span></button>
  <div></div>
</div>

<div style="font-size:0.72rem; color:#8b9bb4; margin-top:8px;">
  Keyboard: W (Fwd), S (Rev), A (Left), D (Right), Space (Stop)
</div>

<script>
  let isFlipped = false;
  const toggleFlip = () => {
    isFlipped = !isFlipped;
    document.getElementById('cam-feed').style.transform = isFlipped ? 'rotate(180deg)' : 'none';
  };

  const changeCamIp = () => {
    let cur = localStorage.getItem('cam_ip') || '10.135.210.5';
    let ip = prompt('Enter ESP32-CAM IP address:', cur);
    if (ip) {
      localStorage.setItem('cam_ip', ip);
      document.getElementById('cam-feed').src = 'http://' + ip + ':81/stream';
    }
  };

  try {
    let savedIp = localStorage.getItem('cam_ip');
    if (savedIp) {
      document.getElementById('cam-feed').src = 'http://' + savedIp + ':81/stream';
    }
  } catch(e) {}

  const sendCmd = async (cmd) => {
    try {
      await fetch('/' + cmd);
    } catch(err) {
      console.error('Command error:', err);
    }
  };

  const setMode = async (mode) => {
    try {
      await fetch('/' + mode);
      await updateStatus();
    } catch(err) {
      console.error('Mode error:', err);
    }
  };

  const updateStatus = async () => {
    try {
      let r = await fetch('/status');
      if (!r.ok) return;
      let d = await r.json();

      let f = document.getElementById('val-front');
      let l = document.getElementById('val-left');
      let rg = document.getElementById('val-right');

      f.innerText = (d.front > 200 ? '>60 cm' : d.front + ' cm');
      l.innerText = (d.left > 200 ? '>60 cm' : d.left + ' cm');
      rg.innerText = (d.right > 200 ? '>60 cm' : d.right + ' cm');

      f.className = (d.front <= 20) ? 'sensor-val sensor-warn' : 'sensor-val';
      l.className = (d.left <= 20) ? 'sensor-val sensor-warn' : 'sensor-val';
      rg.className = (d.right <= 20) ? 'sensor-val sensor-warn' : 'sensor-val';

      let pb = document.getElementById('pothole-badge');
      if (d.pothole === 1) {
        pb.className = 'badge badge-pothole';
        pb.innerText = 'ROAD STATUS: POTHOLE DETECTED (SLOW SPEED)';
      } else {
        pb.className = 'badge badge-clear';
        pb.innerText = 'ROAD STATUS: ALL CLEAR (CRUISE)';
      }

      if (d.mode === 'AUTO') {
        document.getElementById('btn-auto').className = 'btn-mode btn-mode-active';
        document.getElementById('btn-manual').className = 'btn-mode';
      } else {
        document.getElementById('btn-manual').className = 'btn-mode btn-mode-active';
        document.getElementById('btn-auto').className = 'btn-mode';
      }
    } catch(err) {
      console.error('Status fetch error:', err);
    }
  };

  window.addEventListener('keydown', (e) => {
    if (e.key === 'w' || e.key === 'W' || e.key === 'ArrowUp') sendCmd('forward');
    else if (e.key === 's' || e.key === 'S' || e.key === 'ArrowDown') sendCmd('backward');
    else if (e.key === 'a' || e.key === 'A' || e.key === 'ArrowLeft') sendCmd('left');
    else if (e.key === 'd' || e.key === 'D' || e.key === 'ArrowRight') sendCmd('right');
    else if (e.key === ' ') sendCmd('stop');
  });

  setInterval(updateStatus, 300);
  updateStatus();
</script>
</body>
</html>)rawliteral";

#endif // DASHBOARD_H

