#!/usr/bin/env python3
"""
Import a working guest account from ClanGloryBot into the level bot.
Since Garena's registration API is down/changed, reuse existing working accounts.

Usage:
  python3 import_guest.py              # Auto-import first working guest
  python3 import_guest.py --index 2     # Import guest #2 from ClanGloryBot
  python3 import_guest.py --path ~/ClanGloryBot/data/guests.json  # Custom path
"""

import argparse
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(BASE_DIR, "data", "level_accounts.json")

# Default paths to look for ClanGloryBot guests
CLAN_GUEST_PATHS = [
    os.path.expanduser("~/ClanGloryBot/data/guests.json"),
    os.path.expanduser("~/FreeFireClanBot/data/guests.json"),
    os.path.expanduser("~/clan-glory-bot/data/guests.json"),
]


def find_guests_file(custom_path=None):
    if custom_path:
        if os.path.exists(custom_path):
            return custom_path
        return None
    for p in CLAN_GUEST_PATHS:
        if os.path.exists(p):
            return p
    return None


def main():
    parser = argparse.ArgumentParser(description="Import working guest from ClanGloryBot")
    parser.add_argument("--index", type=int, default=1, help="Which guest to import (1-based)")
    parser.add_argument("--path", type=str, default=None, help="Custom path to guests.json")
    parser.add_argument("--list", action="store_true", help="List available guests")
    args = parser.parse_args()

    guests_file = find_guests_file(args.path)
    if not guests_file:
        print("❌ Could not find ClanGloryBot/data/guests.json")
        print("  Checked:")
        for p in CLAN_GUEST_PATHS:
            print(f"    {p}")
        print("\n  Use --path to specify a custom location:")
        print("  python3 import_guest.py --path /path/to/guests.json")
        return

    with open(guests_file) as f:
        guests = json.load(f)

    if not guests:
        print("❌ No guests found in ClanGloryBot data file")
        return

    if args.list:
        print(f"Available guests in {guests_file} ({len(guests)}):")
        for i, g in enumerate(guests):
            uid = g.get("uid", "?")
            pwd = g.get("password", "?")
            print(f"  [{i+1}] UID: {uid}  (password: {pwd[:8]}...)")
        return

    idx = args.index - 1
    if idx < 0 or idx >= len(guests):
        print(f"❌ Index {args.index} out of range (1-{len(guests)})")
        print("  Use --list to see available guests")
        return

    guest = guests[idx]
    uid = guest["uid"]
    password = guest["password"]

    # Save to level bot's account file (replace existing)
    os.makedirs(os.path.dirname(ACCOUNTS_FILE), exist_ok=True)
    with open(ACCOUNTS_FILE, "w") as f:
        json.dump({uid: password}, f, indent=2)

    print("=" * 45)
    print("  Guest imported from ClanGloryBot!")
    print("=" * 45)
    print(f"  UID:      {uid}")
    print(f"  Password: {password[:8]}...{password[-4:]}")
    print(f"  Source:   {guests_file}")
    print(f"  Saved to: {ACCOUNTS_FILE}")
    print()
    print("  Now run: python3 level_menu.py")
    print("=" * 45)


if __name__ == "__main__":
    main()
