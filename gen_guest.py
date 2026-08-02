#!/usr/bin/env python3
"""
Generate a new Free Fire guest account and replace the current level bot account.

Usage on Termux:
  python3 gen_guest.py          # Generate new account, replace old one
  python3 gen_guest.py --keep   # Generate new account, keep old ones
  python3 gen_guest.py --list   # List all saved accounts

Requirements:
  pip install requests
"""

import argparse
import json
import os
import random
import hashlib
import hmac
import time
import requests
import urllib3
urllib3.disable_warnings()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(BASE_DIR, "data", "level_accounts.json")

# ── Garena OAuth constants ──────────────────────────────

HEX_KEY = "32656534343831396539623435393838343531343130363762323831363231383734643064356437616639643866376530306331653534373135623764316533"
HMAC_KEY = bytes.fromhex(HEX_KEY)
CLIENT_SECRET = HMAC_KEY.decode("ascii")
CLIENT_ID = "100067"

REGISTER_URL = "https://connect.garena.com/oauth/guest/register"
OAUTH_V2_URL = "https://ffmconnect.live.gop.garenanow.com/api/v2/oauth/guest/token:grant"
OAUTH_V1_URL = "https://100067.connect.garena.com/oauth/guest/token/grant"

UA_REGISTER = "GarenaMSDK/4.0.19P10(I2404 ;Android 15;en;US;)"
UA_OAUTH_V2 = "GarenaMSDK/4.0.19P10(I2404 ;Android 15;en;US;)"
UA_OAUTH_V1 = "GarenaMSDK/4.0.19P8(ASUS_Z01QD ;Android 12;en;US;)"


def rand_password():
    return ''.join(random.choices('0123456789abcdef', k=32))


def register_guest():
    """Register a new guest account. Works from Termux/phone IPs."""
    password = rand_password()
    sig = hmac.new(HMAC_KEY, password.encode(), hashlib.sha1).hexdigest()

    print("  Registering with Garena...")
    r = requests.post(REGISTER_URL,
        headers={
            "Authorization": f"Signature {sig}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": UA_REGISTER,
            "Accept-Encoding": "gzip",
            "Connection": "Keep-Alive",
        },
        data={
            "password": password,
            "client_id": CLIENT_ID,
            "client_type": "2",
            "response_type": "token",
            "signature": sig,
        },
        timeout=30, verify=False)

    if r.status_code != 200:
        print(f"  Registration failed (HTTP {r.status_code})")
        return None

    data = r.json()
    uid = data.get("uid")
    if not uid:
        print(f"  No UID in response: {data}")
        return None

    print(f"  Got UID: {uid}")

    # Verify with OAuth token grant
    for url, headers, payload in [
        (OAUTH_V2_URL, {"Content-Type": "application/json; charset=utf-8", "User-Agent": UA_OAUTH_V2},
         {"client_id": int(CLIENT_ID), "client_secret": CLIENT_SECRET,
          "password": password, "client_type": 2, "response_type": "token", "uid": int(uid)}),
        (OAUTH_V1_URL, {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": UA_OAUTH_V1},
         {"uid": str(uid), "password": password, "response_type": "token",
          "client_type": "2", "client_secret": CLIENT_SECRET, "client_id": CLIENT_ID}),
    ]:
        try:
            if "json" in headers.get("Content-Type", ""):
                r2 = requests.post(url, json=payload, headers=headers, timeout=15, verify=False)
            else:
                r2 = requests.post(url, data=payload, headers=headers, timeout=15, verify=False)
            if r2.status_code == 200:
                j = r2.json()
                odata = j.get("data", j)
                open_id = odata.get("open_id")
                access_token = odata.get("access_token")
                if open_id and access_token:
                    print(f"  OAuth verified! open_id={open_id[:12]}...")
                    return {"uid": str(uid), "password": password}
        except:
            continue

    print("  OAuth verification failed, but account was registered.")
    return {"uid": str(uid), "password": password}


def load_accounts():
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE) as f:
            return json.load(f)
    return {}


def save_accounts(accounts):
    os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump(accounts, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Generate new Free Fire guest for level bot")
    parser.add_argument("--keep", action="store_true", help="Keep old accounts (don't replace)")
    parser.add_argument("--list", action="store_true", help="List saved accounts")
    parser.add_argument("--count", type=int, default=1, help="Number of accounts to generate")
    args = parser.parse_args()

    if args.list:
        accounts = load_accounts()
        if not accounts:
            print("No accounts saved.")
        else:
            print(f"Saved accounts ({len(accounts)}):")
            for uid, pwd in accounts.items():
                print(f"  UID: {uid}  (password: {pwd[:8]}...)")
        return

    accounts = load_accounts() if args.keep else {}

    print("=" * 45)
    print("  Free Fire Guest Generator")
    print("=" * 45)
    print()

    success = 0
    for i in range(args.count):
        print(f"[{i+1}/{args.count}] Generating guest account...")
        guest = register_guest()
        if guest:
            accounts[guest["uid"]] = guest["password"]
            save_accounts(accounts)
            print(f"  ✅ Saved UID {guest['uid']}")
            success += 1
        else:
            print(f"  ❌ Failed (Garena may block this IP)")
        if i < args.count - 1:
            time.sleep(2)
        print()

    print("=" * 45)
    print(f"  Generated: {success}/{args.count}")
    if success > 0:
        print(f"  Saved to: data/level_accounts.json")
        if not args.keep and success > 0:
            print(f"  Old account replaced!")
        print()
        print("  Now run: python3 level_menu.py")
    print("=" * 45)

    if success == 0:
        print()
        print("⚠ Registration failed from this IP.")
        print("  Try running on your phone via Termux.")
        print("  Or extract a guest from Free Fire app and add manually:")
        print("  → Edit data/level_accounts.json: {\"UID\": \"password\"}")


if __name__ == "__main__":
    main()
