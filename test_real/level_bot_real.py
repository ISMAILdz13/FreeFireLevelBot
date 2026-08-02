"""
Real Level Bot — 1:1 extraction from OB54-TCP-BOT.
Standalone test file — no dependencies on the level-bot package.

Flow:
  1. Login (OAuth → MajorLogin → GetLoginData → get key/iv/token/ports)
  2. TCP connect to Online server + send auth token
  3. auto_start_loop: join team → spam start → wait → leave → repeat

Usage:
  # From guests.json (uses stored open_id + access_token — skips OAuth):
  python3 level_bot_real.py --guests ../data/guests.json 1 <team_code>

  # From level_accounts.json (does OAuth with hex password):
  python3 level_bot_real.py --accounts ../data/level_accounts.json 5822030305 <team_code>

  # Direct uid + password:
  python3 level_bot_real.py <uid> <password> <team_code>

  Examples:
  python3 level_bot_real.py --guests ../data/guests.json 1 2781283
  python3 level_bot_real.py --accounts ../data/level_accounts.json 5822030305 2781283
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

# ── HTTP headers (OB54) ──
HEADERS = {
    'X-Unity-Version': '2018.4.11f1',
    'ReleaseVersion': 'OB54',
    'Content-Type': 'application/octet-stream',
    'X-GA': 'v1 1',
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 11; SM-A145F Build/RP1A.200720.012)',
    'Connection': 'Keep-Alive',
    'Accept-Encoding': 'gzip',
    'Expect': '100-continue',
}

# ── Timing (from OB54-TCP-BOT globals) ──
START_SPAM_DURATION = 17
START_SPAM_DELAY    = 0.2
WAIT_AFTER_MATCH    = 20
JOIN_DELAY          = 2.0
LEAVE_DELAY         = 2.0
CYCLE_DELAY         = 2.0

# ── Garena guest registration constants ──
HEX_KEY = "32656534343831396539623435393838343531343130363762323831363231383734643064356437616639643866376530306331653534373135623764316533"
HMAC_KEY = bytes.fromhex(HEX_KEY)
G_CLIENT_SECRET = HMAC_KEY.decode("ascii")
G_CLIENT_ID = "100067"
REGISTER_URL = "https://connect.garena.com/oauth/guest/register"
OAUTH_V2_URL = "https://ffmconnect.live.gop.garenanow.com/api/v2/oauth/guest/token:grant"
OAUTH_V1_URL = "https://100067.connect.garena.com/oauth/guest/token/grant"
UA_REGISTER = "GarenaMSDK/4.0.19P10(I2404 ;Android 15;en;US;)"
UA_OAUTH_V2 = "GarenaMSDK/4.0.19P10(I2404 ;Android 15;en;US;)"
UA_OAUTH_V1 = "GarenaMSDK/4.0.19P8(ASUS_Z01QD ;Android 12;en;US;)"


# ═══════════════════════════════════════════════════════════════
#  xC4.py — Packet building & encryption (1:1 copy)
# ═══════════════════════════════════════════════════════════════

async def EnC_PacKeT(HeX, K, V):
    return AES.new(K, AES.MODE_CBC, V).encrypt(pad(bytes.fromhex(HeX), 16)).hex()

async def DEc_PacKeT(HeX, K, V):
    return unpad(AES.new(K, AES.MODE_CBC, V).decrypt(bytes.fromhex(HeX)), 16).hex()

async def EnC_Vr(N):
    if N < 0:
        return b""
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
    return await EnC_Vr(field_header) + await EnC_Vr(value)

async def CrEaTe_LenGTh(field_number, value):
    field_header = (field_number << 3) | 2
    encoded_value = value.encode() if isinstance(value, str) else value
    return await EnC_Vr(field_header) + await EnC_Vr(len(encoded_value)) + encoded_value

async def CrEaTe_ProTo(fields):
    packet = bytearray()
    for field, value in fields.items():
        if isinstance(value, dict):
            nested_packet = await CrEaTe_ProTo(value)
            packet.extend(await CrEaTe_LenGTh(field, nested_packet))
        elif isinstance(value, int):
            packet.extend(await CrEaTe_VarianT(field, value))
        elif isinstance(value, str) or isinstance(value, bytes):
            packet.extend(await CrEaTe_LenGTh(field, value))
    return packet

async def DecodE_HeX(H):
    R = hex(H)
    F = str(R)[2:]
    if len(F) == 1:
        F = "0" + F
    return F

async def GeneRaTePk(Pk, N, K, V):
    """Encrypt protobuf and build final packet with header."""
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
        print(f'ErroR => GeneRatinG ThE PacKeT len={len(_)} !!')
        HeadEr = N + "000000"
    return bytes.fromhex(HeadEr + _ + PkEnc)

async def encrypted_proto(encoded_hex):
    """Encrypt MajorLogin protobuf with default key/iv."""
    key = DEFAULT_KEY
    iv = DEFAULT_IV
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded_message = pad(encoded_hex, AES.block_size)
    return cipher.encrypt(padded_message)


# ═══════════════════════════════════════════════════════════════
#  Auth flow — GeNeRaTeAccEss, MajorLogin, GetLoginData (1:1 copy)
# ═══════════════════════════════════════════════════════════════

async def GeNeRaTeAccEss(uid, password):
    """Get OAuth access token from Garena — tries V2 then V1."""
    # V2 endpoint (JSON body)
    v2_headers = {"Content-Type": "application/json; charset=utf-8", "User-Agent": UA_OAUTH_V2}
    v2_data = {
        "client_id": int(G_CLIENT_ID),
        "client_secret": G_CLIENT_SECRET,
        "password": str(password),
        "client_type": 2,
        "response_type": "token",
        "uid": int(uid),
    }
    # V1 endpoint (form body)
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
        "client_secret": "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3",
        "client_id": G_CLIENT_ID,
    }

    async with aiohttp.ClientSession() as session:
        # Try V2 first
        try:
            print(f"  Trying OAuth V2 ({OAUTH_V2_URL})...")
            async with session.post(OAUTH_V2_URL, json=v2_data, headers=v2_headers, ssl=False) as r:
                print(f"  → V2: {r.status}")
                if r.status == 200:
                    j = await r.json()
                    odata = j.get("data", j)
                    oid = odata.get("open_id")
                    tok = odata.get("access_token")
                    if oid and tok:
                        print(f"  ✅ V2 success!")
                        return oid, tok
        except Exception as e:
            print(f"  → V2 error: {e}")

        # Try V1
        try:
            print(f"  Trying OAuth V1 ({OAUTH_V1_URL})...")
            async with session.post(OAUTH_V1_URL, data=v1_data, headers=v1_headers) as r:
                print(f"  → V1: {r.status}")
                if r.status == 200:
                    j = await r.json()
                    oid = j.get("open_id")
                    tok = j.get("access_token")
                    if oid and tok:
                        print(f"  ✅ V1 success!")
                        return oid, tok
                else:
                    body = await r.text()
                    print(f"  → V1 body: {body[:200]}")
        except Exception as e:
            print(f"  → V1 error: {e}")

    return None, None


async def register_new_guest():
    """Register a brand new guest account with Garena."""
    password = ''.join(random.choices('0123456789abcdef', k=32))
    sig = hmac.new(HMAC_KEY, password.encode(), hashlib.sha1).hexdigest()

    print("  Registering new guest with Garena...")
    headers = {
        "Authorization": f"Signature {sig}",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": UA_REGISTER,
        "Accept-Encoding": "gzip",
        "Connection": "Keep-Alive",
    }
    data = {
        "password": password,
        "client_id": G_CLIENT_ID,
        "client_type": "2",
        "response_type": "token",
        "signature": sig,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(REGISTER_URL, data=data, headers=headers, ssl=False) as r:
            print(f"  Register: {r.status}")
            if r.status != 200:
                body = await r.text()
                print(f"  Register body: {body[:200]}")
                return None, None
            j = await r.json()
            uid = j.get("uid")
            if not uid:
                print(f"  No UID in response: {j}")
                return None, None
            print(f"  ✅ Got UID: {uid}")

    # Get OAuth tokens for the new account
    open_id, access_token = await GeNeRaTeAccEss(uid, password)
    if not open_id:
        print("  ⚠️ OAuth failed for new account")
        return str(uid), password, None, None
    return str(uid), password, open_id, access_token

async def EncRypTMajoRLoGin(open_id, access_token):
    """Build MajorLogin protobuf and encrypt it."""
    major_login = MajoRLoGinrEq_pb2.MajorLogin()
    major_login.event_time = str(datetime.now())[:-7]
    major_login.game_name = "free fire"
    major_login.platform_id = 2
    major_login.client_version = "1.126.2"
    major_login.client_version_code = "2024010012"
    major_login.system_software = "Android OS 11 / API-30 (RQ3A.210805.001)"
    major_login.system_hardware = "Handheld"
    major_login.device_type = "Handheld"
    major_login.telecom_operator = "Verizon"
    major_login.network_operator_a = "Verizon"
    major_login.network_type = "WIFI"
    major_login.network_type_a = "WIFI"
    major_login.screen_width = 1080
    major_login.screen_height = 2400
    major_login.screen_dpi = "440"
    major_login.processor_details = "ARMv8"
    major_login.cpu_type = 2
    major_login.cpu_architecture = "64"
    major_login.memory = 6144
    major_login.gpu_renderer = "Adreno (TM) 650"
    major_login.gpu_version = "OpenGL ES 3.2 V@1.50"
    major_login.graphics_api = "OpenGLES3"
    major_login.unique_device_id = "Google|34a7dcdf-a7d5-4cb6-8d7e-3b0e448a0c57"
    major_login.client_ip = ""
    major_login.language = "en"
    major_login.open_id = open_id
    major_login.open_id_type = "4"
    major_login.login_open_id_type = 4
    major_login.access_token = access_token
    major_login.login_by = 3
    major_login.platform_sdk_id = 2
    major_login.origin_platform_type = "4"
    major_login.primary_platform_type = "4"
    memory_available = major_login.memory_available
    memory_available.version = 55
    memory_available.hidden_value = 81
    major_login.external_storage_total = 128512
    major_login.external_storage_available = random.randint(38000, 52000)
    major_login.internal_storage_total = 110731
    major_login.internal_storage_available = random.randint(18000, 32000)
    major_login.game_disk_storage_total = 26628
    major_login.game_disk_storage_available = random.randint(18000, 25000)
    major_login.external_sdcard_total_storage = 119234
    major_login.external_sdcard_avail_storage = random.randint(25000, 60000)
    major_login.library_path = "/data/app/~~random/base.apk"
    major_login.library_token = "hash|base.apk"
    major_login.client_using_version = "7428b253defc164018c604a1ebbfebdf"
    major_login.supported_astc_bitset = 16383
    major_login.analytics_detail = b"FwQVTgUPX1UaUllDDwcWCRBpWAUOUgsvA1snWlBaO1kFYg=="
    major_login.loading_time = random.randint(9000, 18000)
    major_login.release_channel = "android"
    major_login.channel_type = 3
    major_login.reg_avatar = 1
    major_login.if_push = 1
    major_login.is_vpn = 0
    major_login.android_engine_init_flag = 110009
    string = major_login.SerializeToString()
    return await encrypted_proto(string)

async def MajorLogin(payload):
    """Send MajorLogin request — tries all 3 endpoints."""
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
                print(f"  Trying {url}...")
                async with session.post(url, data=payload, headers=HEADERS, ssl=ssl_context) as response:
                    body = await response.read()
                    print(f"  → {response.status}, {len(body)} bytes")
                    if response.status == 200 and len(body) > 30:
                        return body
                    elif response.status == 200:
                        print(f"  ⚠️ 200 but only {len(body)} bytes — rejection")
            except Exception as e:
                print(f"  → Error: {e}")
    return None

async def GetLoginData(base_url, payload, token):
    """Get server IPs and ports."""
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
            print(f"❌ GetLoginData failed: {response.status}")
            return None

async def DecRypTMajoRLoGin(MajoRLoGinResPonsE):
    proto = MajoRLoGinrEs_pb2.MajorLoginRes()
    proto.ParseFromString(MajoRLoGinResPonsE)
    return proto

async def DecRypTLoGinDaTa(LoGinDaTa):
    proto = PorTs_pb2.GetLoginData()
    proto.ParseFromString(LoGinDaTa)
    return proto


# ═══════════════════════════════════════════════════════════════
#  TCP auth startup (1:1 copy)
# ═══════════════════════════════════════════════════════════════

async def xAuThSTarTuP(TarGeT, token, timestamp, key, iv):
    """Build auth token for TCP connection."""
    uid_hex = hex(TarGeT)[2:]
    uid_length = len(uid_hex)
    encrypted_timestamp = await DecodE_HeX(timestamp)
    encrypted_account_token = token.encode().hex()
    encrypted_packet = await EnC_PacKeT(encrypted_account_token, key, iv)
    encrypted_packet_length = hex(len(encrypted_packet) // 2)[2:]
    if uid_length == 9:       headers = '0000000'
    elif uid_length == 8:     headers = '00000000'
    elif uid_length == 10:    headers = '000000'
    elif uid_length == 7:     headers = '000000000'
    else:                    headers = '0000000'
    return f"0115{headers}{uid_hex}{encrypted_timestamp}00000{encrypted_packet_length}{encrypted_packet}"


# ═══════════════════════════════════════════════════════════════
#  Level bot packets (ClanGloryBot 1:1)
# ═══════════════════════════════════════════════════════════════

async def join_teamcode_packet(team_code, key, iv):
    """Join team using code — GenJoinSquadsPacket from xC4.py."""
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
                8: "1.126.2",
                9: 5,
                10: 1,
            },
        },
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', key, iv)

async def open_squad_packet(key, iv):
    """Open/create own squad — OpEnSq from xC4.py."""
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
                8: "1.126.2",
                9: 2,
                10: 4,
            },
        },
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', key, iv)


async def start_match_leader_packet(account_uid, key, iv):
    """Send 3 start-match packets like ClanGloryBot start_match_leader:
    1. Field 269 (detailed start with device info) — match trigger
    2. Field 214 (simple start)
    3. Field 9 (ready signal with account_uid)
    Returns list of 3 packets."""
    pkt_type = '0515'

    # 1. Detailed start with device info (field 1=269)
    fields_detailed = {
        1: 269,
        2: {
            1: 8, 2: 8, 3: 11, 4: 1,
            5: "samsung", 6: "SM-A145F", 7: "arm64-v8a",
            8: "f538dc9b-cec9-43cd-8125-95f7f4f1f7e3",
            9: "FFD58FB4F76F648C2A5E21EBCFA3AAE81B4C9B7D97",
            10: "voice", 11: "V2059", 12: "mt6785",
            13: "AFFD58FB4F76F648C2A5E21EBCFA3AAE81B4C9B7D97",
            14: "ME_1999120752610979840",
            15: 269
        }
    }
    pkt_269 = await GeneRaTePk((await CrEaTe_ProTo(fields_detailed)).hex(), pkt_type, key, iv)

    # 2. Simple start (field 1=214)
    fields_214 = {1: 214, 2: {1: 1}}
    pkt_214 = await GeneRaTePk((await CrEaTe_ProTo(fields_214)).hex(), pkt_type, key, iv)

    # 3. Ready signal (field 1=9) with ACCOUNT UID
    fields_9 = {1: 9, 2: {1: int(account_uid)}}
    pkt_9 = await GeneRaTePk((await CrEaTe_ProTo(fields_9)).hex(), pkt_type, key, iv)

    return [pkt_269, pkt_214, pkt_9]


async def spam_ready_packet(account_uid, key, iv):
    """Build the spam packet: field 1=9, field 2={1: account_uid}."""
    fields = {1: 9, 2: {1: int(account_uid)}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', key, iv)


async def leave_squad_packet(account_uid, key, iv):
    """Leave squad — field 1=7, field 2={1: account_uid}."""
    fields = {1: 7, 2: {1: int(account_uid)}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', key, iv)


async def auth_global_packet(key, iv):
    """AutH_GlobAl — required after TCP connect. Sent on CHAT channel.
    Field 1=3, field 2={2: 5, 3: 'en'}, packet type 1215."""
    fields = {1: 3, 2: {2: 5, 3: "en"}}
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '1215', key, iv)


async def keepalive_packet(key, iv, channel="online"):
    """Keepalive — field 1=99, field 2={1: timestamp, 2: 1}.
    Online channel uses 0515, Chat channel uses 1215."""
    fields = {1: 99, 2: {1: int(time.time()), 2: 1}}
    pkt_type = "1215" if channel == "chat" else "0515"
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), pkt_type, key, iv)




async def join_match_packet(group_id, key, iv, region="ME"):
    """Join match room — field 1=3, packet type 0e15 (online channel).
    Based on ClanGloryBot join_match."""
    fields = {
        1: 3,
        2: {
            1: int(group_id),
            2: "",
            8: {1: "IDC3", 2: 149, 3: region},
            9: b"\x01\x03\x04\x07\x09\x0a\x0b\x12\x0e\x16\x19\x20\x1d",
            10: 1,
            12: {},
            13: 1,
            14: 1,
            16: "en",
            22: {1: 21},
        }
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0e15', key, iv)


async def join_match_chat_packet(group_id, key, iv):
    """Join match on chat channel — field 1=3, packet type 1215."""
    fields = {
        1: 3,
        2: {
            1: int(group_id),
            2: 3,
            3: "en",
        }
    }
    chat_proto = await CrEaTe_ProTo(fields)
    chat_hex = chat_proto.hex() + "7200"
    return await GeneRaTePk(chat_hex, '1215', key, iv)


# ═══════════════════════════════════════════════════════════════
#  auto_start_loop — SOLO MODE (ClanGloryBot solo_cycle 1:1)
# ═══════════════════════════════════════════════════════════════

async def auto_start_loop(team_code, online_writer, chat_writer, key, iv,
                           account_uid=None,
                           spam_duration=START_SPAM_DURATION,
                           spam_delay=START_SPAM_DELAY,
                           wait_after_match=WAIT_AFTER_MATCH,
                           max_cycles=1000):
    """Solo farming: start_match_leader (3 pkts) + spam ready + keepalive."""

    cycle_count = 0

    print(f"\n🚀 Auto start loop — SOLO MODE (ClanGloryBot style)")
    print(f"⚡ Start(269+214+9) → Spam(9) → Wait({wait_after_match}s) → Repeat\n")

    # Pre-build packets
    leader_pkts = await start_match_leader_packet(account_uid, key, iv)
    spam_pkt = await spam_ready_packet(account_uid, key, iv)
    leave_pkt = await leave_squad_packet(account_uid, key, iv)

    # Keepalive
    ka_stop = False

    async def keepalive_loop():
        """Background keepalive every 15s on both channels."""
        while not ka_stop:
            try:
                ka_online = await keepalive_packet(key, iv, "online")
                ka_chat = await keepalive_packet(key, iv, "chat")
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

    while cycle_count < max_cycles:
        try:
            cycle_count += 1
            print(f"\n🔄 Cycle #{cycle_count}")

            # Step 1: Send 3 start-match packets
            print(f"  → Sending start_match_leader (269, 214, 9)...")
            for pkt in leader_pkts:
                online_writer.write(pkt)
                await online_writer.drain()
                await asyncio.sleep(0.5)
            print(f"  ✅ Leader packets sent")

            # Step 2: Spam ready signal
            print(f"  → Spamming ready signal ({spam_duration}s)...")
            end_time = time.time() + spam_duration
            spam_count = 0
            while time.time() < end_time:
                try:
                    online_writer.write(spam_pkt)
                    await online_writer.drain()
                    spam_count += 1
                    await asyncio.sleep(spam_delay)
                except Exception as e:
                    print(f"  ⚠️ Send error: {e}")
                    break
            print(f"  📮 Sent {spam_count} ready packets")

            # Step 3: Wait for match
            print(f"  ⏳ Waiting {wait_after_match}s for match...")
            for _ in range(wait_after_match):
                await asyncio.sleep(1)

            # Step 4: Leave squad
            print(f"  🚪 Leaving squad...")
            try:
                online_writer.write(leave_pkt)
                await online_writer.drain()
            except Exception:
                pass
            await asyncio.sleep(1)
            print(f"  ✅ Cycle {cycle_count} done")

            await asyncio.sleep(CYCLE_DELAY)

        except Exception as e:
            print(f"  ❌ Error in cycle #{cycle_count}: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(3)

    ka_stop = True
    ka_task.cancel()
    print(f"\n🛑 Auto start loop stopped after {cycle_count} cycles")


# ═══════════════════════════════════════════════════════════════
#  Packet reader (background)
# ═══════════════════════════════════════════════════════════════

async def read_online(reader, key, iv, online_writer=None, chat_writer=None, account_uid=None):
    """Background reader — detects match-found (f2=18) and joins the match."""
    from protobuf_decoder.protobuf_decoder import Parser
    import json as _json

    match_found = False
    group_id = None

    while True:
        try:
            data = await asyncio.wait_for(reader.read(65535), timeout=30.0)
            if not data:
                break
            hex_data = data.hex()
            if len(hex_data) > 20:
                print(f"  📥 RX: {len(data)}B header={hex_data[:12]}")

            # Try different offsets to find f2=18 (match found)
            for skip in [10, 8, 12, 6, 4, 0, 14, 16, 18, 20, 2, 22, 24]:
                try:
                    payload = hex_data[skip:]
                    if len(payload) < 20:
                        continue

                    # Try raw parse first (like ClanGloryBot solo_cycle)
                    try:
                        parsed = Parser().parse(payload)
                        parsed_dict = {}
                        for r in parsed:
                            if r.wire_type == 'varint':
                                parsed_dict[r.field] = {'data': r.data, 'wire_type': 'varint'}
                            elif r.wire_type == 'length_delimited':
                                parsed_dict[r.field] = {'data': r.data, 'wire_type': 'length_delimited'}

                        # Check for f2=18 (match found)
                        f2 = parsed_dict.get(2, {})
                        f2_val = f2.get('data') if isinstance(f2, dict) else f2
                        if isinstance(f2_val, int) and f2_val == 18 and not match_found:
                            # Extract GroupID from f5.1
                            f5 = parsed_dict.get(5, {})
                            f5_data = f5.get('data', '') if isinstance(f5, dict) else ''
                            # f5 data might be nested - try to find group_id
                            gid = None
                            if isinstance(f5_data, str):
                                import re as _re
                                # Look for large number (group_id > 1 billion)
                                nums = _re.findall(r'(\d{10,})', f5_data)
                                if nums:
                                    gid = int(nums[0])
                            if isinstance(f5_data, int) and f5_data > 1000000000:
                                gid = f5_data

                            if gid and gid > 1000000000:
                                match_found = True
                                group_id = gid
                                print(f"\n  🎯 MATCH FOUND! f2=18, GroupID={group_id}")
                                print(f"  🎯 Joining match room...")

                                # Join match on online channel (0e15)
                                if online_writer:
                                    join_pkt = await join_match_packet(group_id, key, iv)
                                    online_writer.write(join_pkt)
                                    await online_writer.drain()
                                    print(f"  ✅ Match join sent (0e15)")

                                # Join match on chat channel (1215)
                                if chat_writer:
                                    await asyncio.sleep(0.5)
                                    chat_join_pkt = await join_match_chat_packet(group_id, key, iv)
                                    chat_writer.write(chat_join_pkt)
                                    await chat_writer.drain()
                                    print(f"  ✅ Chat join sent (1215)")

                                # Look for RecruitCode in f5.8
                                f8 = None
                                f5_full = parsed_dict.get(5, {})
                                if isinstance(f5_full, dict):
                                    f8_raw = str(f5_full.get('data', ''))
                                    import re as _re2
                                    rc_match = _re2.search(r'RecruitCode["\']?:?["\']?([^"\',}]+)', f8_raw)
                                    if rc_match:
                                        rc = rc_match.group(1)
                                        print(f"  🎯 RecruitCode: {rc[:40]}...")
                                        if online_writer:
                                            await asyncio.sleep(0.5)
                                            rc_pkt = await join_teamcode_packet(rc, key, iv)
                                            online_writer.write(rc_pkt)
                                            await online_writer.drain()
                                            print(f"  ✅ Match room join sent (RecruitCode)")

                                break  # Found match, stop trying offsets
                    except Exception:
                        pass

                    # Try decryption (server may encrypt some packets)
                    try:
                        decrypted = await DEc_PacKeT(payload, key, iv)
                        if decrypted and len(decrypted) > 10:
                            parsed = Parser().parse(decrypted)
                            parsed_dict = {}
                            for r in parsed:
                                if r.wire_type == 'varint':
                                    parsed_dict[r.field] = {'data': r.data, 'wire_type': 'varint'}
                                elif r.wire_type == 'length_delimited':
                                    parsed_dict[r.field] = {'data': r.data, 'wire_type': 'length_delimited'}

                            f2 = parsed_dict.get(2, {})
                            f2_val = f2.get('data') if isinstance(f2, dict) else f2
                            if isinstance(f2_val, int) and f2_val == 18 and not match_found:
                                f5 = parsed_dict.get(5, {})
                                f5_data = f5.get('data', '') if isinstance(f5, dict) else ''
                                gid = None
                                if isinstance(f5_data, str):
                                    import re as _re
                                    nums = _re.findall(r'(\d{10,})', f5_data)
                                    if nums:
                                        gid = int(nums[0])
                                if isinstance(f5_data, int) and f5_data > 1000000000:
                                    gid = f5_data

                                if gid and gid > 1000000000:
                                    match_found = True
                                    group_id = gid
                                    print(f"\n  🎯 MATCH FOUND (decrypted)! f2=18, GroupID={group_id}")
                                    if online_writer:
                                        join_pkt = await join_match_packet(group_id, key, iv)
                                        online_writer.write(join_pkt)
                                        await online_writer.drain()
                                        print(f"  ✅ Match join sent (0e15)")
                                    if chat_writer:
                                        await asyncio.sleep(0.5)
                                        chat_join_pkt = await join_match_chat_packet(group_id, key, iv)
                                        chat_writer.write(chat_join_pkt)
                                        await chat_writer.drain()
                                        print(f"  ✅ Chat join sent (1215)")
                                    break
                    except Exception:
                        pass

                except Exception:
                    continue
        except asyncio.TimeoutError:
            continue
        except Exception:
            break


# ═══════════════════════════════════════════════════════════════
#  Load accounts
# ═══════════════════════════════════════════════════════════════

def load_from_guests(path, index):
    with open(path) as f:
        guests = json.load(f)
    idx = int(index) - 1
    if idx < 0 or idx >= len(guests):
        print(f"❌ Guest index {index} out of range (1-{len(guests)})")
        sys.exit(1)
    g = guests[idx]
    return {
        "uid": g["uid"],
        "password": g.get("password", ""),
        "open_id": g.get("open_id", ""),
        "access_token": g.get("access_token", ""),
        "name": g.get("name", ""),
        "region": g.get("region", "ME"),
    }

def load_from_accounts(path, uid):
    with open(path) as f:
        accounts = json.load(f)
    uid_str = str(uid)
    if uid_str not in accounts:
        print(f"❌ UID {uid_str} not found in {path}")
        sys.exit(1)
    return {
        "uid": uid_str,
        "password": accounts[uid_str],
        "open_id": None,
        "access_token": None,
    }


# ═══════════════════════════════════════════════════════════════
#  MAIN — Full login + dual TCP connect + level loop
# ═══════════════════════════════════════════════════════════════

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
        cred = {"uid": args[0], "password": args[1], "open_id": None, "access_token": None}
        team_code = args[2]
        use_stored_tokens = False

    uid = cred["uid"]
    region = cred.get("region", "ME")

    print("=" * 55)
    print("  REAL LEVEL BOT — ClanGloryBot 1:1")
    print("=" * 55)
    print(f"  UID:       {uid}")
    print(f"  Team:      {team_code}")
    print(f"  Auth:      {'stored tokens' if use_stored_tokens else 'OAuth'}")
    print(f"  Spam:      {START_SPAM_DURATION}s (delay {START_SPAM_DELAY}s)")
    print(f"  Wait:      {WAIT_AFTER_MATCH}s")
    print("=" * 55)

    # ── Login ──
    open_id = None
    access_token = None
    login_response = None
    payload = None

    if use_stored_tokens:
        print(f"\n📡 Step 1: Stored tokens...")
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
        print(f"\n📡 Step 1c: Registering fresh guest...")
        new_uid, new_pwd, new_oid, new_tok = await register_new_guest()
        if new_oid:
            uid = new_uid
            open_id = new_oid
            access_token = new_tok
            payload = await EncRypTMajoRLoGin(open_id, access_token)
            login_response = await MajorLogin(payload)
        else:
            print("❌ Could not register new guest")
            return

    if not login_response:
        print("\n❌ All login attempts failed. Account may be banned.")
        return

    # ── Decrypt ──
    print("\n📡 Step 2: Decrypting...")
    auth = await DecRypTMajoRLoGin(login_response)
    account_uid = auth.account_uid
    token = auth.token
    url = auth.url
    key = auth.key
    iv = auth.iv
    timestamp = auth.timestamp
    print(f"  ✅ uid={account_uid}, key={key.hex()[:16]}...")

    # ── GetLoginData ──
    print("\n📡 Step 3: GetLoginData...")
    login_data = await GetLoginData(url, payload, token)
    if not login_data:
        print("❌ GetLoginData failed")
        return
    login_data_dec = await DecRypTLoGinDaTa(login_data)
    online_ip, online_port = login_data_dec.Online_IP_Port.split(":")
    chat_ip, chat_port = login_data_dec.AccountIP_Port.split(":")
    print(f"  ✅ Online: {online_ip}:{online_port}")
    print(f"  ✅ Chat:   {chat_ip}:{chat_port}")

    # ── TCP auth token ──
    print("\n📡 Step 4: Building auth token...")
    auth_token = await xAuThSTarTuP(int(account_uid), token, int(timestamp), key, iv)
    auth_bytes = bytes.fromhex(auth_token)
    print(f"  ✅ Token: {len(auth_bytes)} bytes")

    # ── TCP connect to BOTH servers ──
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

    # ── Auth to BOTH servers ──
    print("\n📡 Step 6: Sending auth tokens...")
    online_writer.write(auth_bytes)
    await online_writer.drain()
    chat_writer.write(auth_bytes)
    await chat_writer.drain()
    print(f"  ✅ Auth sent to both ({len(auth_bytes)} bytes each)")
    await asyncio.sleep(1)

    # ── AutH_GlobAl on chat channel ──
    print("📡 Step 6b: AutH_GlobAl on chat...")
    global_pkt = await auth_global_packet(key, iv)
    chat_writer.write(global_pkt)
    await chat_writer.drain()
    print(f"  ✅ AutH_GlobAl sent ({len(global_pkt)} bytes)")
    await asyncio.sleep(0.5)

    # ── Start loop + readers ──
    print("\n🚀 Starting level bot...\n")
    online_reader_task = asyncio.create_task(read_online(online_reader, key, iv, online_writer, chat_writer, account_uid))
    chat_reader_task = asyncio.create_task(read_online(chat_reader, key, iv, online_writer, chat_writer, account_uid))
    loop_task = asyncio.create_task(
        auto_start_loop(team_code, online_writer, chat_writer, key, iv, account_uid=account_uid)
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
