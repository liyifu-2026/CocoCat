"""CocoCat Textual TUI — main chat application."""
import asyncio
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Input, RichLog, Static, Button
from textual.reactive import reactive
from textual.binding import Binding
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.console import RenderableType
from datetime import datetime

from .agent_client import AgentClient


class ChatMessage(Static):
    """A single chat message (user or agent)."""

    def __init__(self, role: str, content: RenderableType, timestamp: str = ""):
        super().__init__()
        self.role = role
        self._content = content
        self._timestamp = timestamp or datetime.now().strftime("%H:%M:%S")

    def render(self) -> RenderableType:
        if self.role == "user":
            return Panel(
                Text(self._content or ""),
                title="[bold cyan]You[/bold cyan]",
                title_align="left",
                border_style="cyan",
                padding=(0, 1),
            )
        return self._content


class ToolStatus(Static):
    """Real-time tool execution status."""

    def __init__(self):
        super().__init__()
        self._tools: list[dict] = []

    def add_tool(self, name: str, args: str = ""):
        self._tools.append({"name": name, "args": args, "status": "running", "result": ""})
        self.refresh()

    def complete_tool(self, name: str, result: str = ""):
        for t in self._tools:
            if t["name"] == name and t["status"] == "running":
                t["status"] = "done"
                t["result"] = result[:80]
                break
        self.refresh()

    def error_tool(self, name: str, error: str = ""):
        for t in self._tools:
            if t["name"] == name and t["status"] == "running":
                t["status"] = "error"
                t["result"] = error[:80]
                break
        self.refresh()

    def render(self) -> RenderableType:
        if not self._tools:
            return Text("")
        lines = []
        for t in self._tools:
            if t["status"] == "running":
                lines.append(Text(f"  ◈ {t['name']} ({t['args']})", style="dim blue"))
            elif t["status"] == "done":
                preview = t["result"].replace("\n", " ")
                lines.append(Text(f"  ✓ {t['name']}", style="green") + Text(f" — {preview}" if preview else "", style="dim"))
            elif t["status"] == "error":
                lines.append(Text(f"  ✗ {t['name']}: {t['result']}", style="red"))
        return "\n".join(lines)


class ThinkingPanel(Static):
    """Shows agent reasoning/thinking process."""

    def __init__(self):
        super().__init__()
        self._content = ""

    def append(self, text: str):
        self._content += text
        if len(self._content) > 500:
            self._content = self._content[-500:]
        self.refresh()

    def clear(self):
        self._content = ""
        self.refresh()

    def render(self) -> RenderableType:
        if not self._content:
            return Text("")
        return Panel(
            Text(self._content.strip(), style="dim italic"),
            title="[dim]Thinking[/dim]",
            border_style="dim",
            padding=(0, 1),
        )


class StreamingMessage(Static):
    """A live-updating streaming message from the agent."""

    def __init__(self, agent_name: str = "Assistant"):
        super().__init__()
        self._agent_name = agent_name
        self._buffer = ""

    def append(self, text: str):
        self._buffer += text
        self.refresh()

    def finalize(self):
        self.refresh()

    def render(self) -> RenderableType:
        if not self._buffer.strip():
            return Text("")
        return Panel(
            Markdown(self._buffer),
            title=f"[bold green]{self._agent_name}[/bold green]",
            border_style="green",
            padding=(0, 1),
        )

    def content(self) -> str:
        return self._buffer


class ChatApp(App):
    """CocoCat TUI — full-screen chat interface."""

    TITLE = "cococat"
    SUB_TITLE = "Multi-Agent AI Platform"
    CSS = """
    Screen {
        background: $surface;
    }
    
    #chat-container {
        height: 1fr;
        overflow: auto;
        padding: 0 1;
    }
    
    #input-container {
        dock: bottom;
        height: 3;
        padding: 0 1;
        background: $surface;
    }
    
    #message-input {
        width: 1fr;
    }
    
    #send-btn {
        width: 8;
    }
    
    ChatMessage, StreamingMessage, ThinkingPanel, ToolStatus {
        margin: 0 0 1 0;
    }
    """

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+l", "clear", "Clear"),
    ]

    def __init__(self, agent_id: str = "leader"):
        super().__init__()
        self._agent_id = agent_id
        self._client = AgentClient()
        self._streaming_msg: StreamingMessage | None = None
        self._thinking: ThinkingPanel | None = None
        self._tools: ToolStatus | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="chat-container"):
            welcome = ChatMessage(
                "system",
                Panel(
                    Text(f"Interactive chat with [bold]{self._agent_id}[/bold]\nType a message to start."),
                    border_style="dim",
                ),
            )
            yield welcome
        with Horizontal(id="input-container"):
            yield Input(id="message-input", placeholder="Type a message...")
            yield Button("Send", id="send-btn", variant="primary")

    def on_mount(self):
        self.query_one("#message-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted):
        self._handle_send(event.value)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "send-btn":
            inp = self.query_one("#message-input", Input)
            if inp.value.strip():
                self._handle_send(inp.value.strip())

    def _handle_send(self, text: str):
        if not text.strip():
            return

        inp = self.query_one("#message-input", Input)
        inp.value = ""
        container = self.query_one("#chat-container")

        user_msg = ChatMessage("user", text.strip())
        container.mount(user_msg)
        container.mount(Static(Text("")))

        self._thinking = ThinkingPanel()
        container.mount(self._thinking)

        self._tools = ToolStatus()
        container.mount(self._tools)

        self._streaming_msg = StreamingMessage(self._agent_id)
        container.mount(self._streaming_msg)

        container.scroll_end(animate=False)

        self.call_from_thread(self._run_agent, text)

    def _run_agent(self, prompt: str):
        try:
            for event in self._client.send(self._agent_id, prompt):
                self._handle_event(event)
        except Exception as e:
            if self._streaming_msg:
                self._streaming_msg.append(f"\n\n[Error: {e}]")

    def _handle_event(self, event: dict):
        etype = event.get("event", "")
        import threading
        if threading.current_thread() is threading.main_thread():
            self._process_event(event)
        else:
            self.call_from_thread(self._process_event, event)

    def _process_event(self, event: dict):
        etype = event.get("event", "")
        if etype == "progress" and self._thinking:
            pass
        elif etype == "delta":
            if self._streaming_msg:
                self._streaming_msg.append(event.get("content", ""))
        elif etype == "done":
            if self._streaming_msg:
                self._streaming_msg.finalize()
            self._streaming_msg = None
            self._thinking = None
            self._tools = None
        elif etype == "tool_start":
            if self._tools:
                self._tools.add_tool(event.get("tool", "?"), event.get("args", ""))
        elif etype == "tool_done":
            if self._tools:
                self._tools.complete_tool(event.get("tool", "?"), event.get("result", ""))
        elif etype == "tool_error":
            if self._tools:
                self._tools.error_tool(event.get("tool", "?"), event.get("result", ""))
        elif etype == "reasoning":
            if self._thinking:
                self._thinking.append(event.get("content", "") + "\n")

    def action_clear(self):
        container = self.query_one("#chat-container")
        for child in list(container.children):
            child.remove()
        welcome = ChatMessage(
            "system",
            Panel(Text("Chat cleared."), border_style="dim"),
        )
        container.mount(welcome)

    def action_quit(self):
        self._client.close()
        self.exit(0)
