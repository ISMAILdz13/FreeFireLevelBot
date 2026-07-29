"""
Game Connection
Manages TCP socket connections to Free Fire game servers.
Maintains both whisper (chat) and online (game state) sockets.

Adapted from level/app.py connect()/sockf1() — made async with
proper error handling, reconnection, and clean shutdown.
"""

import asyncio
import socket
import logging
from typing import Optional, Callable, Any

logger = logging.getLogger("levelbot.connection")


class GameConnection:
    """
    Async TCP connection manager for Free Fire game servers.

    Maintains two sockets:
      - whisper_socket: chat/messaging channel
      - online_socket: game state/match control channel

    Usage:
        conn = GameConnection()
        await conn.connect(whisper_ip, whisper_port, online_ip, online_port, token)
        await conn.send_whisper(packet)
        data = await conn.recv_whisper()
        await conn.close()
    """

    def __init__(self, recv_timeout: float = 1.0):
        self.whisper_socket: Optional[socket.socket] = None
        self.online_socket: Optional[socket.socket] = None
        self.whisper_ip: str = ""
        self.whisper_port: int = 0
        self.online_ip: str = ""
        self.online_port: int = 0
        self.connected = False
        self._recv_timeout = recv_timeout
        self._online_task: Optional[asyncio.Task] = None
        self._on_whisper_data: Optional[Callable] = None
        self._stop_event = asyncio.Event()

    def on_whisper_data(self, callback: Callable[[bytes], Any]):
        """Register callback for incoming whisper socket data."""
        self._on_whisper_data = callback

    async def connect(
        self,
        whisper_ip: str,
        whisper_port: int,
        online_ip: str,
        online_port: int,
        token_hex: str,
    ):
        """
        Connect to both whisper and online servers.
        Sends the auth token immediately after connecting.
        """
        self.whisper_ip = whisper_ip
        self.whisper_port = int(whisper_port)
        self.online_ip = online_ip
        self.online_port = int(online_port)

        # Connect whisper socket (blocking connect in executor)
        logger.info(f"Connecting to whisper server {whisper_ip}:{whisper_port}...")
        self.whisper_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.whisper_socket.settimeout(15)
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self.whisper_socket.connect, (self.whisper_ip, self.whisper_port)
            )
        except Exception as e:
            logger.error(f"Whisper connect failed: {e}")
            raise ConnectionError(f"Cannot connect to whisper server: {e}")

        self.whisper_socket.settimeout(self._recv_timeout)
        self.whisper_socket.send(bytes.fromhex(token_hex))
        logger.info("Whisper socket connected and authenticated")

        # Connect online socket
        logger.info(f"Connecting to online server {online_ip}:{online_port}...")
        self.online_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.online_socket.settimeout(15)
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self.online_socket.connect, (self.online_ip, self.online_port)
            )
        except Exception as e:
            logger.error(f"Online connect failed: {e}")
            raise ConnectionError(f"Cannot connect to online server: {e}")

        self.online_socket.settimeout(self._recv_timeout)
        self.online_socket.send(bytes.fromhex(token_hex))
        logger.info("Online socket connected and authenticated")

        self.connected = True
        self._stop_event.clear()

        # Start background online socket reader (keeps connection alive)
        self._online_task = asyncio.create_task(self._online_reader_loop())

    async def _online_reader_loop(self):
        """Background loop that reads from online socket to keep it alive."""
        while not self._stop_event.is_set() and self.online_socket:
            try:
                data = await asyncio.get_event_loop().run_in_executor(
                    None, self.online_socket.recv, 4096
                )
                if data == b"":
                    logger.warning("Online socket closed by remote")
                    self.connected = False
                    break
                # Online data is game state — we mostly just keep the connection alive
            except socket.timeout:
                continue
            except Exception as e:
                if not self._stop_event.is_set():
                    logger.warning(f"Online socket error: {e}")
                break

        logger.info("Online reader loop ended")

    async def send_whisper(self, data: bytes):
        """Send raw bytes on the whisper socket."""
        if not self.whisper_socket:
            raise ConnectionError("Whisper socket not connected")
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self.whisper_socket.send, data
            )
        except Exception as e:
            logger.error(f"Whisper send failed: {e}")
            raise

    async def send_online(self, data: bytes):
        """Send raw bytes on the online socket."""
        if not self.online_socket:
            raise ConnectionError("Online socket not connected")
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self.online_socket.send, data
            )
        except Exception as e:
            logger.error(f"Online send failed: {e}")
            raise

    async def recv_whisper(self, timeout: float = 5.0) -> Optional[bytes]:
        """
        Receive data from whisper socket with timeout.
        Returns None on timeout.
        """
        if not self.whisper_socket:
            return None
        old_timeout = self.whisper_socket.gettimeout()
        self.whisper_socket.settimeout(timeout)
        try:
            data = await asyncio.get_event_loop().run_in_executor(
                None, self.whisper_socket.recv, 9999
            )
            if data == b"":
                logger.warning("Whisper socket closed by remote")
                self.connected = False
                return None
            return data
        except socket.timeout:
            return None
        except Exception as e:
            logger.warning(f"Whisper recv error: {e}")
            return None
        finally:
            self.whisper_socket.settimeout(old_timeout)

    async def whisper_listen_loop(self, callback: Callable[[bytes], Any]):
        """
        Continuously read from whisper socket and call callback with data.
        This runs until close() is called or the socket dies.
        """
        while not self._stop_event.is_set() and self.whisper_socket:
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
        self._stop_event.set()
        self.connected = False

        if self._online_task:
            self._online_task.cancel()
            try:
                await self._online_task
            except asyncio.CancelledError:
                pass
            self._online_task = None

        for sock_name, sock in [("whisper", self.whisper_socket), ("online", self.online_socket)]:
            if sock:
                try:
                    sock.close()
                    logger.info(f"{sock_name} socket closed")
                except Exception:
                    pass

        self.whisper_socket = None
        self.online_socket = None
