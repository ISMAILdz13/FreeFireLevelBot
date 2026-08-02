"""
Match Engine — 1:1 with ClanGloryBot flow.
Opens own squad (OpEnSq) → gets squad_code → joins with GenJoinSquadsPacket.
Sends all match commands on ONLINE channel only (chat kills connections).
"""

import asyncio
import time
import logging
import random
from dataclasses import dataclass
from typing import Optional, Callable, Any

from .packet_builder import PacketBuilder
from .connection import GameConnection

logger = logging.getLogger("levelbot.engine")


@dataclass
class MatchStats:
    cycles_completed: int = 0
    matches_started: int = 0
    join_attempts: int = 0
    join_failures: int = 0
    leave_attempts: int = 0
    leave_failures: int = 0
    uptime_seconds: float = 0.0
    current_state: str = "idle"
    last_error: str = ""


class MatchEngine:
    """
    Auto level-up loop matching ClanGloryBot:
    1. Open squad (OpEnSq) on ONLINE → parse squad_code from response
    2. Join squad (GenJoinSquadsPacket) on ONLINE
    3. Send 269 + 214 + 9 (start match) on ONLINE only
    4. Spam field 9 ready signal on ONLINE
    5. Wait for match (read both channels)
    6. Leave squad on ONLINE
    7. Repeat
    """

    def __init__(
        self,
        connection: GameConnection,
        packet_builder: PacketBuilder,
        spam_duration: int = 18,
        spam_delay: float = 0.2,
        wait_after_match: int = 20,
        join_delay: float = 2.0,
        leave_delay: float = 2.0,
        cycle_delay: float = 2.0,
        uid: int = 0,
    ):
        self.conn = connection
        self.pb = packet_builder
        self.spam_duration = spam_duration
        self.spam_delay = spam_delay
        self.wait_after_match = wait_after_match
        self.join_delay = join_delay
        self.leave_delay = leave_delay
        self.cycle_delay = cycle_delay
        self.uid = uid

        self.stats = MatchStats()
        self._running = False
        self._stop_requested = False
        self._on_progress: Optional[Callable[[MatchStats], Any]] = None

    def on_progress(self, callback: Callable[[MatchStats], Any]):
        self._on_progress = callback

    def stop(self):
        self._stop_requested = True

    async def start(self, team_code: str, max_cycles: int = 1000) -> MatchStats:
        self._running = True
        self._stop_requested = False
        start_time = time.time()
        logger.info(f"Starting level-up loop: team={team_code}, max_cycles={max_cycles}")

        while not self._stop_requested and self.stats.cycles_completed < max_cycles:
            try:
                await self._run_cycle(team_code)
            except Exception as e:
                logger.error(f"Error in cycle #{self.stats.cycles_completed + 1}: {e}")
                self.stats.last_error = str(e)
                await asyncio.sleep(3)

        self._running = False
        self.stats.uptime_seconds = time.time() - start_time
        self.stats.current_state = "stopped"
        return self.stats

    async def _run_cycle(self, team_code: str):
        cycle_num = self.stats.cycles_completed + 1
        logger.info(f"Cycle #{cycle_num}")

        # ── Step 1: Leave any existing squad first ──
        leave_pkt = self.pb.leave_squad(self.uid)
        await self.conn.send_online(leave_pkt)
        await asyncio.sleep(1)

        # ── Step 2: Open squad (OpEnSq) on ONLINE ──
        self.stats.current_state = "opening_squad"
        open_pkt = self.pb.open_squad()
        await self.conn.send_online(open_pkt)
        logger.info("Sent OpEnSq on ONLINE channel")

        # Read response to get squad_code
        squad_code = None
        for attempt in range(3):
            data = await self.conn.recv_online(timeout=3.0)
            if data:
                self.conn.reset_ka_watchdog()
                squad_code = self._parse_squad_code(data)
                if squad_code:
                    logger.info(f"Got squad_code from OpEnSq: {squad_code[:20]}...")
                    break
                logger.info(f"Online data: {len(data)} bytes (no squad code found)")

        if not squad_code:
            # Fallback: use the provided team_code as squad_code directly
            logger.info(f"No squad_code from OpEnSq — using provided code: {team_code}")
            squad_code = team_code

        if self._stop_requested:
            return

        # ── Step 3: Join squad (GenJoinSquadsPacket) on ONLINE ──
        self.stats.current_state = "joining"
        self.stats.join_attempts += 1

        join_pkt = self.pb.join_squad(str(squad_code))
        ok = await self.conn.send_online(join_pkt)
        if not ok:
            self.stats.join_failures += 1
            logger.error("Join failed — online socket dead")
            return

        # Wait for join confirmation
        await asyncio.sleep(self.join_delay)

        # Read any join response
        join_resp = await self.conn.recv_online(timeout=2.0)
        if join_resp:
            self.conn.reset_ka_watchdog()
            logger.info(f"Join response: {len(join_resp)} bytes")

        logger.info(f"Joined squad on ONLINE channel")
        if self._stop_requested:
            return

        # ── Step 4: Start match (269 + 214 + 9 on ONLINE only) ──
        self.stats.current_state = "matching"

        pkt_269 = self.pb.start_match_detailed(self.uid)
        await self.conn.send_online(pkt_269)
        logger.info("Sent field 269 (detailed start) on ONLINE")
        await asyncio.sleep(0.5)

        pkt_214 = self.pb.start_match_simple()
        await self.conn.send_online(pkt_214)
        logger.info("Sent field 214 (simple start) on ONLINE")
        await asyncio.sleep(0.5)

        # Spam field 9 (ready) on ONLINE only
        pkt_9 = self.pb.start_match_ready(self.uid)
        end_time = time.time() + self.spam_duration
        packets_sent = 2

        while time.time() < end_time and not self._stop_requested:
            ok = await self.conn.send_online(pkt_9)
            if ok:
                packets_sent += 1
            else:
                logger.warning(f"Send failed at packet {packets_sent} — connection dead")
                self.conn.connected = False
                break
            jitter = random.uniform(self.spam_delay * 0.8, self.spam_delay * 1.5)
            await asyncio.sleep(jitter)

        self.stats.matches_started += 1
        logger.info(f"Match start: {packets_sent} packets sent")

        if self._stop_requested:
            await self.conn.send_online(self.pb.leave_squad(self.uid))
            return

        # ── Step 5: Wait for match (read both channels) ──
        self.stats.current_state = "waiting"
        logger.info(f"Waiting {self.wait_after_match}s for match...")

        wait_end = time.time() + self.wait_after_match
        while time.time() < wait_end and self.conn.connected:
            online_data = await self.conn.recv_online(timeout=1.0)
            if online_data:
                self.conn.reset_ka_watchdog()
                logger.info(f"Online data: {len(online_data)} bytes, hex={online_data[:12].hex()}")
            whisper_data = await self.conn.recv_whisper(timeout=1.0)
            if whisper_data:
                self.conn.reset_ka_watchdog()
                logger.info(f"Chat data: {len(whisper_data)} bytes, hex={whisper_data[:12].hex()}")

        if not self.conn.connected:
            logger.warning("Connection lost during wait")
            return

        # ── Step 6: Leave squad on ONLINE ──
        self.stats.current_state = "leaving"
        self.stats.leave_attempts += 1

        ok = await self.conn.send_online(self.pb.leave_squad(self.uid))
        if not ok:
            self.stats.leave_failures += 1
        await asyncio.sleep(self.leave_delay)
        logger.info("Left squad on ONLINE channel")

        # ── Step 7: Cycle delay ──
        self.stats.cycles_completed += 1
        self.stats.uptime_seconds = time.time() - start_time
        if self._on_progress:
            self._on_progress(self.stats)

        if not self._stop_requested:
            await asyncio.sleep(self.cycle_delay)

    def _parse_squad_code(self, data: bytes) -> Optional[str]:
        """Parse squad_code from OpEnSq response (0500 packet).
        Looks for the squad_code string in the response data."""
        try:
            from .xC4 import DeCode_PackEt
            import json
            hex_data = data.hex()

            # Find 0500 packet marker
            idx = hex_data.find("0500")
            if idx < 0:
                return None

            # Parse the protobuf data after the header
            payload = hex_data[idx + 12:]  # Skip 6-byte header
            decoded = DeCode_PackEt(payload)
            if decoded:
                parsed = json.loads(decoded)
                # squad_code is in field 5.31 (squad_code) or 5.5 (team_code)
                f5 = parsed.get("5", {})
                if isinstance(f5, dict):
                    f5_data = f5.get("data", f5)
                    if isinstance(f5_data, dict):
                        # Try field 31 (squad_code)
                        f31 = f5_data.get("31", {})
                        if isinstance(f31, dict):
                            code = f31.get("data", "")
                            if code:
                                return str(code)
                        # Try field 5 (team_code as number)
                        f5_5 = f5_data.get("5", {})
                        if isinstance(f5_5, dict):
                            code = f5_5.get("data", "")
                            if code:
                                return str(code)
        except Exception as e:
            logger.debug(f"Squad code parse error: {e}")
        return None
