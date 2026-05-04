"""System status overview."""
import json
import os
import subprocess
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = BASE_DIR.parent
PID_FILE = PROJECT_DIR / "cococat.pid"


def status():
    """Show overall system status."""
    agents_dir = BASE_DIR / "agents"
    config_path = agents_dir / "config.toml"

    # Load config
    try:
        import tomllib
        lib = tomllib
    except ImportError:
        import tomli as lib
    try:
        with open(config_path, "rb") as f:
            config = lib.load(f)
    except Exception:
        config = {"agents": []}

    agents = config.get("agents", [])
    enabled_count = sum(1 for a in agents if a.get("enabled", False))
    total = len(agents)

    # Check daemon
    daemon_running = False
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            daemon_running = True
        except (ProcessLookupError, ValueError, OSError):
            pass

    # Count dispatch queue
    dispatch_dir = agents_dir / "dispatch_queue"
    pending_dispatches = len(list(dispatch_dir.glob("*.json"))) if dispatch_dir.exists() else 0

    # Count pending hires
    hire_pending = agents_dir / "hire_requests" / "pending"
    pending_hires = len(list(hire_pending.glob("*.json"))) if hire_pending.exists() else 0

    # Count mail
    mailbox_dir = agents_dir / "mailbox"
    total_unread = 0
    if mailbox_dir.exists():
        for agent_dir in mailbox_dir.iterdir():
            inbox = agent_dir / "inbox.jsonl"
            if inbox.exists():
                for line in inbox.read_text().splitlines():
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                        if msg.get("status") == "unread":
                            total_unread += 1
                    except json.JSONDecodeError:
                        pass

    # System info
    rust_version = ""
    try:
        result = subprocess.run(
            [os.path.expanduser("~/.cargo/bin/cargo"), "--version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            rust_version = result.stdout.strip()
    except Exception:
        pass

    table = Table(title="CocoCat System Status")
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    table.add_row("Daemon", "[green]Running[/green]" if daemon_running else "[red]Stopped[/red]")
    table.add_row("Agents", f"{enabled_count}/{total} enabled")
    table.add_row("Pending Dispatches", str(pending_dispatches))
    table.add_row("Pending Hires", str(pending_hires))
    table.add_row("Unread Mail", str(total_unread))
    if rust_version:
        table.add_row("Runtime", rust_version)

    console.print(table)
