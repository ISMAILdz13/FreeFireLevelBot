#!/usr/bin/env python3
"""
Import Free Fire guest accounts from raw .dat files (Garena MSDK local storage format).

These .dat files are extracted directly from the game's local storage and contain
JSON like:
  {"guest_account_info":{"com.garena.msdk.guest_password":"<hex>", "com.garena.msdk.guest_uid":"<uid>"}}

This bypasses Garena's guest-registration API (which blocks server/cloud IPs) —
since these are accounts already registered on-device, they can be logged into
directly via OAuth from anywhere.

Usage on Termux:
  python3 import_dat_guests.py <path_to_dat_or_folder_or_zip>

Examples:
  python3 import_dat_guests.py Guest.zip
  python3 import_dat_guests.py Guest/
  python3 import_dat_guests.py Guest/guest100067.dat

What it does:
  1. Parses all .dat files found (zip, folder, or single file)
  2. For each: OAuth login -> MajorLogin to check if the account is alive
  3. Dead/banned accounts (33-37 byte rejection, account_uid=0) are skipped
  4. Live accounts are auto-joined to the configured clan
  5. Live accounts are saved into data/guests.json (dedup by uid)
"""

import argparse
import asyncio
import json
import os
import sys
import zipfile
import tempfile
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(BASE_DIR, "test_real"))
sys.path.insert(0, os.path.join(BASE_DIR, "test_real", "Pb2"))

GUESTS_FILE = os.path.join(BASE_DIR, "data", "guests.json")
CLAN_ID = 3100938923  # change if your clan ID differs


def find_dat_files(path):
    """Return list of .dat file paths from a zip, folder, or single file."""
    dat_files = []
    if os.path.isdir(path):
        for root, _, files in os.walk(path):
            for f in files:
                if f.endswith(".dat"):
                    dat_files.append(os.path.join(root, f))
    elif path.endswith(".zip"):
        tmp = tempfile.mkdtemp()
        with zipfile.ZipFile(path) as z:
            z.extractall(tmp)
        for root, _, files in os.walk(tmp):
            for f in files:
                if f.endswith(".dat"):
                    dat_files.append(os.path.join(root, f))
    elif path.endswith(".dat"):
        dat_files.append(path)
    return dat_files


def parse_dat_file(filepath):
    """Extract uid + password from a guest .dat file."""
    try:
        with open(filepath) as f:
            data = json.load(f)
        info = data.get("guest_account_info", {})
        uid = info.get("com.garena.msdk.guest_uid")
        password = info.get("com.garena.msdk.guest_password")
        if uid and password:
            return {"uid": str(uid), "password": password}
    except Exception as e:
        print(f"  ⚠ Could not parse {filepath}: {e}")
    return None


async def check_and_import(guest, clan_id):
    """Login-test a guest, join clan if alive, return enriched dict or None."""
    from level_bot_real import GeNeRaTeAccEss, EncRypTMajoRLoGin, MajorLogin, DecRypTMajoRLoGin

    uid, password = guest["uid"], guest["password"]
    oid, tok = await GeNeRaTeAccEss(uid, password)
    if not oid:
        print(f"  [{uid}] ❌ OAuth failed")
        return None

    payload = await EncRypTMajoRLoGin(oid, tok)
    resp = await MajorLogin(payload)
    if not resp:
        print(f"  [{uid}] ❌ MajorLogin failed (no response)")
        return None

    # Dead/banned accounts get a short rejection (~25-40 bytes)
    if len(resp) < 100:
        print(f"  [{uid}] ❌ DEAD/BANNED ({len(resp)}B rejection)")
        return None

    auth = await DecRypTMajoRLoGin(resp)
    account_uid = str(auth.account_uid)
    if account_uid == "0":
        print(f"  [{uid}] ❌ DEAD/BANNED (account_uid=0)")
        return None

    print(f"  [{uid}] ✅ ALIVE — account_uid={account_uid}")

    # Join clan
    joined = await join_clan(auth.token, auth.url, clan_id)
    print(f"  [{uid}] Clan {clan_id}: {'✅ joined' if joined else '❌ failed'}")

    return {
        "uid": uid,
        "password": password,
        "name": f"BOT{uid[-6:]}",
        "region": "ME",
        "status": "registered",
        "open_id": oid,
        "access_token": tok,
    }


async def join_clan(jwt_token, server_url, clan_id):
    import aiohttp
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad
    from level_bot_real import DEFAULT_KEY, DEFAULT_IV

    def encode_varint(value):
        buf = []
        value = int(value)
        while True:
            towrite = value & 0x7f
            value >>= 7
            if value:
                buf.append(towrite | 0x80)
            else:
                buf.append(towrite)
                break
        return bytes(buf).hex()

    gid_int = int(clan_id)
    gid_str_bytes = str(gid_int).encode("utf-8")
    gid_str_len = encode_varint(len(gid_str_bytes))
    gid_varint = encode_varint(gid_int)
    payload_formats = [
        f"0a{gid_str_len}{gid_str_bytes.hex()}",
        f"12{gid_str_len}{gid_str_bytes.hex()}",
        f"10{gid_varint}",
        f"08{gid_varint}",
    ]
    urls = [f"{server_url}/RequestJoinClan", "https://clientbp.common.ggbluefox.com/RequestJoinClan"]
    headers = {
        "Authorization": f"Bearer {jwt_token}",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 11; SM-A145F Build/RP1A.200720.012)",
        "X-Unity-Version": "2018.4.11f1", "X-GA": "v1 1", "ReleaseVersion": "OB54",
        "Connection": "Keep-Alive", "Accept-Encoding": "gzip",
    }
    async with aiohttp.ClientSession() as session:
        for payload_hex in payload_formats:
            cipher = AES.new(DEFAULT_KEY, AES.MODE_CBC, DEFAULT_IV)
            enc_hex = cipher.encrypt(pad(bytes.fromhex(payload_hex), 16)).hex()
            for url in urls:
                try:
                    async with session.post(url, data=bytes.fromhex(enc_hex), headers=headers,
                                             ssl=False, timeout=aiohttp.ClientTimeout(total=10)) as r:
                        body = await r.text()
                        if r.status in (200, 201):
                            return True
                        if r.status == 400 and "already" in body.lower():
                            return True
                except Exception:
                    continue
    return False


async def main():
    parser = argparse.ArgumentParser(description="Import guest .dat files into the level bot")
    parser.add_argument("path", help="Path to .dat file, folder of .dat files, or a .zip")
    parser.add_argument("--clan", type=int, default=CLAN_ID, help="Clan ID to auto-join (default: configured clan)")
    args = parser.parse_args()

    dat_files = find_dat_files(args.path)
    if not dat_files:
        print(f"❌ No .dat files found in {args.path}")
        return

    print(f"Found {len(dat_files)} .dat file(s)")

    parsed = []
    for f in dat_files:
        g = parse_dat_file(f)
        if g:
            parsed.append(g)
            print(f"  📄 {os.path.basename(f)} -> uid={g['uid']}")

    if not parsed:
        print("❌ No valid guest data extracted")
        return

    print(f"\nTesting {len(parsed)} account(s)...\n")

    guests = []
    if os.path.exists(GUESTS_FILE):
        with open(GUESTS_FILE) as f:
            guests = json.load(f)

    added = 0
    for g in parsed:
        result = await check_and_import(g, args.clan)
        if result:
            guests = [x for x in guests if x["uid"] != result["uid"]]  # dedup
            guests.append(result)
            added += 1

    os.makedirs(os.path.dirname(GUESTS_FILE), exist_ok=True)
    with open(GUESTS_FILE, "w") as f:
        json.dump(guests, f, indent=2)

    print(f"\n{'='*50}")
    print(f"  Imported: {added}/{len(parsed)} account(s) alive & saved")
    print(f"  Total guests now: {len(guests)}")
    print(f"  Saved to: {GUESTS_FILE}")
    print(f"{'='*50}")


if __name__ == "__main__":
    asyncio.run(main())
