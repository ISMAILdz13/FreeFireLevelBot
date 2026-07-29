#!/usr/bin/env python3
"""
Free Fire Like Bot Pro — Main Entry Point
MENA Server Edition | Async | Production-Grade

Usage:
    python main.py like --target 123456789 --count 100 --region ME
    python main.py guests import --file guests.json
    python main.py stats
    python main.py test-keys
    python main.py dashboard
"""

import asyncio
import sys
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from src.core.bot import FreeFireBot, BotStats
from src.core.config_loader import get_config
from src.core.logger import setup_logger
from src.guests.importer import GuestImporter
from src.guests.manager import GuestAccount

app = typer.Typer(
    name="ffbot",
    help="Free Fire Like Bot Pro — MENA Server",
    rich_markup_mode="rich",
)
console = Console()
logger = setup_logger("main")

BANNER = """
[bold red]╔══════════════════════════════════════════════════════════════╗[/bold red]
[bold red]║[/bold red]           [bold yellow]FREE FIRE LIKE BOT PRO v2.0[/bold yellow]                    [bold red]║[/bold red]
[bold red]║[/bold red]                                                              [bold red]║[/bold red]
[bold red]║[/bold red]  [cyan]Region:[/cyan] MENA (ME)    [cyan]Mode:[/cyan] Async HTTP/1.1    [cyan]Engine:[/cyan] AES-128  [bold red]║[/bold red]
[bold red]╚══════════════════════════════════════════════════════════════╝[/bold red]
"""


@app.command()
def like(
    target: Optional[str] = typer.Option(None, "--target", "-t", help="Target player UID"),
    count: Optional[int] = typer.Option(None, "--count", "-c", help="Number of likes to send"),
    region: str = typer.Option("ME", "--region", "-r", help="Target region code"),
    workers: int = typer.Option(20, "--workers", "-w", help="Max concurrent workers"),
):
    """[bold green]Execute a like streak on target account.[/bold green]"""
    console.print(BANNER)

    from rich.prompt import Prompt, IntPrompt
    if not target:
        target = Prompt.ask("[bold cyan]Enter target player UID (Where to send likes)[/bold cyan]")
    if not count:
        count = IntPrompt.ask("[bold cyan]Enter number of likes to send[/bold cyan]", default=100)

    async def run():
        bot = FreeFireBot()
        try:
            await bot.initialize()
            stats = await bot.send_likes(target, count, region)

            # Results table
            table = Table(title="Like Streak Results", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Target UID", target)
            table.add_row("Region", region)
            table.add_row("Likes Sent", str(stats.likes_sent))
            table.add_row("Likes Failed", str(stats.likes_failed))
            table.add_row("Guests Available", str(stats.guests_available))
            console.print(table)

        finally:
            await bot.shutdown()

    asyncio.run(run())


@app.command()
def guests(
    action: str = typer.Argument(..., help="Action: import, list, stats, template, verify"),
    file: Optional[str] = typer.Option(None, "--file", "-f", help="File to import"),
    format_type: str = typer.Option("json", "--format", help="File format: json, csv, txt"),
    region: str = typer.Option("ME", "--region", "-r", help="Guest region"),
):
    """[bold blue]Manage guest accounts.[/bold blue]"""

    async def run():
        from src.guests.manager import GuestManager

        gm = GuestManager()
        await gm.initialize()

        if action == "import":
            if not file:
                console.print("[red]Error: --file required for import[/red]")
                raise typer.Exit(1)

            importer = GuestImporter()
            if format_type == "json":
                guests = await importer.from_json(file, region)
            elif format_type == "csv":
                guests = await importer.from_csv(file, region)
            elif format_type == "txt":
                guests = await importer.from_txt(file, region)
            else:
                console.print(f"[red]Unknown format: {format_type}[/red]")
                raise typer.Exit(1)

            added, skipped = await gm.add_guests_bulk(guests)
            console.print(f"[green]✅ Imported {added} guests ({skipped} duplicates skipped)[/green]")

        elif action == "list":
            # List guests in database
            async with gm._db.execute("SELECT uid, region, like_count, is_active, health_status, jwt_failures FROM guests LIMIT 100") as cursor:
                rows = await cursor.fetchall()
            
            table = Table(title="Guest Accounts (First 100)", box=box.ROUNDED)
            table.add_column("UID", style="cyan")
            table.add_column("Region", style="magenta")
            table.add_column("Likes Sent", style="green")
            table.add_column("Status", style="yellow")
            table.add_column("Health", style="blue")
            table.add_column("Failures", style="red")
            
            for row in rows:
                status = "[green]Active[/green]" if row[3] else "[red]Inactive[/red]"
                health = f"[green]{row[4]}[/green]" if row[4] == "healthy" else (f"[red]{row[4]}[/red]" if row[4] == "dead" else f"[yellow]{row[4]}[/yellow]")
                table.add_row(row[0], row[1], str(row[2]), status, health, str(row[5]))
                
            console.print(table)

        elif action == "verify":
            console.print("[bold yellow]Starting guest verification...[/bold yellow]")
            from src.network.http_client import HTTPClient
            from src.crypto.aes_engine import AESEngine
            from src.auth.jwt_manager import JWTManager

            http = HTTPClient()
            await http.initialize()
            aes = AESEngine()
            jwt_mgr = JWTManager(http, aes)
            await jwt_mgr.initialize()

            from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
            
            # We need to get total count first to initialize progress bar
            async with gm._db.execute("SELECT COUNT(*) FROM guests WHERE is_active = 1") as cursor:
                row = await cursor.fetchone()
                total_active = row[0] if row else 0

            if total_active == 0:
                console.print("[yellow]No active guests to verify.[/yellow]")
                await jwt_mgr.close()
                await http.close()
                await gm.close()
                return

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("✅ {task.fields[healthy]} ❌ {task.fields[dead]}"),
            ) as progress:
                task = progress.add_task("Verifying guests", total=total_active, healthy=0, dead=0)

                def progress_cb(guest, success, healthy, dead, total):
                    progress.update(task, advance=1, healthy=healthy, dead=dead)

                healthy, dead = await gm.verify_all_guests(jwt_mgr, progress_callback=progress_cb, concurrency=10)

            console.print(f"[green]Verification complete: {healthy} healthy, {dead} dead accounts.[/green]")
            await jwt_mgr.close()
            await http.close()

        elif action == "stats":
            stats = await gm.get_stats()
            table = Table(title="Guest Pool Statistics", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            for k, v in stats.items():
                table.add_row(k.replace("_", " ").title(), str(v))
            console.print(table)

        elif action == "template":
            template = [
                {"uid": "EXAMPLE_UID_1", "password": "EXAMPLE_PASSWORD_1", "region": region},
                {"uid": "EXAMPLE_UID_2", "password": "EXAMPLE_PASSWORD_2", "region": region},
            ]
            import json
            with open("guests_template.json", "w") as f:
                json.dump(template, f, indent=2)
            console.print("[green]✅ Template saved to guests_template.json[/green]")

        else:
            console.print(f"[red]Unknown action: {action}[/red]")

        await gm.close()

    asyncio.run(run())


@app.command()
def stats():
    """[bold yellow]Show bot system statistics.[/bold yellow]"""

    async def run():
        config = get_config()

        table = Table(title="Bot Configuration", box=box.ROUNDED)
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Bot Name", config.settings.bot.name)
        table.add_row("Version", config.settings.bot.version)
        table.add_row("Target Region", config.settings.server.target_region)
        table.add_row("Game Version", config.settings.server.game_version)
        table.add_row("Max Workers", str(config.settings.bot.max_workers))
        table.add_row("Daily Like Limit", str(config.settings.rate_limiting.target_daily_limit))
        table.add_row("Proxy Enabled", str(config.settings.proxies.enabled))
        console.print(table)

    asyncio.run(run())


@app.command()
def test_keys():
    """[bold magenta]Test AES encryption keys.[/bold magenta]"""

    async def run():
        from src.crypto.aes_engine import AESEngine

        aes = AESEngine()
        results = aes.test_keys()

        table = Table(title="AES Key Test Results", box=box.ROUNDED)
        table.add_column("Key", style="cyan")
        table.add_column("Status", style="green")
        for key, status in results.items():
            color = "green" if "Valid" in status else "red"
            table.add_row(key, f"[{color}]{status}[/{color}]")
        console.print(table)

    asyncio.run(run())


@app.command()
def jwt(
    uid: str = typer.Option(..., "--uid", "-u", help="Guest account UID"),
    password: str = typer.Option(..., "--password", "-p", help="Guest account password"),
    region: str = typer.Option("ME", "--region", "-r", help="Region"),
):
    """[bold cyan]Generate JWT token for a guest account.[/bold cyan]"""

    async def run():
        from src.network.http_client import HTTPClient
        from src.crypto.aes_engine import AESEngine
        from src.auth.jwt_manager import JWTManager

        http = HTTPClient()
        await http.initialize()
        aes = AESEngine()
        jwt_mgr = JWTManager(http, aes)
        await jwt_mgr.initialize()

        result = await jwt_mgr.get_token(uid, password, region)
        if result:
            token, lock_region, server_url = result
            console.print(Panel(
                f"[green]✅ JWT Generated Successfully[/green]\n"
                f"[cyan]UID:[/cyan] {uid}\n"
                f"[cyan]Region:[/cyan] {lock_region}\n"
                f"[cyan]Server:[/cyan] {server_url}\n"
                f"[cyan]Token:[/cyan] {token[:60]}...",
                title="JWT Token",
                border_style="green",
            ))

            # Decode payload
            payload = await jwt_mgr.decode(token)
            if payload:
                console.print("[cyan]Decoded Payload:[/cyan]")
                console.print_json(data=payload)
        else:
            console.print("[red]❌ Failed to generate JWT[/red]")

        await jwt_mgr.close()
        await http.close()

    asyncio.run(run())




@app.command()
def level(
    uid: Optional[str] = typer.Option(None, "--uid", "-u", help="Guest account UID"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="Guest account password"),
    team_code: Optional[str] = typer.Option(None, "--team-code", "-t", help="Team/squad code to join (digits only)"),
    max_cycles: int = typer.Option(1000, "--max-cycles", help="Max match cycles (0 = infinite)"),
    spam_duration: int = typer.Option(18, "--spam-duration", help="Seconds to spam start-match packets"),
    spam_delay: float = typer.Option(0.2, "--spam-delay", help="Delay between start packets (seconds)"),
    wait_after: int = typer.Option(20, "--wait-after", help="Seconds to wait after match starts"),
    accounts_file: Optional[str] = typer.Option(None, "--accounts-file", "-f", help="JSON file with {uid: password} pairs"),
):
    """[bold green]Run auto level-up bot: join team, start match, repeat 24/7.[/bold green]"""
    console.print(LEVEL_BANNER)

    from rich.prompt import Prompt
    from src.level.bot import LevelBot
    from src.level.config import LevelBotConfig

    # Interactive prompts for missing required args
    if not uid and not accounts_file:
        uid = Prompt.ask("[bold cyan]Enter guest account UID[/bold cyan]")
        password = Prompt.ask("[bold cyan]Enter guest account password[/bold cyan]", password=True)
    if not team_code:
        team_code = Prompt.ask("[bold cyan]Enter team code (digits only)[/bold cyan]")

    if max_cycles == 0:
        max_cycles = 999999  # Effectively infinite

    config = LevelBotConfig.from_args(
        uid=uid,
        password=password,
        team_code=team_code,
        max_cycles=max_cycles,
        spam_duration=spam_duration,
        spam_delay=spam_delay,
        wait_after_match=wait_after,
        accounts_file=accounts_file or "",
    )

    errors = config.validate()
    if errors:
        for e in errors:
            console.print(f"[red]❌ {e}[/red]")
        raise typer.Exit(1)

    console.print(f"[cyan]UID:[/cyan] {config.uid}")
    console.print(f"[cyan]Team Code:[/cyan] {config.team_code}")
    console.print(f"[cyan]Spam Duration:[/cyan] {config.spam_duration}s")
    console.print(f"[cyan]Wait After Match:[/cyan] {config.wait_after_match}s")
    console.print(f"[cyan]Max Cycles:[/cyan] {config.max_cycles}")
    console.print()

    async def run():
        bot = LevelBot(
            uid=config.uid,
            password=config.password,
            team_code=config.team_code,
            max_cycles=config.max_cycles,
            spam_duration=config.spam_duration,
            spam_delay=config.spam_delay,
            wait_after_match=config.wait_after_match,
        )
        try:
            stats = await bot.start()
            table = Table(title="Level Bot Results", box=box.ROUNDED)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("UID", stats.uid)
            table.add_row("Team Code", stats.team_code)
            table.add_row("Connected", "✅" if stats.connected else "❌")
            table.add_row("Cycles Completed", str(stats.cycles))
            table.add_row("Matches Started", str(stats.matches))
            table.add_row("Uptime (seconds)", f"{stats.uptime_seconds:.0f}")
            table.add_row("Final State", stats.state)
            console.print(table)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopping bot...[/yellow]")
            await bot.stop()
        except Exception as e:
            console.print(f"[red]❌ Error: {e}[/red]")
            logger.error(f"Level bot error: {e}", exc_info=True)

    asyncio.run(run())


LEVEL_BANNER = """
[bold blue]╔══════════════════════════════════════════════════════════════╗[/bold blue]
[bold blue]║[/bold blue]           [bold yellow]FREE FIRE LEVEL BOT v1.0[/bold yellow]                    [bold blue]║[/bold blue]
[bold blue]║[/bold blue]                                                              [bold blue]║[/bold blue]
[bold blue]║[/bold blue]  [cyan]Mode:[/cyan] Auto Level-Up    [cyan]Engine:[/cyan] TCP + AES-128    [cyan]Loop:[/cyan] 24/7  [bold blue]║[/bold blue]
[bold blue]╚══════════════════════════════════════════════════════════════╝[/bold blue]
"""


@app.command()
def dashboard():
    """[bold white]Launch web dashboard (if enabled).[/bold white]"""
    console.print("[yellow]Dashboard mode — start with:[/yellow]")
    console.print("  uvicorn web.dashboard:app --host 0.0.0.0 --port 8080")


def guest_menu():
    import asyncio
    from rich.prompt import Prompt, Confirm
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich import box
    from src.guests.manager import GuestManager
    
    console = Console()
    
    while True:
        console.clear()
        console.print(BANNER)
        
        menu_content = (
            "[bold green]1.[/bold green] 📋 List Guest Accounts\n"
            "[bold green]2.[/bold green] 📥 Import Guest Accounts\n"
            "[bold green]3.[/bold green] 🔍 Verify All Guest Accounts\n"
            "[bold green]4.[/bold green] 📊 Show Guest Pool Statistics\n"
            "[bold green]5.[/bold green] 📄 Generate Import Template\n"
            "[bold green]6.[/bold green] 🔙 Back to Main Menu"
        )
        
        console.print(Panel(
            menu_content,
            title="[bold yellow]Guest Account Management[/bold yellow]",
            border_style="blue",
            expand=False,
            padding=(1, 5)
        ))
        
        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5", "6", "7"], default="1")
        
        async def handle_choice(c):
            gm = GuestManager()
            await gm.initialize()
            
            if c == "1":
                console.clear()
                # List guests
                async with gm._db.execute("SELECT uid, region, like_count, is_active, health_status, jwt_failures FROM guests LIMIT 100") as cursor:
                    rows = await cursor.fetchall()
                
                table = Table(title="Guest Accounts (First 100)", box=box.ROUNDED)
                table.add_column("UID", style="cyan")
                table.add_column("Region", style="magenta")
                table.add_column("Likes Sent", style="green")
                table.add_column("Status", style="yellow")
                table.add_column("Health", style="blue")
                table.add_column("Failures", style="red")
                
                for row in rows:
                    status = "[green]Active[/green]" if row[3] else "[red]Inactive[/red]"
                    health = f"[green]{row[4]}[/green]" if row[4] == "healthy" else (f"[red]{row[4]}[/red]" if row[4] == "dead" else f"[yellow]{row[4]}[/yellow]")
                    table.add_row(row[0], row[1], str(row[2]), status, health, str(row[5]))
                    
                console.print(table)
                Prompt.ask("\nPress Enter to continue")
                
            elif c == "2":
                console.clear()
                console.print(Panel("[bold yellow]📥 Import Guest Accounts[/bold yellow]", border_style="blue"))
                
                file_path = Prompt.ask("[bold cyan]Enter file path to import[/bold cyan]")
                format_type = Prompt.ask("[bold cyan]Enter file format[/bold cyan]", choices=["json", "csv", "txt"], default="json")
                region = Prompt.ask("[bold cyan]Enter guest region[/bold cyan]", default="ME")
                
                from src.guests.importer import GuestImporter
                importer = GuestImporter()
                try:
                    if format_type == "json":
                        guests = await importer.from_json(file_path, region)
                    elif format_type == "csv":
                        guests = await importer.from_csv(file_path, region)
                    elif format_type == "txt":
                        guests = await importer.from_txt(file_path, region)
                    else:
                        guests = []
                        
                    added, skipped = await gm.add_guests_bulk(guests)
                    console.print(f"\n[green]✅ Imported {added} guests ({skipped} duplicates skipped)[/green]")
                except Exception as e:
                    console.print(f"\n[red]❌ Import failed: {e}[/red]")
                Prompt.ask("\nPress Enter to continue")
                
            elif c == "3":
                console.clear()
                console.print(Panel("[bold yellow]🔍 Verify All Guest Accounts[/bold yellow]", border_style="blue"))
                
                async with gm._db.execute("SELECT COUNT(*) FROM guests WHERE is_active = 1") as cursor:
                    row = await cursor.fetchone()
                    total_active = row[0] if row else 0
                    
                if total_active == 0:
                    console.print("[yellow]No active guest accounts found to verify.[/yellow]")
                    await gm.close()
                    Prompt.ask("\nPress Enter to continue")
                    return
                    
                if not Confirm.ask(f"Do you want to verify all {total_active} active guest accounts in parallel?", default=True):
                    await gm.close()
                    return
                    
                from src.network.http_client import HTTPClient
                from src.crypto.aes_engine import AESEngine
                from src.auth.jwt_manager import JWTManager
                
                http = HTTPClient()
                await http.initialize()
                aes = AESEngine()
                jwt_mgr = JWTManager(http, aes)
                await jwt_mgr.initialize()
                
                from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    TextColumn("✅ {task.fields[healthy]} ❌ {task.fields[dead]}"),
                ) as progress:
                    task = progress.add_task("Verifying guests", total=total_active, healthy=0, dead=0)
                    
                    def progress_cb(guest, success, healthy, dead, total):
                        progress.update(task, advance=1, healthy=healthy, dead=dead)
                        
                    healthy, dead = await gm.verify_all_guests(jwt_mgr, progress_callback=progress_cb, concurrency=10)
                    
                console.print(f"\n[green]✅ Verification complete! {healthy} healthy, {dead} dead accounts.[/green]")
                await jwt_mgr.close()
                await http.close()
                Prompt.ask("\nPress Enter to continue")
                
            elif c == "4":
                console.clear()
                stats = await gm.get_stats()
                table = Table(title="Guest Pool Statistics", box=box.ROUNDED)
                table.add_column("Metric", style="cyan")
                table.add_column("Value", style="green")
                for k, v in stats.items():
                    table.add_row(k.replace("_", " ").title(), str(v))
                console.print(table)
                Prompt.ask("\nPress Enter to continue")
                
            elif c == "5":
                console.clear()
                region = Prompt.ask("[bold cyan]Enter region for template[/bold cyan]", default="ME")
                template = [
                    {"uid": "EXAMPLE_UID_1", "password": "EXAMPLE_PASSWORD_1", "region": region},
                    {"uid": "EXAMPLE_UID_2", "password": "EXAMPLE_PASSWORD_2", "region": region},
                ]
                import json
                with open("guests_template.json", "w") as f:
                    json.dump(template, f, indent=2)
                console.print("[green]✅ Template saved to guests_template.json[/green]")
                Prompt.ask("\nPress Enter to continue")
                
            await gm.close()
            
        if choice == "6":
            break
            
        asyncio.run(handle_choice(choice))


def interactive_menu():
    import sys
    from rich.prompt import Prompt, IntPrompt
    from rich.console import Console
    from rich.panel import Panel
    from rich.align import Align
    
    console = Console()
    
    while True:
        console.clear()
        console.print(BANNER)
        
        menu_content = (
            "[bold green]1.[/bold green] 🎯 Start Like Streak\n"
            "[bold green]2.[/bold green] 👥 Manage Guest Accounts\n"
            "[bold green]3.[/bold green] ⚙️ View Bot Configuration\n"
            "[bold green]4.[/bold green] 🔑 Test AES Encryption Keys\n"
            "[bold green]5.[/bold green] 🌐 Launch Web Dashboard\n"
            "[bold green]6.[/bold green] 🚪 Exit"
        )
        
        console.print(Panel(
            Align.center(menu_content, vertical="middle"),
            title="[bold yellow]Main Menu[/bold yellow]",
            border_style="cyan",
            expand=False,
            padding=(1, 5)
        ))
        
        choice = Prompt.ask("Select an option", choices=["1", "2", "3", "4", "5", "6", "7"], default="1")
        
        if choice == "1":
            # Send Like Streak
            console.clear()
            console.print(Panel("[bold yellow]🎯 Send Like Streak[/bold yellow]", border_style="green"))
            
            # Interactive inputs
            target = Prompt.ask("[bold cyan]Enter target player UID (Where to send likes)[/bold cyan]")
            
            # Show list of regions
            config = get_config()
            regions = list(config.regions.regions.keys())
            regions_str = ", ".join(regions)
            console.print(f"[yellow]Supported regions:[/yellow] {regions_str}")
            region = Prompt.ask("[bold cyan]Enter target region code[/bold cyan]", choices=regions, default="ME")
            
            count = IntPrompt.ask("[bold cyan]Enter number of likes to send[/bold cyan]", default=100)
            workers = IntPrompt.ask("[bold cyan]Enter max concurrent workers[/bold cyan]", default=20)
            
            console.print(f"\n[bold yellow]Preparing to send {count} likes to {target} ({region}) with {workers} workers...[/bold yellow]")
            
            async def run_likes():
                bot = FreeFireBot()
                # Update configuration dynamically
                bot.config.settings.bot.max_workers = workers
                try:
                    await bot.initialize()
                    stats = await bot.send_likes(target, count, region)
                    
                    table = Table(title="Like Streak Results", box=box.ROUNDED)
                    table.add_column("Metric", style="cyan")
                    table.add_column("Value", style="green")
                    table.add_row("Target UID", target)
                    table.add_row("Region", region)
                    table.add_row("Likes Sent", str(stats.likes_sent))
                    table.add_row("Likes Failed", str(stats.likes_failed))
                    table.add_row("Guests Available", str(stats.guests_available))
                    console.print(table)
                finally:
                    await bot.shutdown()
            
            asyncio.run(run_likes())
            Prompt.ask("\nPress Enter to return to main menu")
            
        elif choice == "2":
            guest_menu()
            
        elif choice == "3":
            console.clear()
            async def run_stats():
                config = get_config()
                table = Table(title="Bot Configuration", box=box.ROUNDED)
                table.add_column("Setting", style="cyan")
                table.add_column("Value", style="green")
                table.add_row("Bot Name", config.settings.bot.name)
                table.add_row("Version", config.settings.bot.version)
                table.add_row("Target Region", config.settings.server.target_region)
                table.add_row("Game Version", config.settings.server.game_version)
                table.add_row("Max Workers", str(config.settings.bot.max_workers))
                table.add_row("Daily Like Limit", str(config.settings.rate_limiting.target_daily_limit))
                table.add_row("Proxy Enabled", str(config.settings.proxies.enabled))
                console.print(table)
            asyncio.run(run_stats())
            Prompt.ask("\nPress Enter to return to main menu")
            
        elif choice == "4":
            console.clear()
            async def run_keys():
                from src.crypto.aes_engine import AESEngine
                aes = AESEngine()
                results = aes.test_keys()
                
                table = Table(title="AES Key Test Results", box=box.ROUNDED)
                table.add_column("Key", style="cyan")
                table.add_column("Status", style="green")
                for key, status in results.items():
                    color = "green" if "Valid" in status else "red"
                    table.add_row(key, f"[{color}]{status}[/{color}]")
                console.print(table)
            asyncio.run(run_keys())
            Prompt.ask("\nPress Enter to return to main menu")
            
        elif choice == "5":
            console.clear()
            console.print(Panel(
                "[bold yellow]🌐 Launching Web Dashboard[/bold yellow]\n\n"
                "To start the dashboard, run this command in another terminal:\n"
                "  [green]uvicorn web.dashboard:app --host 0.0.0.0 --port 8080[/green]\n\n"
                "Or do you want to run it right now in this process?",
                title="Dashboard Mode",
                border_style="cyan"
            ))
            run_now = Prompt.ask("Run now in this window? (y/n)", choices=["y", "n"], default="n")
            if run_now == "y":
                import uvicorn
                console.print("[green]Starting Uvicorn server... Press Ctrl+C to stop.[/green]")
                try:
                    uvicorn.run("web.dashboard:app", host="0.0.0.0", port=8080, log_level="info")
                except KeyboardInterrupt:
                    console.print("[yellow]Server stopped.[/yellow]")
            
        elif choice == "6":
            console.clear()
            console.print(Panel("[bold yellow]📈 Auto Level-Up Bot[/bold yellow]", border_style="blue"))

            from rich.prompt import Prompt
            level_uid = Prompt.ask("[bold cyan]Enter guest account UID[/bold cyan]")
            level_password = Prompt.ask("[bold cyan]Enter guest account password[/bold cyan]", password=True)
            level_team_code = Prompt.ask("[bold cyan]Enter team code (digits only)[/bold cyan]")

            from rich.prompt import IntPrompt
            level_spam = IntPrompt.ask("[bold cyan]Spam duration (seconds)[/bold cyan]", default=18)
            level_wait = IntPrompt.ask("[bold cyan]Wait after match (seconds)[/bold cyan]", default=20)
            level_max = IntPrompt.ask("[bold cyan]Max cycles (0 = infinite)[/bold cyan]", default=1000)
            if level_max == 0:
                level_max = 999999

            console.print(f"\n[bold yellow]Starting level bot: team={level_team_code}, spam={level_spam}s, wait={level_wait}s[/bold yellow]")

            async def run_level():
                from src.level.bot import LevelBot
                bot = LevelBot(
                    uid=level_uid,
                    password=level_password,
                    team_code=level_team_code,
                    max_cycles=level_max,
                    spam_duration=level_spam,
                    wait_after_match=level_wait,
                )
                try:
                    stats = await bot.start()
                    table = Table(title="Level Bot Results", box=box.ROUNDED)
                    table.add_column("Metric", style="cyan")
                    table.add_column("Value", style="green")
                    table.add_row("UID", stats.uid)
                    table.add_row("Team Code", stats.team_code)
                    table.add_row("Connected", "✅" if stats.connected else "❌")
                    table.add_row("Cycles", str(stats.cycles))
                    table.add_row("Matches", str(stats.matches))
                    table.add_row("Uptime (s)", f"{stats.uptime_seconds:.0f}")
                    table.add_row("Final State", stats.state)
                    console.print(table)
                except KeyboardInterrupt:
                    console.print("\n[yellow]Stopping...[/yellow]")
                    await bot.stop()
                except Exception as e:
                    console.print(f"[red]❌ {e}[/red]")

            asyncio.run(run_level())
            Prompt.ask("\nPress Enter to return to main menu")

        elif choice == "7":
            console.print("[bold green]Thank you for using Free Fire Bot Pro! Goodbye! 👋[/bold green]")
            sys.exit(0)


@app.command()
def generate(
    count: int = typer.Option(10, "--count", "-c", help="Number of accounts to generate"),
    region: str = typer.Option("ME", "--region", "-r", help="Region code"),
    prefix: str = typer.Option("BOT", "--prefix", "-p", help="Name prefix for accounts"),
    workers: int = typer.Option(3, "--workers", "-w", help="Concurrent workers (keep low to avoid rate-limit)"),
    save: bool = typer.Option(True, "--save/--no-save", help="Save to database automatically"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show debug output for each step"),
    fast: bool = typer.Option(False, "--fast", "-f", help="Fast mode: register only, skip login (recommended)"),
):
    """[bold magenta]Generate new guest accounts automatically via Garena API.[/bold magenta]"""
    import os as _os
    if verbose:
        _os.environ["GEN_DEBUG"] = "1"

    console.print(BANNER)
    mode_label = "fast (register only)" if fast else "full (register + login)"
    console.print(f"[bold cyan]Generating {count} accounts (region: {region}, mode: {mode_label})[/bold cyan]")

    from src.guests.generator import create_guest_account, register_only, save_to_json, save_to_db
    import time
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

    accounts = []
    created = 0
    failed = 0
    start_time = time.time()
    MAX_ATTEMPTS = count * 5

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("OK={task.fields[ok]} FAIL={task.fields[fail]}"),
    ) as progress:
        task = progress.add_task(
            f"Generating {count} accounts",
            total=count, ok=0, fail=0,
        )

        import concurrent.futures

        def worker():
            if fast:
                return register_only(name_prefix=prefix, region=region)
            else:
                return create_guest_account(name_prefix=prefix, region=region)

        attempts = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            while created < count and attempts < MAX_ATTEMPTS:
                needed = min(count - created, workers)
                futures = [pool.submit(worker) for _ in range(needed)]
                for f in concurrent.futures.as_completed(futures):
                    attempts += 1
                    acc = f.result()
                    if acc and acc.get("status") in ("full_login", "registered"):
                        accounts.append(acc)
                        created += 1
                        progress.update(task, advance=1, ok=created)
                    else:
                        failed += 1
                        progress.update(task, fail=failed)
                if created < count and attempts < MAX_ATTEMPTS:
                    time.sleep(2)

    elapsed = time.time() - start_time

    if not accounts:
        console.print(f"\n[red]All {failed} attempts failed![/red]")
        console.print("[yellow]Run with --verbose to see which step fails:[/yellow]")
        console.print("[yellow]  python main.py generate --count 1 --verbose --fast[/yellow]")
        console.print("[yellow]\nCommon causes:[/yellow]")
        console.print("[yellow]  1. Garena rate-limited your IP (wait 5 min, try again)[/yellow]")
        console.print("[yellow]  2. Your network blocks Garena servers (try VPN/mobile data)[/yellow]")
        console.print("[yellow]  3. Registration endpoint down (try later)[/yellow]")
        return

    # Save FIRST (before any display that might crash)
    if save and accounts:
        save_to_json(accounts)
        console.print(f"[green]Saved {len(accounts)} accounts to data/guests.json[/green]")
        try:
            import asyncio as _aio
            _aio.run(save_to_db(accounts))
            console.print(f"[green]Saved to database ({len(accounts)} accounts)[/green]")
        except Exception as e:
            console.print(f"[yellow]DB save failed: {e}[/yellow]")

    console.print(f"\n[green]Generated {created} accounts in {elapsed:.1f}s[/green]")
    if failed:
        console.print(f"[red]{failed} attempts failed[/red]")

    # Simple display (no rich table to avoid type errors)
    for acc in accounts[:10]:
        oid = acc.get("open_id", "")
        has_tok = "YES" if oid else "NO"
        console.print(f"  UID: {acc['uid']}  Password: {acc['password'][:25]}...  Status: {acc['status']}  Tokens: {has_tok}")
    if len(accounts) > 10:
        console.print(f"  ... and {len(accounts)-10} more")

    console.print(f"\n[cyan]Next: python main.py like --target <UID> --count {created}[/cyan]")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        interactive_menu()
    else:
        app()



