"""CocoCat CLI commands — merged from agents.py, chat.py, daemon.py, mailbox.py, hire.py, status.py."""
import json
import os
import select
import signal
import subprocess
import sys
import time
import typer
from contextlib import suppress
from pathlib import Path

from .config import load_config, save_config, CONFIG_PATH as _CONFIG_PATH
from .render import (
    console, print_agent_response, print_success, print_error,
    print_warning, print_info, print_table, print_panel, print_progress,
    print_user_input, print_thinking, print_tool_start, print_tool_done, print_tool_error,
)
from .stream import StreamRenderer
from .session import Session, SessionManager

app = typer.Typer(help="CocoCat CLI commands")
_SAVED_TERM_ATTRS = None

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
def status(
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """Show overall system status."""
    cfg, _ = _load_runtime_config(config)
    if workspace:
        cfg.workspace = workspace
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


# ---------------------------------------------------------------------------
# Signal handling + terminal management (nanobot pattern)
# ---------------------------------------------------------------------------

def _save_terminal():
    global _SAVED_TERM_ATTRS
    with suppress(Exception):
        import termios
        _SAVED_TERM_ATTRS = termios.tcgetattr(sys.stdin.fileno())


def _restore_terminal():
    if _SAVED_TERM_ATTRS is None:
        return
    with suppress(Exception):
        import termios
        termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, _SAVED_TERM_ATTRS)


def _setup_signal_handlers():
    """Register signal handlers for clean shutdown."""
    def _handler(signum, frame):
        _restore_terminal()
        sig_name = signal.Signals(signum).name
        console.print(f"\n[yellow]Received {sig_name}, goodbye![/yellow]")
        sys.exit(0)
    signal.signal(signal.SIGINT, _handler)
    signal.signal(signal.SIGTERM, _handler)
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, _handler)
    if hasattr(signal, 'SIGPIPE'):
        signal.signal(signal.SIGPIPE, signal.SIG_IGN)


def _flush_pending_tty_input():
    """Drop unread keypresses typed while the agent was generating output."""
    try:
        fd = sys.stdin.fileno()
        if not os.isatty(fd):
            return
    except Exception:
        return
    with suppress(Exception):
        import termios
        termios.tcflush(fd, termios.TCIFLUSH)
        return
    with suppress(Exception):
        while True:
            ready, _, _ = select.select([fd], [], [], 0)
            if not ready:
                break
            if not os.read(fd, 4096):
                break


def _load_runtime_config(config_path: str | None = None) -> tuple:
    """Load config with optional override path (nanobot _load_runtime_config pattern)."""
    if config_path:
        from .config import CONFIG_DIR
        cfg_path = Path(config_path).expanduser().resolve()
        if not cfg_path.exists():
            print_error(f"Config not found: {cfg_path}")
            raise typer.Exit(1)
    cfg = load_config()
    return cfg, config_path


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


def _send_to_agent(agent_id: str, prompt: str, timeout: int = 60, on_progress=None) -> dict:
    """Send a task to an agent (non-streaming)."""
    if on_progress:
        on_progress("Connecting to agent...")
    
    runtime = Path(__file__).resolve().parent.parent / "agent_runtime.py"
    try:
        proc = subprocess.Popen(
            ["python3", "-u", str(runtime), "--id", agent_id, "--name", agent_id],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        request = json.dumps({
            "jsonrpc": "2.0", "method": "task",
            "params": {"prompt": prompt}, "id": 1,
        })
        
        if on_progress:
            on_progress("Agent processing...")
        
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


def _stream_from_agent(agent_id: str, prompt: str, timeout: int = 120, on_delta=None, on_progress=None, on_done=None):
    """Send a task_stream request and yield events as they arrive (nanobot streaming pattern).
    
    Reads stdout line-by-line, parsing each as a JSON event:
      {"event": "delta", "content": "..."}  → on_delta()
      {"event": "done", "content": "..."}   → on_done()
    """
    if on_progress:
        on_progress("Connecting to agent...")

    runtime = Path(__file__).resolve().parent.parent / "agent_runtime.py"
    proc = subprocess.Popen(
        ["python3", "-u", str(runtime), "--id", agent_id, "--name", agent_id],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,  # line-buffered
    )

    request = json.dumps({
        "jsonrpc": "2.0", "method": "task_stream",
        "params": {"prompt": prompt}, "id": 1,
    })
    proc.stdin.write(request + "\n")
    proc.stdin.flush()

    if on_progress:
        on_progress("Agent processing...")

    full_content = ""
    start_time = time.monotonic()

    while True:
        if time.monotonic() - start_time > timeout:
            proc.kill()
            if on_done:
                on_done(full_content or "(timeout)")
            return full_content or "(timeout)"

        line = proc.stdout.readline()
        if not line:
            break

        line = line.strip()
        if not line:
            continue

        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(data, dict):
            continue

        event = data.get("event")
        if event == "delta":
            chunk = data.get("content", "")
            full_content += chunk
            if on_delta:
                on_delta(chunk)

        elif event == "done":
            content = data.get("content", full_content)
            full_content = content
            if on_done:
                on_done(content)
            break

        elif event == "progress":
            if on_progress:
                on_progress(data.get("content", ""))

        elif event == "reasoning":
            if on_progress:
                on_progress(f"[thinking] {data.get('content', '')[:80]}...")

        elif event == "tool_start":
            tool = data.get("tool", "?")
            args = data.get("args", "")
            if on_progress:
                on_progress(f"◈ {tool} ({args})")

        elif event == "tool_done":
            tool = data.get("tool", "?")
            result = data.get("result", "")
            if on_progress:
                preview = result.strip()[:60].replace("\n", " ")
                on_progress(f"✓ {tool}" + (f" — {preview}" if preview else ""))

        elif event == "tool_error":
            tool = data.get("tool", "?")
            err = data.get("result", "")
            if on_progress:
                on_progress(f"✗ {tool}: {err[:60]}")

        elif data.get("jsonrpc") == "2.0":
            result = data.get("result", {})
            if result.get("streamed"):
                if not full_content:
                    content = result.get("content", "")
                    if on_done:
                        on_done(content)
                    full_content = content
                break
            error = data.get("error")
            if error:
                full_content = f"Error: {error.get('message', 'unknown')}"
                if on_done:
                    on_done(full_content)
                break

    proc.stdin.close()
    proc.wait(timeout=5)
    return full_content


@chat_app.command("send")
def chat_send(
    agent_id: str = typer.Argument(..., help="Agent ID to message"),
    message: str = typer.Argument(..., help="Message content"),
    timeout: int = typer.Option(120, "--timeout", "-t", help="Response timeout in seconds"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
    no_stream: bool = typer.Option(False, "--no-stream", help="Disable streaming"),
):
    """Send a single message to an agent and get response."""
    cfg, _ = _load_runtime_config(config)
    if workspace:
        cfg.workspace = workspace

    print_user_input(message)

    if no_stream:
        spinner = ThinkingSpinner()
        with spinner:
            result = _send_to_agent(agent_id, message, timeout)
        if "error" in result:
            print_error(result["error"])
            raise typer.Exit(1)
        content = result.get("content", str(result))
        print_agent_response(content, render_markdown=cfg.display.render_markdown, agent_name=agent_id)
        return

    renderer = StreamRenderer(agent_name=agent_id)
    show_progress = cfg.display.show_progress

    _stream_from_agent(
        agent_id, message, timeout,
        on_delta=lambda chunk: renderer.on_delta(chunk),
        on_progress=lambda msg: (
            print_progress(msg) if "◈" in msg or "✓" in msg or "✗" in msg or "[thinking]" in msg
            else None
        ),
        on_done=lambda _: None,
    )

    renderer.on_end()


@chat_app.command("interactive")
def chat_interactive(
    agent_id: str = typer.Argument("leader", help="Agent ID to chat with"),
    timeout: int = typer.Option(120, "--timeout", "-t", help="Response timeout per message"),
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """Start an interactive chat session with an agent."""
    cfg, _ = _load_runtime_config(config)
    if workspace:
        cfg.workspace = workspace
    agent_id = agent_id or cfg.chat.default_agent

    _save_terminal()
    _setup_signal_handlers()

    try:
        import prompt_toolkit
        from prompt_toolkit.history import FileHistory
    except ImportError:
        prompt_toolkit = None

    session_mgr = SessionManager()
    session = session_mgr.get_or_create(agent_id)
    history_path = Path.home() / ".cococat" / "history" / f"{agent_id}.txt"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history = FileHistory(str(history_path))
    psession = prompt_toolkit.PromptSession(history=history) if prompt_toolkit else None

    console.print(f"[bold cyan]Interactive chat with {agent_id}[/bold cyan]")
    if session.messages:
        console.print(f"[dim]Resuming session {session.key} ({len(session.messages)} previous messages)[/dim]")
    console.print("[dim]Type 'exit' or 'quit' to end. Ctrl+C to interrupt.[/dim]\n")

    renderer = None

    while True:
        _flush_pending_tty_input()

        if renderer:
            renderer.stop_for_input()

        try:
            if psession:
                user_input = psession.prompt("You: ").strip()
            else:
                user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break

        print_user_input(user_input)

        renderer = StreamRenderer(agent_name=agent_id)
        show_progress = cfg.display.show_progress
        full_content = ""

        def on_delta(chunk):
            nonlocal full_content
            full_content += chunk
            renderer.on_delta(chunk)

        def on_progress(msg):
            if msg and ("◈" in msg or "✓" in msg or "✗" in msg or "[thinking]" in msg):
                print_progress(msg)

        _stream_from_agent(
            agent_id, user_input, timeout,
            on_delta=on_delta,
            on_progress=on_progress,
            on_done=lambda content: None,
        )

        renderer.on_end()
        if full_content:
            session.add_message("assistant", full_content)

    _restore_terminal()
    if cfg.chat.session_persistence:
        session_mgr.save(session)
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
    config: str | None = typer.Option(None, "--config", "-c", help="Config file path"),
    workspace: str | None = typer.Option(None, "--workspace", "-w", help="Workspace directory"),
):
    """Start the CocoCat Rust daemon."""
    cfg, _ = _load_runtime_config(config)
    if workspace:
        cfg.workspace = workspace

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


# ===========================================================================
# Doctor & Upgrade commands
# ===========================================================================


@app.command()
def doctor():
    """Diagnose system health."""
    from .render import console, print_success, print_error, print_warning, print_info
    import subprocess
    from rich.table import Table

    table = Table(title="CocoCat Doctor")
    table.add_column("Check", style="cyan")
    table.add_column("Status")

    import sys
    py_ok = sys.version_info >= (3, 10)
    table.add_row("Python", f"[{'green' if py_ok else 'red'}]{sys.version}[/]")

    from .config import CONFIG_PATH
    config_ok = CONFIG_PATH.exists()
    table.add_row("Config", "[green]✓[/green]" if config_ok else "[yellow]not found (defaults)[/yellow]")

    agents_dir = Path(__file__).resolve().parent.parent.parent / "agents"
    agent_config = agents_dir / "config.toml"
    table.add_row("Agent config", "[green]✓[/green]" if agent_config.exists() else "[red]✗ missing[/red]")

    try:
        result = subprocess.run(["cargo", "--version"], capture_output=True, text=True, timeout=5)
        table.add_row("Cargo", f"[green]{result.stdout.strip()}[/green]" if result.returncode == 0 else "[red]not found[/red]")
    except Exception:
        table.add_row("Cargo", "[red]not found[/red]")

    pid_file = Path.home() / ".cococat" / "cococat.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            table.add_row("Daemon", f"[green]Running (PID: {pid})[/green]")
        except (ProcessLookupError, ValueError, OSError):
            table.add_row("Daemon", "[yellow]Stale PID[/yellow]")
    else:
        table.add_row("Daemon", "[yellow]Not running[/yellow]")

    console.print(table)
    print_info("Run 'cococat doctor --fix' to attempt auto-fixes.")


@app.command()
def upgrade():
    """Upgrade CocoCat to the latest version."""
    from .render import console, print_info, print_success, print_error
    import subprocess

    print_info("Checking for updates...")
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            if "Already up to date" in result.stdout:
                print_success("Already up to date.")
            else:
                print_success("Updated. Rebuilding...")
                build = subprocess.run(
                    ["cargo", "build", "--release"],
                    capture_output=True, text=True, timeout=300,
                )
                if build.returncode == 0:
                    print_success("Rebuild complete.")
                else:
                    print_error(f"Build failed:\n{build.stderr}")
        else:
            print_error(f"Git pull failed:\n{result.stderr}")
    except Exception as e:
        print_error(f"Upgrade failed: {e}")


@app.command()
def onboard():
    """Interactive setup — configure API keys and test connection."""
    from .onboard import run
    run()


@app.command()
def show_config():
    """Show current configuration."""
    import os
    from .render import console

    console.print("\n[bold]Environment[/bold]")
    providers = [
        ("DEEPSEEK_API_KEY", "DeepSeek"),
        ("OPENAI_API_KEY", "OpenAI"),
        ("ANTHROPIC_API_KEY", "Anthropic"),
        ("SILICONFLOW_API_KEY", "SiliconFlow"),
        ("GEMINI_API_KEY", "Gemini"),
    ]
    for key, name in providers:
        val = os.environ.get(key, "")
        status = "[green]✓[/green]" if val else "[dim]not set[/dim]"
        console.print(f"  {name:20s} {status}")

    console.print("\n[bold]Paths[/bold]")
    console.print(f"  Config:      ~/.cococat/config.json")
    console.print(f"  Sessions:    ~/.cococat/sessions/")
    console.print(f"  Workspace:   {os.path.abspath('.')}")


@app.command()
def validate():
    """Validate configuration and test provider connections."""
    import os, sys
    from .render import console, print_info, print_success, print_error

    console.print("\n[bold]Validating configuration...[/bold]\n")

    # Check required env vars
    has_key = False
    required = [
        ("DEEPSEEK_API_KEY", "DeepSeek"),
        ("OPENAI_API_KEY", "OpenAI"),
        ("ANTHROPIC_API_KEY", "Anthropic"),
        ("SILICONFLOW_API_KEY", "SiliconFlow"),
    ]
    for key, name in required:
        val = os.environ.get(key, "")
        if val:
            print_success(f"{name}: API key configured")
            has_key = True
        else:
            if key == "DEEPSEEK_API_KEY" or key == "OPENAI_API_KEY":
                print_info(f"{name}: not set (recommended)")

    if not has_key:
        print_error("No API keys configured. Run 'cococat onboard' to set up.")
        return

    # Test provider connection
    model = os.environ.get("LLM_MODEL", "")
    if not model:
        if os.environ.get("DEEPSEEK_API_KEY"):
            model = "deepseek-chat"
        elif os.environ.get("OPENAI_API_KEY"):
            model = "gpt-4o-mini"
        elif os.environ.get("ANTHROPIC_API_KEY"):
            model = "claude-sonnet-4-20250514"

    if model:
        print_info(f"Testing connection with model: {model}...")
        try:
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
            from providers import make_provider
            provider = make_provider(model=model)
            resp = provider.chat_with_retry(
                messages=[{"role": "user", "content": "Say exactly: OK"}],
                max_tokens=10, temperature=0,
            )
            if resp.finish_reason != "error":
                print_success(f"Connection OK: {resp.content}")
            else:
                print_error(f"Connection failed: {resp.content[:200]}")
        except Exception as e:
            print_error(f"Connection failed: {e}")

    console.print()
