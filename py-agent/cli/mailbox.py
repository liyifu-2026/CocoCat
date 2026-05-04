"""Mailbox commands - read inter-agent mailboxes."""
import json
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Read agent mailboxes")
console = Console()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = BASE_DIR / "agents"


@app.command()
def list():
    """List all agents with unread mail."""
    from .agents import _load_config

    config = _load_config()
    agents = config.get("agents", [])

    table = Table(title="Agent Mailboxes")
    table.add_column("Agent", style="cyan")
    table.add_column("Unread")
    table.add_column("Total")

    for a in agents:
        aid = a.get("id", "")
        inbox_path = AGENTS_DIR / "mailbox" / aid / "inbox.jsonl"
        total = 0
        unread = 0
        if inbox_path.exists():
            for line in inbox_path.read_text().splitlines():
                if not line.strip():
                    continue
                total += 1
                try:
                    msg = json.loads(line)
                    if msg.get("status") == "unread":
                        unread += 1
                except json.JSONDecodeError:
                    pass
        unread_str = f"[green]{unread}[/green]" if unread > 0 else "[dim]0[/dim]"
        table.add_row(aid, unread_str, str(total))

    console.print(table)


@app.command()
def show(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    unread_only: bool = typer.Option(False, "--unread", "-u", help="Show only unread messages"),
):
    """Show an agent's mailbox contents."""
    inbox_path = AGENTS_DIR / "mailbox" / agent_id / "inbox.jsonl"

    if not inbox_path.exists():
        console.print(f"[yellow]No mailbox found for '{agent_id}'.[/yellow]")
        return

    messages = []
    for line in inbox_path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            msg = json.loads(line)
            if unread_only and msg.get("status") != "unread":
                continue
            messages.append(msg)
        except json.JSONDecodeError:
            continue

    if not messages:
        console.print("[yellow]No messages.[/yellow]")
        return

    table = Table(title=f"Mailbox: {agent_id}")
    table.add_column("#", style="dim")
    table.add_column("From", style="cyan")
    table.add_column("Status")
    table.add_column("Content")

    for i, msg in enumerate(messages, 1):
        status = msg.get("status", "unknown")
        status_str = {
            "unread": "[yellow]unread[/yellow]",
            "read": "[dim]read[/dim]",
        }.get(status, status)
        content = (msg.get("content", "") or "")[:120]
        table.add_row(str(i), msg.get("from", "?"), status_str, content)

    console.print(table)
