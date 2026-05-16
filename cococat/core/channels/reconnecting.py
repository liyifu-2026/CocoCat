"""ReconnectingChannel mixin with exponential backoff."""
import threading
import time
import logging

logger = logging.getLogger("cococat.channel")


class ReconnectingChannel:
    """Mixin that adds exponential-backoff reconnection to ChannelBase subclasses.

    The mixing class must have:
      - self.connected_state  (updated by mixin)
      - self.on_disconnected  (callable or None, called when all retries exhausted)
    """

    MAX_RETRIES = 5
    BASE_DELAY = 2
    MAX_DELAY = 60

    def __init__(self, max_retries=5, base_delay=2, max_delay=60):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self._reconnect_stop = threading.Event()
        self._reconnect_thread = None

    def _start_reconnect_loop(self, connect_fn):
        self._reconnect_stop.clear()
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_worker, args=(connect_fn,), daemon=True
        )
        self._reconnect_thread.start()

    def _reconnect_worker(self, connect_fn):
        for attempt in range(self.max_retries):
            if self._reconnect_stop.is_set():
                return
            self.connected_state = "reconnecting"
            delay = min(self.base_delay * (2 ** attempt), self.max_delay)
            logger.warning(f"Reconnecting (attempt {attempt+1}/{self.max_retries}) in {delay}s")
            time.sleep(delay)
            if self._reconnect_stop.is_set():
                return
            try:
                if connect_fn():
                    self.connected_state = "connected"
                    logger.info("Reconnected successfully")
                    return
            except Exception as e:
                logger.warning(f"Reconnect attempt {attempt+1} failed: {e}")
        self.connected_state = "disconnected"
        logger.error(f"All {self.max_retries} reconnection attempts exhausted")
        if self.on_disconnected:
            self.on_disconnected()

    def stop_reconnect(self):
        self._reconnect_stop.set()
