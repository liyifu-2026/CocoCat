"""Streaming renderer and thinking spinner (nanobot stream.py pattern)."""
import sys
import time
from contextlib import contextmanager
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.status import Status
from rich.text import Text


console = Console()


class ThinkingSpinner:
    """Rich status spinner for 'thinking' state."""

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
    """Render streaming agent responses as live Markdown with debounced refresh.

    Usage:
        renderer = StreamRenderer()
        for delta in stream:
            renderer.on_delta(delta)
        renderer.on_end()
    """

    def __init__(self, render_markdown: bool = True, debounce_s: float = 0.15):
        self._buffer = ""
        self._render_markdown = render_markdown
        self._live: Live | None = None
        self._spinner: ThinkingSpinner | None = None
        self.streamed = False
        self._debounce_s = debounce_s
        self._last_refresh = 0.0

    def _make_renderable(self):
        if not self._buffer.strip():
            return Text("")
        if self._render_markdown:
            return Markdown(self._buffer)
        return Text(self._buffer)

    def _should_refresh(self) -> bool:
        return (time.monotonic() - self._last_refresh) >= self._debounce_s

    def on_delta(self, delta: str):
        self._buffer += delta
        self.streamed = True
        if not self._live and sys.stdout.isatty():
            self._live = Live(
                self._make_renderable(),
                refresh_per_second=8,
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
        """Stop live render before user input to avoid prompt_toolkit conflicts."""
        if self._live:
            self._live.stop()
            self._live = None

    def close(self):
        if self._live:
            self._live.stop()
            self._live = None
