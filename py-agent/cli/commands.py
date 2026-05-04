"""CocoCat CLI commands — merged from agents.py, chat.py, daemon.py, mailbox.py, hire.py, status.py."""
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import typer
from pathlib import Path

from .config import load_config, save_config, CONFIG_PATH
from .render import (
    console, print_agent_response, print_success, print_error,
    print_warning, print_info, print_table, print_panel,
)
from .stream import StreamRenderer, ThinkingSpinner
from .session import Session

app = typer.Typer(help="CocoCat CLI commands")

# ===========================================================================
# Config commands
# ===========================================================================

config_app = typer.Typer(help="Manage configuration")
app.add_typer(config_app, name="config")


@config_app.command("show")
def config_show():
    """Show current configuration."""
    cfg = load_config()
    print_panel("Configuration", cfg.model_dump_json(indent=2))


@config_app.command("set")
def config_set(key: str = typer.Argument(...), value: str = typer.Argument(...)):
    """Set a config value (e.g. 'chat.default_agent leader')."""
    cfg = load_config()
    parts = key.split(".")
    obj = cfg
    for part in parts[:-1]:
        obj = getattr(obj, part, None)
        if obj is None:
            print_error(f"Unknown config key: {key}")
            raise typer.Exit(1)
    setattr(obj, parts[-1], value)
    save_config(cfg)
    print_success(f"Set {key} = {value}")


# ===========================================================================
# Status
# ===========================================================================

@app.command()
def status():
    """Show overall system status."""
    cfg = load_config()
    agents_dir = Path(__file__).resolve().parent.parent.parent / "agents"
    config_path = agents_dir / "config.toml"

    try:
        import tomllib as lib
    except ImportError:
        import tomli as lib
    try:
        with open(config_path, "rb") as f:
            agent_config = lib.load(f)
    except Exception:
        agent_config = {"agents": []}

    agents = agent_config.get("agents", [])
    enabled_count = sum(1 for a in agents if a.get("enabled", False))

    pid_file = Path.home() / ".cococat" / "cococat.pid"
    daemon_running = False
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            daemon_running = True
        except (ProcessLookupError, ValueError, OSError):
            pass

    dispatch_dir = agents_dir / "dispatch_queue"
    pending_dispatches = len(list(dispatch_dir.glob("*.json"))) if dispatch_dir.exists() else 0

    hire_dir = agents_dir / "hire_requests" / "pending"
    pending_hires = len(list(hire_dir.glob("*.json"))) if hire_dir.exists() else 0

    mailbox_dir = agents_dir / "mailbox"
    total_unread = 0
    if mailbox_dir.exists():
        for ad in mailbox_dir.iterdir():
            inbox = ad / "inbox.jsonl"
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

    rust_version = ""
    try:
        result = subprocess.run(
            [cfg.daemon.cargo_path, "--version"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            rust_version = result.stdout.strip()
    except Exception:
        pass

    rows = [
        ("Daemon", "[green]Running[/green]" if daemon_running else "[red]Stopped[/red]"),
        ("Agents", f"{enabled_count}/{len(agents)} enabled"),
        ("Pending Dispatches", str(pending_dispatches)),
        ("Pending Hires", str(pending_hires)),
        ("Unread Mail", str(total_unread)),
    ]
    if rust_version:
        rows.append(("Runtime", rust_version))

    print_table("CocoCat System Status", rows)


# ===========================================================================
# Agent commands
# ===========================================================================

agent_app = typer.Typer(help="Manage and inspect agents")
app.add_typer(agent_app, name="agent")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = BASE_DIR / "agents"


def _load_agent_config():
    try:
        import tomllib as lib
    except ImportError:
        import tomli as lib
    try:
        with open(AGENTS_DIR / "config.toml", "rb") as f:
            return lib.load(f)
    except Exception as e:
        print_error(f"Error loading config: {e}")
        return {"agents": []}


@agent_app.command("list")
def agent_list():
    """List all configured agents."""
    config = _load_agent_config()
    agents = config.get("agents", [])

    if not agents:
        print_warning("No agents configured.")
        return

    from rich.table import Table
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


@agent_app.command("status")
def agent_status(agent_id: str = typer.Argument(..., help="Agent ID")):
    """Show agent details."""
    config = _load_agent_config()
    agents = config.get("agents", [])
    agent = next((a for a in agents if a["id"] == agent_id), None)

    if not agent:
        print_error(f"Agent '{agent_id}' not found.")
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

    rows = [(k, str(v)) for k, v in info.items()]
    print_table(f"Agent: {agent.get('name', agent_id)} ({agent_id})", rows)


@agent_app.command("inspect")
def agent_inspect(agent_id: str = typer.Argument(..., help="Agent ID")):
    """Show detailed agent profile and memory."""
    agent_dir = AGENTS_DIR / agent_id
    if not agent_dir.exists():
        print_error(f"Agent '{agent_id}' not found.")
        raise typer.Exit(1)

    profile_path = agent_dir / "profile.json"
    if profile_path.exists():
        try:
            profile = json.loads(profile_path.read_text())
            text = json.dumps(profile, indent=2, ensure_ascii=False)
            print_panel(f"{agent_id} Profile", text)
        except json.JSONDecodeError:
            print_warning("Profile file is corrupted.")

    memory_path = agent_dir / "memory" / "MEMORY.md"
    if memory_path.exists():
        content = memory_path.read_text()
        preview = content[:2000]
        if len(content) > 2000:
            preview += "\n... [truncated]"
        print_panel(f"{agent_id} Memory", preview)


# ===========================================================================
# Chat commands
# ===========================================================================

chat_app = typer.Typer(help="Chat with agents")
app.add_typer(chat_app, name="chat")

AGENT_RUNTIME = BASE_DIR / "agent_runtime.py"


def _send_to_agent(agent_id: str, prompt: str, timeout: int = 60) -> dict:
    """Send a task to an agent via subprocess and return the result."""
    try:
        proc = subprocess.Popen(
            ["python3", "-u", str(AGENT_RUNTIME), "--id", agent_id, "--name", agent_id],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        request = json.dumps({
            "jsonrpc": "2.0", "method": "task",
            "params": {"prompt": prompt}, "id": 1,
        })
        stdout, _ = proc.communicate(input=request + "\n", timeout=timeout)

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                resp = json.loads(line)
                return resp.get("result") or resp.get("error", {})
            except json.JSONDecodeError:
                continue
        return {"error": stdout.strip() or "(no output)"}
    except subprocess.TimeoutExpired:
        proc.kill()
        return {"error": "Agent timed out"}
    except Exception as e:
        return {"error": str(e)}


@chat_app.command("send")
def chat_send(
    agent_id: str = typer.Argument(..., help="Agent ID to message"),
    message: str = typer.Argument(..., help="Message content"),
    timeout: int = typer.Option(60, "--timeout", "-t", help="Response timeout in seconds"),
):
    """Send a single message to an agent and get response."""
    cfg = load_config()
    print_info(f"Sending to {agent_id}...")
    result = _send_to_agent(agent_id, message, timeout)

    if "error" in result:
        print_error(result["error"])
        raise typer.Exit(1)

    content = result.get("content", str(result))
    print_agent_response(content, render_markdown=cfg.display.render_markdown, agent_name=agent_id)


@chat_app.command("interactive")
def chat_interactive(
    agent_id: str = typer.Argument("leader", help="Agent ID to chat with"),
    timeout: int = typer.Option(120, "--timeout", "-t", help="Response timeout per message"),
):
    """Start an interactive chat session with an agent."""
    cfg = load_config()
    agent_id = agent_id or cfg.chat.default_agent

    session = Session(agent_id)

    console.print(f"[bold cyan]Interactive chat with {agent_id}[/bold cyan]")
    console.print("[dim]Type 'exit' or 'quit' to end. Ctrl+C to interrupt.[/dim]\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        session.add_message("user", user_input)

        console.print(f"[dim]{agent_id} is thinking...[/dim]")
        result = _send_to_agent(agent_id, user_input, timeout)

        if "error" in result:
            print_error(result["error"])
            continue

        content = result.get("content", str(result))
        print_agent_response(content, render_markdown=cfg.display.render_markdown, agent_name=agent_id)
        session.add_message("assistant", content)

    if cfg.chat.session_persistence:
        session.save()
        print_info(f"Session saved: {session.key}")


# ===========================================================================
# Daemon commands
# ===========================================================================

daemon_app = typer.Typer(help="Control the Rust daemon")
app.add_typer(daemon_app, name="daemon")

PID_FILE = Path.home() / ".cococat" / "cococat.pid"
LOG_FILE = Path.home() / ".cococat" / "cococat.log"
PROJECT_DIR = BASE_DIR.parent


@daemon_app.command("start")
def daemon_start(
    foreground: bool = typer.Option(False, "--foreground", "-f", help="Run in foreground"),
):
    """Start the CocoCat Rust daemon."""
    cfg = load_config()

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            print_warning(f"Daemon already running (PID: {pid})")
            raise typer.Exit(1)
        except (ProcessLookupError, ValueError):
            PID_FILE.unlink(missing_ok=True)

    cargo = cfg.daemon.cargo_path
    if not os.path.exists(cargo):
        cargo = "cargo"

    print_info("Building and starting daemon...")

    if foreground:
        proc = subprocess.Popen([cargo, "run", "--quiet"], cwd=str(PROJECT_DIR))
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
            proc.wait()
    else:
        log_path = Path(LOG_FILE)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log = open(log_path, "w")
        proc = subprocess.Popen(
            [cargo, "run", "--quiet"],
            cwd=str(PROJECT_DIR),
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
        PID_FILE.write_text(str(proc.pid))
        print_success(f"Daemon started (PID: {proc.pid})")
        print_info(f"Log: {log_path}")
        print_info("Stop: cococat daemon stop")

        time.sleep(1)
        if proc.poll() is not None:
            log.close()
            print_error("Daemon exited immediately. Check the log:")
            print_info(str(log_path))
            raise typer.Exit(1)


@daemon_app.command("stop")
def daemon_stop():
    """Stop the CocoCat Rust daemon."""
    if not PID_FILE.exists():
        print_warning("No PID file found. Daemon may not be running.")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        print_success(f"Sent SIGTERM to PID {pid}")

        for _ in range(10):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except ProcessLookupError:
                break

        PID_FILE.unlink(missing_ok=True)
    except ProcessLookupError:
        print_warning("Process not found. Cleaning up PID file.")
        PID_FILE.unlink(missing_ok=True)
    except PermissionError:
        print_error(f"Permission denied. Try: kill {pid}")
        raise typer.Exit(1)


@daemon_app.command("status")
def daemon_status():
    """Check daemon status."""
    if not PID_FILE.exists():
        print_error("Daemon not running")
        return

    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)
        print_success(f"Daemon running (PID: {pid})")
    except (ProcessLookupError, ValueError):
        print_error("Daemon not running (stale PID file)")


# ===========================================================================
# Mailbox commands
# ===========================================================================

mailbox_app = typer.Typer(help="Read agent mailboxes")
app.add_typer(mailbox_app, name="mailbox")


@mailbox_app.command("list")
def mailbox_list():
    """List all agents with unread mail."""
    config = _load_agent_config()
    agents = config.get("agents", [])

    from rich.table import Table
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


@mailbox_app.command("show")
def mailbox_show(
    agent_id: str = typer.Argument(..., help="Agent ID"),
    unread_only: bool = typer.Option(False, "--unread", "-u", help="Show only unread messages"),
):
    """Show an agent's mailbox contents."""
    inbox_path = AGENTS_DIR / "mailbox" / agent_id / "inbox.jsonl"

    if not inbox_path.exists():
        print_warning(f"No mailbox found for '{agent_id}'.")
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
        print_warning("No messages.")
        return

    from rich.table import Table
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


# ===========================================================================
# Hire commands
# ===========================================================================

hire_app = typer.Typer(help="Manage hire requests")
app.add_typer(hire_app, name="hire")

HIRE_DIR = AGENTS_DIR / "hire_requests"
PENDING_DIR = HIRE_DIR / "pending"


@hire_app.command("list")
def hire_list():
    """List pending hire requests."""
    if not PENDING_DIR.exists():
        print_warning("No pending hire requests.")
        return

    files = list(PENDING_DIR.glob("*.json"))
    if not files:
        print_warning("No pending hire requests.")
        return

    from rich.table import Table
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


def _resolve_hire_file(filename: str) -> Path:
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
        print_error(f"Multiple matches for '{filename}':")
        for m in matches:
            console.print(f"  {m.name}")
        raise typer.Exit(1)

    print_error(f"Hire request '{filename}' not found.")
    console.print("Use 'cococat hire list' to see pending requests.")
    raise typer.Exit(1)


@hire_app.command("show")
def hire_show(filename: str = typer.Argument(..., help="Hire request filename")):
    """Show details of a pending hire request."""
    path = _resolve_hire_file(filename)
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        print_error(f"Error parsing hire request: {e}")
        raise typer.Exit(1)
    print_panel(path.name, json.dumps(data, indent=2, ensure_ascii=False))


@hire_app.command("approve")
def hire_approve(filename: str = typer.Argument(..., help="Hire request filename")):
    """Approve a pending hire request."""
    import shutil
    path = _resolve_hire_file(filename)
    approved_dir = HIRE_DIR / "approved"
    approved_dir.mkdir(parents=True, exist_ok=True)
    dest = approved_dir / path.name
    shutil.copy2(str(path), str(dest))
    path.unlink()
    print_success(f"Approved {path.name}. Daemon will process it.")


@hire_app.command("reject")
def hire_reject(filename: str = typer.Argument(..., help="Hire request filename")):
    """Reject a pending hire request."""
    import shutil
    path = _resolve_hire_file(filename)
    rejected_dir = HIRE_DIR / "rejected"
    rejected_dir.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(rejected_dir / path.name))
    print_warning(f"Rejected {path.name}.")


# ===========================================================================
# Onboard command
# ===========================================================================

@app.command()
def onboard():
    """Run the interactive setup wizard."""
    from .wizard import run_wizard
    run_wizard()
