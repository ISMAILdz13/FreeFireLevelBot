"""
Packet Builder — uses xC4 GeneRaTePk framing (1:1 with ClanGloryBot).
Fixed: GenJoinSquadsPacket format, full field-269 device info, version 1.126.2.
"""

import asyncio
import time
from typing import Dict, Any, Optional
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

# Current Free Fire version (matches ClanGloryBot)
CLIENT_VERSION = "1.126.2"


class PacketBuilder:
    """Builds encrypted protobuf packets using xC4 GeneRaTePk framing."""

    def __init__(self, key: bytes, iv: bytes, region: str = "ME"):
        self.key = key if isinstance(key, bytes) else bytes.fromhex(key)
        self.iv = iv if isinstance(iv, bytes) else bytes.fromhex(iv)
        self.region = region.lower()

    def _pkt_type(self) -> str:
        if self.region == "ind":
            return "0514"
        elif self.region == "bd":
            return "0519"
        return "0515"

    def _encrypt(self, hex_data: str) -> str:
        plain = bytes.fromhex(hex_data)
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        return cipher.encrypt(pad(plain, AES.block_size)).hex()

    @staticmethod
    def _encode_varint(n: int) -> bytes:
        if n < 0:
            return b""
        buf = []
        while True:
            byte = n & 0x7F
            n >>= 7
            if n:
                byte |= 0x80
            buf.append(byte)
            if not n:
                break
        return bytes(buf)

    @staticmethod
    def _dec_to_hex(n: int) -> str:
        return hex(n)[2:]

    @classmethod
    def _varint_field(cls, field_number: int, value: int) -> bytes:
        header = (field_number << 3) | 0
        return cls._encode_varint(header) + cls._encode_varint(value)

    @classmethod
    def _length_delimited_field(cls, field_number: int, value: Any) -> bytes:
        header = (field_number << 3) | 2
        encoded = value.encode() if isinstance(value, str) else value
        return cls._encode_varint(header) + cls._encode_varint(len(encoded)) + encoded

    @classmethod
    def _build_protobuf(cls, fields: Dict[int, Any]) -> bytes:
        packet = bytearray()
        for field, value in fields.items():
            if isinstance(value, dict):
                nested = cls._build_protobuf(value)
                packet.extend(cls._length_delimited_field(field, nested))
            elif isinstance(value, int):
                packet.extend(cls._varint_field(field, value))
            elif isinstance(value, (str, bytes)):
                packet.extend(cls._length_delimited_field(field, value))
        return bytes(packet)

    def _generate_packet(self, proto_hex: str, pkt_type: str) -> bytes:
        """GeneRaTePk framing: [pkt_type(4)][zeros][length_hex][encrypted_data] — 6-byte header."""
        encrypted = self._encrypt(proto_hex)
        length_hex = self._dec_to_hex(len(encrypted) // 2)

        if len(length_hex) == 1:
            header = pkt_type + "0000000" + length_hex
        elif len(length_hex) == 2:
            header = pkt_type + "000000" + length_hex
        elif len(length_hex) == 3:
            header = pkt_type + "00000" + length_hex
        elif len(length_hex) == 4:
            header = pkt_type + "0000" + length_hex
        elif len(length_hex) == 5:
            header = pkt_type + "000" + length_hex
        elif len(length_hex) == 6:
            header = pkt_type + "00" + length_hex
        elif len(length_hex) == 7:
            header = pkt_type + "0" + length_hex
        else:
            header = pkt_type + length_hex

        return bytes.fromhex(header + encrypted)

    def build_packet(self, fields: Dict[int, Any], pkt_type: str = None) -> bytes:
        proto_hex = self._build_protobuf(fields).hex()
        return self._generate_packet(proto_hex, pkt_type or self._pkt_type())

    # ── Join squad (GenJoinSquadsPacket — EXACT match to ClanGloryBot) ──

    def join_squad(self, squad_code: str) -> bytes:
        """
        GenJoinSquadsPacket — join squad using full squad_code string.
        EXACT match to ClanGloryBot's GenJoinSquadsPacket.
        """
        fields = {
            1: 4,
            2: {
                4: bytes.fromhex("01090a0b121920"),
                5: str(squad_code),
                6: 6,
                8: 1,
                9: {
                    2: 800,
                    6: 11,
                    8: CLIENT_VERSION,
                    9: 5,
                    10: 1,
                },
            },
        }
        return self.build_packet(fields)

    def open_squad(self) -> bytes:
        """OpEnSq — leader opens squad for matchmaking (EXACT match to ClanGloryBot)."""
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
                    8: CLIENT_VERSION,
                    9: 2,
                    10: 4,
                },
            },
        }
        return self.build_packet(fields)

    # ── Start match (EXACT match to ClanGloryBot) ──

    def start_match_detailed(self, uid: int) -> bytes:
        """
        Field 269 — detailed start-match with FULL device info.
        EXACT match to ClanGloryBot's start_match_leader.
        """
        fields = {
            1: 269,
            2: {
                1: 8,
                2: 8,
                3: 11,
                4: 1,
                5: "samsung",
                6: "SM-A145F",
                7: "arm64-v8a",
                8: "f538dc9b-cec9-43cd-8125-95f7f4f1f7e3",
                9: "FFD58FB4F76F648C2A5E21EBCFA3AAE81B4C9B7D97",
                10: "voice",
                11: "V2059",
                12: "mt6785",
                13: "AFFD58FB4F76F648C2A5E21EBCFA3AAE81B4C9B7D97",
                14: f"{self.region.upper()}_1999120752610979840",
                15: 269,
            },
        }
        return self.build_packet(fields)

    def start_match_simple(self) -> bytes:
        """Field 214 — simple start-match (EXACT match to ClanGloryBot)."""
        fields = {1: 214, 2: {1: 1}}
        return self.build_packet(fields)

    def start_match_ready(self, uid: int) -> bytes:
        """Field 9 — ready signal (EXACT match to ClanGloryBot)."""
        fields = {1: 9, 2: {1: uid}}
        return self.build_packet(fields)

    # ── Leave squad ──

    def leave_squad(self, uid: int = 0) -> bytes:
        """ExiT — leave squad (field 1=7). ClanGloryBot sends on ONLINE channel."""
        fields = {1: 7, 2: {1: uid if uid else 1}}
        return self.build_packet(fields)

    # ── Keepalive (field 99) ──

    def keepalive(self) -> bytes:
        """Field 99 keepalive with timestamp (EXACT match to ClanGloryBot)."""
        fields = {1: 99, 2: {1: int(time.time()), 2: 1}}
        return self.build_packet(fields)

    def keepalive_chat(self) -> bytes:
        """Field 99 keepalive for chat channel (uses 1215 packet type)."""
        fields = {1: 99, 2: {1: int(time.time()), 2: 1}}
        return self.build_packet(fields, "1215")

    # ── Chat message ──

    def chat_message(self, text: str, sender_uid: int) -> bytes:
        """In-game chat message (uses 1215 packet type)."""
        fields = {
            1: 1,
            2: {
                1: sender_uid,
                2: sender_uid,
                4: str(text),
                5: int(time.time()),
                7: 2,
                9: {
                    1: "LevelBot",
                    2: 902050001,
                    3: 901049014,
                    4: 330,
                    5: 801040108,
                    8: "Friend",
                    10: 1,
                    11: 1,
                },
                10: "en",
            },
        }
        return self.build_packet(fields, "1215")


    # ── Join match room (0e15 packet — same as ClanGloryBot) ──

    def join_match_room(self, group_id: int) -> bytes:
        """Join match room using GroupID (field 1=3, type 0e15).
        Same as ClanGloryBot's join_match."""
        fields = {
            1: 3,
            2: {
                1: group_id,
                2: "",
                8: {1: "IDC3", 2: 149, 3: self.region.upper()},
                9: b"\x01\x03\x04\x07\x09\x0a\x0b\x12\x0e\x16\x19\x20\x1d",
                10: 1,
                12: {},
                13: 1,
                14: 1,
                16: "en",
                22: {1: 21},
            },
        }
        return self.build_packet(fields, "0e15")


    # ── OB54-TCP-BOT level bot packets (1:1 match) ──

    def join_teamcode(self, team_code: str) -> bytes:
        """Join team using code — 1:1 with OB54-TCP-BOT join_teamcode_packet.
        Field 1=4, field 2.5=str(code), same structure as GenJoinSquadsPacket."""
        fields = {
            1: 4,
            2: {
                4: b"\x01\x09\x0a\x0b\x12\x19\x20",
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
        return self.build_packet(fields)

    def start_auto_match(self, uid: int) -> bytes:
        """Start match packet — 1:1 with OB54-TCP-BOT start_auto_packet / FS.
        Field 1=9, field 2={1: UID}. Just spam this — no 269/214 needed."""
        fields = {
            1: 9,
            2: {
                1: uid,
            },
        }
        return self.build_packet(fields)

    def switch_lone_wolf(self, uid: int) -> bytes:
        """Switch to Lone Wolf 1v1 mode — 1:1 with OB54-TCP-BOT SwitchLoneWolfDule.
        Field 1=17, type 0519."""
        fields = {
            1: 17,
            2: {
                1: uid,
                2: 1,
                3: 1,
                4: 43,
                5: "\x0b",
                8: 1,
                19: 1,
            },
        }
        return self.build_packet(fields, "0519")

    # ── Legacy compatibility (deprecated — use join_squad) ──

    def join_team(self, team_code: str, uid: int = 0) -> bytes:
        """DEPRECATED: use join_squad() instead. Kept for backward compat."""
        return self.join_squad(team_code)

    def leave_team(self, uid: int = 0) -> bytes:
        """DEPRECATED: use leave_squad() instead. Kept for backward compat."""
        return self.leave_squad(uid)
