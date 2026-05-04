"""Unified output rendering (nanobot _print_* pattern)."""
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


def print_agent_response(content: str, render_markdown: bool = True, agent_name: str = ""):
    """Print an agent's response with consistent styling."""
    if agent_name:
        console.print(f"\n[bold green]{agent_name}:[/bold green]")
    if render_markdown:
        console.print(Markdown(content))
    else:
        console.print(Text(content))
    print()


def print_progress(text: str):
    """Print a progress line during agent execution."""
    console.print(f"  [dim]↳ {text}[/dim]")


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
    console.print(f"[cyan]ℹ[/cyan] {text}")


def print_table(title: str, rows: list[tuple[str, str]], headers: tuple[str, str] = ("Key", "Value")):
    """Print a two-column table."""
    table = Table(title=title)
    table.add_column(headers[0], style="cyan")
    table.add_column(headers[1])
    for k, v in rows:
        table.add_row(str(k), str(v))
    console.print(table)


def print_panel(title: str, content: str):
    """Print a panel with content."""
    console.print(Panel(content, title=f"[cyan]{title}[/cyan]"))
