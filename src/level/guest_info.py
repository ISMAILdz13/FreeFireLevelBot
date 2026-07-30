"""
Guest Info Module
Queries the Garena GetPlayerPersonalShow API to get:
  - Nickname, level, EXP, rank
  - Likes received
  - Clan name and level
  - Region, gender, language
  - Ban/blacklist status
  - Last login time
  - Credit score

The flow:
  1. Guest OAuth → access_token + open_id
  2. MajorLogin → JWT token (if fails → account is BANNED)
  3. GetPlayerPersonalShow → full player info
"""

import json
import base64
import logging
from datetime import datetime
from typing import Optional

import httpx
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

logger = logging.getLogger("levelbot.guest_info")

# ── Endpoints ─────────────────────────────────────────────

PLAYER_INFO_URL = "https://clientbp.ggpolarbear.com/GetPlayerPersonalShow"

# ── AES key/IV for UID encryption (same as API encryption) ──

UID_KEY = b"Yg&tc%DEuh6%Zc^8"
UID_IV = b"6oyZDr22E3ychjM%"


def _encrypt_uid(uid: str) -> bytes:
    """Encrypt a UID for the GetPlayerPersonalShow request."""
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from dev_generator_pb2 import dev_generator

    # Create protobuf with UID
    msg = dev_generator()
    msg.saturn_ = int(uid)
    msg.garena = 1
    raw = msg.SerializeToString()

    # Encrypt with AES-CBC
    cipher = AES.new(UID_KEY, AES.MODE_CBC, UID_IV)
    encrypted = cipher.encrypt(pad(raw, AES.block_size))
    return encrypted


class GuestInfo:
    """Fetches and displays guest account information."""

    def __init__(self, http_client: httpx.AsyncClient):
        self.http = http_client

    async def fetch(
        self, uid: str, password: str, jwt_token: Optional[str] = None
    ) -> Optional[dict]:
        """
        Fetch full guest info.

        Args:
            uid: Guest account UID
            password: Guest account password
            jwt_token: Pre-authenticated JWT (optional — if None, we authenticate)

        Returns:
            dict with keys: nickname, level, exp, likes, rank, clan_name,
                           clan_level, region, ban_status, last_login, etc.
            or None if all steps fail.
        """
        result = {
            "uid": uid,
            "nickname": "Unknown",
            "level": 0,
            "exp": 0,
            "likes": 0,
            "rank": 0,
            "max_rank": 0,
            "clan_name": "None",
            "clan_level": 0,
            "clan_id": 0,
            "region": "Unknown",
            "gender": "Unknown",
            "language": "Unknown",
            "ban_status": "Unknown",
            "ban_reason": "",
            "credit_score": 0,
            "last_login": "Unknown",
            "account_created": "Unknown",
            "release_version": "Unknown",
            "has_elite_pass": False,
            "title": 0,
        }

        # Step 1: Authenticate if we don't have a JWT
        from .auth import LevelAuth

        auth = LevelAuth(self.http)

        if not jwt_token:
            # Guest OAuth
            oauth = await auth.guest_token(uid, password)
            if not oauth:
                result["ban_status"] = "DEAD"
                result["ban_reason"] = "Guest OAuth failed — account deleted, password invalid, or rate-limited. Wait 30 min and retry."
                return result
            access_token, open_id = oauth

            # MajorLogin
            login = await auth.major_login(access_token, open_id)
            if not login or (isinstance(login, dict) and login.get("error")):
                # Check if it's a server error (503) vs actual ban
                last_status = login.get("last_status", 0) if isinstance(login, dict) else 0
                
                if last_status == 503:
                    result["ban_status"] = "SERVER_DOWN"
                    result["ban_reason"] = "Garena MajorLogin server is temporarily unavailable (503). Not a ban."
                elif last_status in (400, 401, 403):
                    result["ban_status"] = "BANNED"
                    result["ban_reason"] = f"MajorLogin rejected (HTTP {last_status}) — account may be banned"
                else:
                    result["ban_status"] = "UNKNOWN"
                    result["ban_reason"] = f"MajorLogin failed (HTTP {last_status or 'no response'})"
                # Still try to get player info with the access token
                jwt_token = access_token
            else:
                jwt_token = login["token"]
                result["ban_status"] = "CLEAR"
        else:
            # We have a JWT, assume clear
            result["ban_status"] = "CLEAR"
            access_token = jwt_token

        # Step 2: GetPlayerPersonalShow
        player_info = await self._get_player_personal_show(uid, jwt_token)
        if not player_info:
            if result["ban_status"] == "CLEAR":
                result["ban_status"] = "BLACKLISTED"
                result["ban_reason"] = "GetPlayerPersonalShow failed — account may be blacklisted"
            return result

        # Step 3: Parse the response
        self._parse_info(result, player_info, uid)

        return result

    async def _get_player_personal_show(
        self, uid: str, jwt_token: str
    ) -> Optional[bytes]:
        """Call GetPlayerPersonalShow API."""
        encrypted_uid = _encrypt_uid(uid)

        headers = {
            "User-Agent": "Dalvik/2.1.0",
            "Connection": "Keep-Alive",
            "Accept-Encoding": "gzip",
            "Authorization": f"Bearer {jwt_token}",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Unity-Version": "2018.4.11f1",
            "X-GA": "v1 1",
            "ReleaseVersion": "OB54",
        }

        for attempt in range(3):
            try:
                resp = await self.http.post(
                    PLAYER_INFO_URL,
                    headers=headers,
                    content=encrypted_uid,
                    timeout=15,
                )
                if resp.status_code == 200 and len(resp.content) > 10:
                    logger.info(f"GetPlayerPersonalShow OK ({len(resp.content)} bytes)")
                    return resp.content
                logger.warning(
                    f"GetPlayerPersonalShow attempt {attempt+1}: "
                    f"status={resp.status_code}, len={len(resp.content)}"
                )
            except Exception as e:
                logger.warning(f"GetPlayerPersonalShow attempt {attempt+1} failed: {e}")
            import asyncio
            await asyncio.sleep(1)

        return None

    def _parse_info(self, result: dict, raw_data: bytes, uid: str):
        """Parse the GetPlayerPersonalShow protobuf response."""
        try:
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from data_pb2 import AccountPersonalShowInfo

            info = AccountPersonalShowInfo()
            info.ParseFromString(raw_data)

            # Basic info
            basic = info.basic_info
            if basic:
                result["nickname"] = basic.nickname or "Unknown"
                result["level"] = basic.level or 0
                result["exp"] = basic.exp or 0
                result["likes"] = basic.liked or 0
                result["rank"] = basic.rank or 0
                result["max_rank"] = basic.max_rank or 0
                result["region"] = basic.region or "Unknown"
                result["has_elite_pass"] = basic.has_elite_pass
                result["title"] = basic.title or 0
                result["release_version"] = basic.release_version or "Unknown"

                if basic.last_login_at:
                    try:
                        ts = basic.last_login_at / 1000
                        result["last_login"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                    except Exception:
                        result["last_login"] = str(basic.last_login_at)

                if basic.create_at:
                    try:
                        ts = basic.create_at / 1000
                        result["account_created"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                    except Exception:
                        result["account_created"] = str(basic.create_at)

            # Clan info
            clan = info.clan_basic_info
            if clan and clan.clan_id:
                result["clan_name"] = clan.clan_name or "Unknown"
                result["clan_level"] = clan.clan_level or 0
                result["clan_id"] = clan.clan_id
            else:
                result["clan_name"] = "None"
                result["clan_level"] = 0

            # Social info
            social = info.social_info
            if social:
                # Gender enum
                from data_pb2 import Gender
                gender_map = {0: "Unknown", 1: "Male", 2: "Female"}
                result["gender"] = gender_map.get(social.gender, "Unknown")

                # Language enum
                from data_pb2 import Language
                lang_map = {
                    0: "None", 1: "EN", 2: "CN_Simplified", 3: "CN_Traditional",
                    4: "Thai", 5: "Vietnamese", 6: "Indonesian", 7: "Portuguese",
                    8: "Spanish", 9: "Russian", 10: "Turkish", 11: "German",
                    12: "French", 13: "Arabic", 14: "Hindi", 15: "Bengali",
                    16: "Burmese", 17: "Urdu", 18: "Japanese", 19: "Korean",
                    20: "Romanian",
                }
                result["language"] = lang_map.get(social.language, f"Lang_{social.language}")

            # Credit score (ban indicator)
            credit = info.credit_score_info
            if credit and credit.HasField("score"):
                result["credit_score"] = credit.score
                if credit.status:
                    # status > 0 may indicate ban/penalty
                    if credit.status >= 100:
                        result["ban_status"] = "BLACKLISTED"
                        result["ban_reason"] = f"Credit score penalty (status={credit.status})"
                    elif result["ban_status"] == "CLEAR":
                        result["ban_status"] = "CLEAR"
                        result["ban_reason"] = f"Credit score: {credit.score}"

        except Exception as e:
            logger.error(f"Failed to parse player info: {e}")
            # Fallback: try raw protobuf decoder
            self._parse_raw(result, raw_data, uid)

    def _parse_raw(self, result: dict, raw_data: bytes, uid: str):
        """Fallback: parse with raw protobuf decoder."""
        try:
            from protobuf_decoder.protobuf_decoder import Parser

            hex_data = raw_data.hex()
            parsed = Parser().parse(hex_data)

            for r in parsed:
                field_num = int(r.field)
                if r.wire_type == "length_delimited":
                    for sub in r.data.results:
                        sub_num = int(sub.field)
                        # Field 1 = basic_info, field 6 = clan_info
                        if field_num == 1:
                            if sub_num == 3 and sub.wire_type in ("string", "bytes"):
                                result["nickname"] = sub.data
                            elif sub_num == 6 and sub.wire_type == "varint":
                                result["level"] = int(sub.data)
                            elif sub_num == 7 and sub.wire_type == "varint":
                                result["exp"] = int(sub.data)
                            elif sub_num == 21 and sub.wire_type == "varint":
                                result["likes"] = int(sub.data)
                            elif sub_num == 5 and sub.wire_type in ("string", "bytes"):
                                result["region"] = sub.data
                            elif sub_num == 14 and sub.wire_type == "varint":
                                result["rank"] = int(sub.data)
                            elif sub_num == 50 and sub.wire_type in ("string", "bytes"):
                                result["release_version"] = sub.data
                        elif field_num == 6:
                            if sub_num == 2 and sub.wire_type in ("string", "bytes"):
                                result["clan_name"] = sub.data
                            elif sub_num == 4 and sub.wire_type == "varint":
                                result["clan_level"] = int(sub.data)
        except Exception as e:
            logger.error(f"Raw parse also failed: {e}")
