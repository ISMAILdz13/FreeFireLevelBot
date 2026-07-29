<div align="center">

<!-- Animated Banner SVG -->
<svg xmlns="http://www.w3.org/2000/svg" width="700" height="160" viewBox="0 0 700 160">
  <defs>
    <linearGradient id="bannerGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#FF416C;stop-opacity:1">
        <animate attributeName="offset" values="0;0.5;0" dur="4s" repeatCount="indefinite"/>
      </stop>
      <stop offset="50%" style="stop-color:#FF4B2B;stop-opacity:1"/>
      <stop offset="100%" style="stop-color:#4ECDC4;stop-opacity:1">
        <animate attributeName="offset" values="1;0.5;1" dur="4s" repeatCount="indefinite"/>
      </stop>
    </linearGradient>
    <filter id="glow">
      <feGaussianBlur stdDeviation="3" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <filter id="glow2">
      <feGaussianBlur stdDeviation="5" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
  </defs>
  <rect width="700" height="160" rx="25" fill="url(#bannerGrad)"/>
  <text x="350" y="65" font-family="monospace" font-size="28" font-weight="bold" fill="white" text-anchor="middle" filter="url(#glow)">FREE FIRE LEVEL BOT</text>
  <text x="350" y="100" font-family="monospace" font-size="14" fill="white" text-anchor="middle" opacity="0.9">Auto Level-Up 24/7 | Termux Edition | v2.0</text>
  <circle cx="60" cy="40" r="8" fill="white" opacity="0.5">
    <animate attributeName="opacity" values="0.5;0.1;0.5" dur="2s" repeatCount="indefinite"/>
    <animate attributeName="r" values="8;12;8" dur="2s" repeatCount="indefinite"/>
  </circle>
  <circle cx="640" cy="120" r="6" fill="white" opacity="0.3">
    <animate attributeName="opacity" values="0.3;0.8;0.3" dur="1.5s" repeatCount="indefinite"/>
  </circle>
  <circle cx="120" cy="130" r="4" fill="white" opacity="0.4">
    <animate attributeName="opacity" values="0.4;0.9;0.4" dur="3s" repeatCount="indefinite"/>
  </circle>
  <circle cx="580" cy="45" r="5" fill="white" opacity="0.3">
    <animate attributeName="opacity" values="0.3;0.7;0.3" dur="2.5s" repeatCount="indefinite"/>
    <animate attributeName="r" values="5;8;5" dur="2.5s" repeatCount="indefinite"/>
  </circle>
  <rect x="200" y="115" width="300" height="4" rx="2" fill="white" opacity="0.2">
    <animate attributeName="width" values="100;300;100" dur="5s" repeatCount="indefinite"/>
    <animate attributeName="x" values="300;200;300" dur="5s" repeatCount="indefinite"/>
  </rect>
</svg>

<!-- Badges -->
<img src="https://img.shields.io/badge/Python-3.8+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
<img src="https://img.shields.io/badge/Platform-Termux%20%7C%20Linux%20%7C%20Docker-green?style=for-the-badge&logo=android&logoColor=white" alt="Platform"/>
<img src="https://img.shields.io/badge/Version-2.0-orange?style=for-the-badge" alt="Version"/>
<img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License"/>
<img src="https://img.shields.io/badge/Status-Active-brightgreen?style=for-the-badge" alt="Status"/>

<!-- Animated Status Badge -->
<svg xmlns="http://www.w3.org/2000/svg" width="180" height="28" viewBox="0 0 180 28">
  <rect width="180" height="28" rx="14" fill="#2D2D2D" stroke="#4ECDC4" stroke-width="1.5">
    <animate attributeName="stroke" values="#4ECDC4;#FF416C;#4ECDC4" dur="3s" repeatCount="indefinite"/>
  </rect>
  <circle cx="14" cy="14" r="5" fill="#4ECDC4">
    <animate attributeName="fill" values="#4ECDC4;#FF416C;#4ECDC4" dur="1.5s" repeatCount="indefinite"/>
    <animate attributeName="r" values="5;7;5" dur="1.5s" repeatCount="indefinite"/>
  </circle>
  <text x="30" y="18" font-family="monospace" font-size="11" fill="#4ECDC4" font-weight="bold">SYSTEM ONLINE</text>
</svg>

</div>

---

<div align="center">

## 📋 Table of Contents

| # | Section | # | Section |
|---|---------|---|---------|
| 1 | [Overview](#-overview) | 8 | [How It Works](#-how-it-works) |
| 2 | [Features](#-features) | 9 | [Authentication Flow](#-authentication-flow) |
| 3 | [Installation](#-installation) | 10 | [Match Engine](#-match-engine) |
| 4 | [Configuration](#-configuration) | 11 | [Ban Detection](#-ban-detection) |
| 5 | [Usage](#-usage) | 12 | [FAQ](#-faq) |
| 6 | [Menu Preview](#-menu-preview) | 13 | [Troubleshooting](#-troubleshooting) |
| 7 | [Project Structure](#-project-structure) | 14 | [Credits](#-credits) |

</div>

---

## 🔥 Overview

<details open>
<summary><b>What is Free Fire Level Bot?</b></summary>

<br>

The Free Fire Level Bot is an automated tool designed to **level up Free Fire accounts** by repeatedly joining team matches, starting them, waiting for completion, and leaving — 24/7 without manual intervention. It runs directly on **Android via Termux**, making it accessible without a PC.

The bot handles the full Garena authentication pipeline: guest OAuth token grant, MajorLogin encrypted protobuf handshake, GetLoginData server discovery, and TCP socket communication with game servers — all automatically.

</details>

<!-- Architecture Overview SVG -->
<div align="center">

<svg xmlns="http://www.w3.org/2000/svg" width="680" height="380" viewBox="0 0 680 380">
  <defs>
    <linearGradient id="nodeGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#667eea;stop-opacity:1"/>
      <stop offset="100%" style="stop-color:#764ba2;stop-opacity:1"/>
    </linearGradient>
    <linearGradient id="gameGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#f093fb;stop-opacity:1"/>
      <stop offset="100%" style="stop-color:#f5576c;stop-opacity:1"/>
    </linearGradient>
    <linearGradient id="loopGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#4facfe;stop-opacity:1"/>
      <stop offset="100%" style="stop-color:#00f2fe;stop-opacity:1"/>
    </linearGradient>
    <filter id="dropShadow">
      <feDropShadow dx="2" dy="3" stdDeviation="3" flood-opacity="0.3"/>
    </filter>
  </defs>

  <!-- Title -->
  <text x="340" y="25" font-family="monospace" font-size="14" font-weight="bold" fill="#333" text-anchor="middle">System Architecture</text>

  <!-- Guest Data Node -->
  <rect x="20" y="50" width="140" height="50" rx="12" fill="url(#nodeGrad)" filter="url(#dropShadow)"/>
  <text x="90" y="75" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">Guest Account</text>
  <text x="90" y="90" font-family="monospace" font-size="9" fill="white" text-anchor="middle">UID + Password</text>

  <!-- OAuth Node -->
  <rect x="200" y="50" width="140" height="50" rx="12" fill="url(#nodeGrad)" filter="url(#dropShadow)"/>
  <text x="270" y="75" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">Guest OAuth</text>
  <text x="270" y="90" font-family="monospace" font-size="9" fill="white" text-anchor="middle">access_token + open_id</text>

  <!-- MajorLogin Node -->
  <rect x="380" y="50" width="140" height="50" rx="12" fill="url(#gameGrad)" filter="url(#dropShadow)"/>
  <text x="450" y="75" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">MajorLogin</text>
  <text x="450" y="90" font-family="monospace" font-size="9" fill="white" text-anchor="middle">JWT + AES Key/IV</text>

  <!-- GetLoginData Node -->
  <rect x="560" y="50" width="110" height="50" rx="12" fill="url(#gameGrad)" filter="url(#dropShadow)"/>
  <text x="615" y="72" font-family="monospace" font-size="10" fill="white" text-anchor="middle" font-weight="bold">GetLoginData</text>
  <text x="615" y="88" font-family="monospace" font-size="9" fill="white" text-anchor="middle">Server IP:Port</text>

  <!-- Arrows row 1 -->
  <line x1="160" y1="75" x2="195" y2="75" stroke="#666" stroke-width="2" marker-end="url(#arrowhead)"/>
  <line x1="340" y1="75" x2="375" y2="75" stroke="#666" stroke-width="2" marker-end="url(#arrowhead)"/>
  <line x1="520" y1="75" x2="555" y2="75" stroke="#666" stroke-width="2" marker-end="url(#arrowhead)"/>

  <!-- TCP Connection -->
  <rect x="200" y="140" width="140" height="50" rx="12" fill="url(#loopGrad)" filter="url(#dropShadow)"/>
  <text x="270" y="165" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">TCP Connect</text>
  <text x="270" y="180" font-family="monospace" font-size="9" fill="white" text-anchor="middle">Whisper + Online</text>

  <!-- Match Engine -->
  <rect x="380" y="140" width="140" height="50" rx="12" fill="url(#loopGrad)" filter="url(#dropShadow)"/>
  <text x="450" y="165" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">Match Engine</text>
  <text x="450" y="180" font-family="monospace" font-size="9" fill="white" text-anchor="middle">Join → Spam → Wait</text>

  <!-- Vertical arrows -->
  <line x1="270" y1="100" x2="270" y2="135" stroke="#666" stroke-width="2" marker-end="url(#arrowhead)"/>
  <line x1="340" y1="165" x2="375" y2="165" stroke="#666" stroke-width="2" marker-end="url(#arrowhead)"/>

  <!-- Loop arrow back -->
  <path d="M 450 190 Q 450 230 270 230 Q 270 230 270 195" stroke="#4ECDC4" stroke-width="2" fill="none" stroke-dasharray="5,3" marker-end="url(#arrowhead)">
    <animate attributeName="stroke-dashoffset" values="0;-16" dur="1s" repeatCount="indefinite"/>
  </path>
  <text x="360" y="250" font-family="monospace" font-size="9" fill="#4ECDC4" text-anchor="middle">↻ repeat</text>

  <!-- Output -->
  <rect x="200" y="280" width="280" height="50" rx="12" fill="#2D2D2D" filter="url(#dropShadow)" stroke="#4ECDC4" stroke-width="1.5">
    <animate attributeName="stroke" values="#4ECDC4;#FF416C;#4ECDC4" dur="2s" repeatCount="indefinite"/>
  </rect>
  <text x="340" y="305" font-family="monospace" font-size="12" fill="#4ECDC4" text-anchor="middle" font-weight="bold">+XP +Level ↑</text>
  <text x="340" y="320" font-family="monospace" font-size="9" fill="#999" text-anchor="middle">account grows 24/7</text>

  <line x1="340" y1="230" x2="340" y2="275" stroke="#666" stroke-width="2" marker-end="url(#arrowhead)"/>

  <!-- Arrowhead def -->
  <defs>
    <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#666"/>
    </marker>
  </defs>
</svg>

</div>

---

## ✨ Features

<div align="center">

| Feature | Description |
|---------|-------------|
| 🤖 **Full Automation** | Join → Start → Wait → Leave → Repeat. No manual input needed after setup. |
| 📱 **Termux Support** | Runs directly on Android via Termux. No PC required. |
| 🔐 **Complete Auth Flow** | Guest OAuth → MajorLogin → GetLoginData → TCP — all handled automatically. |
| 🔄 **Retry Logic** | Failed connections auto-retry with configurable delays. |
| 🛡️ **Ban Detection** | Distinguishes between server-down (503), actual bans (400/403), and dead accounts. |
| 📊 **Guest Info** | Check account level, likes, clan, region, and ban status. |
| 🎯 **Custom Settings** | Configurable spam duration, packet delay, wait time, and max cycles. |
| 🔍 **Bulk Checker** | Check all guest accounts at once with the standalone Guest Checker tool. |
| 🐳 **Docker Ready** | Dockerfile and docker-compose included for containerized deployment. |
| 🌐 **Proxy Support** | Configurable proxy rotation for different regions. |

</div>

<!-- Feature Icons SVG -->
<div align="center">

<svg xmlns="http://www.w3.org/2000/svg" width="600" height="40" viewBox="0 0 600 40">
  <rect x="10" y="5" width="130" height="30" rx="15" fill="#667eea" opacity="0.9">
    <animate attributeName="opacity" values="0.9;0.5;0.9" dur="2s" repeatCount="indefinite"/>
  </rect>
  <text x="75" y="24" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">🤖 AUTOMATED</text>
  
  <rect x="155" y="5" width="130" height="30" rx="15" fill="#f5576c" opacity="0.9">
    <animate attributeName="opacity" values="0.9;0.5;0.9" dur="2s" begin="0.3s" repeatCount="indefinite"/>
  </rect>
  <text x="220" y="24" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">📱 TERMUX</text>
  
  <rect x="300" y="5" width="130" height="30" rx="15" fill="#4facfe" opacity="0.9">
    <animate attributeName="opacity" values="0.9;0.5;0.9" dur="2s" begin="0.6s" repeatCount="indefinite"/>
  </rect>
  <text x="365" y="24" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">🛡️ SAFE</text>
  
  <rect x="445" y="5" width="145" height="30" rx="15" fill="#43e97b" opacity="0.9">
    <animate attributeName="opacity" values="0.9;0.5;0.9" dur="2s" begin="0.9s" repeatCount="indefinite"/>
  </rect>
  <text x="517" y="24" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">⚡ FAST</text>
</svg>

</div>

---

## 📦 Installation

<details>
<summary><b>📱 Termux Installation (Recommended for Android)</b></summary>

<br>

### Quick Setup

```bash
# 1. Install Termux from F-Droid (not Play Store)
# 2. Update packages
pkg update && pkg upgrade -y

# 3. Install Python and dependencies
pkg install python git -y
pip install httpx pycryptodome protobuf protobuf-decoder PyJWT

# 4. Clone the repo
git clone https://github.com/ISMAILdz13/ff-level-bot.git
cd ff-level-bot

# 5. Or use the setup script
chmod +x SETUP_LEVEL_TERMUX.sh
./SETUP_LEVEL_TERMUX.sh

# 6. Run the bot
python level_menu.py
```

### One-Liner Install
```bash
pkg update -y && pkg install python git -y && pip install httpx pycryptodome protobuf protobuf-decoder PyJWT && git clone https://github.com/ISMAILdz13/ff-level-bot.git && cd ff-level-bot && python level_menu.py
```

</details>

<details>
<summary><b>🐧 Linux / macOS Installation</b></summary>

<br>

```bash
# 1. Ensure Python 3.8+ is installed
python3 --version

# 2. Clone the repo
git clone https://github.com/ISMAILdz13/ff-level-bot.git
cd ff-level-bot

# 3. Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the bot
python3 level_menu.py
```

</details>

<details>
<summary><b>🐳 Docker Installation</b></summary>

<br>

```bash
# 1. Clone the repo
git clone https://github.com/ISMAILdz13/ff-level-bot.git
cd ff-level-bot

# 2. Build the container
cd docker
docker-compose build

# 3. Run the bot
docker-compose up
```

### Dockerfile
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "level_menu.py"]
```

</details>

---

## ⚙️ Configuration

<details open>
<summary><b>Configuration Options</b></summary>

<br>

### Guest Account Setup

Create or edit `data/level_accounts.json`:
```json
{
  "5877837192": "2C129E64EFB2CC5DFBE6D50671ECC25724D43F1EAB496761D46AA3B2881F4AFA",
  "5842511863": "NAJMI-OSV4YUON1-CORE"
}
```

### Custom Mode Settings

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `spam_duration` | 18 | 1-120 sec | How long to spam start packets |
| `spam_delay` | 0.2 | 0.01-5 sec | Delay between each packet |
| `wait_after` | 20 | 1-300 sec | Wait after match ends |
| `max_cycles` | 0 (∞) | 0-99999 | Max cycles before stopping |
| `join_delay` | 2.0 | - | Delay before joining team |
| `leave_delay` | 2.0 | - | Delay before leaving |
| `cycle_delay` | 2.0 | - | Delay between cycles |

### Config File (`config/settings.yaml`)
```yaml
regions:
  - IND
  - ME
  - BR
  - SG
endpoints:
  oauth: "https://100067.connect.garena.com/oauth/guest/token/grant"
  major_login: "https://loginbp.ggpolarbear.com/MajorLogin"
  login_data: "https://clientbp.ggpolarbear.com/GetLoginData"
  player_info: "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"
```

</details>

---

## 🎮 Usage

### Quick Start Mode
```bash
python level_menu.py
# Select option 1
# Enter team code (e.g., 8659732)
# Bot runs with default settings
```

### Custom Mode
```bash
python level_menu.py
# Select option 2
# Enter team code
# Configure spam duration, delay, wait time, cycles
```

### Guest Info
```bash
python level_menu.py
# Select option 4
# Shows level, likes, clan, ban status
```

### Bulk Account Checker
```bash
python guest_checker.py
# Scans all accounts from guests.json, guests.db, level_accounts.json
# Checks each one: alive/dead/banned
# Saves report to data/guest_report.json
```

---

## 🖥️ Menu Preview

<div align="center">

```
  ========================================
  |        FREE FIRE LEVEL BOT           |
  |  v2.0  |  Termux Edition  |
  ========================================

  Join -> Start -> Wait -> Leave -> Repeat

  ----------------------------------------
  Guest UID: 5877837192
  Status: Ready
  ----------------------------------------

  ----------------------------------------
  [1] Quick Start  (default values)
  [2] Custom Mode  (your values)
  [3] Change Guest Data
  [4] Guest Info    (level/likes/ban)
  [5] Exit
  ----------------------------------------

  Select [1-5]:
```

</div>

---

## 📁 Project Structure

```
ff-level-bot/
├── level_menu.py          # Main Termux CLI menu
├── run_level.py           # Entry point script
├── guest_checker.py       # Standalone bulk account checker
├── main.py                # Direct runner
├── setup.py               # Python package setup
├── requirements.txt        # Python dependencies
├── SETUP_LEVEL_TERMUX.sh  # Termux auto-setup script
│
├── src/
│   └── level/
│       ├── __init__.py
│       ├── auth.py            # Garena auth (OAuth + MajorLogin + GetLoginData)
│       ├── bot.py             # Main bot orchestrator
│       ├── config.py          # Configuration loader
│       ├── connection.py      # TCP connection to game servers
│       ├── match_engine.py    # Join → Spam → Wait → Leave loop
│       ├── packet_builder.py  # Protobuf packet construction
│       ├── guest_info.py       # Player info fetcher
│       ├── data_pb2.py         # Compiled protobuf
│       ├── dev_generator_pb2.py
│       ├── devxt_count_pb2.py
│       └── requirements.txt
│
├── level/
│   ├── MajorLoginRes_pb2.py   # MajorLogin response protobuf
│   └── jwt_generator_pb2.py
│
├── OB54-TCP-BOT/
│   └── Pb2/
│       ├── data_pb2.py
│       ├── dev_generator_pb2.py
│       └── devxt_count_pb2.py
│
├── data/
│   ├── level_accounts.json     # Your guest accounts
│   ├── level_accounts.example.json
│   ├── guests.json             # Guest account list
│   └── guest_report.json       # Checker output
│
├── config/
│   ├── settings.yaml
│   ├── regions.yaml
│   └── proxies.txt
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── frida/
│   └── hooks/
│       ├── guest_hook.js
│       └── aes_key_hook.js
│
└── LICENSE
```

---

## 🔧 How It Works

### The Full Flow

<details open>
<summary><b>Step-by-step breakdown</b></summary>

<br>

#### 1. Guest OAuth Authentication
The bot sends a POST request to `https://100067.connect.garena.com/oauth/guest/token/grant` with the guest UID and password. If valid, Garena returns an `access_token` and `open_id`.

#### 2. MajorLogin
Using the access_token and open_id, the bot constructs an encrypted protobuf payload using a fixed template. The payload is encrypted with AES-CBC using a hardcoded key/IV, then sent to `https://loginbp.ggpolarbear.com/MajorLogin`. The response contains:
- **JWT token** — for authenticating with game servers
- **AES key + IV** — for encrypting TCP packets
- **Timestamp** — server time for token construction
- **URL** — dynamic endpoint for GetLoginData
- **Region** — server region (IND, ME, BR, etc.)

#### 3. GetLoginData
Using the JWT and the dynamic URL from MajorLogin, the bot requests server connection info. The response contains:
- **Whisper server** IP:Port — for chat/lobby
- **Online server** IP:Port — for match operations

#### 4. TCP Connection
The bot connects to both whisper and online servers via TCP sockets. It sends an encrypted connection token (built from the JWT + AES key/IV + timestamp + account UID) to authenticate.

#### 5. Match Engine Loop
Once connected, the match engine runs in a loop:
1. **Join team** — sends a join request with the team code
2. **Spam start** — repeatedly sends match-start packets for `spam_duration` seconds
3. **Wait** — waits for `wait_after` seconds for the match to complete
4. **Leave** — sends a leave request
5. **Repeat** — goes back to step 1

</details>

---

## 🔐 Authentication Flow

<div align="center">

<svg xmlns="http://www.w3.org/2000/svg" width="680" height="420" viewBox="0 0 680 420">
  <defs>
    <linearGradient id="authGrad1" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#667eea"/>
      <stop offset="100%" style="stop-color:#764ba2"/>
    </linearGradient>
    <linearGradient id="authGrad2" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#f093fb"/>
      <stop offset="100%" style="stop-color:#f5576c"/>
    </linearGradient>
    <linearGradient id="authGrad3" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#4facfe"/>
      <stop offset="100%" style="stop-color:#00f2fe"/>
    </linearGradient>
    <linearGradient id="authGrad4" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#43e97b"/>
      <stop offset="100%" style="stop-color:#38f9d7"/>
    </linearGradient>
    <filter id="shadow2">
      <feDropShadow dx="2" dy="3" stdDeviation="3" flood-opacity="0.3"/>
    </filter>
  </defs>

  <!-- Title -->
  <text x="340" y="25" font-family="monospace" font-size="14" font-weight="bold" fill="#333" text-anchor="middle">Authentication Pipeline</text>

  <!-- Step 1: OAuth -->
  <rect x="20" y="50" width="160" height="70" rx="15" fill="url(#authGrad1)" filter="url(#shadow2)"/>
  <text x="100" y="75" font-family="monospace" font-size="12" fill="white" text-anchor="middle" font-weight="bold">Step 1: OAuth</text>
  <text x="100" y="93" font-family="monospace" font-size="8" fill="white" text-anchor="middle">connect.garena.com</text>
  <text x="100" y="107" font-family="monospace" font-size="8" fill="white" text-anchor="middle">→ access_token</text>

  <!-- Step 2: MajorLogin -->
  <rect x="220" y="50" width="160" height="70" rx="15" fill="url(#authGrad2)" filter="url(#shadow2)"/>
  <text x="300" y="75" font-family="monospace" font-size="12" fill="white" text-anchor="middle" font-weight="bold">Step 2: MajorLogin</text>
  <text x="300" y="93" font-family="monospace" font-size="8" fill="white" text-anchor="middle">loginbp.ggpolarbear.com</text>
  <text x="300" y="107" font-family="monospace" font-size="8" fill="white" text-anchor="middle">→ JWT + AES Key/IV</text>

  <!-- Step 3: GetLoginData -->
  <rect x="420" y="50" width="160" height="70" rx="15" fill="url(#authGrad3)" filter="url(#shadow2)"/>
  <text x="500" y="75" font-family="monospace" font-size="12" fill="white" text-anchor="middle" font-weight="bold">Step 3: LoginData</text>
  <text x="500" y="93" font-family="monospace" font-size="8" fill="white" text-anchor="middle">clientbp.ggpolarbear.com</text>
  <text x="500" y="107" font-family="monospace" font-size="8" fill="white" text-anchor="middle">→ Server IP:Port</text>

  <!-- Arrows between steps -->
  <line x1="180" y1="85" x2="215" y2="85" stroke="#666" stroke-width="2.5" marker-end="url(#ah)"/>
  <line x1="380" y1="85" x2="415" y2="85" stroke="#666" stroke-width="2.5" marker-end="url(#ah)"/>

  <!-- Step 4: TCP -->
  <rect x="120" y="170" width="160" height="70" rx="15" fill="url(#authGrad4)" filter="url(#shadow2)"/>
  <text x="200" y="195" font-family="monospace" font-size="12" fill="white" text-anchor="middle" font-weight="bold">Step 4: TCP</text>
  <text x="200" y="213" font-family="monospace" font-size="8" fill="white" text-anchor="middle">Whisper + Online</text>
  <text x="200" y="227" font-family="monospace" font-size="8" fill="white" text-anchor="middle">socket connection</text>

  <!-- Step 5: Match Loop -->
  <rect x="340" y="170" width="160" height="70" rx="15" fill="url(#authGrad4)" filter="url(#shadow2)"/>
  <text x="420" y="195" font-family="monospace" font-size="12" fill="white" text-anchor="middle" font-weight="bold">Step 5: Loop</text>
  <text x="420" y="213" font-family="monospace" font-size="8" fill="white" text-anchor="middle">Join → Start</text>
  <text x="420" y="227" font-family="monospace" font-size="8" fill="white" text-anchor="middle">→ Wait → Leave</text>

  <!-- Arrows down -->
  <line x1="500" y1="120" x2="200" y2="165" stroke="#666" stroke-width="2" marker-end="url(#ah)" stroke-dasharray="5,3"/>
  <line x1="280" y1="205" x2="335" y2="205" stroke="#666" stroke-width="2.5" marker-end="url(#ah)"/>

  <!-- Encryption layer -->
  <rect x="220" y="290" width="240" height="50" rx="12" fill="#2D2D2D" stroke="#FF416C" stroke-width="1.5" filter="url(#shadow2)">
    <animate attributeName="stroke" values="#FF416C;#4ECDC4;#FF416C" dur="2s" repeatCount="indefinite"/>
  </rect>
  <text x="340" y="315" font-family="monospace" font-size="11" fill="#FF416C" text-anchor="middle" font-weight="bold">AES-CBC Encryption</text>
  <text x="340" y="330" font-family="monospace" font-size="8" fill="#999" text-anchor="middle">All packets encrypted with key/IV from MajorLogin</text>

  <!-- Connection -->
  <line x1="340" y1="340" x2="340" y2="370" stroke="#666" stroke-width="2" marker-end="url(#ah)"/>

  <!-- Final Output -->
  <rect x="220" y="370" width="240" height="35" rx="10" fill="#2D2D2D" stroke="#43e97b" stroke-width="1.5">
    <animate attributeName="stroke" values="#43e97b;#4facfe;#43e97b" dur="2s" repeatCount="indefinite"/>
  </rect>
  <text x="340" y="392" font-family="monospace" font-size="11" fill="#43e97b" text-anchor="middle" font-weight="bold">✓ Connected & Running</text>

  <defs>
    <marker id="ah" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#666"/>
    </marker>
  </defs>
</svg>

</div>

---

## 🎯 Match Engine

<div align="center">

<svg xmlns="http://www.w3.org/2000/svg" width="680" height="300" viewBox="0 0 680 300">
  <defs>
    <filter id="glow3">
      <feGaussianBlur stdDeviation="4" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>
    <marker id="ah2" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#666"/>
    </marker>
  </defs>

  <text x="340" y="25" font-family="monospace" font-size="14" font-weight="bold" fill="#333" text-anchor="middle">Match Engine State Machine</text>

  <!-- IDLE -->
  <circle cx="80" cy="100" r="40" fill="#667eea" opacity="0.9" filter="url(#glow3)">
    <animate attributeName="opacity" values="0.9;0.6;0.9" dur="2s" repeatCount="indefinite"/>
  </circle>
  <text x="80" y="95" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">IDLE</text>
  <text x="80" y="110" font-family="monospace" font-size="8" fill="white" text-anchor="middle">waiting</text>

  <!-- JOINING -->
  <circle cx="230" cy="100" r="40" fill="#f5576c" opacity="0.9" filter="url(#glow3)">
    <animate attributeName="opacity" values="0.9;0.6;0.9" dur="2s" begin="0.4s" repeatCount="indefinite"/>
  </circle>
  <text x="230" y="95" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">JOINING</text>
  <text x="230" y="110" font-family="monospace" font-size="8" fill="white" text-anchor="middle">team code</text>

  <!-- SPAMMING -->
  <circle cx="380" cy="100" r="40" fill="#FF4B2B" opacity="0.9" filter="url(#glow3)">
    <animate attributeName="opacity" values="0.9;0.6;0.9" dur="2s" begin="0.8s" repeatCount="indefinite"/>
  </circle>
  <text x="380" y="95" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">SPAM</text>
  <text x="380" y="110" font-family="monospace" font-size="8" fill="white" text-anchor="middle">start pkt</text>

  <!-- WAITING -->
  <circle cx="530" cy="100" r="40" fill="#4facfe" opacity="0.9" filter="url(#glow3)">
    <animate attributeName="opacity" values="0.9;0.6;0.9" dur="2s" begin="1.2s" repeatCount="indefinite"/>
  </circle>
  <text x="530" y="95" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">WAITING</text>
  <text x="530" y="110" font-family="monospace" font-size="8" fill="white" text-anchor="middle">match ends</text>

  <!-- LEAVING -->
  <circle cx="380" cy="220" r="40" fill="#43e97b" opacity="0.9" filter="url(#glow3)">
    <animate attributeName="opacity" values="0.9;0.6;0.9" dur="2s" begin="1.6s" repeatCount="indefinite"/>
  </circle>
  <text x="380" y="215" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">LEAVING</text>
  <text x="380" y="230" font-family="monospace" font-size="8" fill="white" text-anchor="middle">exit team</text>

  <!-- Arrows -->
  <line x1="120" y1="100" x2="190" y2="100" stroke="#666" stroke-width="2" marker-end="url(#ah2)"/>
  <line x1="270" y1="100" x2="340" y2="100" stroke="#666" stroke-width="2" marker-end="url(#ah2)"/>
  <line x1="420" y1="100" x2="490" y2="100" stroke="#666" stroke-width="2" marker-end="url(#ah2)"/>
  
  <!-- WAITING -> LEAVING -->
  <path d="M 530 140 Q 530 180 420 220" stroke="#666" stroke-width="2" fill="none" marker-end="url(#ah2)"/>
  
  <!-- LEAVING -> IDLE (loop back) -->
  <path d="M 340 220 Q 200 220 80 140" stroke="#4ECDC4" stroke-width="2.5" fill="none" stroke-dasharray="6,4" marker-end="url(#ah2)">
    <animate attributeName="stroke-dashoffset" values="0;-20" dur="1s" repeatCount="indefinite"/>
  </path>
  <text x="200" y="260" font-family="monospace" font-size="10" fill="#4ECDC4" text-anchor="middle">↻ repeat cycle</text>

  <!-- Labels on arrows -->
  <text x="155" y="90" font-family="monospace" font-size="8" fill="#999" text-anchor="middle">join_delay</text>
  <text x="305" y="90" font-family="monospace" font-size="8" fill="#999" text-anchor="middle">start spam</text>
  <text x="455" y="90" font-family="monospace" font-size="8" fill="#999" text-anchor="middle">wait_after</text>
</svg>

</div>

### State Transitions

| From | To | Trigger | Config |
|------|-----|---------|--------|
| IDLE | JOINING | Bot starts cycle | `join_delay` (2.0s) |
| JOINING | SPAM | Team joined successfully | — |
| SPAM | WAITING | `spam_duration` elapsed (18s) | `spam_delay` (0.2s between packets) |
| WAITING | LEAVING | `wait_after` elapsed (20s) | — |
| LEAVING | IDLE | Leave packet sent | `cycle_delay` (2.0s) |

---

## 🛡️ Ban Detection

The bot distinguishes between different failure types to avoid false positives:

<div align="center">

| HTTP Status | Meaning | Display | Action |
|-------------|---------|---------|--------|
| `200` | Success | ✅ CLEAR | Proceed to GetLoginData |
| `503` | Server maintenance | 🔧 SERVER_DOWN | Retry later, not a ban |
| `400/401/403` | Account banned | 🚫 BANNED | Account is banned |
| OAuth `auth_error` | Account deleted | 💀 DEAD | Remove account |
| Player info fail | Blacklisted | ⚠️ BLACKLISTED | May still work |

</div>

<!-- Ban Detection Flow SVG -->
<div align="center">

<svg xmlns="http://www.w3.org/2000/svg" width="600" height="220" viewBox="0 0 600 220">
  <defs>
    <marker id="ah3" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
      <polygon points="0 0, 10 3.5, 0 7" fill="#666"/>
    </marker>
  </defs>

  <text x="300" y="25" font-family="monospace" font-size="13" font-weight="bold" fill="#333" text-anchor="middle">Ban Detection Logic</text>

  <!-- Check node -->
  <rect x="220" y="45" width="160" height="40" rx="10" fill="#2D2D2D" stroke="#4ECDC4" stroke-width="1.5"/>
  <text x="300" y="70" font-family="monospace" font-size="11" fill="#4ECDC4" text-anchor="middle" font-weight="bold">Check HTTP Status</text>

  <!-- 200 -->
  <rect x="30" y="130" width="110" height="40" rx="10" fill="#43e97b" opacity="0.9"/>
  <text x="85" y="155" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">200 = OK</text>

  <!-- 503 -->
  <rect x="160" y="130" width="110" height="40" rx="10" fill="#FFA500" opacity="0.9">
    <animate attributeName="opacity" values="0.9;0.5;0.9" dur="2s" repeatCount="indefinite"/>
  </rect>
  <text x="215" y="155" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">503 = DOWN</text>

  <!-- 400/403 -->
  <rect x="290" y="130" width="110" height="40" rx="10" fill="#f5576c" opacity="0.9">
    <animate attributeName="opacity" values="0.9;0.5;0.9" dur="2s" begin="0.5s" repeatCount="indefinite"/>
  </rect>
  <text x="345" y="155" font-family="monospace" font-size="11" fill="white" text-anchor="middle" font-weight="bold">403 = BAN</text>

  <!-- OAuth error -->
  <rect x="420" y="130" width="150" height="40" rx="10" fill="#2D2D2D" stroke="#f5576c" stroke-width="1.5">
    <animate attributeName="stroke" values="#f5576c;#FF416C;#f5576c" dur="1.5s" repeatCount="indefinite"/>
  </rect>
  <text x="495" y="155" font-family="monospace" font-size="11" fill="#f5576c" text-anchor="middle" font-weight="bold">DEAD</text>

  <!-- Arrows -->
  <line x1="250" y1="85" x2="85" y2="125" stroke="#666" stroke-width="1.5" marker-end="url(#ah3)"/>
  <line x1="280" y1="85" x2="215" y2="125" stroke="#666" stroke-width="1.5" marker-end="url(#ah3)"/>
  <line x1="320" y1="85" x2="345" y2="125" stroke="#666" stroke-width="1.5" marker-end="url(#ah3)"/>
  <line x1="350" y1="85" x2="495" y2="125" stroke="#666" stroke-width="1.5" marker-end="url(#ah3)"/>
</svg>

</div>

---

## ❓ FAQ

<details>
<summary><b>The bot says "Garena server is DOWN (503)" — what do I do?</b></summary>

<br>

This means Garena's game servers are temporarily down for maintenance or experiencing issues. This is **not a ban** — your account is fine. Wait a few hours and try again. The bot correctly distinguishes between server-down (503) and actual bans (400/403).

</details>

<details>
<summary><b>How do I get my guest UID and password?</b></summary>

<br>

Guest accounts are stored in `.dat` files in the Free Fire app data directory. You can:
1. Use the Frida hooks included in `frida/hooks/` to extract guest credentials
2. Use option 3 in the menu to load from a `.dat` file
3. Manually enter UID and password

</details>

<details>
<summary><b>What team code should I use?</b></summary>

<br>

The team code is a squad/team invite code from Free Fire. Create a squad in-game, get the invite code, and enter it when the bot asks. The bot will join that squad and start matches automatically.

</details>

<details>
<summary><b>How long does it take to level up?</b></summary>

<br>

Each cycle takes approximately 40-60 seconds (18s spam + 20s wait + delays). At default settings, that's about 60-90 cycles per hour. XP gained depends on the match outcome.

</details>

<details>
<summary><b>Can I run multiple accounts at once?</b></summary>

<br>

Yes! You can run multiple instances of the bot with different guest accounts. Use `data/level_accounts.json` to store multiple accounts and switch between them using option 3 → "Switch account" in the menu.

</details>

<details>
<summary><b>What's the difference between Quick Start and Custom Mode?</b></summary>

<br>

- **Quick Start**: Uses default values (spam=18s, wait=20s, delay=0.2s) — just enter the team code and go.
- **Custom Mode**: Lets you configure all parameters — spam duration, packet delay, wait time, and max cycles.

</details>

<details>
<summary><b>Is this safe?</b></summary>

<br>

The bot uses the same authentication flow as the official Free Fire client. However, any automation tool carries some risk. Use guest accounts (not your main account) and don't abuse the system. The bot includes ban detection to help you monitor account health.

</details>

<details>
<summary><b>What endpoints does the bot use?</b></summary>

<br>

All requests go to `ggpolarbear.com` (Garena's current game API):
- OAuth: `100067.connect.garena.com`
- MajorLogin: `loginbp.ggpolarbear.com`
- GetLoginData: `clientbp.ggpolarbear.com` (or dynamic URL from MajorLogin response)
- PlayerInfo: `clientbp.ggpolarbear.com`

</details>

<details>
<summary><b>What are the protobuf files for?</b></summary>

<br>

The bot uses Protocol Buffers (protobuf) to construct and parse binary packets for Garena's API. The `.pb2.py` files are compiled protobuf definitions that serialize/deserialize the binary data.

</details>

<details>
<summary><b>Can I use a proxy?</b></summary>

<br>

Yes! Add proxies to `config/proxies.txt` (one per line, format: `ip:port` or `user:pass@ip:port`). The bot supports proxy rotation for different regions.

</details>

---

## 🐛 Troubleshooting

<details>
<summary><b>ModuleNotFoundError: No module named 'httpx'</b></summary>

<br>

```bash
pip install httpx
# or
pip install -r requirements.txt
```

</details>

<details>
<summary><b>ModuleNotFoundError: No module named 'Crypto'</b></summary>

<br>

```bash
pip install pycryptodome
# NOT pycrypto — make sure it's pycryptodome
```

</details>

<details>
<summary><b>MajorLogin returns 503</b></summary>

<br>

This is a Garena server-side issue, not a code problem. The game servers are down. Wait and try again later.

</details>

<details>
<summary><b>OAuth returns auth_error</b></summary>

<br>

The guest account's password has expired or the account was deleted. You need to generate a new guest account or get new credentials.

</details>

<details>
<summary><b>Connection refused / timeout</b></summary>

<br>

1. Check your internet connection
2. Verify the team code is valid
3. Try a different guest account
4. Check if Garena servers are up (option 4 in menu)

</details>

<details>
<summary><b>Bot crashes with KeyError: 'token'</b></summary>

<br>

This was a bug in v1.0 where the bot didn't handle MajorLogin failures. Fixed in v2.0 — the bot now gracefully handles 503, ban, and dead account errors.

</details>

---

## 🌐 Supported Regions

<div align="center">

| Code | Region | Endpoint |
|------|--------|----------|
| `IND` | India | ggpolarbear.com |
| `ME` | Middle East | ggpolarbear.com |
| `BR` | Brazil | ggpolarbear.com |
| `SG` | Singapore | ggpolarbear.com |
| `ID` | Indonesia | ggpolarbear.com |
| `TH` | Thailand | ggpolarbear.com |
| `PH` | Philippines | ggpolarbear.com |

</div>

---

## 📊 Stats

<div align="center">

<!-- Animated Stats SVG -->
<svg xmlns="http://www.w3.org/2000/svg" width="640" height="100" viewBox="0 0 640 100">
  <defs>
    <linearGradient id="statGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" style="stop-color:#4ECDC4;stop-opacity:0.2"/>
      <stop offset="100%" style="stop-color:#4ECDC4;stop-opacity:0"/>
    </linearGradient>
  </defs>

  <!-- Stat 1 -->
  <rect x="10" y="10" width="150" height="80" rx="12" fill="url(#statGrad)" stroke="#4ECDC4" stroke-width="1"/>
  <text x="85" y="40" font-family="monospace" font-size="28" font-weight="bold" fill="#4ECDC4" text-anchor="middle">7</text>
  <text x="85" y="65" font-family="monospace" font-size="10" fill="#999" text-anchor="middle">Files in src/</text>

  <!-- Stat 2 -->
  <rect x="170" y="10" width="150" height="80" rx="12" fill="url(#statGrad)" stroke="#FF416C" stroke-width="1"/>
  <text x="245" y="40" font-family="monospace" font-size="28" font-weight="bold" fill="#FF416C" text-anchor="middle">5</text>
  <text x="245" y="65" font-family="monospace" font-size="10" fill="#999" text-anchor="middle">Auth Steps</text>

  <!-- Stat 3 -->
  <rect x="330" y="10" width="150" height="80" rx="12" fill="url(#statGrad)" stroke="#4facfe" stroke-width="1"/>
  <text x="405" y="40" font-family="monospace" font-size="28" font-weight="bold" fill="#4facfe" text-anchor="middle">∞</text>
  <text x="405" y="65" font-family="monospace" font-size="10" fill="#999" text-anchor="middle">Cycles</text>

  <!-- Stat 4 -->
  <rect x="490" y="10" width="140" height="80" rx="12" fill="url(#statGrad)" stroke="#43e97b" stroke-width="1"/>
  <text x="560" y="40" font-family="monospace" font-size="28" font-weight="bold" fill="#43e97b" text-anchor="middle">24/7</text>
  <text x="560" y="65" font-family="monospace" font-size="10" fill="#999" text-anchor="middle">Uptime</text>

  <!-- Animated pulse line -->
  <line x1="10" y1="95" x2="630" y2="95" stroke="#4ECDC4" stroke-width="0.5" opacity="0.3">
    <animate attributeName="opacity" values="0.3;0.6;0.3" dur="2s" repeatCount="indefinite"/>
  </line>
</svg>

</div>

---

## 🤝 Contributing

Contributions are welcome! Here's how you can help:

1. **Fork** the repo
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Areas for Improvement
- [ ] Add GUI version
- [ ] Support for multiple simultaneous accounts
- [ ] Auto-reconnect on disconnect
- [ ] Web dashboard for monitoring
- [ ] Discord/Telegram notifications
- [ ] Auto-recovery for dead accounts

---

## 📜 Changelog

<details>
<summary><b>Version History</b></summary>

<br>

### v2.0 (2026-07-29)
- ✅ Fixed MajorLogin endpoint (ggblueshark.com → ggpolarbear.com)
- ✅ Dynamic GetLoginData URL from MajorLogin response
- ✅ Proper 503 server-down vs ban detection
- ✅ Clean ASCII menu (no more funky Unicode on Termux)
- ✅ Graceful error handling (no more KeyError crashes)
- ✅ Added Guest Checker standalone tool
- ✅ Added guest_info module with player info
- ✅ Added switch account feature
- ✅ Added .dat file import
- ✅ Added Docker support
- ✅ Added Frida hooks

### v1.0
- Initial release
- Basic level bot with hardcoded endpoints
- Simple menu
- No error handling for server-down

</details>

---

## 👤 Credits

<div align="center">

Developed by **ISMAILdz13**

<svg xmlns="http://www.w3.org/2000/svg" width="200" height="30" viewBox="0 0 200 30">
  <rect width="200" height="30" rx="15" fill="#2D2D2D" stroke="#4ECDC4" stroke-width="1">
    <animate attributeName="stroke" values="#4ECDC4;#FF416C;#4ECDC4" dur="3s" repeatCount="indefinite"/>
  </rect>
  <text x="100" y="20" font-family="monospace" font-size="12" fill="#4ECDC4" text-anchor="middle" font-weight="bold">@ISMAILdz13</text>
</svg>

</div>

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

<!-- Footer SVG -->
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="60" viewBox="0 0 600 60">
  <defs>
    <linearGradient id="footerGrad" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" style="stop-color:#FF416C;stop-opacity:0">
        <animate attributeName="offset" values="0;1;0" dur="5s" repeatCount="indefinite"/>
      </stop>
      <stop offset="100%" style="stop-color:#4ECDC4;stop-opacity:0">
        <animate attributeName="offset" values="1;0;1" dur="5s" repeatCount="indefinite"/>
      </stop>
    </linearGradient>
  </defs>
  <rect x="50" y="20" width="500" height="2" rx="1" fill="url(#footerGrad)"/>
  <text x="300" y="45" font-family="monospace" font-size="11" fill="#666" text-anchor="middle">Made with Python | Powered by Garena API | Runs on Termux</text>
</svg>

⭐ **Star this repo if it helped you!** ⭐

</div>
