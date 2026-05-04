"""CocoCat CLI main entry point."""
import typer
from rich.console import Console

from .agents import app as agents_app
from .chat import app as chat_app
from .daemon import app as daemon_app
from .mailbox import app as mailbox_app
from .hire import app as hire_app
from .status import status as status_cmd

console = Console()
app = typer.Typer(
    name="cococat",
    help="CocoCat - Multi-Agent AI Collaboration Platform",
    no_args_is_help=True,
)

app.add_typer(agents_app, name="agent", help="Manage and inspect agents")
app.add_typer(chat_app, name="chat", help="Chat with agents")
app.add_typer(daemon_app, name="daemon", help="Control the Rust daemon")
app.add_typer(mailbox_app, name="mailbox", help="Read agent mailboxes")
app.add_typer(hire_app, name="hire", help="Manage hire requests")
app.command(name="status")(status_cmd)


def entry_point():
    app()
