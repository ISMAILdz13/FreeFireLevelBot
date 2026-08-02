"""
Level Bot Authentication — uses protobuf MajorLogin (same as ClanGloryBot)
Builds the MajorLogin payload dynamically, NOT from a stale template hex.
"""

import asyncio
import logging
import hashlib
from datetime import datetime
from typing import Optional, Tuple

import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

logger = logging.getLogger("levelbot.auth")

# ── Endpoints (same as ClanGloryBot) ──────────────────────

OAUTH_V2_URL = "https://ffmconnect.live.gop.garenanow.com/api/v2/oauth/guest/token:grant"
OAUTH_V1_URL = "https://100067.connect.garena.com/oauth/guest/token/grant"
MAJOR_LOGIN_URL = "https://loginbp.ggpolarbear.com/MajorLogin"
LOGIN_DATA_URL_FALLBACK = "https://clientbp.ggpolarbear.com/GetLoginData"

OAUTH_CLIENT_SECRET = "2ee44819e9b4598845141067b281621874d0d5d7af9d8f7e00c1e54715b7d1e3"

# ── AES key/IV (same as ClanGloryBot) ────────────────────

AES_KEY = bytes([89, 103, 38, 116, 99, 37, 68, 69, 117, 104, 54, 37, 90, 99, 94, 56])
AES_IV = bytes([54, 111, 121, 90, 68, 114, 50, 50, 69, 51, 121, 99, 104, 106, 77, 37])

# ── Client version (same as ClanGloryBot) ────────────────

CLIENT_VERSION = "1.126.2"
CLIENT_VERSION_CODE = "2024010012"

# ── Headers (same as ClanGloryBot — Android 11, OB54) ────

HTTP_HEADERS = {
    'User-Agent': "Dalvik/2.1.0 (Linux; U; Android 11; SM-A145F Build/RP1A.200720.012)",
    'Connection': "Keep-Alive",
    'Accept-Encoding': "gzip",
    'Content-Type': "application/octet-stream",
    'Expect': "100-continue",
    'X-Unity-Version': "2018.4.11f1",
    'X-GA': "v1 1",
    'ReleaseVersion': "OB54",
}


def _build_major_login_payload(open_id: str, access_token: str) -> bytes:
    """Build encrypted MajorLogin payload using protobuf message (same as ClanGloryBot)."""
    from .Pb2.MajoRLoGinrEq_pb2 import MajorLogin

    ml = MajorLogin()
    ml.event_time = str(datetime.now())[:-7]  # "2026-08-02 17:09" — no seconds
    ml.game_name = "free fire"
    ml.platform_id = 2
    ml.client_version = CLIENT_VERSION
    ml.client_version_code = CLIENT_VERSION_CODE
    ml.system_software = "Android OS 11 / API-30"
    ml.system_hardware = "Handheld"
    ml.device_type = "Handheld"
    ml.open_id = open_id
    ml.open_id_type = "4"
    ml.access_token = access_token
    ml.platform_sdk_id = 2
    ml.login_by = 3
    ml.login_open_id_type = 4
    ml.origin_platform_type = "4"
    ml.primary_platform_type = "4"

    raw = ml.SerializeToString()
    enc = AES.new(AES_KEY, AES.MODE_CBC, AES_IV).encrypt(pad(raw, 16))
    return enc


class LevelAuth:
    def __init__(self, http_client: httpx.AsyncClient):
        self.http = http_client

    # ── Step 1: Guest OAuth (v2 → v1 fallback) ─────────────

    async def guest_token(self, uid: str, password: str, retries: int = 3) -> Optional[Tuple[str, str]]:
        # Try v2 (JSON payload) first
        for attempt in range(retries):
            try:
                resp = await self.http.post(
                    OAUTH_V2_URL,
                    json={
                        "client_id": 100067,
                        "client_secret": OAUTH_CLIENT_SECRET,
                        "client_type": 2,
                        "password": password,
                        "response_type": "token",
                        "uid": int(uid),
                    },
                    headers={
                        "Content-Type": "application/json; charset=utf-8",
                        "User-Agent": "GarenaMSDK/4.0.19P10(I2404 ;Android 15;en;US;)",
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    odata = data.get("data", data)
                    at = odata.get("access_token")
                    oid = odata.get("open_id")
                    if at and oid:
                        logger.info(f"Guest token acquired (v2) for UID {uid}")
                        return at, oid
                    error = odata.get("error", data.get("error"))
                    if error:
                        logger.warning(f"OAuth v2 error: {error}")
                        break
                logger.warning(f"OAuth v2 attempt {attempt+1}: HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"OAuth v2 attempt {attempt+1}/{retries} failed: {e}")
            await asyncio.sleep(1)

        # Fall back to v1 (form-urlencoded)
        logger.info("Falling back to OAuth v1")
        for attempt in range(retries):
            try:
                resp = await self.http.post(
                    OAUTH_V1_URL,
                    data={
                        "uid": uid,
                        "password": password,
                        "response_type": "token",
                        "client_type": "2",
                        "client_secret": OAUTH_CLIENT_SECRET,
                        "client_id": "100067",
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "GarenaMSDK/4.0.19P8(ASUS_Z01QD ;Android 12;en;US;)",
                    },
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    at = data.get("access_token")
                    oid = data.get("open_id")
                    if at and oid:
                        logger.info(f"Guest token acquired (v1) for UID {uid}")
                        return at, oid
                logger.warning(f"Guest token v1 attempt {attempt+1}: HTTP {resp.status_code}")
            except Exception as e:
                logger.warning(f"Guest token v1 attempt {attempt+1}/{retries} failed: {e}")
                await asyncio.sleep(2)

        logger.error(f"Failed to get guest token for UID {uid}")
        return None

    # ── Step 2: MajorLogin (protobuf payload, single endpoint) ──

    async def major_login(self, access_token: str, open_id: str, retries: int = 3) -> Optional[dict]:
        payload = _build_major_login_payload(open_id, access_token)

        headers = {**HTTP_HEADERS, "Authorization": f"Bearer {access_token}"}

        last_status = 0
        for attempt in range(retries):
            try:
                resp = await self.http.post(
                    MAJOR_LOGIN_URL, headers=headers, content=payload, timeout=20
                )
                last_status = resp.status_code

                if resp.status_code == 200 and len(resp.content) > 30:
                    result = self._parse_major_login_response(resp.content)
                    if result and result.get("token"):
                        result["payload"] = payload  # Save for GetLoginData reuse
                        logger.info(f"MajorLogin successful — region={result.get('region', '?')}, uid={result.get('account_uid', '?')}")
                        return result
                    logger.warning(f"MajorLogin: 200 OK but parse failed (body_len={len(resp.content)})")
                elif resp.status_code == 200 and len(resp.content) <= 30:
                    body_hex = resp.content.hex()
                    logger.warning(f"MajorLogin: 200 OK but tiny response ({len(resp.content)} bytes)")
                    logger.warning(f"  Raw hex: {body_hex}")
                    # Try to decode as protobuf
                    try:
                        from .Pb2.MajoRLoGinrEs_pb2 import MajorLoginRes
                        msg = MajorLoginRes()
                        msg.ParseFromString(resp.content)
                        logger.warning(f"  Parsed: token={bool(msg.token)}, uid={msg.account_uid}, region={msg.region}")
                        if not msg.token:
                            logger.warning(f"  >>> BANNED or REJECTED — server returned no JWT token")
                    except Exception as pe:
                        logger.warning(f"  Parse error: {pe}")
                    # Try raw protobuf decode
                    try:
                        from protobuf_decoder.protobuf_decoder import Parser
                        parsed = Parser().parse(body_hex)
                        for r in parsed:
                            logger.warning(f"  field {r.field} ({r.wire_type}): {r.data}")
                    except Exception:
                        pass
                else:
                    logger.warning(f"MajorLogin attempt {attempt+1}: status={resp.status_code}, body_len={len(resp.content)}")
            except Exception as e:
                logger.warning(f"MajorLogin attempt {attempt+1}/{retries} failed: {e}")
            await asyncio.sleep(2)

        logger.error(f"MajorLogin failed after {retries} attempts (last status: {last_status})")
        return {"error": "major_login_failed", "last_status": last_status}

    def _parse_major_login_response(self, content: bytes) -> Optional[dict]:
        """Parse MajorLogin protobuf response — uses correct field names (key, iv, not ak, aiv)."""
        try:
            from .Pb2.MajoRLoGinrEs_pb2 import MajorLoginRes

            msg = MajorLoginRes()
            msg.ParseFromString(content)

            if not msg.token:
                logger.warning("MajorLoginRes: no token in response (banned?)")
                return None

            key = msg.key if isinstance(msg.key, bytes) else bytes.fromhex(msg.key)
            iv = msg.iv if isinstance(msg.iv, bytes) else bytes.fromhex(msg.iv)

            # timestamp is a raw int64 (nanoseconds combined)
            ts = msg.timestamp

            return {
                "token": msg.token,
                "key": key,
                "iv": iv,
                "timestamp": ts,
                "url": msg.url if msg.url else LOGIN_DATA_URL_FALLBACK,
                "region": msg.region if msg.region else "IND",
                "account_uid": msg.account_uid if msg.account_uid else 0,
            }
        except Exception as e:
            logger.warning(f"Protobuf parse failed: {e}")
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

            token = result_dict.get(8, "")
            if isinstance(token, bytes):
                token = token.decode("utf-8", errors="replace")
            if not token:
                return None

            key_raw = result_dict.get(22, b"")
            iv_raw = result_dict.get(23, b"")
            key = key_raw if isinstance(key_raw, bytes) else b""
            iv = iv_raw if isinstance(iv_raw, bytes) else b""

            url = result_dict.get(10, LOGIN_DATA_URL_FALLBACK)
            if isinstance(url, bytes):
                url = url.decode("utf-8", errors="replace")
            region = result_dict.get(2, "IND")
            if isinstance(region, bytes):
                region = region.decode("utf-8", errors="replace")
            account_uid = result_dict.get(1, 0)

            return {
                "token": token if isinstance(token, str) else token.decode("utf-8", errors="replace"),
                "key": key, "iv": iv, "timestamp": result_dict.get(21, 0),
                "url": url, "region": region, "account_uid": account_uid,
            }
        except Exception as e:
            logger.error(f"Raw parse also failed: {e}")
            return None

    # ── Step 3: GetLoginData (reuse MajorLogin payload) ────

    async def get_login_data(
        self, jwt_token: str, base_url: Optional[str] = None,
        access_token: Optional[str] = None,
        major_login_payload: Optional[bytes] = None, retries: int = 3,
    ) -> Optional[Tuple[str, int, str, int]]:
        url = base_url.rstrip("/") + "/GetLoginData" if base_url else LOGIN_DATA_URL_FALLBACK

        # Reuse MajorLogin payload (same as ClanGloryBot)
        if major_login_payload:
            payload = major_login_payload
        elif access_token:
            payload = _build_major_login_payload("", access_token)
        else:
            logger.error("No payload available for GetLoginData")
            return None

        host = url.split("//")[1].split("/")[0] if "//" in url else "clientbp.ggpolarbear.com"
        headers = {**HTTP_HEADERS, "Authorization": f"Bearer {jwt_token}", "Host": host}

        for attempt in range(retries):
            try:
                resp = await self.http.post(url, headers=headers, content=payload, timeout=30)
                if resp.status_code == 200 and len(resp.content) > 10:
                    server_info = self._parse_server_info_pb(resp.content)
                    if server_info:
                        return server_info
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

    # ── Step 4: Connection Token (xC4 — same as ClanGloryBot) ──

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
