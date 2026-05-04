"""CocoCat CLI main entry point."""
from .commands import app
from .theme import theme_app

app.add_typer(theme_app, name="theme")

def entry_point():
    app()
