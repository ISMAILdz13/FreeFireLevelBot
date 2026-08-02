"""
Real Level Bot — BAAN-FIXED approach (proven working).

Based on BAAN_FIXED_LEVEL_UP_BOT's /lw farming logic:
  1. Login (OAuth V2 → V1 → MajorLogin → GetLoginData → get key/iv/token/ports)
  2. TCP connect to Online + Chat servers, send auth tokens
  3. AutH_GlobAl on chat channel
  4. Farming loop: join team → spam start(9) → wait → leave → repeat

Key differences from previous version:
  - Region-aware packet types (0514 IND, 0519 BD, 0515 default)
  - Start/leave packets use hardcoded room 12480598706 (proven to work)
  - Only field 1=9 for start (not 3-packet leader approach)
  - Spam delay 0.1s, wait 10s (matching BAAN bot's proven timings)
  - Content-Type: application/x-www-form-urlencoded for MajorLogin
  - No match-found detection needed — blind spam works

Usage:
  # From guests.json (uses stored open_id + access_token — skips OAuth):
  python3 level_bot_real.py --guests ../data/guests.json 1 <team_code>

  # From level_accounts.json (does OAuth with hex password):
  python3 level_bot_real.py --accounts ../data/level_accounts.json <uid> <team_code>

  # Direct uid + password:
  python3 level_bot_real.py <uid> <password> <team_code>

  Examples:
  python3 level_bot_real.py --guests ../data/guests.json 1 2781283
  python3 level_bot_real.py 4067187731 D9EA225CABFF4D2CDF3371300596E705C94677A17A3C5001AD01FFE2D4F5BAD4 2781283
"""

import asyncio
import aiohttp
import ssl
import time
import random
import os
import sys
import json
import hashlib
import hmac
from datetime import datetime

# ── Protobuf ──
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Pb2'))
import MajoRLoGinrEq_pb2
import MajoRLoGinrEs_pb2
import PorTs_pb2

# ── Crypto ──
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# ── Constants ──
DEFAULT_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
DEFAULT_IV  = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

# Garena OAuth constants
HEX_KEY = "32656534343831396539623435393838343531343130363762323831363231383734643064356437616639643866376530306331653534373135623764316533"
HMAC_KEY = bytes.fromhex(HEX_KEY)
G_CLIENT_SECRET = HMAC_KEY.decode("ascii")
G_CLIENT_ID = "100067"

OAUTH_V2_URL = "https://ffmconnect.live.gop.garenanow.com/api/v2/oauth/guest/token:grant"
OAUTH_V1_URL = "https://100067.connect.garena.com/oauth/guest/token/grant"
REGISTER_URL = "https://connect.garena.com/oauth/guest/register"

UA_REGISTER = "GarenaMSDK/4.0.19P10(I2404 ;Android 15;en;US;)"
UA_OAUTH_V2 = "GarenaMSDK/4.0.19P10(I2404 ;Android 15;en;US;)"
UA_OAUTH_V1 = "GarenaMSDK/4.0.19P8(ASUS_Z01QD ;Android 12;en;US;)"

# BAAN bot proven constants
LW_ROOM_ID = 12480598706  # Hardcoded Lone Wolf room ID — proven to work
START_SPAM_DURATION = 18   # seconds (BAAN: 18s)
START_SPAM_DELAY = 0.1     # seconds between packets (BAAN: 0.1s)
WAIT_AFTER_MATCH = 10      # seconds to wait after spam (BAAN: 10s)
CYCLE_DELAY = 2            # seconds between cycles

# HTTP headers — matching BAAN bot
HEADERS = {
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 11; ASUS_Z01QD Build/PI)',
    'Connection': 'Keep-Alive',
    'Accept-Encoding': 'gzip',
    'Content-Type': 'application/x-www-form-urlencoded',
    'Expect': '100-continue',
    'X-Unity-Version': '2018.4.11f1',
    'X-GA': 'v1 1',
    'ReleaseVersion': 'OB54',
}


# ════════════════════════════════════════════════════════
#  PACKET BUILDING (matching BAAN bot 1:1)
# ════════════════════════════════════════════════════════

async def EnC_PacKeT(HeX, K, V):
    """Encrypt packet with AES-CBC."""
    return AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(HeX), 16)).hex()

async def DEc_PacKeT(HeX, K, V):
    """Decrypt packet with AES-CBC."""
    return unpad(AES.new(K, AES.MODE_CBC, V).decrypt(bytes.fromhex(HeX)), 16).hex()

async def EnC_Vr(N):
    """Encode varint."""
    if N < 0:
        return b''
    H = []
    while True:
        BesTo = N & 0x7F
        N >>= 7
        if N:
            BesTo |= 0x80
        H.append(BesTo)
        if not N:
            break
    return bytes(H)

async def CrEaTe_VarianT(field_number, value):
    field_header = (field_number << 3) | 0
    return (await EnC_Vr(field_header)) + (await EnC_Vr(value))

async def CrEaTe_LenGTh(field_number, value):
    field_header = (field_number << 3) | 2
    encoded_value = value.encode() if isinstance(value, str) else value
    return (await EnC_Vr(field_header)) + (await EnC_Vr(len(encoded_value))) + encoded_value

async def CrEaTe_ProTo(fields):
    """Build protobuf from dict of fields."""
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested_packet = await CrEaTe_ProTo(value)
            packet.extend(await CrEaTe_LenGTh(field, nested_packet))
        elif isinstance(value, int):
            packet.extend(await CrEaTe_VarianT(field, value))
        elif isinstance(value, (str, bytes)):
            packet.extend(await CrEaTe_LenGTh(field, value))
    return bytes(packet)

async def DecodE_HeX(H):
    """Convert decimal to hex string, padded."""
    R = hex(H)
    F = str(R)[2:]
    if len(F) == 1:
        return "0" + F
    return F

async def GeneRaTePk(Pk, N, K, V):
    """Encrypt protobuf and build final packet with header.
    Pk = protobuf hex, N = packet type (e.g. '0515'), K/V = key/iv."""
    PkEnc = await EnC_PacKeT(Pk, K, V)
    _ = await DecodE_HeX(int(len(PkEnc) // 2))
    if len(_) == 2:    HeadEr = N + "000000"
    elif len(_) == 3:  HeadEr = N + "00000"
    elif len(_) == 4:  HeadEr = N + "0000"
    elif len(_) == 5:  HeadEr = N + "000"
    elif len(_) == 6:  HeadEr = N + "00"
    elif len(_) == 7:  HeadEr = N + "0"
    elif len(_) == 8:  HeadEr = N
    elif len(_) == 1:  HeadEr = N + "0000000"
    else:
        HeadEr = N + "000000"
    return bytes.fromhex(HeadEr + _ + PkEnc)


# ════════════════════════════════════════════════════════
#  GAME PACKETS (BAAN bot 1:1)
# ════════════════════════════════════════════════════════

def get_pkt_type(region):
    """Get packet type based on region — BAAN bot style."""
    r = region.lower() if region else "me"
    if r == "ind" or r == "in" or r == "india":
        return '0514'
    elif r == "bd" or r == "bangladesh":
        return '0519'
    else:
        return '0515'

async def join_teamcode_packet(team_code, key, iv, region="ME"):
    """Join team using code — BAAN bot's join_teamcode_packet."""
    fields = {
        1: 4,
        2: {
            4: bytes.fromhex("01090a0b121920"),
            5: str(team_code),
            6: 6,
            8: 1,
            9: {
                2: 800,
                6: 11,
                8: "1.111.1",
                9: 5,
                10: 1,
            },
        },
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), get_pkt_type(region), key, iv)

async def start_auto_packet(key, iv, region="ME"):
    """Start match — BAAN bot's start_auto_packet.
    Field 1=9, field 2={1: LW_ROOM_ID}."""
    fields = {
        1: 9,
        2: {
            1: LW_ROOM_ID,
        },
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), get_pkt_type(region), key, iv)

async def leave_squad_packet(key, iv, region="ME"):
    """Leave squad — BAAN bot's leave_squad_packet.
    Field 1=7, field 2={1: LW_ROOM_ID}."""
    fields = {
        1: 7,
        2: {
            1: LW_ROOM_ID,
        },
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), get_pkt_type(region), key, iv)

async def open_squad_packet(key, iv, region="ME"):
    """Open/create own squad — for solo farming."""
    fields = {
        1: 1,
        2: {
            2: "\u0001",
            3: 1,
            4: 1,
            5: "en",
            9: 1,
            11: 1,
            13: 1,
            14: {
                2: 5756,
                6: 11,
                8: "1.111.1",
                9: 2,
                10: 4,
            },
        },
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), get_pkt_type(region), key, iv)

async def auth_global_packet(key, iv):
    """AutH_GlobAl — required after TCP connect on chat channel."""
    fields = {1: 3, 2: {2: 5, 3: "en"}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '1215', key, iv)

async def keepalive_packet(key, iv, channel="online", region="ME"):
    """Keepalive — field 1=99."""
    fields = {1: 99, 2: {1: int(time.time()), 2: 1}}
    pkt_type = "1215" if channel == "chat" else get_pkt_type(region)
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), pkt_type, key, iv)


# ════════════════════════════════════════════════════════
#  AUTHENTICATION
# ════════════════════════════════════════════════════════

async def encrypted_proto(raw_bytes):
    """Encrypt MajorLogin protobuf with default key/iv."""
    cipher = AES.new(DEFAULT_KEY, AES.MODE_CBC, DEFAULT_IV)
    if isinstance(raw_bytes, str):
        raw_bytes = bytes.fromhex(raw_bytes)
    return cipher.encrypt(pad(raw_bytes, AES.block_size))

async def GeNeRaTeAccEss(uid, password):
    """Get open_id + access_token via OAuth. Tries V2 first, then V1."""
    # V2 (JSON body)
    v2_headers = {
        "Content-Type": "application/json; charset=utf-8",
        "User-Agent": UA_OAUTH_V2,
    }
    v2_data = {
        "client_id": int(G_CLIENT_ID),
        "client_secret": G_CLIENT_SECRET,
        "password": str(password),
        "client_type": 2,
        "response_type": "token",
        "uid": int(uid),
    }
    # V1 (form body)
    v1_headers = {
        "Host": "100067.connect.garena.com",
        "User-Agent": UA_OAUTH_V1,
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "close",
    }
    v1_data = {
        "uid": str(uid),
        "password": str(password),
        "response_type": "token",
        "client_type": "2",
        "client_secret": G_CLIENT_SECRET,
        "client_id": G_CLIENT_ID,
    }

    async with aiohttp.ClientSession() as session:
        # Try V2 first
        try:
            async with session.post(OAUTH_V2_URL, json=v2_data, headers=v2_headers, ssl=False) as r:
                if r.status == 200:
                    j = await r.json()
                    odata = j.get("data", j)
                    oid = odata.get("open_id")
                    tok = odata.get("access_token")
                    if oid and tok:
                        return oid, tok
        except Exception:
            pass

        # Try V1
        try:
            async with session.post(OAUTH_V1_URL, data=v1_data, headers=v1_headers) as r:
                if r.status == 200:
                    j = await r.json()
                    oid = j.get("open_id")
                    tok = j.get("access_token")
                    if oid and tok:
                        return oid, tok
        except Exception:
            pass

    return None, None


async def EncRypTMajoRLoGin(open_id, access_token):
    """Build MajorLogin protobuf and encrypt it."""
    major_login = MajoRLoGinrEq_pb2.MajorLogin()
    major_login.event_time = str(datetime.now())[:-7]
    major_login.game_name = "free fire"
    major_login.platform_id = 1
    major_login.client_version = "1.126.9"
    major_login.client_version_code = "2019120816"
    major_login.system_software = "Android OS 13 / API-33 (TP1A.220905.001/R.206769c-2)"
    major_login.system_hardware = "Handheld"
    major_login.telecom_operator = "45403"
    major_login.network_operator_a = "45403"
    major_login.network_type = "WIFI"
    major_login.network_type_a = "WIFI"
    major_login.screen_width = 1280
    major_login.screen_height = 720
    major_login.screen_dpi = "320"
    major_login.processor_details = "ARM64 FP ASIMD AES | 2352 | 8"
    major_login.memory = 128
    major_login.gpu_renderer = "Mali-G610"
    major_login.gpu_version = "OpenGL ES 3.2 v1.g18p0-01eac0.2d5e200a1514bdef1a4909db66e37e28"
    major_login.graphics_api = "OpenGLES2"
    major_login.unique_device_id = "Google|7a9732a4-2549-4edc-840e-d61263d128f5"
    major_login.client_ip = ""
    major_login.language = "en"
    major_login.open_id = open_id
    major_login.open_id_type = "4"
    major_login.login_open_id_type = 4
    major_login.device_type = "Handheld"
    major_login.device_model = "OPPO CPH2217"
    major_login.access_token = access_token
    major_login.login_by = 3
    major_login.platform_sdk_id = 1
    major_login.origin_platform_type = "4"
    major_login.primary_platform_type = "4"
    major_login.cpu_type = 2
    major_login.cpu_architecture = "64"
    major_login.client_using_version = "1ac4b80ecf0478a44203bf8fac6120f5"
    major_login.supported_astc_bitset = 16383
    major_login.analytics_detail = b"FwQVTgUPX1UaUllDDwcWCRBpWA0FUgsvA1snWlBaO1kFYg=="
    major_login.loading_time = random.randint(9000, 25000)
    major_login.release_channel = "3rd_party"
    major_login.channel_type = 6
    major_login.reg_avatar = 1
    major_login.if_push = 1
    major_login.is_vpn = 1
    major_login.android_engine_init_flag = 110009
    major_login.external_storage_total = 20660
    major_login.external_storage_available = 17445
    major_login.internal_storage_total = 2663
    major_login.internal_storage_available = 1500
    major_login.game_disk_storage_available = 17573
    major_login.game_disk_storage_total = 20660
    major_login.external_sdcard_avail_storage = 17573
    major_login.external_sdcard_total_storage = 20660
    major_login.library_path = "/data/app/~~xHaSHUdUBlxvhJaRWh018A==/com.dts.freefireth-4OBn7-sLMoPuswIfmgixhA==/lib/arm64"
    major_login.library_token = "4c322aeb56444feaa151d1ea91a8f7f2|/data/app/~~xHaSHUdUBlxvhJaRWh018A==/com.dts.freefireth-4OBn7-sLMoPuswIfmgixhA==/base.apk"
    major_login.extra_info = "KqsHTz+zAigQ0BOzKhQHN8ae/IefLXcroDjaj4QY+OF71nTuiQh+myDUqCZFPJQ5gyC9LfEeKoon9d461764VIGguRHcIyKfExGAh4bvxFZRgp2t"
    major_login.extra_json = '{"cur_rate":null,"support_etc2":false}'
    string = major_login.SerializeToString()
    return await encrypted_proto(string)


async def MajorLogin(payload):
    """Send MajorLogin request — tries all endpoints."""
    urls = [
        "https://loginbp.ggpolarbear.com/MajorLogin",
        "https://loginbp.ggwhitehawk.com/MajorLogin",
        "https://loginbp.ggblueshark.com/MajorLogin",
    ]
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    async with aiohttp.ClientSession() as session:
        for url in urls:
            try:
                async with session.post(url, data=payload, headers=HEADERS, ssl=ssl_context) as response:
                    if response.status == 200:
                        data = await response.read()
                        if len(data) > 50:
                            return data
            except Exception:
                continue
    return None


async def GetLoginData(base_url, payload, token):
    """Get login data (ports, server info)."""
    url = f"{base_url}/GetLoginData"
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    headers = dict(HEADERS)
    headers['Authorization'] = f"Bearer {token}"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=payload, headers=headers, ssl=ssl_context) as response:
            if response.status == 200:
                return await response.read()
            return None


async def DecRypTMajoRLoGin(response_bytes):
    """Decrypt MajorLogin response."""
    proto = MajoRLoGinrEs_pb2.MajorLoginRes()
    proto.ParseFromString(response_bytes)
    return proto


async def DecRypTLoGinDaTa(data_bytes):
    """Decrypt GetLoginData response."""
    proto = PorTs_pb2.GetLoginData()
    proto.ParseFromString(data_bytes)
    return proto


async def xAuThSTarTuP(account_uid, token, timestamp, key, iv):
    """Build TCP auth token — BAAN bot's xAuThSTarTuP."""
    uid_hex = hex(int(account_uid))[2:]
    uid_length = len(uid_hex)
    encrypted_timestamp = await DecodE_HeX(int(timestamp))
    encrypted_account_token = token.encode().hex()
    encrypted_packet = await EnC_PacKeT(encrypted_account_token, key, iv)
    encrypted_packet_length = hex(len(encrypted_packet) // 2)[2:]

    if uid_length == 9:      headers = '0000000'
    elif uid_length == 8:    headers = '00000000'
    elif uid_length == 10:   headers = '000000'
    elif uid_length == 7:    headers = '000000000'
    else:                    headers = '0000000'

    return f"0115{headers}{uid_hex}{encrypted_timestamp}00000{encrypted_packet_length}{encrypted_packet}"


# ════════════════════════════════════════════════════════
#  ACCOUNT LOADING
# ════════════════════════════════════════════════════════

def load_from_guests(path, index):
    """Load guest from guests.json by 1-based index."""
    with open(path) as f:
        guests = json.load(f)
    idx = int(index) - 1 if int(index) >= 1 else int(index)
    g = guests[idx]
    return {
        "uid": str(g["uid"]),
        "password": g.get("password", ""),
        "open_id": g.get("open_id"),
        "access_token": g.get("access_token"),
        "region": g.get("region", "ME"),
    }

def load_from_accounts(path, uid):
    """Load from level_accounts.json — maps uid → hex password."""
    with open(path) as f:
        accounts = json.load(f)
    if uid not in accounts:
        print(f"❌ UID {uid} not found in {path}")
        print(f"   Available: {list(accounts.keys())}")
        sys.exit(1)
    return {
        "uid": str(uid),
        "password": accounts[uid],
        "open_id": None,
        "access_token": None,
        "region": "ME",
    }


# ════════════════════════════════════════════════════════
#  FARMING LOOP (BAAN bot's auto_start_loop 1:1)
# ════════════════════════════════════════════════════════

async def auto_start_loop(team_code, online_writer, chat_writer, key, iv,
                           account_uid=None, region="ME", max_cycles=100000):
    """BAAN bot farming loop: join → spam start(9) → wait → leave → repeat.

    This is the proven working approach from BAAN_FIXED_LEVEL_UP_BOT:
    - join_teamcode_packet (field 1=4)
    - spam start_auto_packet (field 1=9, room 12480598706) for 18s
    - wait 10s for match
    - leave_squad_packet (field 1=7, room 12480598706)
    - repeat 24/7
    """
    cycle_count = 0
    stop = False

    print(f"\n🚀 Auto Start Loop — BAAN MODE")
    print(f"⚡ Join → Spam(9, {START_SPAM_DURATION}s, {START_SPAM_DELAY}s delay) → Wait({WAIT_AFTER_MATCH}s) → Leave → Repeat")
    print(f"🎯 Room ID: {LW_ROOM_ID}")
    print(f"🌍 Region: {region} (pkt type: {get_pkt_type(region)})\n")

    # Pre-build packets
    join_pkt = await join_teamcode_packet(team_code, key, iv, region)
    start_pkt = await start_auto_packet(key, iv, region)
    leave_pkt = await leave_squad_packet(key, iv, region)

    # Background keepalive (every 15s)
    ka_stop = False

    async def keepalive_loop():
        while not ka_stop:
            try:
                ka_online = await keepalive_packet(key, iv, "online", region)
                ka_chat = await keepalive_packet(key, iv, "chat", region)
                if online_writer and not online_writer.is_closing():
                    online_writer.write(ka_online)
                    await online_writer.drain()
                if chat_writer and not chat_writer.is_closing():
                    chat_writer.write(ka_chat)
                    await chat_writer.drain()
            except Exception:
                pass
            await asyncio.sleep(15)

    ka_task = asyncio.create_task(keepalive_loop())

    while cycle_count < max_cycles and not stop:
        try:
            cycle_count += 1
            print(f"\n🔄 Cycle #{cycle_count}")

            # Step 1: Join team
            print(f"  → Joining team {team_code}...")
            try:
                online_writer.write(join_pkt)
                await online_writer.drain()
            except Exception as e:
                print(f"  ⚠️ Join send error: {e}")
            await asyncio.sleep(2)

            # Step 2: Spam start packet
            print(f"  → Spamming start ({START_SPAM_DURATION}s, delay {START_SPAM_DELAY}s)...")
            end_time = time.time() + START_SPAM_DURATION
            spam_count = 0
            while time.time() < end_time:
                try:
                    online_writer.write(start_pkt)
                    await online_writer.drain()
                    spam_count += 1
                    await asyncio.sleep(START_SPAM_DELAY)
                except Exception as e:
                    print(f"  ⚠️ Spam send error: {e}")
                    break
            print(f"  📮 Sent {spam_count} start packets")

            # Step 3: Wait for match
            print(f"  ⏳ Waiting {WAIT_AFTER_MATCH}s...")
            for _ in range(WAIT_AFTER_MATCH):
                await asyncio.sleep(1)

            # Step 4: Leave squad
            print(f"  🚪 Leaving squad...")
            try:
                online_writer.write(leave_pkt)
                await online_writer.drain()
            except Exception:
                pass

            await asyncio.sleep(CYCLE_DELAY)
            print(f"  ✅ Cycle {cycle_count} done")

        except Exception as e:
            print(f"  ❌ Error in cycle #{cycle_count}: {e}")
            await asyncio.sleep(3)

    ka_stop = True
    ka_task.cancel()


# ════════════════════════════════════════════════════════
#  READER (background TCP reader — logs incoming packets)
# ════════════════════════════════════════════════════════

async def read_packets(reader, label, key, iv):
    """Background reader — just logs packet sizes for debugging."""
    while True:
        try:
            data = await reader.read(9999)
            if not data:
                print(f"  [{label}] Connection closed")
                break
            # Just log size — we don't need to parse for the BAAN approach
            hex_data = data.hex()
            if len(hex_data) > 100:
                print(f"  [{label}] Received {len(data)} bytes (f2={hex_data[2:4] if len(hex_data)>4 else '?'})")
        except Exception as e:
            print(f"  [{label}] Reader error: {e}")
            break


# ════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════

async def main():
    args = sys.argv[1:]

    if len(args) >= 1 and args[0] == '--guests':
        if len(args) < 4:
            print("Usage: python3 level_bot_real.py --guests <path> <index> <team_code>")
            sys.exit(1)
        cred = load_from_guests(args[1], args[2])
        team_code = args[3]
        use_stored_tokens = bool(cred["open_id"] and cred["access_token"])

    elif len(args) >= 1 and args[0] == '--accounts':
        if len(args) < 4:
            print("Usage: python3 level_bot_real.py --accounts <path> <uid> <team_code>")
            sys.exit(1)
        cred = load_from_accounts(args[1], args[2])
        team_code = args[3]
        use_stored_tokens = False

    else:
        if len(args) < 3:
            print("Usage:")
            print("  python3 level_bot_real.py --guests <path> <index> <team_code>")
            print("  python3 level_bot_real.py --accounts <path> <uid> <team_code>")
            print("  python3 level_bot_real.py <uid> <password> <team_code>")
            sys.exit(1)
        cred = {"uid": args[0], "password": args[1], "open_id": None, "access_token": None, "region": "ME"}
        team_code = args[2]
        use_stored_tokens = False

    uid = cred["uid"]
    region = cred.get("region", "ME")

    print("=" * 55)
    print("  REAL LEVEL BOT — BAAN FIXED MODE")
    print("=" * 55)
    print(f"  UID:       {uid}")
    print(f"  Team:      {team_code}")
    print(f"  Auth:      {'stored tokens' if use_stored_tokens else 'OAuth'}")
    print(f"  Spam:      {START_SPAM_DURATION}s (delay {START_SPAM_DELAY}s)")
    print(f"  Wait:      {WAIT_AFTER_MATCH}s")
    print(f"  Room:      {LW_ROOM_ID}")
    print(f"  Region:    {region} (pkt: {get_pkt_type(region)})")
    print("=" * 55)

    # ── Step 1: Login ──
    open_id = None
    access_token = None
    login_response = None
    payload = None

    if use_stored_tokens:
        print(f"\n📡 Step 1: Using stored tokens...")
        open_id = cred["open_id"]
        access_token = cred["access_token"]
        payload = await EncRypTMajoRLoGin(open_id, access_token)
        login_response = await MajorLogin(payload)
        if login_response:
            print(f"  ✅ MajorLogin: {len(login_response)} bytes")

    if not login_response and cred.get("password"):
        print(f"\n📡 Step 1b: OAuth...")
        open_id, access_token = await GeNeRaTeAccEss(uid, cred["password"])
        if open_id:
            print(f"  ✅ OAuth OK")
            payload = await EncRypTMajoRLoGin(open_id, access_token)
            login_response = await MajorLogin(payload)
            if login_response:
                print(f"  ✅ MajorLogin: {len(login_response)} bytes")

    if not login_response:
        print("\n❌ All login attempts failed. Account may be banned.")
        return

    # ── Step 2: Decrypt ──
    print("\n📡 Step 2: Decrypting...")
    auth = await DecRypTMajoRLoGin(login_response)
    account_uid = auth.account_uid
    token = auth.token
    url = auth.url
    key = auth.key
    iv = auth.iv
    timestamp = auth.timestamp

    # Use region from auth if available
    if hasattr(auth, 'region') and auth.region:
        region = auth.region
    print(f"  ✅ uid={account_uid}, key={key.hex()[:16]}...")
    print(f"  ✅ server={url}, region={region}")

    # ── Step 3: GetLoginData ──
    print("\n📡 Step 3: GetLoginData...")
    login_data = await GetLoginData(url, payload, token)
    if not login_data:
        print("❌ GetLoginData failed")
        return
    login_data_dec = await DecRypTLoGinDaTa(login_data)
    online_ip, online_port = login_data_dec.Online_IP_Port.split(":")
    chat_ip, chat_port = login_data_dec.AccountIP_Port.split(":")
    acc_name = login_data_dec.AccountName
    print(f"  ✅ Online: {online_ip}:{online_port}")
    print(f"  ✅ Chat:   {chat_ip}:{chat_port}")
    print(f"  ✅ Name:   {acc_name}")

    # ── Step 4: TCP auth token ──
    print("\n📡 Step 4: Building TCP auth token...")
    auth_token = await xAuThSTarTuP(int(account_uid), token, int(timestamp), key, iv)
    auth_bytes = bytes.fromhex(auth_token)
    print(f"  ✅ Token: {len(auth_bytes)} bytes")

    # ── Step 5: TCP connect ──
    import socket as _socket

    print(f"\n📡 Step 5: Connecting Online {online_ip}:{online_port}...")
    try:
        online_reader, online_writer = await asyncio.open_connection(online_ip, int(online_port))
    except Exception as e:
        print(f"❌ Online TCP failed: {e}")
        return
    print(f"  ✅ Online connected!")

    print(f"📡 Step 5b: Connecting Chat {chat_ip}:{chat_port}...")
    try:
        chat_reader, chat_writer = await asyncio.open_connection(chat_ip, int(chat_port))
    except Exception as e:
        print(f"❌ Chat TCP failed: {e}")
        return
    print(f"  ✅ Chat connected!")

    # OS-level TCP keepalive
    for w in [online_writer, chat_writer]:
        sock = w.get_extra_info('socket')
        if sock:
            sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_KEEPALIVE, 1)

    # ── Step 6: Auth ──
    print("\n📡 Step 6: Sending auth tokens...")
    online_writer.write(auth_bytes)
    await online_writer.drain()
    chat_writer.write(auth_bytes)
    await chat_writer.drain()
    print(f"  ✅ Auth sent to both ({len(auth_bytes)} bytes each)")
    await asyncio.sleep(1)

    # AutH_GlobAl on chat channel
    print("📡 Step 6b: AutH_GlobAl on chat...")
    global_pkt = await auth_global_packet(key, iv)
    chat_writer.write(global_pkt)
    await chat_writer.drain()
    print(f"  ✅ AutH_GlobAl sent ({len(global_pkt)} bytes)")
    await asyncio.sleep(0.5)

    # ── Start farming ──
    print(f"\n🚀 Starting BAAN-mode level bot...\n")

    online_reader_task = asyncio.create_task(read_packets(online_reader, "ONLINE", key, iv))
    chat_reader_task = asyncio.create_task(read_packets(chat_reader, "CHAT", key, iv))
    loop_task = asyncio.create_task(
        auto_start_loop(team_code, online_writer, chat_writer, key, iv,
                        account_uid=account_uid, region=region)
    )

    try:
        await loop_task
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
    finally:
        online_reader_task.cancel()
        chat_reader_task.cancel()
        online_writer.close()
        chat_writer.close()
        await online_writer.wait_closed()
        await chat_writer.wait_closed()
        print("✅ Disconnected")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")
