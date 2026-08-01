"""
Match Engine
Core level-up loop: join team → start match → wait → leave → repeat.

Adapted from level/app.py auto_start_loop() — made async, config-driven,
with stats tracking, progress callbacks, and clean stop.
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Callable, Any

from .packet_builder import PacketBuilder
from .connection import GameConnection

logger = logging.getLogger("levelbot.engine")


@dataclass
class MatchStats:
    """Runtime stats for the level bot."""
    cycles_completed: int = 0
    matches_started: int = 0
    join_attempts: int = 0
    join_failures: int = 0
    leave_attempts: int = 0
    leave_failures: int = 0
    uptime_seconds: float = 0.0
    current_state: str = "idle"  # idle, joining, matching, waiting, leaving
    last_error: str = ""


class MatchEngine:
    """
    Orchestrates the auto level-up loop.

    Each cycle:
        1. Join squad with team_code
        2. Spam start-match packets for spam_duration seconds
        3. Wait wait_after_match seconds for match to complete
        4. Leave squad
        5. Repeat

    Usage:
        engine = MatchEngine(conn, packet_builder, config)
        await engine.start(team_code="123456", max_cycles=100)
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
        self._on_message: Optional[Callable[[str], Any]] = None
        self._sender_uid: int = 0

    def on_progress(self, callback: Callable[[MatchStats], Any]):
        """Register callback for progress updates (called after each cycle)."""
        self._on_progress = callback

    def on_message(self, callback: Callable[[str], Any]):
        """Register callback for chat messages to send in-game."""
        self._on_message = callback

    def set_sender_uid(self, uid: int):
        """Set the UID used for in-game chat messages."""
        self._sender_uid = uid

    @property
    def is_running(self) -> bool:
        return self._running

    def stop(self):
        """Request the engine to stop after the current cycle."""
        self._stop_requested = True
        logger.info("Stop requested — will finish current cycle then halt")

    async def start(self, team_code: str, max_cycles: int = 1000) -> MatchStats:
        """
        Start the auto level-up loop.

        Args:
            team_code: The squad/team code to join (digits only)
            max_cycles: Safety limit on number of cycles

        Returns:
            Final MatchStats
        """
        if not team_code.isdigit():
            raise ValueError(f"Team code must be numeric, got: {team_code}")

        self._running = True
        self._stop_requested = False
        start_time = time.time()
        logger.info(f"🚀 Starting level-up loop: team={team_code}, max_cycles={max_cycles}")

        while not self._stop_requested and self.stats.cycles_completed < max_cycles:
            try:
                await self._run_cycle(team_code)
            except Exception as e:
                logger.error(f"Error in cycle #{self.stats.cycles_completed + 1}: {e}")
                self.stats.last_error = str(e)
                # Brief recovery pause
                await asyncio.sleep(3)

        self._running = False
        self.stats.uptime_seconds = time.time() - start_time
        self.stats.current_state = "stopped"
        logger.info(
            f"🛑 Level-up loop ended: {self.stats.cycles_completed} cycles, "
            f"{self.stats.matches_started} matches, "
            f"{self.stats.uptime_seconds:.0f}s uptime"
        )
        return self.stats

    async def _run_cycle(self, team_code: str):
        """Run a single join → start → wait → leave cycle."""
        cycle_num = self.stats.cycles_completed + 1
        logger.info(f"🔄 Cycle #{cycle_num}")

        # ── Step 1: Join team ──
        self.stats.current_state = "joining"
        self.stats.join_attempts += 1
        join_packet = self.pb.join_team(team_code, self.uid)
        await self.conn.send_whisper(join_packet)
        # Also send on online channel (server may expect it there)
        await self.conn.send_online(join_packet)
        await asyncio.sleep(self.join_delay)
        logger.info(f"Joined team {team_code}")

        if self._stop_requested:
            return

        # ── Step 2: Start match (send 269 + 214, then spam field 9 ready) ──
        self.stats.current_state = "matching"

        # Send the actual match-start commands (field 269 + 214) — these trigger matchmaking
        start_detailed = self.pb.start_match_detailed(self.uid)
        start_simple = self.pb.start_match_simple()
        ready_packet = self.pb.start_match_ready(self.uid)

        # Send 269 (detailed start) on both channels
        await self.conn.send_online(start_detailed)
        await self.conn.send_whisper(start_detailed)
        logger.info(f"Sent field 269 (detailed start) on both channels")

        await asyncio.sleep(0.5)

        # Send 214 (simple start) on both channels
        await self.conn.send_online(start_simple)
        await self.conn.send_whisper(start_simple)
        logger.info(f"Sent field 214 (simple start) on both channels")

        await asyncio.sleep(0.5)

        # Now spam field 9 (ready signal) for the duration
        end_time = time.time() + self.spam_duration
        packets_sent = 2  # Already sent 269 + 214

        while time.time() < end_time and not self._stop_requested:
            await self.conn.send_online(ready_packet)
            packets_sent += 1
            await asyncio.sleep(self.spam_delay)

        self.stats.matches_started += 1
        logger.info(f"Match start packets sent: {packets_sent}")

        if self._stop_requested:
            # Still try to leave before stopping
            leave_packet = self.pb.leave_team(self.uid)
            try:
                await self.conn.send_whisper(leave_packet)
            except Exception:
                pass
            return

        # ── Step 3: Wait for match to complete ──
        self.stats.current_state = "waiting"
        logger.info(f"Waiting {self.wait_after_match}s for match completion...")
        await asyncio.sleep(self.wait_after_match)

        # ── Step 4: Leave team ──
        self.stats.current_state = "leaving"
        self.stats.leave_attempts += 1
        leave_packet = self.pb.leave_team(self.uid)
        await self.conn.send_whisper(leave_packet)
        await asyncio.sleep(self.leave_delay)
        logger.info("Left team")

        # ── Step 5: Brief delay before next cycle ──
        self.stats.cycles_completed += 1
        self.stats.uptime_seconds = time.time() - (time.time() - self.stats.uptime_seconds)
        if self._on_progress:
            self._on_progress(self.stats)

        if not self._stop_requested:
            await asyncio.sleep(self.cycle_delay)

    async def send_chat(self, text: str):
        """Send a chat message in-game (uses whisper socket)."""
        if self._sender_uid:
            msg_packet = self.pb.chat_message(text, self._sender_uid)
            await self.conn.send_whisper(msg_packet)
