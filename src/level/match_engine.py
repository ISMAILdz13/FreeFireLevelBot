"""
Match Engine — Lone Wolf 1v1 farming flow.
Solo matchmaking: send start-match → match found → join → exit immediately.
Opponent gets the win, bot gets participation EXP. Cycle repeats.

Flow (matching ClanGloryBot solo mode):
1. Send start match (269 + 214 + 9) on ONLINE — no squad needed for solo
2. Spam field 9 (ready) on ONLINE for spam_duration
3. Read both channels for match-found packet (f2=18 with GroupID)
4. If match found: join match (0e15) + join room (GenJoinSquadsPacket)
5. Immediately exit (ExiT field 7) — opponent wins, bot gets EXP
6. Wait for match to end
7. Leave squad (if any) and repeat
"""

import asyncio
import time
import logging
import random
import json
from dataclasses import dataclass
from typing import Optional, Callable, Any

from .packet_builder import PacketBuilder
from .connection import GameConnection

logger = logging.getLogger("levelbot.engine")

# Match timing (tuned for Lone Wolf 1v1)
SPAM_DURATION = 15      # seconds to spam field 9 ready
MATCH_WAIT = 60         # seconds to wait for match to be found
MATCH_EXIT_WAIT = 10    # seconds to wait after exiting match
CYCLE_DELAY = 3         # seconds between cycles


@dataclass
class MatchStats:
    cycles_completed: int = 0
    matches_started: int = 0
    matches_found: int = 0
    matches_exited: int = 0
    join_attempts: int = 0
    join_failures: int = 0
    uptime_seconds: float = 0.0
    current_state: str = "idle"
    last_error: str = ""


class MatchEngine:
    """
    Lone Wolf 1v1 level bot — solo matchmaking.
    
    No squad formation needed (like ClanGloryBot solo_mode).
    Bot independently starts matchmaking, enters match, exits immediately.
    """

    def __init__(
        self,
        connection: GameConnection,
        packet_builder: PacketBuilder,
        spam_duration: int = 15,
        spam_delay: float = 0.2,
        wait_after_match: int = 25,
        join_delay: float = 2.0,
        leave_delay: float = 2.0,
        cycle_delay: float = 3.0,
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
        self._match_found = False
        self._group_id: Optional[int] = None
        self._recruit_code: Optional[str] = None

    def on_progress(self, callback: Callable[[MatchStats], Any]):
        self._on_progress = callback

    def stop(self):
        self._stop_requested = True

    async def start(self, squad_code: str, max_cycles: int = 1000) -> MatchStats:
        self._running = True
        self._stop_requested = False
        self._start_time = time.time()
        
        # Squad code is ignored in Lone Wolf solo mode — we don't join squads
        logger.info(f"Starting Lone Wolf 1v1 loop: max_cycles={max_cycles}")

        while not self._stop_requested and self.stats.cycles_completed < max_cycles:
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error(f"Error in cycle #{self.stats.cycles_completed + 1}: {e}")
                self.stats.last_error = str(e)
                await asyncio.sleep(3)

        self._running = False
        self.stats.uptime_seconds = time.time() - self._start_time
        self.stats.current_state = "stopped"
        return self.stats

    async def _run_cycle(self):
        cycle_num = self.stats.cycles_completed + 1
        logger.info(f"--- Cycle #{cycle_num} ---")
        print(f"\n  --- Cycle #{cycle_num} ---")

        # Reset per-cycle state
        self._match_found = False
        self._group_id = None
        self._recruit_code = None

        # ── Step 1: Leave any existing squad ──
        await self.conn.send_online(self.pb.leave_squad(self.uid))
        await asyncio.sleep(1)

        if self._stop_requested:
            return

        # ── Step 2: Start match (269 + 214 on ONLINE) ──
        self.stats.current_state = "matching"
        self.stats.matches_started += 1
        print(f"  >> Sending start match (269 + 214 + 9)...")

        pkt_269 = self.pb.start_match_detailed(self.uid)
        await self.conn.send_online(pkt_269)
        logger.info("Sent field 269 (detailed start)")
        await asyncio.sleep(0.5)

        pkt_214 = self.pb.start_match_simple()
        await self.conn.send_online(pkt_214)
        logger.info("Sent field 214 (simple start)")
        await asyncio.sleep(0.5)

        # ── Step 3: Spam field 9 (ready) + read for match (concurrent) ──
        pkt_9 = self.pb.start_match_ready(self.uid)
        
        spam_task = asyncio.create_task(self._spam_ready(pkt_9))
        read_task = asyncio.create_task(self._read_for_match())
        
        # Wait for spam to finish or match to be found
        spam_duration = max(self.spam_duration, 15)
        try:
            await asyncio.wait_for(
                asyncio.gather(spam_task, read_task),
                timeout=spam_duration + MATCH_WAIT
            )
        except asyncio.TimeoutError:
            pass
        finally:
            spam_task.cancel()
            read_task.cancel()
            try:
                await spam_task
            except asyncio.CancelledError:
                pass
            try:
                await read_task
            except asyncio.CancelledError:
                pass

        if self._stop_requested:
            await self.conn.send_online(self.pb.leave_squad(self.uid))
            return

        # ── Step 4: Match found? Join + exit immediately ──
        if self._match_found and self._group_id:
            self.stats.matches_found += 1
            self.stats.current_state = "in_match"
            print(f"  >> Match found! GroupID={self._group_id}")
            
            # Join match room (0e15 packet)
            await self._join_match(self._group_id)
            await asyncio.sleep(1)

            # Join with RecruitCode if available (GenJoinSquadsPacket)
            if self._recruit_code:
                print(f"  >> Joining match room (RecruitCode)...")
                join_pkt = self.pb.join_squad(str(self._recruit_code))
                await self.conn.send_online(join_pkt)
                await asyncio.sleep(1)

            # EXIT immediately — opponent wins, bot gets EXP
            print(f"  >> Exiting match immediately (Lone Wolf exit)...")
            exit_pkt = self.pb.leave_squad(self.uid)
            await self.conn.send_online(exit_pkt)
            self.stats.matches_exited += 1
            logger.info("Exited match — opponent gets the win")
            
            # Wait for match to end (bot already left, short wait)
            self.stats.current_state = "waiting"
            print(f"  >> Waiting {MATCH_EXIT_WAIT}s for match to end...")
            await asyncio.sleep(MATCH_EXIT_WAIT)
            
            # Drain any remaining packets
            await self._drain_channels()
        else:
            logger.info("No match found this cycle")
            print(f"  >> No match found this cycle")
            # Drain channels
            await self._drain_channels()

        # ── Step 5: Leave squad ──
        self.stats.current_state = "leaving"
        await self.conn.send_online(self.pb.leave_squad(self.uid))
        await asyncio.sleep(self.leave_delay)

        # ── Step 6: Cycle delay ──
        self.stats.cycles_completed += 1
        self.stats.uptime_seconds = time.time() - self._start_time
        if self._on_progress:
            self._on_progress(self.stats)

        print(f"  >> Cycle #{cycle_num} done: {self.stats.matches_found} matches found, "
              f"{self.stats.matches_exited} exited")

        if not self._stop_requested:
            await asyncio.sleep(self.cycle_delay)

    async def _spam_ready(self, pkt_9: bytes):
        """Spam field 9 (ready signal) on ONLINE channel with jitter."""
        end_time = time.time() + self.spam_duration
        sent = 0
        while time.time() < end_time and not self._stop_requested and not self._match_found:
            ok = await self.conn.send_online(pkt_9)
            if ok:
                sent += 1
            else:
                logger.warning(f"Send failed at packet {sent} — connection dead")
                self.conn.connected = False
                break
            jitter = random.uniform(self.spam_delay * 0.8, self.spam_delay * 1.5)
            await asyncio.sleep(jitter)
        logger.info(f"Spam done: {sent} ready packets sent")

    async def _read_for_match(self):
        """Read both channels for match-found packet (f2=18 with GroupID)."""
        deadline = time.time() + self.spam_duration + MATCH_WAIT
        
        while time.time() < deadline and not self._match_found and not self._stop_requested:
            if not self.conn.connected:
                break
            
            # Read online channel
            online_data = await self.conn.recv_online(timeout=3.0)
            if online_data:
                self.conn.reset_ka_watchdog()
                await self._parse_match_packet(online_data, "online")
                if self._match_found:
                    return
            
            # Read chat channel
            chat_data = await self.conn.recv_whisper(timeout=3.0)
            if chat_data:
                self.conn.reset_ka_watchdog()
                await self._parse_match_packet(chat_data, "chat")
                if self._match_found:
                    return
        
        if not self._match_found:
            logger.info("No match packet found in wait window")

    async def _parse_match_packet(self, data: bytes, channel: str):
        """Parse incoming packet for match-found signal (f2=18 with GroupID).
        Same logic as ClanGloryBot's read_solo_match."""
        try:
            hex_data = data.hex()
            if len(hex_data) < 20:
                return

            # Try different offsets (server may prepend headers)
            for skip in [10, 8, 12, 6, 4, 0, 14, 16, 18, 20, 2, 22, 24]:
                try:
                    payload = hex_data[skip:]
                    if len(payload) < 20:
                        continue

                    # Try decrypting first
                    parsed = None
                    try:
                        from .xC4 import DEc_PacKeT, DeCode_PackEt
                        decrypted = await DEc_PacKeT(payload, self.pb.key, self.pb.iv)
                        if decrypted:
                            json_str = await DeCode_PackEt(decrypted)
                            if json_str:
                                parsed = json.loads(json_str)
                    except Exception:
                        pass

                    # Try raw decode
                    if not parsed:
                        try:
                            from .xC4 import DeCode_PackEt
                            json_str = await DeCode_PackEt(payload)
                            if json_str:
                                parsed = json.loads(json_str)
                        except Exception:
                            pass

                    if not parsed:
                        continue

                    f2 = parsed.get('2', {})
                    f2_val = f2.get('data') if isinstance(f2, dict) else f2
                    if not isinstance(f2_val, int) or f2_val < 1:
                        continue

                    # f2=18 means match found
                    if f2_val == 18 and not self._match_found:
                        f5 = parsed.get('5', {})
                        f5d = f5.get('data', {}) if isinstance(f5, dict) else {}
                        if not isinstance(f5d, dict):
                            continue

                        # Extract GroupID from field 5.1
                        f1_5 = f5d.get('1', {})
                        group_id = None
                        if isinstance(f1_5, dict) and 'data' in f1_5:
                            group_id = f1_5['data']

                        if group_id and isinstance(group_id, int) and group_id > 1000000000:
                            self._match_found = True
                            self._group_id = group_id
                            logger.info(f"MATCH FOUND! f2=18, GroupID={group_id} on {channel}")
                            print(f"  *** MATCH FOUND! GroupID={group_id} ({channel}) ***")

                            # Print match details
                            for k in sorted(f5d.keys())[:15]:
                                v = f5d[k]
                                if isinstance(v, dict) and 'data' in v:
                                    print(f"    5.{k} = {str(v['data'])[:100]}")

                            # Extract RecruitCode from field 5.8
                            f8 = f5d.get('8', {})
                            if isinstance(f8, dict) and 'data' in f8:
                                rc_str = str(f8['data'])
                                import re
                                rc_match = re.search(r'RecruitCode["\s:]+([^"]+)', rc_str)
                                if rc_match:
                                    self._recruit_code = rc_match.group(1)
                                    print(f"    RecruitCode: {self._recruit_code[:40]}...")
                            return
                    break  # Found valid parsed data at this offset
                except Exception:
                    continue
        except Exception as e:
            logger.debug(f"Parse error: {e}")

    async def _join_match(self, group_id: int):
        """Join match room using GroupID (0e15 packet)."""
        try:
            pkt = self.pb.join_match_room(group_id)
            await self.conn.send_online(pkt)
            logger.info(f"Match join sent (GroupID={group_id}, type=0e15)")
            print(f"  >> Joined match room (GroupID={group_id})")
            await asyncio.sleep(0.5)
        except Exception as e:
            logger.warning(f"Match join failed: {e}")

    async def _drain_channels(self, timeout: float = 2.0):
        """Read and discard any pending data from both channels."""
        for _ in range(3):
            online_data = await self.conn.recv_online(timeout=1.0)
            if online_data:
                self.conn.reset_ka_watchdog()
                logger.info(f"Drained online: {len(online_data)} bytes")
            chat_data = await self.conn.recv_whisper(timeout=1.0)
            if chat_data:
                self.conn.reset_ka_watchdog()
                logger.info(f"Drained chat: {len(chat_data)} bytes")
