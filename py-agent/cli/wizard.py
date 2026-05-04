"""Interactive setup wizard (nanobot onboard.py pattern)."""
import typer
from rich.console import Console
from rich.panel import Panel

from .config import Config, CONFIG_DIR, save_config
from .render import print_success, print_info

console = Console()


def run_wizard() -> Config:
    """Run the interactive configuration wizard."""
    import questionary

    console.print(Panel.fit(
        "[bold cyan]CocoCat Setup Wizard[/bold cyan]\n"
        "This will guide you through the initial configuration.",
    ))

    cargo_path = questionary.path(
        "Path to cargo binary:",
        default=str(Config().daemon.cargo_path),
    ).ask()
    if not cargo_path:
        cargo_path = str(Config().daemon.cargo_path)

    default_agent = questionary.select(
        "Default chat agent:",
        choices=["leader", "employee_a", "employee_b", "employee_c"],
        default="leader",
    ).ask()
    if not default_agent:
        default_agent = "leader"

    timeout = questionary.text(
        "Response timeout (seconds):",
        default=str(Config().chat.response_timeout),
    ).ask()
    if not timeout:
        timeout = "120"

    render_md = questionary.confirm(
        "Render agent responses as Markdown?",
        default=True,
    ).ask()

    config = Config()
    config.daemon.cargo_path = cargo_path
    config.chat.default_agent = default_agent
    config.chat.response_timeout = int(timeout)
    config.display.render_markdown = render_md

    save_config(config)
    print_success(f"Configuration saved to {CONFIG_DIR / 'config.json'}")
    print_info("Run 'cococat chat' to start chatting!")

    return config
