"""
Game Connection — 1:1 with ClanGloryBot approach.
Uses asyncio.open_connection, SO_KEEPALIVE, field-99 keepalive with timestamp.
Sends join/start/leave on ONLINE channel only (chat kills connections).
"""

import asyncio
import socket
import time
import logging
from typing import Optional, Callable, Any

logger = logging.getLogger("levelbot.connection")

# Region → packet type (same as ClanGloryBot)
REGION_PACKETS = {"ind": "0514", "bd": "0519"}
DEFAULT_PACKET = "0515"


class GameConnection:
    """Async TCP connection manager — matches ClanGloryBot."""

    def __init__(self, recv_timeout: float = 1.0):
        self.online_reader: Optional[asyncio.StreamReader] = None
        self.online_writer: Optional[asyncio.StreamWriter] = None
        self.whisper_reader: Optional[asyncio.StreamReader] = None
        self.whisper_writer: Optional[asyncio.StreamWriter] = None
        self.whisper_ip: str = ""
        self.whisper_port: int = 0
        self.online_ip: str = ""
        self.online_port: int = 0
        self.connected = False
        self._recv_timeout = recv_timeout
        self._ka_task: Optional[asyncio.Task] = None
        self._ka_stop: Optional[asyncio.Event] = None
        self._last_data_time: float = 0.0
        self._on_whisper_data: Optional[Callable] = None
        self._key: bytes = b""
        self._iv: bytes = b""
        self._region: str = "ME"

    def set_crypto(self, key: bytes, iv: bytes, region: str = "ME"):
        self._key = key
        self._iv = iv
        self._region = region.lower()

    def on_whisper_data(self, callback: Callable[[bytes], Any]):
        self._on_whisper_data = callback

    async def connect(
        self,
        whisper_ip: str,
        whisper_port: int,
        online_ip: str,
        online_port: int,
        token_hex: str,
    ):
        """Connect to both servers, send auth token, start keepalive."""
        self.whisper_ip = whisper_ip
        self.whisper_port = int(whisper_port)
        self.online_ip = online_ip
        self.online_port = int(online_port)

        auth_bytes = bytes.fromhex(token_hex)

        logger.info(f"Connecting to online {online_ip}:{online_port}...")
        self.online_reader, self.online_writer = await asyncio.open_connection(
            self.online_ip, self.online_port
        )

        logger.info(f"Connecting to chat {whisper_ip}:{whisper_port}...")
        self.whisper_reader, self.whisper_writer = await asyncio.open_connection(
            self.whisper_ip, self.whisper_port
        )

        # OS-level TCP keepalive on both sockets
        for writer in [self.online_writer, self.whisper_writer]:
            sock = writer.get_extra_info('socket')
            if sock:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
                if hasattr(socket, 'TCP_KEEPIDLE'):
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 15)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
                    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)

        # Send auth token to both sockets
        self.online_writer.write(auth_bytes)
        await self.online_writer.drain()
        self.whisper_writer.write(auth_bytes)
        await self.whisper_writer.drain()

        logger.info("TCP connected + auth token sent")

        # Send AutH_GlobAl on chat channel (required by Garena)
        await asyncio.sleep(1)
        await self._send_global_auth()

        self.connected = True
        self._last_data_time = time.time()
        self._ka_stop = asyncio.Event()
        self._ka_task = asyncio.create_task(self._keepalive_loop())

    async def _send_global_auth(self):
        """Send AutH_GlobAl on chat channel (same as ClanGloryBot)."""
        try:
            from .xC4 import AutH_GlobAl
            packet = await AutH_GlobAl(self._key, self._iv)
            self.whisper_writer.write(packet)
            await self.whisper_writer.drain()
            logger.info("AutH_GlobAl sent on chat channel")
        except Exception as e:
            logger.warning(f"AutH_GlobAl failed: {e}")

    async def _keepalive_loop(self):
        """Send field-99 keepalive every 15s on BOTH channels (same as ClanGloryBot).
        Includes timestamp {1: time.time(), 2: 1} — not just {1: 99}."""
        from .xC4 import CrEaTe_ProTo, GeneRaTePk
        while not self._ka_stop.is_set():
            try:
                proto = await CrEaTe_ProTo({1: 99, 2: {1: int(time.time()), 2: 1}})
                # Online channel: region-specific packet type
                pkt_type = REGION_PACKETS.get(self._region, DEFAULT_PACKET)
                pkt_online = await GeneRaTePk(proto.hex(), pkt_type, self._key, self._iv)
                if self.online_writer and not self.online_writer.is_closing():
                    self.online_writer.write(pkt_online)
                    await self.online_writer.drain()
                # Chat channel: 1215 packet type
                pkt_chat = await GeneRaTePk(proto.hex(), "1215", self._key, self._iv)
                if self.whisper_writer and not self.whisper_writer.is_closing():
                    self.whisper_writer.write(pkt_chat)
                    await self.whisper_writer.drain()

                # Watchdog: 300s no data = dead
                if time.time() - self._last_data_time > 300:
                    logger.warning("Watchdog: no data for 300s, marking disconnected")
                    self.connected = False
                    break
            except Exception as e:
                if not self._ka_stop.is_set():
                    logger.warning(f"Keepalive error: {e}")
                    self.connected = False
                    break
            await asyncio.sleep(15)

    def reset_ka_watchdog(self):
        """Call when any data is received from server."""
        self._last_data_time = time.time()

    async def send_whisper(self, data: bytes) -> bool:
        """Send raw bytes on chat/whisper socket. Returns True on success."""
        if not self.whisper_writer or self.whisper_writer.is_closing():
            logger.warning("Whisper socket not connected")
            return False
        try:
            self.whisper_writer.write(data)
            await self.whisper_writer.drain()
            return True
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.warning(f"Whisper send error: {e}")
            self.connected = False
            return False

    async def send_online(self, data: bytes) -> bool:
        """Send raw bytes on online socket. Returns True on success."""
        if not self.online_writer or self.online_writer.is_closing():
            logger.warning("Online socket not connected")
            return False
        try:
            self.online_writer.write(data)
            await self.online_writer.drain()
            return True
        except (ConnectionResetError, BrokenPipeError, OSError) as e:
            logger.warning(f"Online send error: {e}")
            self.connected = False
            return False

    async def recv_whisper(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self.whisper_reader:
            return None
        try:
            data = await asyncio.wait_for(self.whisper_reader.read(9999), timeout=timeout)
            if data:
                self._last_data_time = time.time()
            return data if data else None
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.warning(f"Whisper recv error: {e}")
            self.connected = False
            return None

    async def recv_online(self, timeout: float = 5.0) -> Optional[bytes]:
        if not self.online_reader:
            return None
        try:
            data = await asyncio.wait_for(self.online_reader.read(9999), timeout=timeout)
            if data:
                self._last_data_time = time.time()
            return data if data else None
        except asyncio.TimeoutError:
            return None
        except Exception as e:
            logger.warning(f"Online recv error: {e}")
            self.connected = False
            return None

    async def close(self):
        logger.info("Closing game connection...")
        if self._ka_stop:
            self._ka_stop.set()
        if self._ka_task:
            self._ka_task.cancel()
            try:
                await self._ka_task
            except asyncio.CancelledError:
                pass
            self._ka_task = None

        self.connected = False
        for name, writer in [("whisper", self.whisper_writer), ("online", self.online_writer)]:
            if writer and not writer.is_closing():
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

        self.whisper_reader = None
        self.whisper_writer = None
        self.online_reader = None
        self.online_writer = None
