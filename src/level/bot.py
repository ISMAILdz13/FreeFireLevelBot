"""
Level Bot Orchestrator
Coordinates auth, connection, and match engine for automated leveling.

Usage:
    bot = LevelBot(uid="12345678", password="abc123", team_code="654321")
    await bot.start()
    # ... runs until stopped
    await bot.stop()
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from .auth import LevelAuth
from .connection import GameConnection
from .match_engine import MatchEngine, MatchStats
from .packet_builder import PacketBuilder

logger = logging.getLogger("levelbot")


@dataclass
class LevelBotStats:
    """Top-level bot stats for display."""
    uid: str = ""
    team_code: str = ""
    connected: bool = False
    cycles: int = 0
    matches: int = 0
    uptime_seconds: float = 0.0
    state: str = "idle"


class LevelBot:
    """
    Main level bot controller.

    Flow:
        1. Authenticate via Garena guest OAuth + MajorLogin
        2. Connect to whisper + online TCP servers
        3. Run match loop (join → start → wait → leave → repeat)
        4. Graceful shutdown on stop

    Args:
        uid: Garena guest UID
        password: Guest password
        team_code: Squad team code to join
        max_cycles: Safety limit (default 1000)
        spam_duration: Seconds to spam start packets (default 18)
        spam_delay: Delay between start packets (default 0.2s)
        wait_after_match: Seconds to wait after match (default 20)
    """

    def __init__(
        self,
        uid: str,
        password: str,
        team_code: str,
        max_cycles: int = 1000,
        spam_duration: int = 18,
        spam_delay: float = 0.2,
        wait_after_match: int = 20,
        join_delay: float = 2.0,
        leave_delay: float = 2.0,
        cycle_delay: float = 2.0,
    ):
        self.uid = uid
        self.password = password
        self.team_code = team_code
        self.max_cycles = max_cycles
        self.spam_duration = spam_duration
        self.spam_delay = spam_delay
        self.wait_after_match = wait_after_match
        self.join_delay = join_delay
        self.leave_delay = leave_delay
        self.cycle_delay = cycle_delay

        self.connection: Optional[GameConnection] = None
        self.engine: Optional[MatchEngine] = None
        self.auth: Optional[LevelAuth] = None
        self.http: Optional[httpx.AsyncClient] = None
        self.pb: Optional[PacketBuilder] = None
        self.stats = LevelBotStats(uid=uid, team_code=team_code)
        self._running = False

    async def start(self) -> LevelBotStats:
        """
        Start the bot: authenticate, connect, and run the match loop.
        Returns final stats when done.
        """
        logger.info(f"🚀 LevelBot starting | UID: {self.uid} | Team: {self.team_code}")
        self.stats.state = "authenticating"

        # ── HTTP client for auth ──
        self.http = httpx.AsyncClient(verify=False, follow_redirects=True)
        self.auth = LevelAuth(self.http)

        # ── Step 1: Guest OAuth ──
        oauth_result = await self.auth.guest_token(self.uid, self.password)
        if not oauth_result:
            self.stats.state = "auth_failed"
            logger.error("Guest OAuth failed")
            await self.http.aclose()
            return self.stats

        access_token, open_id = oauth_result

        # ── Step 2: MajorLogin ──
        login_result = await self.auth.major_login(access_token, open_id)
        if not login_result or (isinstance(login_result, dict) and login_result.get("error")):
            # Check if the response was a tiny 200 (banned/rejected, not a server error)
            if login_result and isinstance(login_result, dict) and not login_result.get("error"):
                pass  # Has result but no token — handled below
            elif not login_result:
                self.stats.state = "banned"
                logger.error("MajorLogin: server returned 200 but no JWT token — account likely BANNED")
                print(f"\n  [!] MajorLogin: Server accepted request but returned no token.")
                print(f"      This usually means the guest account is BANNED or suspended.")
                print(f"      Try a different guest account.\n")
                await self.http.aclose()
                return self.stats
            last_status = login_result.get("last_status", 0) if isinstance(login_result, dict) else 0
            if last_status == 503:
                self.stats.state = "server_down"
                logger.error("MajorLogin: Garena server is DOWN (503). Try again later.")
                print(f"\n  [!] Garena server is DOWN (503). Not a ban - server maintenance.")
                print(f"      Try again in a few hours.\n")
            elif last_status in (400, 401, 403):
                self.stats.state = "banned"
                logger.error(f"MajorLogin: Account BANNED (HTTP {last_status})")
                print(f"\n  [!] Account is BANNED (HTTP {last_status}).\n")
            else:
                self.stats.state = "auth_failed"
                logger.error(f"MajorLogin failed (HTTP {last_status})")
                print(f"\n  [!] MajorLogin failed (HTTP {last_status or 'no response'}).\n")
            await self.http.aclose()
            return self.stats

        jwt_token = login_result["token"]
        key = login_result["key"]
        iv = login_result["iv"]
        timestamp = login_result["timestamp"]

        logger.info(f"Auth successful | Key: {key.hex()[:8]}... | IV: {iv.hex()[:8]}...")

        # ── Step 3: GetLoginData ──
        # Use the dynamic URL from MajorLogin response for GetLoginData
        base_url = login_result.get("url", None)
        # Pass the MajorLogin encrypted payload for reuse (same as ClanGloryBot)
        major_login_payload = login_result.get("payload", None)
        server_info = await self.auth.get_login_data(
            jwt_token, base_url, access_token, major_login_payload
        )
        if not server_info:
            self.stats.state = "auth_failed"
            logger.error("GetLoginData failed")
            await self.http.aclose()
            return self.stats

        whisper_ip, whisper_port, online_ip, online_port = server_info

        # ── Step 4: Build connection token ──
        account_uid = login_result.get("account_uid", int(self.uid))
        conn_token = await self.auth.build_connection_token(
            jwt_token, key, iv, timestamp, account_uid
        )
        if not conn_token:
            self.stats.state = "auth_failed"
            logger.error("Connection token build failed")
            await self.http.aclose()
            return self.stats

        # Close HTTP client — we're on TCP now
        await self.http.aclose()

        # ── Step 5: Connect to game servers ──
        self.stats.state = "connecting"
        self.connection = GameConnection()
        region = login_result.get("region", "ME")
        self.pb = PacketBuilder(key, iv, region=region)

        # Set crypto keys on connection (for keepalive + global auth)
        self.connection.set_crypto(key, iv)

        try:
            await self.connection.connect(
                whisper_ip, whisper_port,
                online_ip, online_port,
                conn_token,
            )
            self.stats.connected = True
            logger.info("✅ Connected to game servers")
        except Exception as e:
            self.stats.state = "connection_failed"
            logger.error(f"Connection failed: {e}")
            return self.stats

        # ── Step 6: Run match loop ──
        self.stats.state = "running"
        self._running = True
        self.engine = MatchEngine(
            connection=self.connection,
            packet_builder=self.pb,
            spam_duration=self.spam_duration,
            spam_delay=self.spam_delay,
            wait_after_match=self.wait_after_match,
            join_delay=self.join_delay,
            leave_delay=self.leave_delay,
            cycle_delay=self.cycle_delay,
            uid=account_uid,
        )

        def on_progress(stats: MatchStats):
            self.stats.cycles = stats.cycles_completed
            self.stats.matches = stats.matches_started
            self.stats.uptime_seconds = stats.uptime_seconds
            self.stats.state = stats.current_state

        self.engine.on_progress(on_progress)

        match_stats = await self.engine.start(self.team_code, self.max_cycles)

        # ── Cleanup ──
        self.stats.cycles = match_stats.cycles_completed
        self.stats.matches = match_stats.matches_started
        self.stats.uptime_seconds = match_stats.uptime_seconds
        self.stats.state = "stopped"
        self._running = False

        await self.connection.close()
        logger.info(f"✅ LevelBot done | Cycles: {self.stats.cycles} | Matches: {self.stats.matches}")

        return self.stats

    async def stop(self):
        """Stop the match loop gracefully (finishes current cycle)."""
        if self.engine:
            self.engine.stop()
        self._running = False
        logger.info("Stop requested")

    @property
    def is_running(self) -> bool:
        return self._running
