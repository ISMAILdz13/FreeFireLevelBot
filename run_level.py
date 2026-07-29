#!/usr/bin/env python3
"""
Standalone Level Bot Runner
Quick start without the full CLI.

Usage:
    python run_level.py --uid 12345678 --password abc123 --team-code 654321
    python run_level.py --accounts-file accounts.json --team-code 654321
    python run_level.py --uid 12345678 --password abc123 --team-code 654321 --max-cycles 0
"""

import asyncio
import argparse
import json
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("data/level_bot.log"),
        ],
    )
    # Suppress noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


async def run_single(uid: str, password: str, team_code: str, args):
    """Run a single level bot instance."""
    from src.level.bot import LevelBot

    bot = LevelBot(
        uid=uid,
        password=password,
        team_code=team_code,
        max_cycles=args.max_cycles,
        spam_duration=args.spam_duration,
        spam_delay=args.spam_delay,
        wait_after_match=args.wait_after,
    )

    try:
        stats = await bot.start()
        print(f"\n{'='*50}")
        print(f"  Bot finished!")
        print(f"  UID:         {stats.uid}")
        print(f"  Team Code:   {stats.team_code}")
        print(f"  Connected:   {'✅' if stats.connected else '❌'}")
        print(f"  Cycles:      {stats.cycles}")
        print(f"  Matches:     {stats.matches}")
        print(f"  Uptime:      {stats.uptime_seconds:.0f}s")
        print(f"  Final State:  {stats.state}")
        print(f"{'='*50}")
    except KeyboardInterrupt:
        print("\n⏹️  Stopping bot...")
        await bot.stop()
    except Exception as e:
        logging.error(f"Bot error: {e}", exc_info=True)
        return 1

    return 0


async def run_multi(accounts: dict, team_code: str, args):
    """Run multiple level bot instances concurrently."""
    from src.level.bot import LevelBot

    tasks = []
    for uid, password in accounts.items():
        bot = LevelBot(
            uid=uid,
            password=password,
            team_code=team_code,
            max_cycles=args.max_cycles,
            spam_duration=args.spam_duration,
            spam_delay=args.spam_delay,
            wait_after_match=args.wait_after,
        )
        tasks.append(bot.start())

    results = await asyncio.gather(*tasks, return_exceptions=True)
    for i, (uid, result) in enumerate(zip(accounts.keys(), results)):
        if isinstance(result, Exception):
            print(f"❌ {uid}: {result}")
        else:
            print(f"✅ {uid}: {result.cycles} cycles, {result.matches} matches")


def main():
    parser = argparse.ArgumentParser(
        description="Free Fire Level Bot — Auto level-up via team match spam",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single account
  python run_level.py --uid 12345678 --password abc123 --team-code 654321

  # Multiple accounts from JSON file
  python run_level.py --accounts-file accounts.json --team-code 654321

  # Infinite loops, faster cycles
  python run_level.py --uid 12345678 --password abc123 --team-code 654321 --max-cycles 0 --spam-duration 10 --wait-after 15
        """,
    )
    parser.add_argument("--uid", "-u", help="Guest account UID")
    parser.add_argument("--password", "-p", help="Guest account password")
    parser.add_argument("--team-code", "-t", required=True, help="Team/squad code (digits only)")
    parser.add_argument("--accounts-file", "-f", help="JSON file with {uid: password} pairs")
    parser.add_argument("--max-cycles", type=int, default=1000, help="Max match cycles (0 = infinite)")
    parser.add_argument("--spam-duration", type=int, default=18, help="Seconds to spam start packets")
    parser.add_argument("--spam-delay", type=float, default=0.2, help="Delay between start packets")
    parser.add_argument("--wait-after", type=int, default=20, help="Seconds to wait after match")
    parser.add_argument("--verbose", "-v", action="store_true", help="Debug logging")
    args = parser.parse_args()

    # Ensure data directory exists
    os.makedirs("data", exist_ok=True)
    setup_logging(args.verbose)

    logger = logging.getLogger("levelbot")

    if args.accounts_file:
        if not os.path.exists(args.accounts_file):
            print(f"❌ Accounts file not found: {args.accounts_file}")
            sys.exit(1)
        with open(args.accounts_file) as f:
            accounts = json.load(f)
        if not accounts:
            print("❌ No accounts in file")
            sys.exit(1)
        print(f"🚀 Starting {len(accounts)} bot instance(s) | Team: {args.team_code}")
        asyncio.run(run_multi(accounts, args.team_code, args))
    elif args.uid and args.password:
        print(f"🚀 Starting level bot | UID: {args.uid} | Team: {args.team_code}")
        exit_code = asyncio.run(run_single(args.uid, args.password, args.team_code, args))
        sys.exit(exit_code)
    else:
        print("❌ Either --uid + --password or --accounts-file is required")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
