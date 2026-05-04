"""Daemon control commands."""
import os
import signal
import subprocess
import time
import typer
from pathlib import Path
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Control the Rust daemon")
console = Console()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_DIR = BASE_DIR.parent
PID_FILE = PROJECT_DIR / "cococat.pid"
LOG_FILE = PROJECT_DIR / "cococat.log"


@app.command()
def start(
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground"),
):
    """Start the CocoCat Rust daemon."""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            console.print(f"[yellow]Daemon already running (PID: {pid})[/yellow]")
            raise typer.Exit(1)
        except (ProcessLookupError, ValueError):
            PID_FILE.unlink(missing_ok=True)

    cargo = os.path.expanduser("~/.cargo/bin/cargo")
    if not os.path.exists(cargo):
        cargo = "cargo"

    console.print("[dim]Building and starting daemon...[/dim]")

    if foreground:
        proc = subprocess.Popen(
            [cargo, "run", "--quiet"],
            cwd=str(PROJECT_DIR),
        )
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()
    else:
        log = open(LOG_FILE, "w")
        proc = subprocess.Popen(
            [cargo, "run", "--quiet"],
            cwd=str(PROJECT_DIR),
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        PID_FILE.write_text(str(proc.pid))
        console.print(f"[green]Daemon started (PID: {proc.pid})[/green]")
        console.print(f"[dim]Log: {LOG_FILE}[/dim]")
        console.print(f"[dim]Stop: cococat daemon stop[/dim]")

        # Give it a moment, check if it's still running
        time.sleep(1)
        if proc.poll() is not None:
            console.print(f"[red]Daemon exited immediately. Check logs:[/red]")
            console.print(log.read() if hasattr(log, 'read') else f"[dim]{LOG_FILE}[/dim]")
            raise typer.Exit(1)


@app.command()
def stop():
    """Stop the CocoCat Rust daemon."""
    if not PID_FILE.exists():
        console.print("[yellow]No PID file found. Daemon may not be running.[/yellow]")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        console.print(f"[green]Sent SIGTERM to PID {pid}[/green]")

        for _ in range(10):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except ProcessLookupError:
                break

        PID_FILE.unlink(missing_ok=True)
    except ProcessLookupError:
        console.print("[yellow]Process not found. Cleaning up PID file.[/yellow]")
        PID_FILE.unlink(missing_ok=True)
    except PermissionError:
        console.print(f"[red]Permission denied. Try: kill {pid}[/red]")
        raise typer.Exit(1)


@app.command()
def status():
    """Check daemon status."""
    if not PID_FILE.exists():
        console.print("[red]Daemon not running[/red]")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        console.print(f"[green]Daemon running (PID: {pid})[/green]")
    except (ProcessLookupError, ValueError):
        console.print("[red]Daemon not running (stale PID file)[/red]")
