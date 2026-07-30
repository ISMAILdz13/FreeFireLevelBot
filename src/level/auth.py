"""
Level Bot Authentication
Handles the full Garena auth flow for the level bot:
  1. Guest OAuth token grant -> access_token + open_id
  2. MajorLogin (encrypted protobuf) -> JWT + AES key/iv + timestamp + url
  3. GetLoginData -> whisper/online server IP:port

Updated endpoints (2026-07-30):
  - OAuth v2:   ffmconnect.live.gop.garenanow.com (new, JSON payload)
  - OAuth v1:   100067.connect.garena.com (legacy, form-urlencoded)
  - MajorLogin: Tries multiple endpoints (ggwhitehawk, ggpolarbear, ggblueshark)
  - GetLoginData: Dynamic URL from MajorLogin response
"""

import json
import base64
import asyncio
import logging
from datetime import datetime
from typing import Optional, Tuple

import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

logger = logging.getLogger("levelbot.auth")

# ── Endpoints ─────────────────────────────────────────────

# OAuth — try v2 first (new JSON API), fall back to v1 (legacy form-urlencoded)
OAUTH_URLS = [
    "https://ffmconnect.live.gop.garenanow.com/api/v2/oauth/guest/token:grant",  # v2 (new)
    "https://100067.connect.garena.com/oauth/guest/token/grant",                # v1 (legacy)
]

# MajorLogin — try multiple endpoints in order
MAJOR_LOGIN_URLS = [
    "https://loginbp.ggwhitehawk.com/MajorLogin",   # newest
    "https://loginbp.ggpolarbear.com/MajorLogin",   # primary
    "https://loginbp.ggblueshark.com/MajorLogin",   # fallback
]

# GetLoginData — dynamic from MajorLogin response, this is just a fallback
LOGIN_DATA_URL_FALLBACK = "https://clientbp.ggpolarbear.com/GetLoginData"

GARENA_CLIENT_ID = "100067"
GARENA_CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"

# ── Fixed AES key/IV for API payload encryption (unchanged) ──────────

API_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
API_IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

# ── Template values that get substituted ──────────────────

OLD_ACCESS_TOKEN = "ff90c07eb9815af30a43b4a9f6019516e0e4c703b44092516d0defa4cef51f2a"
OLD_OPEN_ID = "996a629dbcdb3964be6b6978f5d814db"
OLD_DATE = "2025-07-30 11:02:51"
OLD_SIGNATURE_MD5 = "7428b253defc164018c604a1ebbfebdf"

# ── Updated User-Agent strings (Android 15, P10) ─────────

UA_OAUTH_V2 = "GarenaMSDK/4.0.19P10(I2404 ;Android 15;en;US;)"
UA_OAUTH_V1 = "GarenaMSDK/4.0.19P9(A063 ;Android 13;en;IN;)"
UA_DALVIK = "Dalvik/2.1.0 (Linux; U; Android 15; I2404 Build/AP3A.240905.015.A2_V000L1)"

# ── The shared template hex (extracted from original level/app.py) ──

TEMPLATE_HEX = (
    "1a13323032352d30372d33302031313a30323a3531220966726565206669726528013a07312e3131382e31422c416e64726f6964204f5320372e312e32202f204150492d323320284e32473438482f373030323530323234294a0848616e6468656c645207416e64726f69645a045749464960c00c68840772033332307a1f41524d7637205646507633204e454f4e20564d48207c2032343635207c203480019a1b8a010f416472656e6f2028544d292036343092010d4f70656e474c20455320332e319a012b476f6f676c657c31663361643662372d636562342d343934622d383730622d623164616364373230393131a2010c3139372e312e31322e313335aa0102656eb201203939366136323964626364623339363462653662363937386635643831346462ba010134c2010848616e6468656c64ca011073616d73756e6720534d2d473935354eea014066663930633037656239383135616633306134336234613966363031393531366530653463373033623434303932353136643064656661346365663531663261f00101ca0207416e64726f6964d2020457494649ca03203734323862323533646566633136343031386336303461316562626665626466e003daa907e803899b07f003bf0ff803ae088004999b078804daa9079004999b079804daa907c80403d204262f646174612f6170702f636f6d2e6474732e667265656669726574682d312f6c69622f61726de00401ea044832303837663631633139663537663261663465376665666630623234643964397c2f646174612f6170702f636f6d2e6474732e667265656669726574682d312f626173652e61706bf00403f804018a050233329a050a32303139313138363933a80503b205094f70656e474c455332b805ff7fc00504e005dac901ea0507616e64726f6964f2055c4b71734854394748625876574c6668437950416c52526873626d43676542557562555551317375746d525536634e30524f3751453141486e496474385963784d614c575437636d4851322b7374745279377830663935542b6456593d8806019006019a060134a2060134b2061e40001147550d0c074f530b4d5c584d57416657545a065f2a091d6a0d5033"
)


def _encrypt_api(hex_data: str) -> str:
    """Encrypt hex payload with the fixed API AES key/IV."""
    plain = bytes.fromhex(hex_data)
    cipher = AES.new(API_KEY, AES.MODE_CBC, API_IV)
    return cipher.encrypt(pad(plain, AES.block_size)).hex()


class LevelAuth:
    """
    Handles authentication for the level bot.

    Flow:
        1. guest_token(uid, password) -> access_token + open_id
        2. major_login(access_token, open_id) -> JWT + key + iv + timestamp + url
        3. get_login_data(jwt, url, access_token) -> whisper_ip:port + online_ip:port

    Server URLs (updated 2026-07-30):
        - OAuth v2:  ffmconnect.live.gop.garenanow.com (JSON)
        - OAuth v1:  100067.connect.garena.com (form-urlencoded)
        - MajorLogin: ggwhitehawk -> ggpolarbear -> ggblueshark (fallback)
        - GetLoginData: {url from MajorLogin response}/GetLoginData
    """

    def __init__(self, http_client: httpx.AsyncClient):
        self.http = http_client

    # ── Step 1: Guest OAuth ───────────────────────────────

    async def guest_token(
        self, uid: str, password: str, retries: int = 3
    ) -> Optional[Tuple[str, str]]:
        """Get Garena guest OAuth access_token + open_id.
        Tries v2 JSON endpoint first, falls back to v1 form-urlencoded."""
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
                resp = await self.http.post(
                    OAUTH_URLS[1], headers=headers, data=data, timeout=30
                )
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

    # ── Step 2: MajorLogin ────────────────────────────────

    async def major_login(
        self, access_token: str, open_id: str, retries: int = 2
    ) -> Optional[dict]:
        """
        MajorLogin -> JWT token + AES key + IV + timestamp + server URL.
        Substitutes access_token and open_id in the template.
        Tries multiple MajorLogin endpoints in order.

        Returns dict with:
            token: JWT string
            key:   AES key (bytes)
            iv:    AES IV (bytes)
            timestamp: combined timestamp (int)
            url:   base URL for GetLoginData
            region: server region
            account_uid: account UID

        On failure returns:
            {"error": "major_login_failed", "last_status": <http_status>}
        """
        data = bytes.fromhex(TEMPLATE_HEX)
        data = data.replace(OLD_OPEN_ID.encode(), open_id.encode())
        data = data.replace(OLD_ACCESS_TOKEN.encode(), access_token.encode())

        encrypted = _encrypt_api(data.hex())
        payload = bytes.fromhex(encrypted)

        # Updated headers — Android 15, P10 SDK
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
                    h = {**headers, "Host": host,
                         "Authorization": f"Bearer {access_token}"}
                    resp = await self.http.post(
                        ml_url, headers=h, content=payload, timeout=20
                    )
                    last_status = resp.status_code
                    last_body = resp.content

                    if resp.status_code == 200 and len(resp.content) > 30:
                        # Check for "Protection Bypass" anti-bot response
                        if b"Protection" in resp.content or b"Bypass" in resp.content:
                            logger.warning(
                                f"MajorLogin {host}: Protection Bypass detected "
                                f"(anti-bot). Trying next endpoint..."
                            )
                            break  # Skip to next endpoint

                        result = self._parse_major_login_response(resp.content)
                        if result and result.get("token"):
                            logger.info(
                                f"MajorLogin successful via {host} -- JWT acquired, "
                                f"region={result.get('region', '?')}, "
                                f"url={result.get('url', '?')}"
                            )
                            return result
                        else:
                            logger.warning(
                                f"MajorLogin {host}: 200 OK but parse failed, "
                                f"trying raw parser..."
                            )
                            result = self._parse_raw(resp.content)
                            if result and result.get("token"):
                                return result
                    else:
                        logger.warning(
                            f"MajorLogin {host} attempt {attempt+1}: "
                            f"status={resp.status_code}, body_len={len(resp.content)}"
                        )
                except Exception as e:
                    logger.warning(
                        f"MajorLogin {host} attempt {attempt+1}/{retries} failed: {e}"
                    )
                await asyncio.sleep(2)

        logger.error(f"MajorLogin failed on all endpoints")
        return {
            "error": "major_login_failed",
            "last_status": last_status,
            "last_body": last_body[:100].hex() if last_body else "",
        }

    def _parse_major_login_response(self, content: bytes) -> Optional[dict]:
        """Parse MajorLogin protobuf response -> token, key, iv, timestamp, url, region."""
        try:
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "level"))
            from MajorLoginRes_pb2 import MajorLoginRes
            from google.protobuf.timestamp_pb2 import Timestamp

            msg = MajorLoginRes()
            msg.ParseFromString(content)

            ts = Timestamp()
            ts.FromNanoseconds(msg.timestamp)
            combined = ts.seconds * 1_000_000_000 + ts.nanos

            key = msg.key if isinstance(msg.key, bytes) else bytes.fromhex(msg.key)
            iv = msg.iv if isinstance(msg.iv, bytes) else bytes.fromhex(msg.iv)

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
        """Fallback: parse MajorLogin response using raw protobuf decoder."""
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
            if isinstance(key_raw, str):
                key = bytes.fromhex(key_raw) if all(c in "0123456789abcdef" for c in key_raw.lower()) else key_raw.encode()
            else:
                key = key_raw if isinstance(key_raw, bytes) else b""
            if isinstance(iv_raw, str):
                iv = bytes.fromhex(iv_raw) if all(c in "0123456789abcdef" for c in iv_raw.lower()) else iv_raw.encode()
            else:
                iv = iv_raw if isinstance(iv_raw, bytes) else b""

            ts_data = result_dict.get(8, {})
            ts_seconds = 0
            ts_nanos = 0
            if isinstance(ts_data, dict):
                ts_seconds = int(ts_data.get(1, 0))
                ts_nanos = int(ts_data.get(2, 0))
            combined = ts_seconds * 1_000_000_000 + ts_nanos

            url = result_dict.get(5, LOGIN_DATA_URL_FALLBACK)
            if isinstance(url, bytes):
                url = url.decode("utf-8", errors="replace")

            region = result_dict.get(4, "IND")
            if isinstance(region, bytes):
                region = region.decode("utf-8", errors="replace")

            return {
                "token": token if isinstance(token, str) else token.decode("utf-8", errors="replace"),
                "key": key,
                "iv": iv,
                "timestamp": combined,
                "url": url,
                "region": region,
                "account_uid": 0,
            }
        except Exception as e:
            logger.error(f"Raw parse also failed: {e}")
            return None

    # ── Step 3: GetLoginData ───────────────────────────────

    async def get_login_data(
        self,
        jwt_token: str,
        base_url: Optional[str] = None,
        access_token: Optional[str] = None,
        retries: int = 3,
    ) -> Optional[Tuple[str, int, str, int]]:
        """
        GetLoginData -> whisper_ip:port + online_ip:port.
        Uses the URL from MajorLogin response (base_url), or falls back.
        """
        url = base_url.rstrip("/") + "/GetLoginData" if base_url else LOGIN_DATA_URL_FALLBACK

        data = bytes.fromhex(TEMPLATE_HEX)

        new_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data = data.replace(OLD_DATE.encode(), new_date.encode())

        if access_token:
            data = data.replace(OLD_ACCESS_TOKEN.encode(), access_token.encode())

        import hashlib
        sig_input = f"free_fire{new_date}WmfdlkTOtsflIWMx4bpg5m4bpg5V31m0bpgm4bpg5mO24bpgN31m0bpgZ31m0m4G"
        sig_md5 = hashlib.md5(sig_input.encode()).hexdigest()
        data = data.replace(OLD_SIGNATURE_MD5.encode(), sig_md5.encode())

        encrypted = _encrypt_api(data.hex())
        payload = bytes.fromhex(encrypted)

        host = url.split("//")[1].split("/")[0] if "//" in url else "clientbp.ggpolarbear.com"
        headers = {
            "X-Unity-Version": "2018.4.11f1",
            "ReleaseVersion": "OB54",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-GA": "v1 1",
            "Content-Length": str(len(payload)),
            "User-Agent": UA_DALVIK,
            "Authorization": f"Bearer {jwt_token}",
            "Host": host,
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
        }

        for attempt in range(retries):
            try:
                resp = await self.http.post(
                    url, headers=headers, content=payload, timeout=30
                )
                if resp.status_code == 200 and len(resp.content) > 10:
                    server_info = self._parse_server_info(resp.content.hex())
                    if server_info:
                        whisper_ip, whisper_port, online_ip, online_port = server_info
                        logger.info(
                            f"LoginData: whisper={whisper_ip}:{whisper_port}, "
                            f"online={online_ip}:{online_port}"
                        )
                        return server_info
                logger.warning(
                    f"LoginData attempt {attempt+1}: status={resp.status_code}, "
                    f"body_len={len(resp.content)}"
                )
            except Exception as e:
                logger.warning(f"LoginData attempt {attempt+1}/{retries} failed: {e}")
            await asyncio.sleep(2)

        logger.error(f"GetLoginData failed after {retries} attempts")
        return None

    def _parse_server_info(self, hex_data: str) -> Optional[Tuple[str, int, str, int]]:
        """Parse GetLoginData response to extract server IPs and ports."""
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

            whisper_addr = result_dict.get("32", "")
            if isinstance(whisper_addr, dict):
                whisper_addr = whisper_addr.get("1", whisper_addr.get("data", ""))
            online_addr = result_dict.get("14", "")
            if isinstance(online_addr, dict):
                online_addr = online_addr.get("1", online_addr.get("data", ""))

            if not whisper_addr or not online_addr:
                logger.warning(f"Missing server addresses. Keys: {list(result_dict.keys())}")
                return None

            whisper_ip = whisper_addr[: len(whisper_addr) - 6]
            whisper_port = int(whisper_addr[len(whisper_addr) - 5:])
            online_ip = online_addr[: len(online_addr) - 6]
            online_port = int(online_addr[len(online_addr) - 5:])

            return whisper_ip, whisper_port, online_ip, online_port
        except Exception as e:
            logger.error(f"Server info parse failed: {e}")
            return None

    # ── Connection Token ──────────────────────────────────

    async def build_connection_token(
        self, jwt_token: str, key: bytes, iv: bytes, timestamp: int, account_id: int
    ) -> str:
        """Build the final connection token for TCP socket auth."""
        import jwt as pyjwt

        try:
            decoded = pyjwt.decode(jwt_token, options={"verify_signature": False})
            account_id = decoded.get("account_id", account_id)
        except Exception:
            pass

        token_hex = jwt_token.encode().hex()
        key_b = key if isinstance(key, bytes) else bytes.fromhex(key)
        iv_b = iv if isinstance(iv, bytes) else bytes.fromhex(iv)

        try:
            cipher = AES.new(key_b, AES.MODE_CBC, iv_b)
            encrypted = cipher.encrypt(pad(bytes.fromhex(token_hex), AES.block_size)).hex()
        except Exception as e:
            logger.error(f"Token encryption failed: {e}")
            return ""

        head_len = len(encrypted) // 2
        head_len_hex = hex(head_len)[2:]

        encoded_acc = hex(account_id)[2:]
        time_hex = hex(timestamp)[2:]

        acc_len = len(encoded_acc)
        if acc_len == 9:
            zeros = "0000000"
        elif acc_len == 8:
            zeros = "00000000"
        elif acc_len == 10:
            zeros = "000000"
        elif acc_len == 7:
            zeros = "000000000"
        else:
            zeros = "0" * max(0, 17 - acc_len - len(time_hex) - len(head_len_hex))

        head = f"0115{zeros}{encoded_acc}{time_hex}00000{head_len_hex}"
        return head + encrypted
