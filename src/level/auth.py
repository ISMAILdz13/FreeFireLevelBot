"""
Level Bot Authentication — OB54 + xC4 connection token
Merges the OB54 multi-endpoint approach with xC4-based TCP auth.

Flow:
  1. Guest OAuth (v2 JSON → v1 form-urlencoded fallback)
  2. MajorLogin (ggwhitehawk → ggpolarbear → ggblueshark fallback)
  3. GetLoginData (dynamic URL, PorTs_pb2 parsing)
  4. Connection token (xC4 EnC_PacKeT + DecodE_HeX)
"""

import json
import base64
import asyncio
import logging
import hashlib
from datetime import datetime
from typing import Optional, Tuple

import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

logger = logging.getLogger("levelbot.auth")

# ── Endpoints (OB54) ─────────────────────────────────────

OAUTH_URLS = [
    "https://ffmconnect.live.gop.garenanow.com/api/v2/oauth/guest/token:grant",
    "https://100067.connect.garena.com/oauth/guest/token/grant",
]

MAJOR_LOGIN_URLS = [
    "https://loginbp.ggwhitehawk.com/MajorLogin",
    "https://loginbp.ggpolarbear.com/MajorLogin",
    "https://loginbp.ggblueshark.com/MajorLogin",
]

LOGIN_DATA_URL_FALLBACK = "https://clientbp.ggpolarbear.com/GetLoginData"

GARENA_CLIENT_ID = "100067"
GARENA_CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"

# ── Fixed AES key/IV for API payload encryption ──────────

API_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
API_IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

# ── Template values ──────────────────────────────────────

OLD_ACCESS_TOKEN = "ff90c07eb9815af30a43b4a9f6019516e0e4c703b44092516d0defa4cef51f2a"
OLD_OPEN_ID = "996a629dbcdb3964be6b6978f5d814db"
OLD_DATE = "2025-07-30 11:02:51"
OLD_SIGNATURE_MD5 = "7428b253defc164018c604a1ebbfebdf"

# ── User-Agent strings (OB54, Android 15) ────────────────

UA_OAUTH_V2 = "GarenaMSDK/4.0.19P10(I2404 ;Android 15;en;US;)"
UA_OAUTH_V1 = "GarenaMSDK/4.0.19P9(A063 ;Android 13;en;IN;)"
UA_DALVIK = "Dalvik/2.1.0 (Linux; U; Android 15; I2404 Build/AP3A.240905.015.A2_V000L1)"

# ── Template hex ─────────────────────────────────────────

TEMPLATE_HEX = (
    "1a13323032352d30372d33302031313a30323a3531220966726565206669726528013a07312e3131382e31422c416e64726f6964204f5320372e312e32202f204150492d323320284e32473438482f373030323530323234294a0848616e6468656c645207416e64726f69645a045749464960c00c68840772033332307a1f41524d7637205646507633204e454f4e20564d48207c2032343635207c203480019a1b8a010f416472656e6f2028544d292036343092010d4f70656e474c20455320332e319a012b476f6f676c657c31663361643662372d636562342d343934622d383730622d623164616364373230393131a2010c3139372e312e31322e313335aa0102656eb201203939366136323964626364623339363462653662363937386635643831346462ba010134c2010848616e6468656c64ca011073616d73756e6720534d2d473935354eea014066663930633037656239383135616633306134336234613966363031393531366530653463373033623434303932353136643064656661346365663531663261f00101ca0207416e64726f6964d2020457494649ca03203734323862323533646566633136343031386336303461316562626665626466e003daa907e803899b07f003bf0ff803ae088004999b078804daa9079004999b079804daa907c80403d204262f646174612f6170702f636f6d2e6474732e667265656669726574682d312f6c69622f61726de00401ea044832303837663631633139663537663261663465376665666630623234643964397c2f646174612f6170702f636f6d2e6474732e667265656669726574682d312f626173652e61706bf00403f804018a050233329a050a32303139313138363933a80503b205094f70656e474c455332b805ff7fc00504e005dac901ea0507616e64726f6964f2055c4b71734854394748625876574c6668437950416c52526873626d43676542557562555551317375746d525536634e30524f3751453141486e496474385963784d614c575437636d4851322b7374745279377830663935542b6456593d8806019006019a060134a2060134b2061e40001147550d0c074f530b4d5c584d57416657545a065f2a091d6a0d5033"
)


def _encrypt_api(hex_data: str) -> str:
    plain = bytes.fromhex(hex_data)
    cipher = AES.new(API_KEY, AES.MODE_CBC, API_IV)
    return cipher.encrypt(pad(plain, AES.block_size)).hex()


def _build_payload(access_token: str, open_id: str) -> bytes:
    """Build encrypted MajorLogin/GetLoginData payload with date+signature substitution."""
    data = bytes.fromhex(TEMPLATE_HEX)

    # Substitute date (template has 2025-07-30 — must update to current time)
    new_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = data.replace(OLD_DATE.encode(), new_date.encode())

    # Substitute access_token + open_id
    data = data.replace(OLD_OPEN_ID.encode(), open_id.encode())
    data = data.replace(OLD_ACCESS_TOKEN.encode(), access_token.encode())

    # Substitute signature MD5 (must match the new date)
    sig_input = f"free_fire{new_date}WmfdlkTOtsflIWMx4bpg5m4bpg5V31m0bpgm4bpg5mO24bpgN31m0bpgZ31m0m4G"
    sig_md5 = hashlib.md5(sig_input.encode()).hexdigest()
    data = data.replace(OLD_SIGNATURE_MD5.encode(), sig_md5.encode())

    encrypted = _encrypt_api(data.hex())
    return bytes.fromhex(encrypted)


class LevelAuth:
    def __init__(self, http_client: httpx.AsyncClient):
        self.http = http_client

    # ── Step 1: Guest OAuth (v2 → v1 fallback) ─────────────

    async def guest_token(self, uid: str, password: str, retries: int = 3) -> Optional[Tuple[str, str]]:
        # Try v2 (JSON payload) first
        for attempt in range(retries):
            try:
                resp = await self.http.post(
                    OAUTH_URLS[0],
                    json={
                        "client_id": int(GARENA_CLIENT_ID),
                        "client_secret": GARENA_CLIENT_SECRET,
                        "client_type": 2,
                        "password": password,
                        "response_type": "token",
                        "uid": int(uid),
                    },
                    headers={
                        "User-Agent": UA_OAUTH_V2,
                        "Accept": "application/json",
                        "Content-Type": "application/json; charset=utf-8",
                        "Connection": "Keep-Alive",
                        "Accept-Encoding": "gzip",
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    resp_data = resp.json()
                    data = resp_data.get("data", resp_data)
                    access_token = data.get("access_token")
                    open_id = data.get("open_id")
                    if access_token and open_id:
                        logger.info(f"Guest token acquired (v2) for UID {uid}")
                        return access_token, open_id
                    error = data.get("error", resp_data.get("error"))
                    if error:
                        logger.warning(f"OAuth v2 error: {error}")
                        break
                logger.warning(f"OAuth v2 attempt {attempt+1}: HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"OAuth v2 attempt {attempt+1}/{retries} failed: {e}")
            await asyncio.sleep(1)

        # Fall back to v1 (form-urlencoded)
        logger.info("Falling back to OAuth v1 (100067.connect.garena.com)")
        headers = {
            "Host": "100067.connect.garena.com",
            "User-Agent": UA_OAUTH_V1,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "close",
        }
        data = {
            "uid": uid,
            "password": password,
            "response_type": "token",
            "client_type": "2",
            "client_secret": GARENA_CLIENT_SECRET,
            "client_id": GARENA_CLIENT_ID,
        }

        for attempt in range(retries):
            try:
                resp = await self.http.post(OAUTH_URLS[1], headers=headers, data=data, timeout=30)
                resp_data = resp.json()
                access_token = resp_data.get("access_token")
                open_id = resp_data.get("open_id")
                if access_token and open_id:
                    logger.info(f"Guest token acquired (v1) for UID {uid}")
                    return access_token, open_id
                logger.warning(f"Guest token v1 response missing fields: {resp_data}")
            except Exception as e:
                logger.warning(f"Guest token v1 attempt {attempt+1}/{retries} failed: {e}")
                await asyncio.sleep(2)

        logger.error(f"Failed to get guest token for UID {uid} (both v1 and v2)")
        return None

    # ── Step 2: MajorLogin (multi-endpoint fallback) ───────

    async def major_login(self, access_token: str, open_id: str, retries: int = 2) -> Optional[dict]:
        payload = _build_payload(access_token, open_id)

        # OB54 headers
        headers = {
            "X-Unity-Version": "2018.4.11f1",
            "ReleaseVersion": "OB54",
            "Content-Type": "application/octet-stream",
            "X-GA": "v1 1",
            "Expect": "100-continue",
            "User-Agent": UA_DALVIK,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
        }

        last_status = 0
        last_body = b""

        for ml_url in MAJOR_LOGIN_URLS:
            host = ml_url.split("//")[1].split("/")[0]
            for attempt in range(retries):
                try:
                    h = {**headers, "Host": host, "Authorization": f"Bearer {access_token}"}
                    resp = await self.http.post(ml_url, headers=h, content=payload, timeout=20)
                    last_status = resp.status_code
                    last_body = resp.content

                    if resp.status_code == 200 and len(resp.content) > 30:
                        if b"Protection" in resp.content or b"Bypass" in resp.content:
                            logger.warning(f"MajorLogin {host}: Protection Bypass detected. Trying next endpoint...")
                            break

                        result = self._parse_major_login_response(resp.content)
                        if result and result.get("token"):
                            result["payload"] = payload  # Save for GetLoginData reuse
                            logger.info(f"MajorLogin successful via {host} — region={result.get('region', '?')}")
                            return result

                        result = self._parse_raw(resp.content)
                        if result and result.get("token"):
                            result["payload"] = payload
                            return result
                    else:
                        logger.warning(f"MajorLogin {host} attempt {attempt+1}: status={resp.status_code}, body_len={len(resp.content)}")
                except Exception as e:
                    logger.warning(f"MajorLogin {host} attempt {attempt+1}/{retries} failed: {e}")
                await asyncio.sleep(2)

        logger.error(f"MajorLogin failed on all {len(MAJOR_LOGIN_URLS)} endpoints")
        return {"error": "major_login_failed", "last_status": last_status, "last_body": last_body[:100].hex() if last_body else ""}

    def _parse_major_login_response(self, content: bytes) -> Optional[dict]:
        try:
            import sys, os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "level"))
            from MajorLoginRes_pb2 import MajorLoginRes
            from google.protobuf.timestamp_pb2 import Timestamp

            msg = MajorLoginRes()
            msg.ParseFromString(content)

            ts = Timestamp()
            ts.FromNanoseconds(msg.kts)
            combined = ts.seconds * 1_000_000_000 + ts.nanos

            key = msg.ak if isinstance(msg.ak, bytes) else bytes.fromhex(msg.ak)
            iv = msg.aiv if isinstance(msg.aiv, bytes) else bytes.fromhex(msg.aiv)

            return {
                "token": msg.token,
                "key": key,
                "iv": iv,
                "timestamp": combined,
                "url": msg.url if msg.url else LOGIN_DATA_URL_FALLBACK,
                "region": msg.region if msg.region else "IND",
                "account_uid": msg.account_uid if msg.account_uid else 0,
            }
        except Exception as e:
            logger.warning(f"Protobuf parse failed: {e}, trying raw parser...")
            return self._parse_raw(content)

    def _parse_raw(self, content: bytes) -> Optional[dict]:
        try:
            from protobuf_decoder.protobuf_decoder import Parser

            parsed = Parser().parse(content.hex())
            result_dict = {}
            for r in parsed:
                if r.wire_type == "varint":
                    result_dict[r.field] = r.data
                elif r.wire_type in ("string", "bytes"):
                    result_dict[r.field] = r.data
                elif r.wire_type == "length_delimited":
                    sub = {}
                    for sr in r.data.results:
                        if sr.wire_type in ("string", "bytes"):
                            sub[sr.field] = sr.data
                        elif sr.wire_type == "varint":
                            sub[sr.field] = sr.data
                    result_dict[r.field] = sub

            token = result_dict.get(7, "")
            if isinstance(token, bytes):
                token = token.decode("utf-8", errors="replace")
            if not token:
                return None

            key_raw = result_dict.get(18, b"")
            iv_raw = result_dict.get(19, b"")
            key = key_raw if isinstance(key_raw, bytes) else (bytes.fromhex(key_raw) if isinstance(key_raw, str) and all(c in "0123456789abcdef" for c in key_raw.lower()) else b"")
            iv = iv_raw if isinstance(iv_raw, bytes) else (bytes.fromhex(iv_raw) if isinstance(iv_raw, str) and all(c in "0123456789abcdef" for c in iv_raw.lower()) else b"")

            ts_data = result_dict.get(8, {})
            combined = int(ts_data.get(1, 0)) * 1_000_000_000 + int(ts_data.get(2, 0)) if isinstance(ts_data, dict) else 0

            url = result_dict.get(5, LOGIN_DATA_URL_FALLBACK)
            if isinstance(url, bytes):
                url = url.decode("utf-8", errors="replace")
            region = result_dict.get(4, "IND")
            if isinstance(region, bytes):
                region = region.decode("utf-8", errors="replace")

            return {
                "token": token if isinstance(token, str) else token.decode("utf-8", errors="replace"),
                "key": key, "iv": iv, "timestamp": combined,
                "url": url, "region": region, "account_uid": 0,
            }
        except Exception as e:
            logger.error(f"Raw parse also failed: {e}")
            return None

    # ── Step 3: GetLoginData ───────────────────────────────

    async def get_login_data(
        self, jwt_token: str, base_url: Optional[str] = None,
        access_token: Optional[str] = None,
        major_login_payload: Optional[bytes] = None, retries: int = 3,
    ) -> Optional[Tuple[str, int, str, int]]:
        url = base_url.rstrip("/") + "/GetLoginData" if base_url else LOGIN_DATA_URL_FALLBACK

        # Reuse MajorLogin payload (same as ClanGloryBot) or build fresh
        if major_login_payload:
            payload = major_login_payload
        elif access_token:
            payload = _build_payload(access_token, "")
        else:
            payload = _build_payload("", "")

        host = url.split("//")[1].split("/")[0] if "//" in url else "clientbp.ggpolarbear.com"
        headers = {
            "X-Unity-Version": "2018.4.11f1",
            "ReleaseVersion": "OB54",
            "Content-Type": "application/octet-stream",
            "X-GA": "v1 1",
            "User-Agent": UA_DALVIK,
            "Authorization": f"Bearer {jwt_token}",
            "Host": host,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
        }

        for attempt in range(retries):
            try:
                resp = await self.http.post(url, headers=headers, content=payload, timeout=30)
                if resp.status_code == 200 and len(resp.content) > 10:
                    # Try PorTs_pb2 first (same as ClanGloryBot)
                    server_info = self._parse_server_info_pb(resp.content)
                    if server_info:
                        return server_info
                    # Fallback to generic parser
                    server_info = self._parse_server_info(resp.content.hex())
                    if server_info:
                        return server_info
                logger.warning(f"LoginData attempt {attempt+1}: status={resp.status_code}, body_len={len(resp.content)}")
            except Exception as e:
                logger.warning(f"LoginData attempt {attempt+1}/{retries} failed: {e}")
            await asyncio.sleep(2)

        logger.error(f"GetLoginData failed after {retries} attempts")
        return None

    def _parse_server_info_pb(self, raw_data: bytes) -> Optional[Tuple[str, int, str, int]]:
        try:
            from .Pb2.PorTs_pb2 import GetLoginData as GetLoginDataProto
            proto = GetLoginDataProto()
            proto.ParseFromString(raw_data)

            online_addr = proto.Online_IP_Port
            chat_addr = proto.AccountIP_Port

            if not online_addr or not chat_addr or ":" not in online_addr or ":" not in chat_addr:
                logger.warning(f"PorTs_pb2: bad addresses: online={online_addr}, chat={chat_addr}")
                return None

            online_ip, online_port = online_addr.rsplit(":", 1)
            chat_ip, chat_port = chat_addr.rsplit(":", 1)
            return chat_ip, int(chat_port), online_ip, int(online_port)
        except Exception as e:
            logger.warning(f"PorTs_pb2 parse failed: {e}")
            return None

    def _parse_server_info(self, hex_data: str) -> Optional[Tuple[str, int, str, int]]:
        try:
            from protobuf_decoder.protobuf_decoder import Parser
            parsed = Parser().parse(hex_data)
            result_dict = {}
            for r in parsed:
                if r.wire_type == "varint":
                    result_dict[str(r.field)] = r.data
                elif r.wire_type in ("string", "bytes"):
                    result_dict[str(r.field)] = r.data
                elif r.wire_type == "length_delimited":
                    sub = {}
                    for sr in r.data.results:
                        if sr.wire_type in ("string", "bytes"):
                            sub[str(sr.field)] = sr.data
                        elif sr.wire_type == "varint":
                            sub[str(sr.field)] = sr.data
                    result_dict[str(r.field)] = sub

            online_addr = result_dict.get("14", "")
            if isinstance(online_addr, dict):
                online_addr = online_addr.get("1", online_addr.get("data", ""))
            whisper_addr = result_dict.get("32", "")
            if isinstance(whisper_addr, dict):
                whisper_addr = whisper_addr.get("1", whisper_addr.get("data", ""))

            if not online_addr or not whisper_addr or ":" not in online_addr or ":" not in whisper_addr:
                return None

            online_ip, online_port_str = online_addr.rsplit(":", 1)
            whisper_ip, whisper_port_str = whisper_addr.rsplit(":", 1)
            return whisper_ip, int(whisper_port_str), online_ip, int(online_port_str)
        except Exception as e:
            logger.error(f"Server info parse failed: {e}")
            return None

    # ── Step 4: Connection Token (xC4) ─────────────────────

    async def build_connection_token(self, jwt_token: str, key: bytes, iv: bytes, timestamp: int, account_id: int) -> str:
        from .xC4 import EnC_PacKeT, DecodE_HeX

        uid_hex = hex(account_id)[2:]
        uid_length = len(uid_hex)
        encrypted_timestamp = await DecodE_HeX(timestamp)
        encrypted_account_token = jwt_token.encode().hex()
        encrypted_packet = await EnC_PacKeT(encrypted_account_token, key, iv)
        encrypted_packet_length = hex(len(encrypted_packet) // 2)[2:]

        if uid_length == 9: headers = '0000000'
        elif uid_length == 8: headers = '00000000'
        elif uid_length == 10: headers = '000000'
        elif uid_length == 7: headers = '000000000'
        else: headers = '0000000'

        return f"0115{headers}{uid_hex}{encrypted_timestamp}00000{encrypted_packet_length}{encrypted_packet}"
