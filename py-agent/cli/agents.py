"""Agent management commands."""
import json
import os
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(help="Manage and inspect agents")
console = Console()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = BASE_DIR / "agents"
CONFIG_PATH = AGENTS_DIR / "config.toml"


def _load_config():
    try:
        import tomllib
        lib = tomllib
    except ImportError:
        import tomli as lib
    try:
        with open(CONFIG_PATH, "rb") as f:
            return lib.load(f)
    except (FileNotFoundError, Exception) as e:
        console.print(f"[red]Error loading config: {e}[/red]")
        return {"agents": []}


def _read_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


@app.command()
def list():
    """List all configured agents."""
    config = _load_config()
    agents = config.get("agents", [])

    if not agents:
        console.print("[yellow]No agents configured.[/yellow]")
        return

    table = Table(title="Agents")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="green")
    table.add_column("Enabled")
    table.add_column("Scene")
    table.add_column("Running")

    for a in agents:
        agent_id = a.get("id", "")
        enabled = "[green]✓[/green]" if a.get("enabled", False) else "[red]✗[/red]"
        scene = a.get("scene", "default")
        running = "[yellow]?[/yellow]"
        pid_path = AGENTS_DIR / agent_id / ".pid"
        if pid_path.exists():
            running = "[green]✓[/green]" if pid_path.read_text().strip().isdigit() else "[red]✗[/red]"
        table.add_row(agent_id, a.get("name", ""), enabled, scene, running)

    console.print(table)


@app.command()
def status(agent_id: str = typer.Argument(..., help="Agent ID")):
    """Show agent status and info."""
    config = _load_config()
    agents = config.get("agents", [])
    agent = next((a for a in agents if a["id"] == agent_id), None)

    if not agent:
        console.print(f"[red]Agent '{agent_id}' not found.[/red]")
        raise typer.Exit(1)

    agent_dir = AGENTS_DIR / agent_id
    profile_path = agent_dir / "profile.json"
    memory_path = agent_dir / "memory" / "MEMORY.md"

    info = {
        "ID": agent_id,
        "Name": agent.get("name", ""),
        "Enabled": str(agent.get("enabled", False)),
        "Scene": agent.get("scene", "default"),
        "Interpreter": agent.get("interpreter", ""),
        "Script": agent.get("script", ""),
    }

    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text())
            info["Role"] = profile.get("role", "")
            info["Objective"] = profile.get("objective", "")
        except json.JSONDecodeError:
            pass

    memory_size = ""
    if memory_path.exists():
        size = len(memory_path.read_text())
        memory_size = f"{size} chars"

    info["Memory"] = memory_size or "[dim]empty[/dim]"

    table = Table(title=f"Agent: {info['Name']} ({agent_id})")
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    for k, v in info.items():
        table.add_row(k, str(v))

    console.print(table)


@app.command()
def inspect(agent_id: str = typer.Argument(..., help="Agent ID")):
    """Show detailed agent profile and memory."""
    agent_dir = AGENTS_DIR / agent_id

    if not agent_dir.exists():
        console.print(f"[red]Agent '{agent_id}' not found.[/red]")
        raise typer.Exit(1)

    profile_path = agent_dir / "profile.json"
    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text())
            text = json.dumps(profile, indent=2, ensure_ascii=False)
            console.print(Panel(text, title=f"[cyan]{agent_id}[/cyan] Profile"))
        except json.JSONDecodeError:
            console.print("[yellow]Profile file is corrupted.[/yellow]")

    memory_path = agent_dir / "memory" / "MEMORY.md"
    if memory_path.exists():
        content = memory_path.read_text()
        preview = content[:2000]
        if len(content) > 2000:
            preview += "\n... [truncated]"
        console.print(Panel(preview, title=f"[cyan]{agent_id}[/cyan] Memory"))
