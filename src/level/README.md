<div align="center">

# 🎮 Free Fire Level Bot

### Auto-join teams, spam match-start, and grind XP 24/7

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Version](https://img.shields.io/badge/Version-2.0-green.svg)](#)
[![Termux](https://img.shields.io/badge/Platform-Termux-ff69b4.svg)](#)

</div>

---

## 📋 Table of Contents

- [Overview](#overview)
- [Termux Menu](#termux-menu)
- [Quick Start](#quick-start)
- [Guest Info](#guest-info)
- [Architecture](#architecture)
- [How It Works](#how-it-works)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)

---

## Overview

The Level Bot automates the Free Fire leveling process:
1. Authenticates with a guest account via Garena OAuth
2. Connects to game TCP servers (whisper + online sockets)
3. Joins a squad team code
4. Spamming match-start packets
5. Waiting for the match to begin
6. Leaving the team
7. Repeating the cycle 24/7

---

## Termux Menu

Run `python level_menu.py` to get a cool 5-option menu:

| Option | What it does |
|--------|-------------|
| **1. Quick Start** | Asks for team code, starts immediately with default values (spam=18s, wait=20s) |
| **2. Custom Mode** | Lets you choose spam duration, delay, wait time, max cycles |
| **3. Change Guest Data** | Enter UID+password, load from .dat file, or load from JSON |
| **4. Guest Info** | Shows level, likes, clan, rank, ban/blacklist status |
| **5. Exit** | Quits |

---

## Guest Info

Option 4 queries the Garena `GetPlayerPersonalShow` API to show:

- **Nickname** — player display name
- **Level & EXP** — current level and experience
- **Likes** — total likes received ❤️
- **Rank & Max Rank** — current and highest rank
- **Clan** — clan name, level, and ID
- **Region, Gender, Language** — account details
- **Ban Status** — CLEAR ✅ / BANNED ❌ / BLACKLISTED ⚠️ / DEAD ❌
- **Credit Score** — Garena credit score
- **Last Login** — when account was last active
- **Account Created** — creation date
- **Elite Pass** — whether account has elite pass
- **Game Version** — last client version used

### Ban Detection Logic

| Auth Step | Result | Status |
|-----------|--------|--------|
| Guest OAuth fails | Account deleted/invalid | **DEAD** ❌ |
| MajorLogin fails | Account banned | **BANNED** ❌ |
| Player Info fails | Account restricted | **BLACKLISTED** ⚠️ |
| All steps succeed | Account is fine | **CLEAR** ✅ |

---

## Quick Start

### Termux (Android)

```bash
bash SETUP_LEVEL_TERMUX.sh
python level_menu.py
```

### Standalone

```bash
python run_level.py --uid 5822030305 --password 1FEDC7BF... --team-code 654321
```

---

## Architecture

```
src/level/
├── __init__.py          # Module exports
├── packet_builder.py    # Protobuf packet construction + AES-128 encryption
├── auth.py              # Garena OAuth → MajorLogin → GetLoginData → token
├── connection.py        # Async TCP socket manager (whisper + online)
├── match_engine.py      # Core loop: join → start → wait → leave → repeat
├── bot.py               # Top-level orchestrator
├── config.py            # Config dataclass + validation
├── guest_info.py        # GetPlayerPersonalShow → level/likes/clan/ban status
├── dev_generator_pb2.py # Protobuf: UID encryption request
├── data_pb2.py          # Protobuf: AccountPersonalShowInfo response
├── devxt_count_pb2.py   # Protobuf: fallback player info
└── requirements.txt     # Dependencies
```

---

## How It Works

Each cycle:
1. **Join** — sends join-team protobuf packet via whisper socket
2. **Spam Start** — sends match-start packets every 200ms for 18s via online socket
3. **Wait** — waits 20s for the match to start/complete
4. **Leave** — sends leave-team packet
5. **Repeat** — 2s delay, then back to step 1

---

## Configuration

| Parameter | CLI Flag | Default | Description |
|-----------|----------|---------|-------------|
| UID | `--uid` | (prompt) | Guest account UID |
| Password | `--password` | (prompt) | Guest password |
| Team Code | `--team-code` | (prompt) | Squad code (digits only) |
| Max Cycles | `--max-cycles` | 1000 | Safety limit (0 = infinite) |
| Spam Duration | `--spam-duration` | 18 | Seconds to spam start packets |
| Spam Delay | `--spam-delay` | 0.2 | Delay between start packets |
| Wait After | `--wait-after` | 20 | Seconds to wait after match |
| Accounts File | `--accounts-file` | None | JSON with {uid: password} |

---

## Troubleshooting

| Problem | Solution |
|---------|---------|
| `503 Service Unavailable` | Garena MajorLogin server is down. Wait and retry. |
| `auth_error` from OAuth | Guest account may be rate-limited, banned, or deleted. Wait 30 min and retry. |
| `ModuleNotFoundError` | Run `pip install httpx pycryptodome protobuf protobuf-decoder PyJWT` |
| Guest Info shows DEAD | Account is deleted or password is invalid |
| Guest Info shows BANNED | Account is banned by Garena |
| Guest Info shows BLACKLISTED | Account is restricted/blacklisted |
| Connection timeout | Check internet / game servers may be under maintenance |
