"""
Match Engine — EXACT match of OB54-TCP-BOT auto_start_loop.
The real level bot flow: join team → spam start → wait → leave → repeat.

No match detection, no f2=18 parsing, no join_match_room.
Just spam and wait — server handles everything.

Flow (1:1 with OB54-TCP-BOT):
1. (Optional) SwitchLoneWolfDule — switch to 1v1 mode
2. Join team with team_code (field 1=4, GenJoinSquadsPacket)
3. Spam start match (field 1=9) for 17s with 0.2s delay
4. Wait 20s (match starts, bot is AFK, match ends)
5. Leave squad (field 1=7)
6. Repeat
"""

import asyncio
import time
import logging
from dataclasses import dataclass
from typing import Optional, Callable, Any

from .packet_builder import PacketBuilder
from .connection import GameConnection

logger = logging.getLogger("levelbot.engine")


@dataclass
class MatchStats:
    cycles_completed: int = 0
    matches_started: int = 0
    uptime_seconds: float = 0.0
    current_state: str = "idle"
    last_error: str = ""


class MatchEngine:
    """
    Level bot — 1:1 with OB54-TCP-BOT auto_start_loop.
    Join team → spam start → wait → leave → repeat.
    """

    def __init__(
        self,
        connection: GameConnection,
        packet_builder: PacketBuilder,
        spam_duration: int = 17,
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
        self._start_time: float = 0.0
        self._on_progress: Optional[Callable[[MatchStats], Any]] = None

    def on_progress(self, callback: Callable[[MatchStats], Any]):
        self._on_progress = callback

    def stop(self):
        self._stop_requested = True

    async def start(self, team_code: str, max_cycles: int = 1000) -> MatchStats:
        self._running = True
        self._stop_requested = False
        self._start_time = time.time()

        logger.info(f"Starting level bot loop: team_code={team_code}, max_cycles={max_cycles}")
        print(f"\n  🚀 Level bot started — team: {team_code}")
        print(f"  ⚡ Join → Start → Wait({self.wait_after_match}s) → Leave → Repeat")

        # Send Lone Wolf switch if no team_code (solo mode)
        if not team_code or team_code == "0":
            logger.info("Solo mode — sending SwitchLoneWolfDule")
            lw_pkt = self.pb.switch_lone_wolf(self.uid)
            await self.conn.send_online(lw_pkt)
            await asyncio.sleep(1)

        while not self._stop_requested and self.stats.cycles_completed < max_cycles:
            try:
                await self._run_cycle(team_code)
            except Exception as e:
                logger.error(f"Error in cycle #{self.stats.cycles_completed + 1}: {e}")
                self.stats.last_error = str(e)
                print(f"  ❌ Cycle error: {e}")
                await asyncio.sleep(3)

        self._running = False
        self.stats.uptime_seconds = time.time() - self._start_time
        self.stats.current_state = "stopped"
        return self.stats

    async def _run_cycle(self, team_code: str):
        cycle_num = self.stats.cycles_completed + 1
        self.stats.current_state = "joining"
        print(f"\n  🔄 Cycle #{cycle_num}")

        # ── Step 1: Join team ──
        if team_code and team_code != "0":
            join_pkt = self.pb.join_teamcode(str(team_code))
            await self.conn.send_online(join_pkt)
            logger.info(f"Joined team: {team_code}")
            print(f"  ✅ Joined team {team_code}")
            await asyncio.sleep(self.join_delay)

        if self._stop_requested:
            return

        # ── Step 2: Spam start match (field 1=9) ──
        self.stats.current_state = "spamming"
        self.stats.matches_started += 1
        
        start_pkt = self.pb.start_auto_match(self.uid)
        end_time = time.time() + self.spam_duration
        spam_count = 0

        print(f"  🎯 Spamming start match ({self.spam_duration}s)...")
        while time.time() < end_time and not self._stop_requested:
            ok = await self.conn.send_online(start_pkt)
            if ok:
                spam_count += 1
            else:
                logger.warning("Send failed — connection dead")
                self.conn.connected = False
                break
            await asyncio.sleep(self.spam_delay)

        logger.info(f"Spam done: {spam_count} packets")
        print(f"  📮 Sent {spam_count} start packets")

        if self._stop_requested:
            return

        # ── Step 3: Wait for match to complete ──
        self.stats.current_state = "waiting"
        print(f"  ⏳ Waiting {self.wait_after_match}s for match...")

        waited = 0
        while waited < self.wait_after_match and not self._stop_requested:
            await asyncio.sleep(1)
            waited += 1

        if self._stop_requested:
            return

        # ── Step 4: Leave squad ──
        self.stats.current_state = "leaving"
        leave_pkt = self.pb.leave_squad(self.uid)
        await self.conn.send_online(leave_pkt)
        logger.info("Left squad")
        print(f"  🚪 Left team — restarting cycle")
        await asyncio.sleep(self.leave_delay)

        # ── Step 5: Cycle delay ──
        self.stats.cycles_completed += 1
        self.stats.uptime_seconds = time.time() - self._start_time
        if self._on_progress:
            self._on_progress(self.stats)

        if not self._stop_requested:
            await asyncio.sleep(self.cycle_delay)
