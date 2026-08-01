"""
Packet Builder
Constructs raw protobuf packets for Free Fire TCP protocol.
Handles encryption, varint encoding, and packet framing.

Adapted from level/important_zitado.py and level/byte.py — cleaned up,
type-hinted, and made reusable.
"""

from typing import Dict, Any, Optional
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


class PacketBuilder:
    """
    Builds encrypted protobuf packets for the Free Fire TCP protocol.

    Usage:
        pb = PacketBuilder(key, iv)
        packet = pb.build_packet(0x0515, {1: 9, 2: {1: 12345678}})
        socket.send(packet)
    """

    def __init__(self, key: bytes, iv: bytes):
        self.key = key if isinstance(key, bytes) else bytes.fromhex(key)
        self.iv = iv if isinstance(iv, bytes) else bytes.fromhex(iv)

    # ── Encryption ──────────────────────────────────────────

    def encrypt(self, hex_data: str) -> str:
        """AES-CBC encrypt hex string, return hex ciphertext."""
        plain = bytes.fromhex(hex_data)
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        return cipher.encrypt(pad(plain, AES.block_size)).hex()

    def encrypt_bytes(self, data: bytes) -> bytes:
        """AES-CBC encrypt raw bytes, return encrypted bytes."""
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        return cipher.encrypt(pad(data, AES.block_size))

    # ── Varint encoding ──────────────────────────────────────

    @staticmethod
    def encode_varint(number: int) -> bytes:
        """Encode a non-negative integer as a protobuf varint."""
        if number < 0:
            raise ValueError("Number must be non-negative")
        encoded = []
        while True:
            byte = number & 0x7F
            number >>= 7
            if number:
                byte |= 0x80
            encoded.append(byte)
            if not number:
                break
        return bytes(encoded)

    @staticmethod
    def dec_to_hex(n: int) -> str:
        """Convert integer to hex string, zero-padded to 2 chars."""
        h = hex(n)[2:]
        return h if len(h) >= 2 else "0" + h

    # ── Protobuf field builders ──────────────────────────────

    @classmethod
    def _varint_field(cls, field_number: int, value: int) -> bytes:
        header = (field_number << 3) | 0
        return cls.encode_varint(header) + cls.encode_varint(value)

    @classmethod
    def _length_delimited_field(cls, field_number: int, value: Any) -> bytes:
        header = (field_number << 3) | 2
        encoded = value.encode() if isinstance(value, str) else value
        return cls.encode_varint(header) + cls.encode_varint(len(encoded)) + encoded

    @classmethod
    def build_protobuf(cls, fields: Dict[int, Any]) -> bytes:
        """
        Build a raw protobuf message from a dict of field_number -> value.
        Supports nested dicts (length-delimited submessages),
        ints (varint), and str/bytes (length-delimited).
        """
        packet = bytearray()
        for field, value in fields.items():
            if isinstance(value, dict):
                nested = cls.build_protobuf(value)
                packet.extend(cls._length_delimited_field(field, nested))
            elif isinstance(value, int):
                packet.extend(cls._varint_field(field, value))
            elif isinstance(value, (str, bytes)):
                packet.extend(cls._length_delimited_field(field, value))
        return bytes(packet)

    # ── Full packet construction ─────────────────────────────

    def build_packet(self, packet_type: str, fields: Dict[int, Any]) -> bytes:
        """
        Build a complete encrypted packet:
        [packet_type_hex][length_header][encrypted_protobuf]

        Args:
            packet_type: 4-char hex string like "0515"
            fields: protobuf field dict

        Returns:
            Raw bytes ready to send over TCP socket
        """
        proto_hex = self.build_protobuf(fields).hex()
        encrypted = self.encrypt(proto_hex)
        length = len(encrypted) // 2
        length_hex = self.dec_to_hex(length)

        # Pad length to match packet framing (same logic as original)
        if len(length_hex) == 2:
            frame = "00000000" + length_hex
        elif len(length_hex) == 3:
            frame = "0000000" + length_hex
        elif len(length_hex) == 4:
            frame = "000000" + length_hex
        elif len(length_hex) == 5:
            frame = "00000" + length_hex
        else:
            frame = length_hex.rjust(10, "0")

        return bytes.fromhex(packet_type + frame + encrypted)

    # ── Game-specific packet builders ────────────────────────

    def join_team(self, team_code: str) -> bytes:
        """Build join-squad packet."""
        fields = {
            1: 4,
            2: {
                1: 1,
                2: int(team_code),
            },
        }
        return self.build_packet("0515", fields)

    def start_match(self, uid: int = 0) -> bytes:
        """Build start-match (ready) packet — field 1=9 triggers match start."""
        fields = {
            1: 9,
            2: {
                1: uid if uid else 12480598706,
            },
        }
        return self.build_packet("0515", fields)

    def leave_team(self, uid: int = 0) -> bytes:
        """Build leave-squad packet — field 1=7 triggers leave."""
        fields = {
            1: 7,
            2: {
                1: uid if uid else 12480598706,
            },
        }
        return self.build_packet("0515", fields)

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
        return self.build_packet("1215", fields)
