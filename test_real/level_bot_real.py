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
    'Content-Type': 'application/x-www-form-urlencoded',
    'X-GA': 'v1 1',
    'User-Agent': 'Dalvik/2.1.0 (Linux; U; Android 9; G011A Build/PI)',
    'Connection': 'Keep-Alive',
    'Accept-Encoding': 'gzip',
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
#  Level bot packets (1:1 copy from OB54-TCP-BOT)
# ═══════════════════════════════════════════════════════════════

async def join_teamcode_packet(team_code, key, iv):
    """Join team using code — 1:1 with OB54-TCP-BOT join_teamcode_packet."""
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

async def start_auto_packet(uid, key, iv):
    """Start match packet — field 1=9, field 2={1: UID}."""
    fields = {
        1: 9,
        2: {
            1: uid,
        },
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', key, iv)

async def leave_squad_packet(uid, key, iv):
    """Leave squad — field 1=7, field 2={1: UID}."""
    fields = {
        1: 7,
        2: {
            1: uid,
        },
    }
    return await GeneRaTePk((await CrEaTe_ProTo(fields)).hex(), '0515', key, iv)


# ═══════════════════════════════════════════════════════════════
#  auto_start_loop — THE REAL LEVEL BOT LOOP (1:1 copy)
# ═══════════════════════════════════════════════════════════════

async def auto_start_loop(team_code, online_writer, key, iv, bot_uid,
                           spam_duration=START_SPAM_DURATION,
                           spam_delay=START_SPAM_DELAY,
                           wait_after_match=WAIT_AFTER_MATCH,
                           max_cycles=1000):
    """Auto start loop: join → spam start → wait → leave → repeat."""

    cycle_count = 0

    print(f"\n🚀 Auto start loop — team: {team_code}")
    print(f"⚡ Join → Start → Wait({wait_after_match}s) → Leave → Repeat\n")

    while cycle_count < max_cycles:
        try:
            cycle_count += 1
            print(f"\n🔄 Cycle #{cycle_count}")

            # ── Step 1: Join team ──
            print(f"  → Joining team {team_code}...")
            join_packet = await join_teamcode_packet(team_code, key, iv)
            online_writer.write(join_packet)
            await online_writer.drain()
            await asyncio.sleep(JOIN_DELAY)
            print(f"  ✅ Joined team {team_code}")

            # ── Step 2: Spam start match (field 1=9) ──
            print(f"  → Spamming start match ({spam_duration}s)...")
            start_packet = await start_auto_packet(bot_uid, key, iv)
            end_time = time.time() + spam_duration
            spam_count = 0

            while time.time() < end_time:
                online_writer.write(start_packet)
                await online_writer.drain()
                spam_count += 1
                await asyncio.sleep(spam_delay)

            print(f"  📮 Sent {spam_count} start packets")

            # ── Step 3: Wait for match to complete ──
            print(f"  ⏳ Waiting {wait_after_match}s for match...")
            waited = 0
            while waited < wait_after_match:
                await asyncio.sleep(1)
                waited += 1

            # ── Step 4: Leave squad ──
            print(f"  🚪 Leaving team...")
            leave_packet = await leave_squad_packet(bot_uid, key, iv)
            online_writer.write(leave_packet)
            await online_writer.drain()
            await asyncio.sleep(LEAVE_DELAY)
            print(f"  ✅ Left team — cycle {cycle_count} done")

            # ── Step 5: Cycle delay ──
            await asyncio.sleep(CYCLE_DELAY)

        except Exception as e:
            print(f"  ❌ Error in cycle #{cycle_count}: {e}")
            import traceback
            traceback.print_exc()
            await asyncio.sleep(3)

    print(f"\n🛑 Auto start loop stopped after {cycle_count} cycles")


# ═══════════════════════════════════════════════════════════════
#  Online reader — reads server responses (for debugging)
# ═══════════════════════════════════════════════════════════════

async def read_online(reader, key, iv):
    """Read packets from online server — for debugging."""
    while True:
        try:
            data = await reader.read(9999)
            if not data:
                print("  ⚠️ Server closed connection")
                break
            data_hex = data.hex()
            pkt_type = data_hex[:4] if len(data_hex) >= 4 else "?"
            pkt_len = len(data)
            if len(data_hex) > 8:
                try:
                    # Try to decrypt the payload
                    encrypted_hex = data_hex[8:]
                    decrypted = await DEc_PacKeT(encrypted_hex, key, iv)
                    # Parse first few fields
                    print(f"  📥 RX [{pkt_type}] {pkt_len}B → {decrypted[:100]}...")
                except:
                    print(f"  📥 RX [{pkt_type}] {pkt_len}B (encrypted, type={pkt_type})")
            else:
                print(f"  📥 RX [{pkt_type}] {pkt_len}B")
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"  ⚠️ Read error: {e}")
            break


# ═══════════════════════════════════════════════════════════════
#  Credential loading
# ═══════════════════════════════════════════════════════════════

def load_from_guests(path, index):
    """Load guest from guests.json — uses stored open_id + access_token."""
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
    """Load from level_accounts.json — hex password for OAuth."""
    with open(path) as f:
        accounts = json.load(f)
    uid_str = str(uid)
    if uid_str not in accounts:
        print(f"❌ UID {uid_str} not found in {path}")
        print(f"   Available: {list(accounts.keys())}")
        sys.exit(1)
    return {
        "uid": uid_str,
        "password": accounts[uid_str],
        "open_id": None,
        "access_token": None,
    }


# ═══════════════════════════════════════════════════════════════
#  MAIN — Full login + connect + level loop
# ═══════════════════════════════════════════════════════════════

async def main():
    args = sys.argv[1:]

    # Parse args
    if len(args) >= 1 and args[0] == '--guests':
        # --guests <path> <index> <team_code>
        if len(args) < 4:
            print("Usage: python3 level_bot_real.py --guests <path> <index> <team_code>")
            print("Example: python3 level_bot_real.py --guests ../data/guests.json 1 2781283")
            sys.exit(1)
        guests_path = args[1]
        guest_index = args[2]
        team_code = args[3]
        cred = load_from_guests(guests_path, guest_index)
        use_stored_tokens = bool(cred["open_id"] and cred["access_token"])

    elif len(args) >= 1 and args[0] == '--accounts':
        # --accounts <path> <uid> <team_code>
        if len(args) < 4:
            print("Usage: python3 level_bot_real.py --accounts <path> <uid> <team_code>")
            print("Example: python3 level_bot_real.py --accounts ../data/level_accounts.json 5822030305 2781283")
            sys.exit(1)
        accounts_path = args[1]
        uid = args[2]
        team_code = args[3]
        cred = load_from_accounts(accounts_path, uid)
        use_stored_tokens = False

    else:
        # Direct: <uid> <password> <team_code>
        if len(args) < 3:
            print("Usage:")
            print("  python3 level_bot_real.py --guests <path> <index> <team_code>")
            print("  python3 level_bot_real.py --accounts <path> <uid> <team_code>")
            print("  python3 level_bot_real.py <uid> <password> <team_code>")
            sys.exit(1)
        cred = {
            "uid": args[0],
            "password": args[1],
            "open_id": None,
            "access_token": None,
        }
        team_code = args[2]
        use_stored_tokens = False

    uid = cred["uid"]
    password = cred.get("password", "")
    region = cred.get("region", "ME")

    print("=" * 55)
    print("  REAL LEVEL BOT — OB54-TCP-BOT 1:1")
    print("=" * 55)
    print(f"  UID:       {uid}")
    print(f"  Team:      {team_code}")
    print(f"  Auth:      {'stored tokens (skip OAuth)' if use_stored_tokens else 'OAuth (uid+password)'}")
    print(f"  Spam:      {START_SPAM_DURATION}s (delay {START_SPAM_DELAY}s)")
    print(f"  Wait:      {WAIT_AFTER_MATCH}s")
    print("=" * 55)

    # ── Step 1: Get open_id + access_token ──
    open_id = None
    access_token = None

    if use_stored_tokens:
        print(f"\n📡 Step 1: Using stored tokens from guests.json...")
        open_id = cred["open_id"]
        access_token = cred["access_token"]
        print(f"  ✅ open_id: {open_id}")
        print(f"  ✅ token:   {access_token[:20]}...")
    else:
        print(f"\n📡 Step 1: Getting access token via OAuth...")
        open_id, access_token = await GeNeRaTeAccEss(uid, password)
        if open_id:
            print(f"  ✅ open_id: {open_id}")
            print(f"  ✅ token:   {access_token[:20]}...")

    if not open_id and cred.get("password"):
        # Try OAuth with stored password
        print(f"\n📡 Step 1b: Trying OAuth with stored password...")
        open_id, access_token = await GeNeRaTeAccEss(uid, cred["password"])
        if open_id:
            print(f"  ✅ open_id: {open_id}")
            print(f"  ✅ token:   {access_token[:20]}...")

    if not open_id:
        # Last resort: register a new guest
        print(f"\n📡 Step 1c: All tokens expired. Registering fresh guest...")
        new_uid, new_pwd, new_oid, new_tok = await register_new_guest()
        if new_oid:
            uid = new_uid
            open_id = new_oid
            access_token = new_tok
            print(f"  ✅ New guest: UID={uid}")
            print(f"  ✅ open_id: {open_id}")
            print(f"  ✅ token:   {access_token[:20]}...")
        else:
            print("❌ Could not get tokens — try running gen_guest.py first")
            return

    # ── Step 2: MajorLogin ──
    print("\n📡 Step 2: MajorLogin...")
    payload = await EncRypTMajoRLoGin(open_id, access_token)
    login_response = await MajorLogin(payload)
    if not login_response:
        print("❌ MajorLogin failed — all endpoints returned rejection")
        print("  Tokens may be expired. Try:")
        print("  1. python3 gen_guest.py  (generate fresh guest)")
        print("  2. python3 level_bot_real.py --accounts ../data/level_accounts.json <uid> <team_code>")
        return

    print(f"  ✅ Got login response: {len(login_response)} bytes")

    # ── Step 3: Decrypt login response ──
    print("\n📡 Step 3: Decrypting login response...")
    auth = await DecRypTMajoRLoGin(login_response)

    account_uid = auth.account_uid
    token = auth.token
    url = auth.url
    key = auth.key
    iv = auth.iv
    timestamp = auth.timestamp

    print(f"  ✅ account_uid: {account_uid}")
    print(f"  ✅ token:      {token[:30]}...")
    print(f"  ✅ url:         {url}")
    print(f"  ✅ key:         {key.hex()}")
    print(f"  ✅ iv:          {iv.hex()}")
    print(f"  ✅ timestamp:   {timestamp}")

    # ── Step 4: GetLoginData (server IPs) ──
    print("\n📡 Step 4: Getting server IPs...")
    login_data = await GetLoginData(url, payload, token)
    if not login_data:
        print("❌ GetLoginData failed")
        return

    login_data_dec = await DecRypTLoGinDaTa(login_data)
    online_ports = login_data_dec.Online_IP_Port
    chat_ports = login_data_dec.AccountIP_Port
    acc_name = login_data_dec.AccountName

    online_ip, online_port = online_ports.split(":")
    chat_ip, chat_port = chat_ports.split(":")

    print(f"  ✅ Online server: {online_ip}:{online_port}")
    print(f"  ✅ Chat server:   {chat_ip}:{chat_port}")
    print(f"  ✅ Account name:  {acc_name}")

    # ── Step 5: Build auth token for TCP ──
    print("\n📡 Step 5: Building TCP auth token...")
    auth_token = await xAuThSTarTuP(int(account_uid), token, int(timestamp), key, iv)
    print(f"  ✅ Auth token: {len(auth_token)} chars")

    # ── Step 6: TCP connect to Online server ──
    print(f"\n📡 Step 6: Connecting to {online_ip}:{online_port}...")
    try:
        reader, writer = await asyncio.open_connection(online_ip, int(online_port))
    except Exception as e:
        print(f"❌ TCP connection failed: {e}")
        return

    print(f"  ✅ Connected!")

    # ── Step 7: Send auth token ──
    print("\n📡 Step 7: Sending auth token...")
    auth_bytes = bytes.fromhex(auth_token)
    writer.write(auth_bytes)
    await writer.drain()
    print(f"  ✅ Auth token sent ({len(auth_bytes)} bytes)")

    # Wait for server to process auth
    await asyncio.sleep(2)

    # ── Step 8: Start level bot loop + reader ──
    print("\n🚀 Starting level bot + packet reader...\n")

    reader_task = asyncio.create_task(read_online(reader, key, iv))
    loop_task = asyncio.create_task(auto_start_loop(team_code, writer, key, iv, int(account_uid)))

    try:
        await loop_task
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
    finally:
        reader_task.cancel()
        writer.close()
        await writer.wait_closed()
        print("✅ Disconnected")


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")
