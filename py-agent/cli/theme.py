"""Theme management commands."""
import json
from pathlib import Path
import typer
from .render import console, print_table, print_success, print_error

theme_app = typer.Typer(help="Manage TUI themes")

BUILTIN_THEMES = {
    "catppuccin-mocha": {"background": "#1e1e2e", "text": "#cdd6f4", "accent": "#89b4fa"},
    "nord": {"background": "#2e3440", "text": "#eceff4", "accent": "#88c0d0"},
    "dracula": {"background": "#282a36", "text": "#f8f8f2", "accent": "#bd93f9"},
    "tokyonight": {"background": "#1a1b26", "text": "#a9b1d6", "accent": "#7aa2f7"},
    "gruvbox": {"background": "#282828", "text": "#ebdbb2", "accent": "#83a598"},
}


@theme_app.command("list")
def theme_list():
    """List available themes."""
    rows = []
    for name, colors in sorted(BUILTIN_THEMES.items()):
        preview = f"[on {colors['background']}]  [/on {colors['background']}]"
        rows.append((name, preview, colors.get("accent", "")))
    print_table("Available Themes", rows, headers=("Name", "Preview", "Accent"))


@theme_app.command("set")
def theme_set(name: str = typer.Argument(..., help="Theme name")):
    """Set the active theme."""
    if name not in BUILTIN_THEMES:
        available = ", ".join(sorted(BUILTIN_THEMES.keys()))
        print_error(f"Unknown theme '{name}'. Available: {available}")
        raise typer.Exit(1)
    config_dir = Path.home() / ".cococat"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"
    config = {}
    if config_path.exists():
        config = json.loads(config_path.read_text())
    config["theme"] = name
    config_path.write_text(json.dumps(config, indent=2))
    print_success(f"Theme set to '{name}'. Restart TUI to see changes.")
