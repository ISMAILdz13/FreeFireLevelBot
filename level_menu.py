#!/usr/bin/env python3
"""
Free Fire Level Bot - Termux Menu
Usage: python level_menu.py
"""

import os
import sys
import json
import asyncio
import platform

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)


# ── Colors ─────────────────────────────────────────────

class C:
    R = "\033[0m"    # reset
    B = "\033[1m"    # bold
    D = "\033[2m"    # dim
    R1 = "\033[91m"  # red
    G  = "\033[92m"  # green
    Y  = "\033[93m"  # yellow
    BL = "\033[94m"  # blue
    M  = "\033[95m"  # magenta
    CY = "\033[96m"  # cyan
    W  = "\033[97m"  # white


def clear():
    os.system("clear" if platform.system() != "Windows" else "cls")


# ── Banner ─────────────────────────────────────────────

def banner():
    clear()
    print(f"{C.CY}{C.B}")
    print("  ========================================")
    print("  |        FREE FIRE LEVEL BOT           |")
    print(f"  |{C.R}  v2.0  {C.CY}{C.B}|{C.R}  Termux Edition  {C.CY}{C.B}|{C.R}")
    print("  ========================================")
    print(f"{C.R}")
    print(f"{C.D}  Join -> Start -> Wait -> Leave -> Repeat{C.R}")
    print()


# ── Menu ────────────────────────────────────────────────

def menu():
    print(f"{C.CY}  ----------------------------------------{C.R}")
    print(f"  {C.G}[1]{C.W} Quick Start  {C.D}(default values){C.R}")
    print(f"  {C.G}[2]{C.W} Custom Mode  {C.D}(your values){C.R}")
    print(f"  {C.G}[3]{C.W} Change Guest Data{C.R}")
    print(f"  {C.G}[4]{C.W} Guest Info    {C.D}(level/likes/ban){C.R}")
    print(f"  {C.R1}[5]{C.W} Exit{C.R}")
    print(f"{C.CY}  ----------------------------------------{C.R}")
    print()


# ── Status ─────────────────────────────────────────────

def status(account=None):
    print(f"{C.CY}  ----------------------------------------{C.R}")
    if account:
        print(f"  {C.Y}Guest UID:{C.W} {account.get('uid', 'N/A')}{C.R}")
        print(f"  {C.Y}Status:{C.G} Ready{C.R}")
    else:
        print(f"  {C.Y}Guest UID:{C.R1} Not set (use option 3){C.R}")
        print(f"  {C.Y}Status:{C.R1} No guest data{C.R}")
    print(f"{C.CY}  ----------------------------------------{C.R}")
    print()


# ── Guest Data ─────────────────────────────────────────

def load_guest():
    data_file = os.path.join(PROJECT_ROOT, "data", "level_accounts.json")
    if os.path.exists(data_file):
        with open(data_file) as f:
            accounts = json.load(f)
        if accounts:
            uid = list(accounts.keys())[-1]
            password = accounts[uid]
            return {"uid": uid, "password": password}
    return None


def save_guest(uid, password):
    data_dir = os.path.join(PROJECT_ROOT, "data")
    os.makedirs(data_dir, exist_ok=True)
    data_file = os.path.join(data_dir, "level_accounts.json")
    with open(data_file, "w") as f:
        json.dump({uid: password}, f, indent=2)
    print(f"\n  {C.G}>> Guest data saved!{C.R}")


def parse_dat_file(filepath):
    with open(filepath, "rb") as f:
        content = f.read()
    try:
        data = json.loads(content)
        guest_info = data.get("guest_account_info", {})
        uid = guest_info.get("com.garena.msdk.guest_uid", "")
        password = guest_info.get("com.garena.msdk.guest_password", "")
        if uid and password:
            return uid, password
    except Exception:
        pass
    return None, None


# ── Run Bot ─────────────────────────────────────────────

async def run_bot(uid, password, team_code, spam_duration=18, spam_delay=0.2,
                  wait_after=20, max_cycles=0):
    from src.level.bot import LevelBot

    if max_cycles == 0:
        max_cycles = 999999

    bot = LevelBot(
        uid=uid, password=password, team_code=team_code,
        max_cycles=max_cycles, spam_duration=spam_duration,
        spam_delay=spam_delay, wait_after_match=wait_after,
    )

    print()
    print(f"  {C.CY}----------------------------------------{C.R}")
    print(f"  {C.B}Starting Level Bot...{C.R}")
    print(f"  {C.D}UID:  {C.W}{uid}{C.R}")
    print(f"  {C.D}Squad: {C.W}{team_code}{C.R}")
    print(f"  {C.D}Spam: {C.W}{spam_duration}s{C.D} (delay {spam_delay}s){C.R}")
    print(f"  {C.D}Wait: {C.W}{wait_after}s{C.R}")
    print(f"  {C.D}Cycles: {C.W}{'infinite' if max_cycles >= 999999 else max_cycles}{C.R}")
    print(f"  {C.CY}----------------------------------------{C.R}")
    print(f"  {C.Y}Press Ctrl+C to stop{C.R}")
    print()

    try:
        stats = await bot.start()
        print()
        print(f"  {C.CY}----------------------------------------{C.R}")
        print(f"  {C.B}Bot Finished{C.R}")
        print(f"  {C.D}Cycles: {C.W}{stats.cycles}{C.R}")
        print(f"  {C.D}Matches:{C.W} {stats.matches}{C.R}")
        print(f"  {C.D}Uptime: {C.W}{stats.uptime_seconds:.0f}s{C.R}")
        print(f"  {C.D}State:  {C.W}{stats.state}{C.R}")
        print(f"  {C.CY}----------------------------------------{C.R}")
    except KeyboardInterrupt:
        print(f"\n\n  {C.Y}>> Stopping bot...{C.R}")
        await bot.stop()
        print(f"  {C.G}>> Bot stopped.{C.R}")
    except Exception as e:
        print(f"\n  {C.R1}>> Error: {e}{C.R}")


# ── Option 1: Quick Start ───────────────────────────────

def opt1_quick():
    banner()
    print(f"  {C.B}{C.G}>> QUICK START{C.R}")
    print(f"  {C.D}Default: spam=18s, wait=20s, delay=0.2s{C.R}")
    print()

    guest = load_guest()
    status(account=guest)

    if not guest:
        print(f"  {C.R1}No guest data! Use option 3 first.{C.R}")
        input(f"\n  {C.D}Press Enter...{C.R}")
        return

    squad_code = input(f"  {C.CY}Squad code {C.D}(or 'solo' to open own):{C.W} ").strip()
    if not squad_code:
        print(f"  {C.R1}Empty! Enter a squad code or 'solo'.{C.R}")
        input(f"\n  {C.D}Press Enter...{C.R}")
        return

    code = "" if squad_code.lower() == "solo" else squad_code
    asyncio.run(run_bot(
        uid=guest["uid"], password=guest["password"], team_code=code,
    ))


# ── Option 2: Custom Mode ───────────────────────────────

def opt2_custom():
    banner()
    print(f"  {C.B}{C.Y}>> CUSTOM MODE{C.R}")
    print()

    guest = load_guest()
    status(account=guest)

    if not guest:
        print(f"  {C.R1}No guest data! Use option 3 first.{C.R}")
        input(f"\n  {C.D}Press Enter...{C.R}")
        return

    squad_code = input(f"  {C.CY}Squad code {C.D}(or 'solo' to open own):{C.W} ").strip()
    if not squad_code:
        print(f"  {C.R1}Empty! Enter a squad code or 'solo'.{C.R}")
        input(f"\n  {C.D}Press Enter...{C.R}")
        return

    code = "" if squad_code.lower() == "solo" else squad_code
    def num(prompt, default, lo=1, hi=9999):
        raw = input(f"  {C.CY}{prompt} {C.D}[{default}]:{C.W} ").strip()
        if not raw:
            return default
        try:
            v = int(raw)
            return v if lo <= v <= hi else default
        except ValueError:
            return default

    def dec(prompt, default, lo=0.01, hi=10):
        raw = input(f"  {C.CY}{prompt} {C.D}[{default}]:{C.W} ").strip()
        if not raw:
            return default
        try:
            v = float(raw)
            return v if lo <= v <= hi else default
        except ValueError:
            return default

    print(f"\n  {C.D}-- Custom Settings --{C.R}\n")
    spam_dur = num("Spam duration (sec)", 18, 1, 120)
    spam_dly = dec("Packet delay (sec)", 0.2, 0.01, 5)
    wait_af  = num("Wait after match (sec)", 20, 1, 300)
    max_cyc  = num("Max cycles (0=inf)", 0, 0, 99999)

    asyncio.run(run_bot(
        uid=guest["uid"], password=guest["password"], team_code=code,
        spam_duration=spam_dur, spam_delay=spam_dly,
        wait_after=wait_af, max_cycles=max_cyc,
    ))


# ── Option 3: Change Guest ──────────────────────────────

def opt3_guest():
    while True:
        banner()
        print(f"  {C.B}{C.M}>> CHANGE GUEST DATA{C.R}")
        print()

        guest = load_guest()
        if guest:
            print(f"  {C.D}Current: {C.W}{guest['uid']}{C.R}")
        print()
        print(f"  {C.G}[1]{C.W} Enter UID + Password manually{C.R}")
        print(f"  {C.G}[2]{C.W} Load from .dat file{C.R}")
        print(f"  {C.G}[3]{C.W} Switch account{C.R}")
        print(f"  {C.R1}[0]{C.W} Back{C.R}")
        print()

        sub = input(f"  {C.CY}Choice: {C.W}").strip()

        if sub == "1":
            uid = input(f"  {C.CY}UID: {C.W}").strip()
            pwd = input(f"  {C.CY}Password: {C.W}").strip()
            if uid and pwd:
                save_guest(uid, pwd)
            else:
                print(f"  {C.R1}Empty UID or password!{C.R}")
            input(f"\n  {C.D}Press Enter...{C.R}")

        elif sub == "2":
            filepath = input(f"  {C.CY}.dat file path: {C.W}").strip()
            if not filepath:
                filepath = os.path.join(PROJECT_ROOT, "data", "d098197e3_guest100067.dat")
            if os.path.exists(filepath):
                uid, pwd = parse_dat_file(filepath)
                if uid and pwd:
                    save_guest(uid, pwd)
                else:
                    print(f"  {C.R1}Could not parse .dat file!{C.R}")
            else:
                print(f"  {C.R1}File not found: {filepath}{C.R}")
            input(f"\n  {C.D}Press Enter...{C.R}")

        elif sub == "3":
            data_file = os.path.join(PROJECT_ROOT, "data", "level_accounts.json")
            if os.path.exists(data_file):
                with open(data_file) as f:
                    accounts = json.load(f)
                if len(accounts) > 1:
                    print()
                    for i, (uid, _) in enumerate(accounts.items(), 1):
                        mark = f" {C.G}(current){C.R}" if i == len(accounts) else ""
                        print(f"  {C.G}[{i}]{C.W} {uid}{mark}{C.R}")
                    print()
                    idx = input(f"  {C.CY}Select: {C.W}").strip()
                    try:
                        idx = int(idx)
                        uids = list(accounts.keys())
                        if 1 <= idx <= len(uids):
                            selected_uid = uids[idx - 1]
                            selected_pwd = accounts.pop(selected_uid)
                            accounts[selected_uid] = selected_pwd
                            with open(data_file, "w") as f:
                                json.dump(accounts, f, indent=2)
                            print(f"  {C.G}>> Switched to {selected_uid}{C.R}")
                    except (ValueError, IndexError):
                        print(f"  {C.R1}Invalid selection!{C.R}")
                else:
                    print(f"  {C.R1}Only one account saved.{C.R}")
            input(f"\n  {C.D}Press Enter...{C.R}")

        elif sub == "0":
            return


# ── Option 4: Guest Info ────────────────────────────────

def opt4_info():
    banner()
    print(f"  {C.B}{C.CY}>> GUEST INFO{C.R}")
    print(f"  {C.D}Checking level, likes, clan, ban status...{C.R}")
    print()

    guest = load_guest()
    if not guest:
        print(f"  {C.R1}No guest data! Use option 3 first.{C.R}")
        input(f"\n  {C.D}Press Enter...{C.R}")
        return

    uid = guest["uid"]
    pwd = guest["password"]

    print(f"  {C.D}UID: {C.W}{uid}{C.R}")
    print(f"  {C.D}Querying Garena servers...{C.R}")
    print()

    async def fetch_info():
        import httpx
        http = httpx.AsyncClient(verify=False, follow_redirects=True)
        try:
            from src.level.guest_info import GuestInfo
            info = GuestInfo(http)
            result = await info.fetch(uid, pwd)
            return result
        finally:
            await http.aclose()

    result = asyncio.run(fetch_info())

    ban = result.get("ban_status", "UNKNOWN")
    if ban == "CLEAR":
        bc, bi = C.G, "[OK]"
    elif ban == "BANNED":
        bc, bi = C.R1, "[BANNED]"
    elif ban == "DEAD":
        bc, bi = C.R1, "[DEAD]"
    elif ban == "BLACKLISTED":
        bc, bi = C.Y, "[BLACKLISTED]"
    elif ban == "SERVER_DOWN":
        bc, bi = C.Y, "[SERVER DOWN]"
    else:
        bc, bi = C.Y, "[?]"

    print(f"  {C.CY}========================================{C.R}")
    print(f"  {C.B}  GUEST ACCOUNT INFO{C.R}")
    print(f"  {C.CY}========================================{C.R}")
    print()
    print(f"  {C.Y}Nickname:{C.W}  {result.get('nickname', 'Unknown')}{C.R}")
    print(f"  {C.Y}UID:{C.W}       {result.get('uid', 'Unknown')}{C.R}")
    print(f"  {C.Y}Level:{C.W}     {C.B}{result.get('level', 0)}{C.R}")
    print(f"  {C.Y}EXP:{C.W}       {result.get('exp', 0)}{C.R}")
    print(f"  {C.Y}Likes:{C.W}     {result.get('likes', 0)}{C.R}")
    print(f"  {C.Y}Rank:{C.W}      {result.get('rank', 0)}{C.R}")
    print(f"  {C.Y}Region:{C.W}    {result.get('region', 'Unknown')}{C.R}")
    print()
    print(f"  {C.CY}----------------------------------------{C.R}")
    print(f"  {C.Y}Clan:{C.W}      {result.get('clan_name', 'None')}{C.R}")
    if result.get('clan_level', 0) > 0:
        print(f"  {C.Y}Clan Lvl:{C.W}   {result.get('clan_level', 0)}{C.R}")
    print()
    print(f"  {C.CY}----------------------------------------{C.R}")
    print(f"  {C.Y}Ban Status:{C.W} {bc}{bi} {ban}{C.R}")
    if result.get("ban_reason"):
        print(f"  {C.D}  {result['ban_reason']}{C.R}")
    print()
    print(f"  {C.Y}Version:{C.W}    {result.get('release_version', 'Unknown')}{C.R}")
    print(f"  {C.CY}========================================{C.R}")
    print()

    input(f"  {C.D}Press Enter...{C.R}")


# ── Option 5: Exit ──────────────────────────────────────

def opt5_exit():
    clear()
    print(f"\n  {C.B}{C.CY}Thanks for using Level Bot!{C.R}")
    print(f"  {C.D}Goodbye{C.R}\n")
    sys.exit(0)


# ── Main Loop ───────────────────────────────────────────

def main():
    while True:
        banner()
        guest = load_guest()
        status(account=guest)
        menu()

        choice = input(f"  {C.B}{C.Y}Select [1-5]:{C.W} ").strip()

        if choice == "1":
            opt1_quick()
        elif choice == "2":
            opt2_custom()
        elif choice == "3":
            opt3_guest()
        elif choice == "4":
            opt4_info()
        elif choice == "5":
            opt5_exit()
        else:
            print(f"  {C.R1}Invalid! Choose 1-5.{C.R}")
            import time
            time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n  {C.Y}Goodbye!{C.R}\n")
        sys.exit(0)
