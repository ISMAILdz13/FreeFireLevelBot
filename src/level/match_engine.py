"""
Match Engine — 1:1 with ClanGloryBot flow.
- If squad_code provided: join existing squad with GenJoinSquadsPacket
- If no squad_code: open own squad (OpEnSq) and start matchmaking solo
- All match commands on ONLINE channel only (chat kills connections)
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
    
    Mode A (squad_code provided):
    1. Join squad (GenJoinSquadsPacket) on ONLINE
    2. Send 269 + 214 + 9 on ONLINE
    3. Spam field 9 ready on ONLINE
    4. Wait for match (read both channels)
    5. Leave squad on ONLINE
    6. Repeat
    
    Mode B (no squad_code — solo):
    1. Open squad (OpEnSq) on ONLINE — opener is already in squad
    2. Send 269 + 214 + 9 on ONLINE
    3. Spam field 9 ready on ONLINE
    4. Wait for match
    5. Leave squad on ONLINE
    6. Repeat
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

    async def start(self, squad_code: str, max_cycles: int = 1000) -> MatchStats:
        self._running = True
        self._stop_requested = False
        start_time = time.time()
        
        # Mode A: join existing squad. Mode B: open own squad.
        solo_mode = not squad_code or squad_code == "0" or squad_code == "solo"
        if solo_mode:
            logger.info("Solo mode — will open own squad each cycle")
        else:
            logger.info(f"Squad mode — joining squad_code: {squad_code}")

        while not self._stop_requested and self.stats.cycles_completed < max_cycles:
            try:
                await self._run_cycle(squad_code, solo_mode)
            except Exception as e:
                logger.error(f"Error in cycle #{self.stats.cycles_completed + 1}: {e}")
                self.stats.last_error = str(e)
                await asyncio.sleep(3)

        self._running = False
        self.stats.uptime_seconds = time.time() - start_time
        self.stats.current_state = "stopped"
        return self.stats

    async def _run_cycle(self, squad_code: str, solo_mode: bool):
        cycle_num = self.stats.cycles_completed + 1
        logger.info(f"Cycle #{cycle_num}")

        # ── Step 1: Leave any existing squad ──
        await self.conn.send_online(self.pb.leave_squad(self.uid))
        await asyncio.sleep(1)

        if solo_mode:
            # ── Solo: Open own squad (opener is already in it) ──
            self.stats.current_state = "opening_squad"
            await self.conn.send_online(self.pb.open_squad())
            logger.info("Opened squad (OpEnSq) — solo mode")
            await asyncio.sleep(2)
            
            # Read response (but don't need to parse — opener is in squad)
            data = await self.conn.recv_online(timeout=2.0)
            if data:
                self.conn.reset_ka_watchdog()
                logger.info(f"OpEnSq response: {len(data)} bytes")
        else:
            # ── Join existing squad with GenJoinSquadsPacket ──
            self.stats.current_state = "joining"
            self.stats.join_attempts += 1
            
            join_pkt = self.pb.join_squad(str(squad_code))
            ok = await self.conn.send_online(join_pkt)
            if not ok:
                self.stats.join_failures += 1
                logger.error("Join failed — online socket dead")
                return
            
            await asyncio.sleep(self.join_delay)
            
            # Read join response
            join_resp = await self.conn.recv_online(timeout=2.0)
            if join_resp:
                self.conn.reset_ka_watchdog()
                logger.info(f"Join response: {len(join_resp)} bytes, hex={join_resp[:12].hex()}")
            
            logger.info(f"Joined squad on ONLINE channel")

        if self._stop_requested:
            return

        # ── Step 2: Start match (269 + 214 + 9 on ONLINE only) ──
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

        # ── Step 3: Wait for match (read both channels) ──
        self.stats.current_state = "waiting"
        logger.info(f"Waiting {self.wait_after_match}s for match...")

        wait_end = time.time() + self.wait_after_match
        while time.time() < wait_end and self.conn.connected:
            online_data = await self.conn.recv_online(timeout=1.0)
            if online_data:
                self.conn.reset_ka_watchdog()
                logger.info(f"Online: {len(online_data)} bytes, hex={online_data[:12].hex()}")
            whisper_data = await self.conn.recv_whisper(timeout=1.0)
            if whisper_data:
                self.conn.reset_ka_watchdog()
                logger.info(f"Chat: {len(whisper_data)} bytes, hex={whisper_data[:12].hex()}")

        if not self.conn.connected:
            logger.warning("Connection lost during wait")
            return

        # ── Step 4: Leave squad on ONLINE ──
        self.stats.current_state = "leaving"
        self.stats.leave_attempts += 1

        ok = await self.conn.send_online(self.pb.leave_squad(self.uid))
        if not ok:
            self.stats.leave_failures += 1
        await asyncio.sleep(self.leave_delay)
        logger.info("Left squad on ONLINE channel")

        # ── Step 5: Cycle delay ──
        self.stats.cycles_completed += 1
        self.stats.uptime_seconds = time.time() - start_time
        if self._on_progress:
            self._on_progress(self.stats)

        if not self._stop_requested:
            await asyncio.sleep(self.cycle_delay)
