"""Unified output rendering — Rich Panel-based, opencode-inspired."""
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.syntax import Syntax
from rich.columns import Columns
from rich.rule import Rule
from rich.style import Style
from rich.align import Align

console = Console()

THEME = {
    "user": "bold cyan",
    "agent": "bold green",
    "thinking": "dim italic",
    "tool": "dim blue",
    "tool_done": "green",
    "tool_error": "red",
    "info": "dim",
    "border": "bright_blue",
    "success": "green",
    "warning": "yellow",
    "error": "red",
}


def print_user_input(content: str):
    """Print user input with a clear visual style."""
    console.print(f"\n[bold cyan]You:[/bold cyan] {content}", highlight=False)


def print_agent_response(content: str, render_markdown: bool = True, agent_name: str = "Assistant"):
    """Print agent response in a styled panel (opencode-inspired)."""
    if render_markdown and content.strip():
        renderable = Markdown(content)
    else:
        renderable = Text(content or "(empty response)")

    panel = Panel(
        renderable,
        title=f"[bold green]{agent_name}[/bold green]",
        border_style="green",
        padding=(1, 2),
    )
    console.print(panel)


def print_thinking(content: str):
    """Print the agent's reasoning/thinking in a muted collapsible panel."""
    panel = Panel(
        Text(content, style="dim italic"),
        title="[dim]Thinking[/dim]",
        border_style="dim",
        padding=(0, 2),
    )
    console.print(panel)


def print_tool_start(tool_name: str, args: dict | None = None):
    """Print a tool execution start message."""
    arg_str = ""
    if args:
        parts = [f"{k}={v}" for k, v in args.items() if v]
        if parts:
            arg_str = f" [dim]({', '.join(parts[:2])})[/dim]"
    console.print(f"  [bright_blue]◈[/bright_blue] [dim]{tool_name}[/dim]{arg_str}")


def print_tool_done(tool_name: str, result: str = ""):
    """Print a tool completion message with result preview."""
    preview = result.strip()[:80].replace("\n", " ")
    if preview:
        console.print(f"  [green]✓[/green] [dim]{tool_name}[/dim] [dim]{preview}[/dim]")
    else:
        console.print(f"  [green]✓[/green] [dim]{tool_name}[/dim]")


def print_tool_error(tool_name: str, error: str):
    """Print a tool error."""
    console.print(f"  [red]✗[/red] [dim]{tool_name}[/dim] [red]{error[:80]}[/red]")


def print_progress(text: str):
    """Print a progress line."""
    console.print(f"  [dim]{text}[/dim]")


def print_success(text: str):
    """Print a success message."""
    console.print(f"[green]✓[/green] {text}")


def print_error(text: str):
    """Print an error message."""
    console.print(f"[red]✗[/red] {text}")


def print_warning(text: str):
    """Print a warning message."""
    console.print(f"[yellow]⚠[/yellow] {text}")


def print_info(text: str):
    """Print an info message."""
    console.print(f"[dim]ℹ[/dim] {text}")


def print_table(title: str, rows: list[tuple[str, str]], headers: tuple[str, str] = ("Key", "Value")):
    """Print a two-column table."""
    table = Table(title=title, title_style="bold")
    table.add_column(headers[0], style="cyan")
    table.add_column(headers[1])
    for k, v in rows:
        table.add_row(str(k), str(v))
    console.print(table)


def print_panel(title: str, content: str, border: str = "blue"):
    """Print a panel with content."""
    console.print(Panel(content, title=f"[{border}]{title}[/{border}]", border_style=border))
