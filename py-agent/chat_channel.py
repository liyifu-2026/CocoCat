"""ChatChannel — session-queued message processing pipeline (CowAgent ChatChannel pattern).

Provides:
- Per-session message queue with concurrency control
- _compose_context() for building Context with prefix/group/blacklist logic
- _handle() pipeline: generate_reply -> decorate_reply -> send_reply
- Plugin event hooks at each pipeline stage
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from queue import Queue

from channel import Channel
from channel_context import Context, ContextType, Reply, ReplyType

logger = logging.getLogger("cococat.chat_channel")

handler_pool = ThreadPoolExecutor(max_workers=8)


class ChatChannel(Channel):
    """Abstract channel with session queuing and reply pipeline.

    Subclasses implement startup() and send(reply, context).
    """

    NOT_SUPPORT_REPLYTYPE = [ReplyType.VOICE, ReplyType.IMAGE]

    def __init__(self):
        super().__init__()
        self.futures: dict[str, list[Future]] = {}
        self.sessions: dict[str, list] = {}
        self.lock = threading.Lock()
        _thread = threading.Thread(target=self._consume, daemon=True)
        _thread.start()

    # --- Session queue ---

    def produce(self, context: Context):
        """Queue a context for processing, grouped by session_id."""
        session_id = context["session_id"]
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = [
                    Queue(),
                    threading.BoundedSemaphore(1),
                ]
            q = self.sessions[session_id][0]
            if context.type == ContextType.TEXT and context.content.startswith("#"):
                items = []
                while not q.empty():
                    items.append(q.get_nowait())
                q.put(context)
                for item in items:
                    q.put(item)
            else:
                q.put(context)

    def _consume(self):
        """Background thread: drain session queues and dispatch to handler pool."""
        while True:
            with self.lock:
                session_ids = list(self.sessions.keys())
            for session_id in session_ids:
                with self.lock:
                    if session_id not in self.sessions:
                        continue
                    ctx_queue, semaphore = self.sessions[session_id]
                if semaphore.acquire(blocking=False):
                    if not ctx_queue.empty():
                        context = ctx_queue.get_nowait()
                        future = handler_pool.submit(self._handle, context)
                        future.add_done_callback(self._make_callback(session_id))
                    else:
                        semaphore.release()
            time.sleep(0.2)

    def _make_callback(self, session_id: str):
        def cb(worker: Future):
            try:
                exc = worker.exception()
                if exc:
                    logger.error(f"Handler error for session {session_id}: {exc}")
            except Exception:
                pass
            with self.lock:
                if session_id in self.sessions:
                    self.sessions[session_id][1].release()
        return cb

    # --- Context composition ---

    def _compose_context(self, ctype: ContextType, content: str, **kwargs) -> Context | None:
        """Build a Context from raw message data.

        Override in subclasses to add prefix matching, group detection, etc.
        """
        context = Context(ctype, content)
        context.kwargs = kwargs
        context["channel_type"] = self.channel_type
        context["origin_ctype"] = ctype
        return context

    # --- Reply pipeline ---

    def _handle(self, context: Context):
        """Full reply pipeline: generate -> decorate -> send."""
        if context is None or not context.content:
            return
        reply = self._generate_reply(context)
        if reply and reply.content:
            reply = self._decorate_reply(context, reply)
            self._send_reply(context, reply)

    def _generate_reply(self, context: Context, reply: Reply = None) -> Reply:
        """Generate a reply via Bridge.

        Override in subclasses to customize.
        Bridge integration (LocalBridge / MailboxBridge) will replace this stub.
        """
        if reply is None:
            reply = Reply(ReplyType.TEXT, "")
        if context.type == ContextType.TEXT:
            reply.content = context.content
            reply.type = ReplyType.TEXT
        return reply

    def _decorate_reply(self, context: Context, reply: Reply) -> Reply:
        """Decorate reply with prefix/suffix, @-mentions, etc.

        Override in subclasses.
        """
        return reply

    def _send_reply(self, context: Context, reply: Reply):
        """Send reply with optional media extraction.

        Override in subclasses.
        """
        self._send(reply, context)

    def _send(self, reply: Reply, context: Context, retry_cnt=0):
        try:
            self.send(reply, context)
        except NotImplementedError:
            pass
        except Exception as e:
            if retry_cnt < 2:
                time.sleep(3 + 3 * retry_cnt)
                self._send(reply, context, retry_cnt + 1)

    # --- Session management ---

    def cancel_session(self, session_id: str):
        """Cancel queued and in-flight tasks for a session."""
        with self.lock:
            if session_id in self.sessions:
                for future in self.futures.get(session_id, []):
                    future.cancel()
                self.sessions[session_id][0] = Queue()

    def cancel_all_session(self):
        """Cancel all sessions."""
        with self.lock:
            for session_id in list(self.sessions.keys()):
                for future in self.futures.get(session_id, []):
                    future.cancel()
                self.sessions[session_id][0] = Queue()
