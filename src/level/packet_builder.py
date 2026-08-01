"""
Packet Builder — rewritten to use xC4 GeneRaTePk framing.
Fixes: 6-byte header (not 7), proper start-match (269+214+9), full join fields.
"""

import asyncio
from typing import Dict, Any, Optional
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


class PacketBuilder:
    """
    Builds encrypted protobuf packets using xC4 GeneRaTePk framing.

    Usage:
        pb = PacketBuilder(key, iv)
        packet = pb.join_team("1785611837")
        socket.send(packet)
    """

    def __init__(self, key: bytes, iv: bytes, region: str = "ME"):
        self.key = key if isinstance(key, bytes) else bytes.fromhex(key)
        self.iv = iv if isinstance(iv, bytes) else bytes.fromhex(iv)
        self.region = region.lower()

    # ── xC4 packet type by region ──────────────────────────

    def _pkt_type(self) -> str:
        if self.region == "ind":
            return "0514"
        elif self.region == "bd":
            return "0519"
        return "0515"

    # ── Encryption (same as xC4 EnC_PacKeT) ──────────────────

    def _encrypt(self, hex_data: str) -> str:
        """AES-CBC encrypt hex string, return hex ciphertext (same as xC4 EnC_PacKeT)."""
        plain = bytes.fromhex(hex_data)
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        return cipher.encrypt(pad(plain, AES.block_size)).hex()

    # ── Varint encoding (same as xC4 EnC_Vr) ────────────────

    @staticmethod
    def _encode_varint(n: int) -> bytes:
        if n < 0:
            raise ValueError("Number must be non-negative")
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
        h = hex(n)[2:]
        return h

    # ── Protobuf field builders (same as xC4 CrEaTe_ProTo) ──

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

    # ── GeneRaTePk — correct 6-byte header framing ──────────

    def _generate_packet(self, proto_hex: str, pkt_type: str) -> bytes:
        """
        Build packet with xC4 GeneRaTePk framing:
          [pkt_type(4)][zeros(6-len)][length_hex][encrypted_data]

        Total header = 4 + 8 = 12 hex chars = 6 bytes (CORRECT).
        Old PacketBuilder used 4 + 10 = 14 hex = 7 bytes (WRONG).
        """
        encrypted = self._encrypt(proto_hex)
        length_hex = self._dec_to_hex(len(encrypted) // 2)

        # Pad zeros so header = pkt_type(4) + zeros + length = 12 hex total
        # len == 2 → 6 zeros, len == 3 → 5 zeros, len == 4 → 4 zeros, len == 5 → 3 zeros
        if len(length_hex) == 2:
            header = pkt_type + "000000" + length_hex
        elif len(length_hex) == 3:
            header = pkt_type + "00000" + length_hex
        elif len(length_hex) == 4:
            header = pkt_type + "0000" + length_hex
        elif len(length_hex) == 5:
            header = pkt_type + "000" + length_hex
        else:
            header = pkt_type + length_hex.rjust(8, "0")

        return bytes.fromhex(header + encrypted)

    def build_packet(self, fields: Dict[int, Any], pkt_type: str = None) -> bytes:
        """Build a complete encrypted packet with correct framing."""
        proto_hex = self._build_protobuf(fields).hex()
        return self._generate_packet(proto_hex, pkt_type or self._pkt_type())

    # ── Game-specific packets ────────────────────────────────

    def join_team(self, team_code: str, uid: int = 0) -> bytes:
        """
        Build join-squad packet — full fields matching xC4 redzed.
        Uses string code (field 2.10) + owner UID + device/version info.
        """
        owner_uid = uid if uid else 1
        fields = {
            1: 4,
            2: {
                1: owner_uid,
                3: owner_uid,
                8: 1,
                9: {
                    2: 161,
                    4: "y[WW",
                    6: 11,
                    8: "1.114.18",
                    9: 3,
                    10: 1,
                },
                10: str(team_code),
            },
        }
        return self.build_packet(fields)

    def start_match_detailed(self, uid: int) -> bytes:
        """
        Build field 269 (detailed start-match) — includes device info.
        This is the PRIMARY match trigger in ClanGloryBot.
        """
        fields = {
            1: 269,
            2: {
                1: uid,
                9: {
                    2: 800,
                    6: 11,
                    8: "1.111.5",
                    9: 5,
                    10: 4,
                },
            },
        }
        return self.build_packet(fields)

    def start_match_simple(self) -> bytes:
        """
        Build field 214 (simple start-match) — backup trigger.
        """
        fields = {
            1: 214,
            2: {
                1: 1,
            },
        }
        return self.build_packet(fields)

    def start_match_ready(self, uid: int) -> bytes:
        """
        Build field 9 (ready signal) — tells server "I'm ready".
        Must be sent AFTER 269 and 214, not instead of them.
        """
        fields = {
            1: 9,
            2: {
                1: uid,
            },
        }
        return self.build_packet(fields)

    def leave_team(self, uid: int = 0) -> bytes:
        """Build leave-squad packet — field 1=7."""
        owner_uid = uid if uid else 1
        fields = {
            1: 7,
            2: {
                1: owner_uid,
            },
        }
        return self.build_packet(fields)

    def chat_message(self, text: str, sender_uid: int) -> bytes:
        """Build in-game chat message packet."""
        from datetime import datetime
        fields = {
            1: 1,
            2: {
                1: 12947146032,
                2: sender_uid,
                3: 2,
                4: str(text),
                5: int(datetime.now().timestamp()),
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
                10: "ME",
            },
        }
        return self.build_packet(fields, "1215")
