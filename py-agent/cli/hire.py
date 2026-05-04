"""Hire management commands."""
import json
import shutil
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

app = typer.Typer(help="Manage hire requests")
console = Console()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = BASE_DIR / "agents"
HIRE_DIR = AGENTS_DIR / "hire_requests"
PENDING_DIR = HIRE_DIR / "pending"


@app.command()
def list():
    """List pending hire requests."""
    if not PENDING_DIR.exists():
        console.print("[yellow]No pending hire requests.[/yellow]")
        return

    files = list(PENDING_DIR.glob("*.json"))
    if not files:
        console.print("[yellow]No pending hire requests.[/yellow]")
        return

    table = Table(title="Pending Hire Requests")
    table.add_column("File", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Role")
    table.add_column("Scene")

    for f in files:
        try:
            data = json.loads(f.read_text())
            table.add_row(
                f.name,
                data.get("name", "?"),
                data.get("profile", {}).get("role", "?"),
                data.get("scene", "default"),
            )
        except (json.JSONDecodeError, KeyError):
            continue

    console.print(table)


@app.command()
def show(
    filename: str = typer.Argument(..., help="Hire request filename"),
):
    """Show details of a pending hire request."""
    path = PENDING_DIR / filename
    if not path.exists():
        path = PENDING_DIR / f"{filename}.json"
    if not path.exists():
        console.print(f"[red]Hire request '{filename}' not found.[/red]")
        raise typer.Exit(1)

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        console.print(f"[red]Error parsing hire request: {e}[/red]")
        raise typer.Exit(1)

    text = json.dumps(data, indent=2, ensure_ascii=False)
    console.print(Panel(text, title=f"[cyan]{path.name}[/cyan]"))


@app.command()
def approve(
    filename: str = typer.Argument(..., help="Hire request filename (or part of it)"),
):
    """Approve a pending hire request."""
    path = _resolve_file(filename)
    if path is None:
        return

    approved_dir = HIRE_DIR / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)
    dest = approved_dir / path.name
    shutil.copy2(str(path), str(dest))
    path.unlink()
    console.print(f"[green]Approved {path.name}. The daemon will process it.[/green]")


@app.command()
def reject(
    filename: str = typer.Argument(..., help="Hire request filename (or part of it)"),
):
    """Reject a pending hire request."""
    path = _resolve_file(filename)
    if path is None:
        return

    rejected_dir = HIRE_DIR / "rejected"
    rejected_dir.mkdir(parents=True, exist_ok=True)
    dest = rejected_dir / path.name
    shutil.move(str(path), str(dest))
    console.print(f"[yellow]Rejected {path.name}.[/yellow]")


def _resolve_file(filename: str) -> Path | None:
    """Resolve a filename to a pending hire request file."""
    path = PENDING_DIR / filename
    if path.exists():
        return path

    path = PENDING_DIR / f"{filename}.json"
    if path.exists():
        return path

    matches = list(PENDING_DIR.glob(f"*{filename}*"))
    if len(matches) == 1:
        return matches[0]

    if len(matches) > 1:
        console.print(f"[red]Multiple matches for '{filename}':[/red]")
        for m in matches:
            console.print(f"  {m.name}")
        raise typer.Exit(1)

    console.print(f"[red]Hire request '{filename}' not found.[/red]")
    console.print(f"Use 'cococat hire list' to see pending requests.")
    raise typer.Exit(1)
