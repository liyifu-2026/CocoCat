"""Streaming renderer — opencode-inspired, Panel-wrapped Markdown."""
import sys
import time
from contextlib import contextmanager
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.status import Status
from rich.text import Text

console = Console()


class ThinkingSpinner:
    """Animated spinner with pause/resume."""

    def __init__(self, text: str = "Thinking..."):
        self._status = Status(text, spinner="dots")
        self._paused = False

    def __enter__(self):
        if sys.stdout.isatty() and not self._paused:
            self._status.start()
        return self

    def __exit__(self, *args):
        self.stop()

    @contextmanager
    def pause(self):
        self.stop()
        self._paused = True
        try:
            yield
        finally:
            self._paused = False
            if sys.stdout.isatty():
                self._status.start()

    def stop(self):
        try:
            if self._status._live is not None:
                self._status.stop()
        except Exception:
            pass

    def update(self, text: str):
        self._status.update(text)


class StreamRenderer:
    """Live streaming Markdown renderer wrapped in a Panel.

    Renders agent responses in a styled Panel that updates in real-time.
    """

    def __init__(self, agent_name: str = "Assistant", debounce_s: float = 0.08):
        self._agent_name = agent_name
        self._buffer = ""
        self._live: Live | None = None
        self.streamed = False
        self._debounce_s = debounce_s
        self._last_refresh = 0.0

    def _make_renderable(self):
        if not self._buffer.strip():
            return Text("")
        md = Markdown(self._buffer)
        return Panel(
            md,
            title=f"[bold green]{self._agent_name}[/bold green]",
            border_style="green",
            padding=(1, 2),
        )

    def _should_refresh(self) -> bool:
        return (time.monotonic() - self._last_refresh) >= self._debounce_s

    def on_delta(self, delta: str):
        self._buffer += delta
        self.streamed = True
        if not self._live and sys.stdout.isatty():
            self._live = Live(
                self._make_renderable(),
                refresh_per_second=12,
                vertical_overflow="visible",
            )
            self._live.start()
            self._last_refresh = time.monotonic()
        elif self._live and self._should_refresh():
            self._live.update(self._make_renderable())
            self._last_refresh = time.monotonic()

    def on_end(self, resuming: bool = False):
        if resuming:
            self._buffer = ""
            return
        if self._live:
            self._live.stop()
            self._live = None
        if self._buffer.strip():
            renderable = self._make_renderable()
            console.print(renderable)

    def stop_for_input(self):
        if self._live:
            self._live.stop()
            self._live = None

    def close(self):
        if self._live:
            self._live.stop()
            self._live = None
