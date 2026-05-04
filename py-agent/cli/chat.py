"""Chat commands - send messages to agents interactively."""
import asyncio
import json
import os
import subprocess
import sys
import typer
from pathlib import Path
from rich.console import Console
from rich.markdown import Markdown

app = typer.Typer(help="Chat with agents")
console = Console()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
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
        stdout, stderr = proc.communicate(input=request + "\n", timeout=timeout)

        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                resp = json.loads(line)
                result = resp.get("result") or resp.get("error", {})
                return result
            except json.JSONDecodeError:
                continue
        return {"error": stdout.strip() or "(no output)"}
    except subprocess.TimeoutExpired:
        proc.kill()
        return {"error": "Agent timed out"}
    except Exception as e:
        return {"error": str(e)}


@app.command()
def send(
    agent_id: str = typer.Argument(..., help="Agent ID to message"),
    message: str = typer.Argument(..., help="Message content"),
    timeout: int = typer.Option(60, "--timeout", "-t", help="Response timeout in seconds"),
):
    """Send a single message to an agent and get response."""
    console.print(f"[dim]Sending to [cyan]{agent_id}[/cyan]...[/dim]")
    result = _send_to_agent(agent_id, message, timeout)

    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        raise typer.Exit(1)

    content = result.get("content", str(result))
    console.print(Markdown(content))


@app.command()
def interactive(
    agent_id: str = typer.Argument("leader", help="Agent ID to chat with"),
    timeout: int = typer.Option(120, "--timeout", "-t", help="Response timeout per message"),
):
    """Start an interactive chat session with an agent."""
    console.print(f"[cyan]Interactive chat with [bold]{agent_id}[/bold][/cyan]")
    console.print("[dim]Type 'exit' or 'quit' to end.[/dim]\n")

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

        console.print(f"[dim]{agent_id} is thinking...[/dim]")
        result = _send_to_agent(agent_id, user_input, timeout)

        if "error" in result:
            console.print(f"[red]Error: {result['error']}[/red]")
            continue

        content = result.get("content", str(result))
        console.print(f"\n[bold green]{agent_id}:[/bold green]")
        console.print(Markdown(content))
        print()
