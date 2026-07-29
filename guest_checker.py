#!/usr/bin/env python3
"""
Guest Account Checker - Standalone Tool
Scans all guest accounts, checks which are alive/dead/banned,
and gets their level, likes, nickname, clan, region.

This is SEPARATE from the level bot. It only checks account status.

Usage:
    python guest_checker.py              # check all accounts
    python guest_checker.py --db guests.db  # specific db
    python guest_checker.py --json guests.json  # specific json
"""

import os
import sys
import json
import sqlite3
import asyncio
import argparse
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


class C:
    R = "\033[0m"
    B = "\033[1m"
    D = "\033[2m"
    R1 = "\033[91m"
    G  = "\033[92m"
    Y  = "\033[93m"
    CY = "\033[96m"
    W  = "\033[97m"


# ── Load accounts from all sources ──────────────────────

def load_all_accounts():
    """Load guest accounts from all sources, deduplicated."""
    accounts = {}  # uid -> {"password": ..., "source": [...], "name": ...}
    
    # Source 1: data/guests.json
    guests_json = os.path.join(PROJECT_ROOT, "data", "guests.json")
    if os.path.exists(guests_json):
        with open(guests_json) as f:
            try:
                guests = json.load(f)
                for g in guests:
                    uid = g.get("uid", "")
                    pwd = g.get("password", "")
                    name = g.get("name", "")
                    if uid and pwd:
                        if uid not in accounts:
                            accounts[uid] = {"password": pwd, "sources": [], "name": name}
                        accounts[uid]["sources"].append("guests.json")
                        if name and not accounts[uid].get("name"):
                            accounts[uid]["name"] = name
            except Exception as e:
                print(f"  {C.R1}Error reading guests.json: {e}{C.R}")
    
    # Source 2: data/guests.db (SQLite)
    guests_db = os.path.join(PROJECT_ROOT, "data", "guests.db")
    if os.path.exists(guests_db):
        try:
            conn = sqlite3.connect(guests_db)
            cursor = conn.cursor()
            cursor.execute("SELECT uid, password, nickname, health_status FROM guests")
            for row in cursor.fetchall():
                uid, pwd, nick, health = row
                if uid and pwd:
                    if uid not in accounts:
                        accounts[uid] = {"password": pwd, "sources": [], "name": nick or ""}
                    accounts[uid]["sources"].append(f"guests.db({health})")
                    if nick and not accounts[uid].get("name"):
                        accounts[uid]["name"] = nick
            conn.close()
        except Exception as e:
            print(f"  {C.R1}Error reading guests.db: {e}{C.R}")
    
    # Source 3: data/level_accounts.json
    level_json = os.path.join(PROJECT_ROOT, "data", "level_accounts.json")
    if os.path.exists(level_json):
        with open(level_json) as f:
            try:
                data = json.load(f)
                for uid, pwd in data.items():
                    if uid and pwd:
                        if uid not in accounts:
                            accounts[uid] = {"password": pwd, "sources": [], "name": ""}
                        accounts[uid]["sources"].append("level_accounts.json")
            except Exception as e:
                print(f"  {C.R1}Error reading level_accounts.json: {e}{C.R}")
    
    return accounts


# ── Check a single account ──────────────────────────────

async def check_account(http, uid, password, name=""):
    """Check a single guest account. Returns a dict with all info."""
    result = {
        "uid": uid,
        "name": name or "",
        "password": password,
        "oauth_status": "UNKNOWN",
        "ban_status": "UNKNOWN",
        "ban_reason": "",
        "nickname": "Unknown",
        "level": 0,
        "exp": 0,
        "likes": 0,
        "rank": 0,
        "region": "Unknown",
        "clan_name": "None",
        "clan_level": 0,
        "release_version": "Unknown",
        "checked_at": datetime.now().isoformat(),
    }
    
    from src.level.auth import LevelAuth
    auth = LevelAuth(http)
    
    # Step 1: OAuth (works even when game servers are down)
    oauth = await auth.guest_token(uid, password, retries=2)
    if not oauth:
        result["oauth_status"] = "DEAD"
        result["ban_status"] = "DEAD"
        result["ban_reason"] = "OAuth failed - account deleted or password invalid"
        return result
    
    access_token, open_id = oauth
    result["oauth_status"] = "ALIVE"
    
    # Step 2: MajorLogin (only works when game servers are up)
    login = await auth.major_login(access_token, open_id, retries=2)
    
    if login and not login.get("error"):
        result["ban_status"] = "CLEAR"
        jwt_token = login["token"]
        
        # Step 3: Player Info
        try:
            from src.level.guest_info import GuestInfo
            info = GuestInfo(http)
            player_data = await info._get_player_personal_show(uid, jwt_token)
            if player_data:
                info._parse_info(result, player_data, uid)
        except Exception as e:
            result["ban_reason"] = f"Player info error: {e}"
    else:
        last_status = login.get("last_status", 0) if isinstance(login, dict) else 0
        if last_status == 503:
            result["ban_status"] = "SERVER_DOWN"
            result["ban_reason"] = "Garena servers down (503) - not a ban"
        elif last_status in (400, 401, 403):
            result["ban_status"] = "BANNED"
            result["ban_reason"] = f"Account banned (HTTP {last_status})"
        else:
            result["ban_status"] = "UNKNOWN"
            result["ban_reason"] = f"MajorLogin failed (HTTP {last_status})"
    
    return result


# ── Main check loop ────────────────────────────────────

async def check_all_accounts(accounts, concurrent=3):
    """Check all accounts with limited concurrency."""
    import httpx
    
    async def check_one(http, uid, data, idx, total):
        result = await check_account(http, uid, data["password"], data.get("name", ""))
        # Print live progress
        status = result["ban_status"]
        if status == "CLEAR":
            icon = f"{C.G}OK{C.R}"
            extra = f"Lv{result['level']} {result['likes']}likes {result['nickname']}"
        elif status == "SERVER_DOWN":
            icon = f"{C.Y}SVR{C.R}"
            extra = f"{C.D}oauth=alive, servers down{C.R}"
        elif status == "BANNED":
            icon = f"{C.R1}BAN{C.R}"
            extra = f"{C.D}{result['ban_reason']}{C.R}"
        elif status == "DEAD":
            icon = f"{C.R1}DEAD{C.R}"
            extra = f"{C.D}account deleted{C.R}"
        else:
            icon = f"{C.Y}??{C.R}"
            extra = f"{C.D}{result['ban_reason']}{C.R}"
        
        print(f"  [{idx}/{total}] {uid:15s} {icon}  {extra}")
        return result
    
    total = len(accounts)
    print(f"\n  {C.B}Checking {total} accounts...{C.R}")
    print(f"  {C.D}(OAuth works even if game servers are down){C.R}\n")
    
    # Create shared HTTP client
    http = httpx.AsyncClient(verify=False, follow_redirects=True)
    
    # Process with limited concurrency
    semaphore = asyncio.Semaphore(concurrent)
    results = []
    
    async def limited_check(uid, data, idx):
        async with semaphore:
            return await check_one(http, uid, data, idx, total)
    
    tasks = []
    for i, (uid, data) in enumerate(accounts.items(), 1):
        tasks.append(limited_check(uid, data, i))
    
    results = await asyncio.gather(*tasks)
    await http.aclose()
    
    return results


# ── Report ─────────────────────────────────────────────

def print_report(results):
    """Print a summary table of all accounts."""
    print()
    print(f"  {C.CY}========================================{C.R}")
    print(f"  {C.B}  GUEST ACCOUNT REPORT{C.R}")
    print(f"  {C.CY}========================================{C.R}")
    print()
    
    # Header
    print(f"  {'UID':15s} {'STATUS':8s} {'NICK':12s} {'LVL':>4s} {'LIKES':>5s} {'REGION':6s} {'CLAN':12s}")
    print(f"  {'-'*15} {'-'*8} {'-'*12} {'-'*4} {'-'*5} {'-'*6} {'-'*12}")
    
    alive = 0
    dead = 0
    banned = 0
    server_down = 0
    unknown = 0
    
    for r in results:
        status = r["ban_status"]
        if status == "CLEAR":
            sc = C.G
            alive += 1
        elif status == "DEAD":
            sc = C.R1
            dead += 1
        elif status == "BANNED":
            sc = C.R1
            banned += 1
        elif status == "SERVER_DOWN":
            sc = C.Y
            server_down += 1
        else:
            sc = C.Y
            unknown += 1
        
        nick = (r["nickname"] or "?")[:12]
        clan = (r["clan_name"] or "None")[:12]
        
        print(f"  {r['uid']:15s} {sc}{status:8s}{C.R} {nick:12s} {r['level']:4d} {r['likes']:5d} {r['region']:6s} {clan:12s}")
    
    print()
    print(f"  {C.CY}----------------------------------------{C.R}")
    print(f"  {C.B}Summary:{C.R}")
    print(f"  {C.G}Alive:       {alive}{C.R}")
    if server_down:
        print(f"  {C.Y}Server Down: {server_down}{C.R}")
    if banned:
        print(f"  {C.R1}Banned:      {banned}{C.R}")
    if dead:
        print(f"  {C.R1}Dead:        {dead}{C.R}")
    if unknown:
        print(f"  {C.Y}Unknown:     {unknown}{C.R}")
    print(f"  {C.B}Total:       {len(results)}{C.R}")
    print(f"  {C.CY}========================================{C.R}")
    print()


def save_report(results):
    """Save report to JSON file."""
    report_file = os.path.join(PROJECT_ROOT, "data", "guest_report.json")
    
    # Clean up for JSON
    clean = []
    for r in results:
        c = dict(r)
        clean.append(c)
    
    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_accounts": len(results),
        "alive": sum(1 for r in results if r["ban_status"] == "CLEAR"),
        "dead": sum(1 for r in results if r["ban_status"] == "DEAD"),
        "banned": sum(1 for r in results if r["ban_status"] == "BANNED"),
        "server_down": sum(1 for r in results if r["ban_status"] == "SERVER_DOWN"),
        "unknown": sum(1 for r in results if r["ban_status"] == "UNKNOWN"),
        "accounts": clean,
    }
    
    with open(report_file, "w") as f:
        json.dump(summary, f, indent=2)
    
    print(f"  {C.G}Report saved to: data/guest_report.json{C.R}")
    print()


# ── Main ────────────────────────────────────────────────

def main():
    print()
    print(f"  {C.CY}{C.B}========================================{C.R}")
    print(f"  {C.CY}{C.B}    GUEST ACCOUNT CHECKER  v1.0        {C.R}")
    print(f"  {C.CY}{C.B}========================================{C.R}")
    print()
    
    # Load all accounts
    accounts = load_all_accounts()
    
    if not accounts:
        print(f"  {C.R1}No guest accounts found!{C.R}")
        print(f"  {C.D}Put accounts in data/guests.json or data/level_accounts.json{C.R}")
        return
    
    print(f"  Found {len(accounts)} accounts:")
    for uid, data in accounts.items():
        srcs = ", ".join(data["sources"])
        name = data.get("name", "")
        print(f"  {C.D}{uid:15s} {C.W}{name:12s} {C.D}({srcs}){C.R}")
    print()
    
    # Run checks
    results = asyncio.run(check_all_accounts(accounts))
    
    # Print report
    print_report(results)
    
    # Save
    save_report(results)
    
    print(f"  {C.D}Done!{C.R}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {C.Y}Interrupted.{C.R}\n")
        sys.exit(0)
