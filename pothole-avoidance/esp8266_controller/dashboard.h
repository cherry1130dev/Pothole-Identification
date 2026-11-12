/**
 * ======================================================================================
 * PROJECT: AI-Driven Pothole Identification and Smart Obstacle Avoidance System
 * MODULE:  ESP8266 All-in-One Web Control & Browser-Side Image Processing Dashboard
 * FILE:    dashboard.h
 * ======================================================================================
 * Note: Kept in .h header using ES6 arrow functions so Arduino IDE's preprocessor
 * never injects C++ prototypes into the JavaScript code.
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
    .header { background: #151d2a; padding: 12px; border-radius: 12px; margin-bottom: 10px; border: 1px solid #233145; max-width: 500px; margin-left: auto; margin-right: auto; }
    h1 { font-size: 1.1rem; color: #00e5ff; letter-spacing: 0.5px; }
    .ip-info { font-size: 0.74rem; color: #8b9bb4; margin-top: 4px; }
    .cam-wrap { position: relative; width: 100%; max-width: 480px; margin: 0 auto 10px; background: #000; border-radius: 10px; overflow: hidden; border: 2px solid #233145; aspect-ratio: 4/3; display: flex; align-items: center; justify-content: center; }
    .cam-wrap img { width: 100%; height: 100%; display: block; object-fit: contain; background: #000; transition: transform 0.2s ease; }
    .cam-wrap canvas { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; }
    .cam-msg { position: absolute; bottom: 6px; left: 8px; right: 8px; font-size: 0.7rem; background: rgba(11,15,23,0.78); color: #8b9bb4; padding: 4px 8px; border-radius: 5px; pointer-events: none; }
    .btn-toolbar { display: flex; flex-wrap: wrap; justify-content: center; gap: 6px; max-width: 480px; margin: 0 auto 8px; }
    .tool-btn { background: #151d2a; border: 1px solid #00e5ff; color: #00e5ff; padding: 6px 10px; border-radius: 6px; font-size: 0.74rem; font-weight: bold; cursor: pointer; }
    .tool-btn.active { background: #00e5ff; color: #000; }
    .tool-btn:active { opacity: 0.8; }
    .cam-bar { display: flex; gap: 6px; max-width: 480px; margin: 0 auto 10px; }
    .cam-bar input { flex: 1; background: #151d2a; border: 1px solid #233145; color: #f0f4f8; padding: 6px 10px; border-radius: 6px; font-size: 0.8rem; outline: none; }
    .badge { padding: 10px; border-radius: 8px; font-weight: bold; font-size: 0.86rem; margin: 0 auto 10px; max-width: 480px; transition: all 0.25s; }
    .badge-clear { background: rgba(0, 230, 118, 0.14); border: 1px solid #00e676; color: #00e676; }
    .badge-pothole { background: rgba(255, 23, 68, 0.25); border: 1px solid #ff1744; color: #ff1744; }
    .radar { display: flex; justify-content: space-around; max-width: 480px; margin: 0 auto 10px; gap: 8px; }
    .sensor-box { flex: 1; background: #151d2a; padding: 10px 6px; border-radius: 8px; border: 1px solid #233145; }
    .sensor-title { font-size: 0.66rem; color: #8b9bb4; text-transform: uppercase; }
    .sensor-val { font-size: 1.2rem; font-weight: 800; color: #00e5ff; margin-top: 4px; }
    .sensor-warn { color: #ff1744 !important; }
    .mode-row { display: flex; max-width: 480px; margin: 0 auto 10px; gap: 8px; }
    .btn-mode { flex: 1; padding: 11px; border-radius: 8px; border: 1px solid #233145; background: #151d2a; color: #8b9bb4; font-weight: bold; cursor: pointer; font-size: 0.86rem; }
    .btn-mode-active { background: #00e5ff; color: #000; border-color: #00e5ff; font-weight: 800; }
    .controls { max-width: 245px; margin: 0 auto 10px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
    .btn { background: #1c2636; border: 1px solid #33445c; color: #fff; padding: 13px 6px; border-radius: 8px; font-size: 1.05rem; font-weight: bold; cursor: pointer; user-select: none; }
    .btn:active { background: #00e5ff; color: #000; }
    .btn-stop { background: rgba(255, 23, 68, 0.25); border-color: #ff1744; color: #ff1744; }
    .btn-stop:active { background: #ff1744; color: #fff; }
  </style>
</head>
<body>

<div class="header">
  <h1>POTHOLE CAR CONTROL &amp; AI DASHBOARD</h1>
  <div class="ip-info" id="ip-info">Hotspot: Pothole car | Connecting...</div>
</div>

<div class="cam-wrap">
  <img id="cam-feed" crossorigin="anonymous" alt="Waiting for ESP32-CAM stream...">
  <canvas id="ai-overlay" width="320" height="240"></canvas>
  <div class="cam-msg" id="ai-telemetry">AI Image Processing: Initializing...</div>
</div>

<div class="cam-bar">
  <input type="text" id="cam-ip-input" placeholder="ESP32-CAM IP (auto-detecting...)">
  <button class="tool-btn" onclick="applyCamIp()">CONNECT</button>
  <button class="tool-btn" id="btn-scan" onclick="scanForCam()">SCAN</button>
</div>

<div class="btn-toolbar">
  <button class="tool-btn active" id="btn-ai" onclick="toggleAI()">AI VISION: ON</button>
  <button class="tool-btn active" id="btn-tg" onclick="toggleTG()">TG ALERT: ON</button>
  <button class="tool-btn" onclick="toggleFlip()">&#128260; FLIP 180&deg;</button>
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

<div style="font-size:0.72rem; color:#8b9bb4; margin-top:6px;">
  Keyboard: W (Fwd), S (Rev), A (Left), D (Right), Space (Stop)
</div>

<script>
  const TG_TOKEN = '9138292752:AAFdtNKDLzFQVDEwx8mSyhJ1kMcRNApC0xg';
  const TG_CHAT_ID = '2022474265';
  const TG_COOLDOWN_MS = 15000;

  let isFlipped = false;
  let aiEnabled = true;
  let tgEnabled = true;
  let activeCamIp = '';
  let manualCamOverride = false;

  // AI Processing Buffers (160x120 for ~12 FPS real-time JS processing)
  const PW = 160, PH = 120;
  const procCanvas = document.createElement('canvas');
  procCanvas.width = PW;
  procCanvas.height = PH;
  const procCtx = procCanvas.getContext('2d', { willReadFrequently: true });
  const gray = new Uint8Array(PW * PH);
  const blur = new Uint8Array(PW * PH);
  const mask = new Uint8Array(PW * PH);
  const visited = new Uint8Array(PW * PH);
  const bfsQueue = new Int32Array(PW * PH);
  const hist = new Int32Array(256);

  // Debounce & Alert State
  let detectStreak = 0;
  let clearStreak = 0;
  let localPotholeState = 0;
  let lastTgSentMs = 0;
  let geoInfo = { city: 'Hotspot Area', lat: null, lon: null };

  // Preload IP Geolocation asynchronously for Telegram maps link
  fetch('https://ipapi.co/json/')
    .then((r) => r.ok ? r.json() : null)
    .then((g) => {
      if (g && g.latitude) {
        geoInfo = { city: (g.city || 'Unknown') + ', ' + (g.region || ''), lat: g.latitude, lon: g.longitude };
      }
    })
    .catch(() => {});

  const connectCam = (ip) => {
    if (!ip || ip === activeCamIp) return;
    activeCamIp = ip;
    document.getElementById('cam-ip-input').value = ip;
    localStorage.setItem('cam_ip', ip);
    const img = document.getElementById('cam-feed');
    img.src = 'http://' + ip + ':81/stream';
  };

  const applyCamIp = () => {
    const val = document.getElementById('cam-ip-input').value.trim();
    if (val) {
      manualCamOverride = true;
      activeCamIp = '';
      connectCam(val);
    }
  };

  const scanForCam = async () => {
    const btn = document.getElementById('btn-scan');
    btn.innerText = 'SCANNING...';
    const hostParts = window.location.hostname.split('.');
    if (hostParts.length !== 4) { btn.innerText = 'SCAN'; return; }
    const prefix = hostParts[0] + '.' + hostParts[1] + '.' + hostParts[2] + '.';
    const selfLast = parseInt(hostParts[3], 10);
    let found = '';

    for (let start = 2; start <= 254 && !found; start += 25) {
      const checks = [];
      for (let i = start; i < start + 25 && i <= 254; i++) {
        if (i === selfLast) continue;
        const ip = prefix + i;
        checks.push(
          fetch('http://' + ip + ':81/ping', { signal: AbortSignal.timeout(650) })
            .then((r) => r.ok ? r.text() : '')
            .then((t) => { if (t.includes('POTHOLE_CAM') && !found) found = ip; })
            .catch(() => {})
        );
      }
      await Promise.all(checks);
    }
    btn.innerText = 'SCAN';
    if (found) {
      manualCamOverride = true;
      activeCamIp = '';
      connectCam(found);
    } else {
      document.getElementById('ai-telemetry').innerText = 'Cam scan finished: none found on :81';
    }
  };

  const toggleFlip = () => {
    isFlipped = !isFlipped;
    document.getElementById('cam-feed').style.transform = isFlipped ? 'rotate(180deg)' : 'none';
  };

  const toggleAI = () => {
    aiEnabled = !aiEnabled;
    const btn = document.getElementById('btn-ai');
    btn.innerText = aiEnabled ? 'AI VISION: ON' : 'AI VISION: OFF';
    btn.className = aiEnabled ? 'tool-btn active' : 'tool-btn';
    if (!aiEnabled) {
      const ov = document.getElementById('ai-overlay');
      ov.getContext('2d').clearRect(0, 0, ov.width, ov.height);
      if (localPotholeState === 1) {
        localPotholeState = 0;
        fetch('/pothole?state=0').catch(() => {});
      }
      document.getElementById('ai-telemetry').innerText = 'AI Vision Paused (Live Stream Only)';
    }
  };

  const toggleTG = () => {
    tgEnabled = !tgEnabled;
    const btn = document.getElementById('btn-tg');
    btn.innerText = tgEnabled ? 'TG ALERT: ON' : 'TG ALERT: OFF';
    btn.className = tgEnabled ? 'tool-btn active' : 'tool-btn';
  };

  const sendTelegramAlert = (boxes) => {
    const now = Date.now();
    if (!tgEnabled || (now - lastTgSentMs < TG_COOLDOWN_MS)) return;
    lastTgSentMs = now;

    try {
      const img = document.getElementById('cam-feed');
      const snap = document.createElement('canvas');
      snap.width = 320;
      snap.height = 240;
      const sctx = snap.getContext('2d');
      if (isFlipped) {
        sctx.translate(320, 240);
        sctx.rotate(Math.PI);
        sctx.drawImage(img, 0, 0, 320, 240);
        sctx.setTransform(1, 0, 0, 1, 0, 0);
      } else {
        sctx.drawImage(img, 0, 0, 320, 240);
      }

      // Burn red boxes onto alert snapshot
      sctx.strokeStyle = '#ff1744';
      sctx.lineWidth = 3;
      boxes.forEach((b) => {
        sctx.strokeRect(b.x, b.y, b.w, b.h);
        sctx.fillStyle = '#ff1744';
        sctx.fillRect(b.x, Math.max(0, b.y - 16), 96, 16);
        sctx.fillStyle = '#ffffff';
        sctx.font = 'bold 11px Arial';
        sctx.fillText('POTHOLE ' + Math.round(b.conf * 100) + '%', b.x + 3, Math.max(12, b.y - 4));
      });

      const locLine = geoInfo.lat
        ? '\nLocation: ' + geoInfo.city + '\nMap: https://maps.google.com/?q=' + geoInfo.lat + ',' + geoInfo.lon
        : '\nHotspot Network: Pothole car';
      const topConf = boxes.length ? Math.round(boxes[0].conf * 100) : 80;
      const caption = 'POTHOLE DETECTED!\nConfidence: ' + topConf + '%\nSpeed: Throttled to SLOW\nTime: ' + new Date().toLocaleTimeString() + locLine;

      snap.toBlob((blob) => {
        if (!blob) return;
        const fd = new FormData();
        fd.append('chat_id', TG_CHAT_ID);
        fd.append('caption', caption);
        fd.append('photo', blob, 'pothole.jpg');
        fetch('https://api.telegram.org/bot' + TG_TOKEN + '/sendPhoto', { method: 'POST', body: fd })
          .then((r) => {
            if (r.ok) document.getElementById('ai-telemetry').innerText = 'AI Alert + Snapshot Sent to Telegram!';
          })
          .catch(() => {});
      }, 'image/jpeg', 0.85);
    } catch (e) {}
  };

  // Real-time Classical Image Processing Loop in Dashboard
  const runImageProcessing = () => {
    if (!aiEnabled) return;
    const img = document.getElementById('cam-feed');
    const ov = document.getElementById('ai-overlay');
    const octx = ov.getContext('2d');
    const tel = document.getElementById('ai-telemetry');

    if (!img.complete || img.naturalWidth === 0) {
      tel.innerText = activeCamIp
        ? ('Connecting to Camera http://' + activeCamIp + ':81/stream ...')
        : 'Waiting for ESP32-CAM IP on hotspot... (or click SCAN)';
      return;
    }

    let pixels;
    try {
      procCtx.setTransform(1, 0, 0, 1, 0, 0);
      if (isFlipped) {
        procCtx.translate(PW, PH);
        procCtx.rotate(Math.PI);
      }
      procCtx.drawImage(img, 0, 0, PW, PH);
      pixels = procCtx.getImageData(0, 0, PW, PH).data;
    } catch (err) {
      tel.innerText = 'Stream active (CORS pixel block — reload cam)';
      return;
    }

    const roiY1 = 60, roiY2 = 117, roiX1 = 8, roiX2 = 152;
    for (let y = roiY1 - 2; y <= roiY2 + 2; y++) {
      const rowOff = y * PW;
      for (let x = roiX1 - 2; x <= roiX2 + 2; x++) {
        const idx = rowOff + x;
        const p = idx * 4;
        gray[idx] = (pixels[p] * 77 + pixels[p + 1] * 150 + pixels[p + 2] * 29) >> 8;
      }
    }

    hist.fill(0);
    let roiCount = 0;
    for (let y = roiY1; y < roiY2; y++) {
      const r = y * PW;
      for (let x = roiX1; x < roiX2; x++) {
        const i = r + x;
        const v = (gray[i - PW - 1] + gray[i - PW] + gray[i - PW + 1] +
                   gray[i - 1] + gray[i] * 2 + gray[i + 1] +
                   gray[i + PW - 1] + gray[i + PW] + gray[i + PW + 1]) / 10 | 0;
        blur[i] = v;
        hist[v]++;
        roiCount++;
      }
    }

    // Compute median luminance in ROI
    let acc = 0, median = 128;
    const half = roiCount >> 1;
    for (let b = 0; b < 256; b++) {
      acc += hist[b];
      if (acc >= half) { median = b; break; }
    }

    const darkThresh = Math.max(22, Math.min(125, (median * 0.62) | 0));
    mask.fill(0);
    visited.fill(0);
    for (let y = roiY1; y < roiY2; y++) {
      const r = y * PW;
      for (let x = roiX1; x < roiX2; x++) {
        const i = r + x;
        if (blur[i] < darkThresh) mask[i] = 1;
      }
    }

    // Extract connected crater blobs via BFS
    const detections = [];
    for (let y = roiY1; y < roiY2; y++) {
      for (let x = roiX1; x < roiX2; x++) {
        const startIdx = y * PW + x;
        if (!mask[startIdx] || visited[startIdx]) continue;

        let head = 0, tail = 0;
        bfsQueue[tail++] = startIdx;
        visited[startIdx] = 1;
        let minX = x, maxX = x, minY = y, maxY = y, innerSum = 0;

        while (head < tail) {
          const cur = bfsQueue[head++];
          const cy = (cur / PW) | 0;
          const cx = cur - cy * PW;
          innerSum += blur[cur];
          if (cx < minX) minX = cx;
          if (cx > maxX) maxX = cx;
          if (cy < minY) minY = cy;
          if (cy > maxY) maxY = cy;

          if (cx + 1 < roiX2 && mask[cur + 1] && !visited[cur + 1]) { visited[cur + 1] = 1; bfsQueue[tail++] = cur + 1; }
          if (cx - 1 >= roiX1 && mask[cur - 1] && !visited[cur - 1]) { visited[cur - 1] = 1; bfsQueue[tail++] = cur - 1; }
          if (cy + 1 < roiY2 && mask[cur + PW] && !visited[cur + PW]) { visited[cur + PW] = 1; bfsQueue[tail++] = cur + PW; }
          if (cy - 1 >= roiY1 && mask[cur - PW] && !visited[cur - PW]) { visited[cur - PW] = 1; bfsQueue[tail++] = cur - PW; }
        }

        const area = tail;
        if (area < 120 || area > 4500) continue;
        const bw = maxX - minX + 1;
        const bh = maxY - minY + 1;
        const aspect = bw / bh;
        if (aspect < 0.35 || aspect > 3.2) continue;
        const extent = area / (bw * bh);
        if (extent < 0.35) continue;

        // Contrast check against surrounding rim
        const padX1 = Math.max(roiX1, minX - 4), padX2 = Math.min(roiX2 - 1, maxX + 4);
        const padY1 = Math.max(roiY1, minY - 4), padY2 = Math.min(roiY2 - 1, maxY + 4);
        let rimSum = 0, rimCnt = 0;
        for (let rx = padX1; rx <= padX2; rx++) {
          rimSum += blur[padY1 * PW + rx] + blur[padY2 * PW + rx];
          rimCnt += 2;
        }
        const innerMean = innerSum / area;
        const outerMean = rimSum / (rimCnt || 1);
        const contrast = outerMean - innerMean;
        if (contrast < 18) continue;

        const conf = Math.min(0.96, Math.max(0.50, 0.45 + extent * 0.25 + (contrast / 100) * 0.25));
        detections.push({ x: minX * 2, y: minY * 2, w: bw * 2, h: bh * 2, conf });
      }
    }

    // Draw HUD Overlay (320x240)
    octx.clearRect(0, 0, 320, 240);
    octx.strokeStyle = 'rgba(0, 229, 255, 0.55)';
    octx.lineWidth = 1;
    octx.setLineDash([5, 4]);
    octx.strokeRect(16, 120, 288, 114);
    octx.setLineDash([]);
    octx.fillStyle = 'rgba(0, 229, 255, 0.85)';
    octx.font = 'bold 10px Arial';
    octx.fillText('ROAD AI ROI', 20, 132);

    detections.forEach((d) => {
      octx.strokeStyle = '#ff1744';
      octx.lineWidth = 2.5;
      octx.strokeRect(d.x, d.y, d.w, d.h);
      octx.fillStyle = '#ff1744';
      octx.fillRect(d.x, Math.max(0, d.y - 16), 92, 16);
      octx.fillStyle = '#ffffff';
      octx.font = 'bold 10px Arial';
      octx.fillText('POTHOLE ' + Math.round(d.conf * 100) + '%', d.x + 3, Math.max(11, d.y - 4));
    });

    // Temporal Debouncing (3 frames confirm, 8 frames clear)
    if (detections.length > 0) {
      detectStreak++;
      clearStreak = 0;
      if (detectStreak >= 3 && localPotholeState === 0) {
        localPotholeState = 1;
        fetch('/pothole?state=1').catch(() => {});
        sendTelegramAlert(detections);
      }
    } else {
      clearStreak++;
      detectStreak = 0;
      if (clearStreak >= 8 && localPotholeState === 1) {
        localPotholeState = 0;
        fetch('/pothole?state=0').catch(() => {});
      }
    }

    tel.innerText = localPotholeState === 1
      ? ('AI: POTHOLE DETECTED (' + detections.length + ') | SLOW MODE ACTIVE')
      : ('AI Active | Road Clear (Median Lum: ' + median + ')');
  };

  const sendCmd = async (cmd) => {
    try { await fetch('/' + cmd); } catch (err) {}
  };

  const setMode = async (mode) => {
    try {
      await fetch('/' + mode);
      await updateStatus();
    } catch (err) {}
  };

  const updateStatus = async () => {
    try {
      const r = await fetch('/status');
      if (!r.ok) return;
      const d = await r.json();

      if (d.ip) {
        document.getElementById('ip-info').innerText =
          'Hotspot: Pothole car | Robot: ' + d.ip + (d.cam_ip ? ' | Cam: ' + d.cam_ip : '');
      }

      // Auto-connect camera if discovered via UDP and not manually overridden
      if (!manualCamOverride && d.cam_ip && d.cam_ip !== activeCamIp) {
        connectCam(d.cam_ip);
      }

      const f = document.getElementById('val-front');
      const l = document.getElementById('val-left');
      const rg = document.getElementById('val-right');

      f.innerText = (d.front > 200 ? '>60 cm' : d.front + ' cm');
      l.innerText = (d.left > 200 ? '>60 cm' : d.left + ' cm');
      rg.innerText = (d.right > 200 ? '>60 cm' : d.right + ' cm');

      f.className = (d.front <= 20) ? 'sensor-val sensor-warn' : 'sensor-val';
      l.className = (d.left <= 20) ? 'sensor-val sensor-warn' : 'sensor-val';
      rg.className = (d.right <= 20) ? 'sensor-val sensor-warn' : 'sensor-val';

      const pb = document.getElementById('pothole-badge');
      const potholeActive = (d.pothole === 1 || localPotholeState === 1);
      if (potholeActive) {
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
    } catch (err) {}
  };

  window.addEventListener('keydown', (e) => {
    if (document.activeElement && document.activeElement.tagName === 'INPUT') return;
    if (e.key === 'w' || e.key === 'W' || e.key === 'ArrowUp') sendCmd('forward');
    else if (e.key === 's' || e.key === 'S' || e.key === 'ArrowDown') sendCmd('backward');
    else if (e.key === 'a' || e.key === 'A' || e.key === 'ArrowLeft') sendCmd('left');
    else if (e.key === 'd' || e.key === 'D' || e.key === 'ArrowRight') sendCmd('right');
    else if (e.key === ' ') { e.preventDefault(); sendCmd('stop'); }
  });

  // Restore last saved camera IP only if it belongs to the same hotspot subnet
  try {
    const savedIp = localStorage.getItem('cam_ip');
    const hostPrefix = window.location.hostname.split('.').slice(0, 3).join('.');
    if (savedIp && hostPrefix && savedIp.startsWith(hostPrefix + '.')) {
      connectCam(savedIp);
    }
  } catch (e) {}

  setInterval(updateStatus, 300);
  setInterval(runImageProcessing, 90);
  updateStatus();
</script>
</body>
</html>)rawliteral";

#endif // DASHBOARD_H
