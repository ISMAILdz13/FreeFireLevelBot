"""
Game Connection — rewritten to match the working ClanGloryBot approach.
Uses asyncio.open_connection, SO_KEEPALIVE, and application-level keepalive.
"""

import asyncio
import socket
import time
import logging
from typing import Optional, Callable, Any

logger = logging.getLogger("levelbot.connection")


class GameConnection:
    """Async TCP connection manager using asyncio streams (like ClanGloryBot)."""

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
        self._region: str = "IND"

    def set_crypto(self, key: bytes, iv: bytes, region: str = "IND"):
        self._key = key
        self._iv = iv
        self._region = region

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
        """Connect to both servers using asyncio streams + send auth token."""
        self.whisper_ip = whisper_ip
        self.whisper_port = int(whisper_port)
        self.online_ip = online_ip
        self.online_port = int(online_port)

        auth_bytes = bytes.fromhex(token_hex)

        # Connect online socket
        logger.info(f"Connecting to online server {online_ip}:{online_port}...")
        self.online_reader, self.online_writer = await asyncio.open_connection(
            self.online_ip, self.online_port
        )

        # Connect whisper (chat) socket
        logger.info(f"Connecting to whisper server {whisper_ip}:{whisper_port}...")
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

        logger.info("TCP connected + auth token sent on both channels")

        # Send AutH_GlobAl packet on chat channel (required by Garena)
        await asyncio.sleep(1)
        await self._send_global_auth()

        self.connected = True
        self._last_data_time = time.time()

        # Start keepalive loop
        self._ka_stop = asyncio.Event()
        self._ka_task = asyncio.create_task(self._keepalive_loop())

    async def _send_global_auth(self):
        """Send AutH_GlobAl packet on chat channel (same as ClanGloryBot)."""
        if not self._key or not self._iv:
            logger.warning("No crypto keys set — skipping global auth")
            return
        try:
            from .xC4 import AutH_GlobAl
            packet = await AutH_GlobAl(self._key, self._iv)
            self.whisper_writer.write(packet)
            await self.whisper_writer.drain()
            logger.info("AutH_GlobAl sent on chat channel")
        except Exception as e:
            logger.warning(f"AutH_GlobAl failed: {e}")

    async def _keepalive_loop(self):
        """Send field-99 keepalive every 15s on both channels (same as ClanGloryBot)."""
        from .xC4 import CrEaTe_ProTo, GeneRaTePk
        while not self._ka_stop.is_set():
            try:
                proto = await CrEaTe_ProTo({1: 99})
                pkt_type = "0515"
                packet = await GeneRaTePk(proto.hex(), pkt_type, self._key, self._iv)
                if self.online_writer and not self.online_writer.is_closing():
                    self.online_writer.write(packet)
                    await self.online_writer.drain()
                if self.whisper_writer and not self.whisper_writer.is_closing():
                    self.whisper_writer.write(packet)
                    await self.whisper_writer.drain()
            except Exception as e:
                if not self._ka_stop.is_set():
                    logger.warning(f"Keepalive error: {e}")
                    self.connected = False
                    break
            await asyncio.sleep(15)

    async def send_whisper(self, data: bytes):
        """Send raw bytes on the whisper (chat) socket."""
        if not self.whisper_writer or self.whisper_writer.is_closing():
            raise ConnectionError("Whisper socket not connected")
        self.whisper_writer.write(data)
        await self.whisper_writer.drain()

    async def send_online(self, data: bytes):
        """Send raw bytes on the online socket."""
        if not self.online_writer or self.online_writer.is_closing():
            raise ConnectionError("Online socket not connected")
        self.online_writer.write(data)
        await self.online_writer.drain()
        self._last_data_time = time.time()

    async def recv_whisper(self, timeout: float = 5.0) -> Optional[bytes]:
        """Receive data from whisper socket with timeout."""
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
        """Receive data from online socket with timeout."""
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

    async def whisper_listen_loop(self, callback: Callable[[bytes], Any]):
        """Continuously read from whisper socket and call callback with data."""
        while not self._ka_stop or not self._ka_stop.is_set():
            data = await self.recv_whisper(timeout=2.0)
            if data is None:
                if not self.connected:
                    break
                continue
            try:
                callback(data)
            except Exception as e:
                logger.warning(f"Whisper callback error: {e}")

    async def close(self):
        """Close all sockets and stop background tasks."""
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
                    logger.info(f"{name} socket closed")
                except Exception:
                    pass

        self.whisper_reader = None
        self.whisper_writer = None
        self.online_reader = None
        self.online_writer = None
